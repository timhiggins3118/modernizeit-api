#!/usr/bin/env python3
"""
Clean Java Generator

Generates readable Java code from COBOL semantic models.
Includes line number references for traceability.

Input:
  - ifpr321_complete_data_model.json (fields, groups, conditions)
  - ifpr321_procedure_model.json (paragraphs, statements)

Output:
  - IFPR321.java (clean, readable Java)
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class CleanJavaGenerator:
    """Generates clean Java from COBOL semantic models."""

    def __init__(self, data_model: Dict, procedure_model: Dict, class_name: str = "IFPR321"):
        self.data_model = data_model
        self.procedure_model = procedure_model
        self.class_name = class_name
        self.imports = set()
        self.output = []
        self.indent_level = 0

        # Build field type lookup: java_name -> java_type
        # This enables type-aware MOVE statement generation
        self.field_types = {}
        for field in data_model.get('fields', []):
            java_name = field.get('java_name')
            java_type = field.get('java_type', 'String')
            # Check if both occurs and inherited_occurs exist -> 2D array
            if '[]' in java_type:
                has_occurs = field.get('occurs')
                has_inherited = field.get('inherited_occurs')
                if has_occurs and has_inherited:
                    base = java_type.replace('[]', '')
                    java_type = f'{base}[][]'  # Upgrade to 2D array
            if java_name:
                self.field_types[java_name] = java_type
                # Also map COBOL name (lowercase, hyphens to underscores)
                cobol_name = field.get('cobol_name', '')
                if cobol_name:
                    self.field_types[cobol_name.lower().replace('-', '_')] = java_type

        # Add missing fields that weren't captured due to multi-line COBOL definitions
        # These exist in WORKING-STORAGE but span multiple lines
        self._add_missing_fields()

        # Build parent -> children map for group class generation
        # Fields have 'parent' key pointing to their parent group's cobol_name
        self.children_by_parent = {}
        for field in data_model.get('fields', []):
            parent = field.get('parent')
            if parent:
                if parent not in self.children_by_parent:
                    self.children_by_parent[parent] = []
                self.children_by_parent[parent].append(field)

    def _add_missing_fields(self):
        """Add fields from copybooks and multi-line definitions.

        Uses auto-loaded copybook types from comprehensive parse results,
        plus manual overrides for multi-line definitions the parser missed.
        """
        # Manual additions for multi-line definitions that parser can't handle
        # (PIC on continuation line after OCCURS)
        missing_fields = {
            # Multi-line OCCURS+PIC definitions from main program
            'nontaxbl': 'BigDecimal[]',      # NONTAXBL OCCURS 7 TIMES (PIC on next line)
            'annlTaxbl': 'BigDecimal[]',     # ANNL-TAXBL OCCURS 7 TIMES (PIC on next line)
            'inc': 'BigDecimal',             # INC PIC S9(9)V99

            # REDEFINES views of array elements
            'nontaxblFed': 'BigDecimal',
            'nontaxblStt': 'BigDecimal',
            'nontaxblLoc': 'BigDecimal',
            'nontaxblCit': 'BigDecimal',
            'nontaxblOth': 'BigDecimal',
            'nontaxblFica': 'BigDecimal',
            'nontaxblEic': 'BigDecimal',
            'nontaxblFicaYtd': 'BigDecimal',

            # Other multi-line fields
            'ibmCt': 'BigDecimal',
            'ernErnQtdNet': 'BigDecimal',
            'ernErnYtdNet': 'BigDecimal',
        }

        # Add missing fields if not already present
        for java_name, java_type in missing_fields.items():
            if java_name not in self.field_types:
                self.field_types[java_name] = java_type

        # AUTO-APPLY copybook types from comprehensive parse
        # This handles fields like PER-TAX-PARA that are in copybooks
        copybook_types = self.data_model.get('copybook_types', {})
        type_corrections = {}

        for java_name, copybook_type in copybook_types.items():
            current_type = self.field_types.get(java_name)
            # Only correct if types differ significantly
            if current_type and current_type != copybook_type:
                # Copybook says BigDecimal[] but we have String[] -> correct it
                if 'BigDecimal' in copybook_type and 'String' in str(current_type):
                    type_corrections[java_name] = copybook_type
                # Copybook says BigDecimal but we have int -> correct it
                elif copybook_type == 'BigDecimal' and current_type in ('int', 'short', 'long'):
                    type_corrections[java_name] = copybook_type

        # Manual overrides for known problem fields (multi-line OCCURS+PIC)
        type_corrections['perTaxPara'] = 'BigDecimal[]'   # OCCURS 7 + PIC S9(7)V99 COMP-3 on next line
        type_corrections['benArrsCtr'] = 'BigDecimal[]'   # From copybook, needs array

        # Apply all corrections
        for java_name, java_type in type_corrections.items():
            self.field_types[java_name] = java_type

        # Store for generate_fields() to use corrected types
        self.type_corrections = type_corrections

        # Store missing fields for declaration generation
        self.missing_fields = {k: v for k, v in missing_fields.items()
                               if k not in type_corrections}

    def indent(self) -> str:
        return "    " * self.indent_level

    def emit(self, line: str, line_ref: Optional[int] = None, cobol_ref: Optional[str] = None):
        """Emit a line of Java code with optional COBOL reference."""
        if line_ref and cobol_ref:
            # Pad to align comments
            padded = f"{self.indent()}{line}".ljust(60)
            self.output.append(f"{padded}// L:{line_ref} {cobol_ref}")
        elif line_ref:
            padded = f"{self.indent()}{line}".ljust(60)
            self.output.append(f"{padded}// L:{line_ref}")
        else:
            self.output.append(f"{self.indent()}{line}")

    def emit_blank(self):
        self.output.append("")

    def cobol_to_java_name(self, cobol_name: str) -> str:
        """Convert COBOL-NAME to javaName, handling array subscripts.

        COBOL examples:
          DED-AMT-SUM(J) -> dedAmtSum[J.intValue()]
          FIELD-NAME(I, J) -> fieldName[I.intValue()][J.intValue()]
          SIMPLE-NAME -> simpleName
        """
        if not cobol_name:
            return "unknown"

        # Check for subscript(s) in parentheses (allow optional space before parenthesis)
        subscript_match = re.match(r'^([^(\s]+)\s*\(([^)]+)\)$', cobol_name)
        if subscript_match:
            base_name = subscript_match.group(1)
            subscripts = subscript_match.group(2)

            # Convert base name to camelCase
            name = re.sub(r'^\d+-', '', base_name)
            parts = name.lower().split('-')
            if len(parts) == 1:
                java_base = parts[0]
            else:
                java_base = parts[0] + ''.join(p.title() for p in parts[1:])

            # Convert subscripts to Java array notation
            # Handle comma-separated subscripts: (I, J) -> [I.intValue()][J.intValue()]
            subscript_parts = [s.strip() for s in subscripts.split(',')]
            java_subscripts = ''
            for sub in subscript_parts:
                # Convert subscript name to camelCase
                sub_name = re.sub(r'^\d+-', '', sub)
                sub_parts = sub_name.lower().split('-')
                if len(sub_parts) == 1:
                    sub_java = sub_parts[0]
                else:
                    sub_java = sub_parts[0] + ''.join(p.title() for p in sub_parts[1:])

                # Check if subscript is a BigDecimal field (needs .intValue())
                sub_type = self.field_types.get(sub_java, 'unknown')
                if sub_type == 'BigDecimal':
                    java_subscripts += f'[{sub_java}.intValue()]'
                else:
                    java_subscripts += f'[{sub_java}]'

            return java_base + java_subscripts

        # No subscript - standard conversion
        name = re.sub(r'^\d+-', '', cobol_name)
        parts = name.lower().split('-')
        if len(parts) == 1:
            return parts[0]
        return parts[0] + ''.join(p.title() for p in parts[1:])

    def cobol_to_method_name(self, cobol_name: str) -> str:
        """Convert COBOL paragraph name to Java method name.

        COBOL paragraphs can start with numbers like:
        - 200-174-0-CONTROL -> para200_174_0Control
        - 800-200-CLOSE-FILES -> closeFiles_800_200
        - 010-OPEN-FILES -> openFiles_010

        Java identifiers cannot start with numbers, so we handle this.
        """
        if not cobol_name:
            return "unknown"

        # Split on hyphens
        parts = cobol_name.split('-')

        # Collect leading number parts and text parts
        num_parts = []
        text_parts = []

        for part in parts:
            if part.isdigit():
                num_parts.append(part)
            else:
                text_parts.append(part)

        if not text_parts:
            # All numbers like "200-174-0" - prefix with "para"
            return f"para_{'_'.join(num_parts)}"

        # Build camelCase from text parts
        text_parts_lower = [p.lower() for p in text_parts]
        if len(text_parts_lower) == 1:
            base = text_parts_lower[0]
        else:
            base = text_parts_lower[0] + ''.join(p.title() for p in text_parts_lower[1:])

        # If base starts with a digit (shouldn't happen but be safe), prefix it
        if base and base[0].isdigit():
            base = 'para' + base

        # Append number suffix if there were numbers
        if num_parts:
            return f"{base}_{'_'.join(num_parts)}"
        return base

    def cobol_to_class_name(self, cobol_name: str) -> str:
        """Convert COBOL name to PascalCase class name."""
        name = re.sub(r'^\d+-', '', cobol_name)
        parts = name.lower().split('-')
        return ''.join(p.title() for p in parts)

    def get_field_type(self, java_name: str) -> str:
        """Get the Java type of a field from the data model.

        Args:
            java_name: The Java field name (camelCase)

        Returns:
            The base Java type (String, BigDecimal, int, short, long) or 'unknown'
            For array types, returns the element type (BigDecimal[] -> BigDecimal)
        """
        # Strip array subscript if present: field[i] -> field
        # Also handle spaces before brackets: field [i] -> field
        base_name = re.sub(r'\s*\[.*\]', '', java_name).strip()
        field_type = self.field_types.get(base_name, 'unknown')
        # For array types, return the element type
        if '[]' in field_type:
            return field_type.replace('[]', '')
        return field_type

    def generate_type_safe_assignment(self, target_java: str, source_java: str,
                                       source_type: str, line_num: int,
                                       cobol_ref: str) -> None:
        """Generate a type-safe assignment for MOVE statements.

        Handles type conversions between COBOL and Java types:
        - BigDecimal <- 0/ZEROS -> BigDecimal.ZERO
        - BigDecimal <- numeric literal -> BigDecimal.valueOf(n)
        - BigDecimal <- String field -> new BigDecimal(field)
        - BigDecimal <- int/short/long field -> BigDecimal.valueOf(field)
        - String <- BigDecimal field -> field.toString()
        - String <- numeric field -> String.valueOf(field)
        - int/short/long <- BigDecimal field -> field.intValue()/shortValue()/longValue()
        """
        target_type = self.get_field_type(target_java)

        # If target type is unknown, we need to check source type for conversion
        # External stub fields (CL1-*, TIM-*, etc.) are typically String
        if target_type == 'unknown':
            src_type = self.get_field_type(source_java)
            if src_type == 'BigDecimal':
                # BigDecimal -> unknown (likely String) - use toString()
                self.emit(f'{target_java} = {source_java}.toString();', line_num, cobol_ref)
            elif src_type in ('int', 'short', 'long'):
                # Numeric -> unknown (likely String) - use String.valueOf()
                self.emit(f'{target_java} = String.valueOf({source_java});', line_num, cobol_ref)
            else:
                # String or unknown -> unknown - direct assignment
                self.emit(f'{target_java} = {source_java};', line_num, cobol_ref)
            return

        # Handle BigDecimal targets
        if target_type == 'BigDecimal':
            if source_java == '0' or source_type == 'ZEROS':
                self.emit(f'{target_java} = BigDecimal.ZERO;', line_num, cobol_ref)
            elif source_java == '""' or source_type == 'SPACES':
                # SPACES to BigDecimal - use ZERO
                self.emit(f'{target_java} = BigDecimal.ZERO;', line_num, cobol_ref)
            elif source_java.lstrip('-').replace('.', '').isdigit():
                # Numeric literal
                self.emit(f'{target_java} = BigDecimal.valueOf({source_java});', line_num, cobol_ref)
            else:
                # Source is a field - check its type
                src_type = self.get_field_type(source_java)
                if src_type == 'BigDecimal':
                    self.emit(f'{target_java} = {source_java};', line_num, cobol_ref)
                elif src_type == 'String':
                    self.emit(f'{target_java} = new BigDecimal({source_java});', line_num, cobol_ref)
                elif src_type in ('int', 'short', 'long'):
                    self.emit(f'{target_java} = BigDecimal.valueOf({source_java});', line_num, cobol_ref)
                else:
                    # Unknown source - use new BigDecimal() which accepts String
                    # This is safer than valueOf() which only accepts numeric primitives
                    self.emit(f'{target_java} = new BigDecimal({source_java});', line_num, cobol_ref)

        # Handle String targets
        elif target_type == 'String':
            if source_java.startswith('"') or source_java.startswith("'"):
                # String literal - direct assignment
                self.emit(f'{target_java} = {source_java};', line_num, cobol_ref)
            elif source_java == '""' or source_type == 'SPACES':
                self.emit(f'{target_java} = "";', line_num, cobol_ref)
            elif source_java.lstrip('-').replace('.', '').isdigit():
                # Numeric literal to String
                self.emit(f'{target_java} = "{source_java}";', line_num, cobol_ref)
            else:
                src_type = self.get_field_type(source_java)
                if src_type == 'String':
                    self.emit(f'{target_java} = {source_java};', line_num, cobol_ref)
                elif src_type == 'BigDecimal':
                    self.emit(f'{target_java} = {source_java}.toString();', line_num, cobol_ref)
                elif src_type in ('int', 'short', 'long'):
                    self.emit(f'{target_java} = String.valueOf({source_java});', line_num, cobol_ref)
                else:
                    self.emit(f'{target_java} = String.valueOf({source_java});', line_num, cobol_ref)

        # Handle numeric targets (int, short, long)
        elif target_type in ('int', 'short', 'long'):
            if source_java == '0' or source_type == 'ZEROS':
                self.emit(f'{target_java} = 0;', line_num, cobol_ref)
            elif source_java.lstrip('-').replace('.', '').isdigit():
                # Numeric literal - may need cast for short
                if target_type == 'short':
                    self.emit(f'{target_java} = (short){source_java};', line_num, cobol_ref)
                else:
                    self.emit(f'{target_java} = {source_java};', line_num, cobol_ref)
            else:
                src_type = self.get_field_type(source_java)
                if src_type == 'BigDecimal':
                    if target_type == 'int':
                        self.emit(f'{target_java} = {source_java}.intValue();', line_num, cobol_ref)
                    elif target_type == 'short':
                        self.emit(f'{target_java} = {source_java}.shortValue();', line_num, cobol_ref)
                    else:  # long
                        self.emit(f'{target_java} = {source_java}.longValue();', line_num, cobol_ref)
                elif src_type == 'String':
                    if target_type == 'int':
                        self.emit(f'{target_java} = Integer.parseInt({source_java});', line_num, cobol_ref)
                    elif target_type == 'short':
                        self.emit(f'{target_java} = Short.parseShort({source_java});', line_num, cobol_ref)
                    else:  # long
                        self.emit(f'{target_java} = Long.parseLong({source_java});', line_num, cobol_ref)
                elif src_type in ('int', 'short', 'long'):
                    if target_type == 'short' and src_type != 'short':
                        self.emit(f'{target_java} = (short){source_java};', line_num, cobol_ref)
                    else:
                        self.emit(f'{target_java} = {source_java};', line_num, cobol_ref)
                else:
                    self.emit(f'{target_java} = {source_java};', line_num, cobol_ref)

        else:
            # Unknown target type - fall back to direct assignment
            self.emit(f'{target_java} = {source_java};', line_num, cobol_ref)

    # =========================================================================
    # ARITHMETIC STATEMENT TRANSLATION - REAL CODE, NOT COMMENTS
    # =========================================================================

    def translate_compute(self, raw_text: str, line_num: int, cobol_ref: str) -> None:
        """Translate COBOL COMPUTE statement to Java.

        Examples:
            COMPUTE J = J + FD-COUNT  ->  j = j + fdCount;
            COMPUTE W1 ROUNDED = P1 * SA.  ->  w1 = p1.multiply(sa).setScale(2, RoundingMode.HALF_UP);
            COMPUTE A = (X * E) + (Y * F)  ->  a = (x.multiply(e)).add(y.multiply(f));
        """
        # raw_text is already stripped by generate_statement, use directly
        content = raw_text
        # Strip leading sequence numbers (e.g., "018070        COMPUTE...")
        content = re.sub(r'^\d{6}\s+', '', content)
        # Remove trailing period and comments
        content = re.sub(r'\.\s*$', '', content)
        content = re.sub(r'\s+\d{6}$', '', content)  # Remove trailing sequence numbers
        # Remove trailing codes like REQ01376, BUG01493, ID-599
        # Pattern 1: With space before trailing code
        content = re.sub(r'\s+[A-Z]{2,}[-]?\d+$', '', content)
        # Pattern 2: No space - digit followed by uppercase+digits (e.g., YTD-1REQ01118)
        content = re.sub(r'(\d)([A-Z]{3,}\d+)$', r'\1', content)

        # Pattern: COMPUTE target [ROUNDED] = expression
        match = re.match(r'COMPUTE\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)\s*(ROUNDED)?\s*=\s*(.+)',
                         content, re.IGNORECASE)
        if not match:
            self.emit(f'// COMPUTE parse failed: {content}', line_num, cobol_ref)
            return

        target_cobol = match.group(1).strip()
        rounded = match.group(2) is not None
        expression = match.group(3).strip()

        # Check for incomplete expression (ends with operator - multi-line statement)
        if expression.endswith(('+', '-', '*', '/', '(', ',')):
            self.emit(f'// COMPUTE incomplete (multi-line): {content}', line_num, cobol_ref)
            return

        target_java = self.cobol_to_java_name(target_cobol)
        target_type = self.get_field_type(target_java)

        # Translate the expression
        expr_java = self.translate_arithmetic_expression(expression, target_type)

        if target_type == 'BigDecimal' and rounded:
            self.emit(f'{target_java} = ({expr_java}).setScale(2, RoundingMode.HALF_UP);',
                      line_num, cobol_ref)
        else:
            self.emit(f'{target_java} = {expr_java};', line_num, cobol_ref)

    def translate_add(self, raw_text: str, line_num: int, cobol_ref: str) -> None:
        """Translate COBOL ADD statement to Java.

        Examples:
            ADD 1 TO J  ->  j = j + 1;
            ADD TIM-AMOUNT TO DED-AMT-SUM(I)  ->  dedAmtSum[i] = dedAmtSum[i].add(timAmount);
            ADD A, B GIVING C  ->  c = a + b; or c = a.add(b);
            ADD A TO B GIVING C  ->  c = a + b;
        """
        # raw_text is already stripped by generate_statement, use directly
        content = raw_text
        # Strip leading sequence numbers (e.g., "018070        ADD...")
        content = re.sub(r'^\d{6}\s+', '', content)
        content = re.sub(r'\.\s*$', '', content)
        content = re.sub(r'\s+\d{6}$', '', content)  # Remove trailing sequence numbers
        # Remove trailing codes like REQ01376, BUG01493, ID-599
        content = re.sub(r'\s+[A-Z]{2,}[-]?\d+$', '', content)
        content = re.sub(r'(\d)([A-Z]{3,}\d+)$', r'\1', content)

        # Pattern 1: ADD a, b GIVING c  or  ADD a b GIVING c
        giving_match = re.match(
            r'ADD\s+(.+?)\s+GIVING\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)',
            content, re.IGNORECASE)
        if giving_match:
            operands_str = giving_match.group(1).strip()
            target_cobol = giving_match.group(2).strip()
            # Remove "TO" if present in operands
            operands_str = re.sub(r'\s+TO\s+', ', ', operands_str, flags=re.IGNORECASE)
            # Parse operands keeping subscripts with their variables: NAME(subscript)
            operands = self._parse_operands(operands_str)

            target_java = self.cobol_to_java_name(target_cobol)
            target_type = self.get_field_type(target_java)

            operands_java = [self.cobol_to_java_name(op) for op in operands]
            expr = self._build_add_expression(operands_java, target_type)
            self.emit(f'{target_java} = {expr};', line_num, cobol_ref)
            return

        # Pattern 2: ADD a TO b  (b = b + a)
        to_match = re.match(
            r'ADD\s+(.+?)\s+TO\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)',
            content, re.IGNORECASE)
        if to_match:
            addend_str = to_match.group(1).strip()
            target_cobol = to_match.group(2).strip()

            target_java = self.cobol_to_java_name(target_cobol)
            target_type = self.get_field_type(target_java)

            # Handle multiple addends: ADD A, B TO C  or  ADD A B TO C
            # Use _parse_operands to keep subscripts with variables
            addends = self._parse_operands(addend_str)
            addends_java = [self.cobol_to_java_name(op) for op in addends]

            if target_type == 'BigDecimal':
                expr = target_java
                for addend in addends_java:
                    addend_type = self.get_field_type(addend)
                    if addend.isdigit() or (addend.startswith('-') and addend[1:].isdigit()):
                        expr = f'{expr}.add(BigDecimal.valueOf({addend}))'
                    elif addend_type == 'BigDecimal':
                        expr = f'{expr}.add({addend})'
                    else:
                        expr = f'{expr}.add(BigDecimal.valueOf({addend}))'
                self.emit(f'{target_java} = {expr};', line_num, cobol_ref)
            else:
                addend_expr = ' + '.join(addends_java)
                self.emit(f'{target_java} = {target_java} + {addend_expr};', line_num, cobol_ref)
            return

        # Fallback - couldn't parse
        self.emit(f'// ADD parse failed: {content}', line_num, cobol_ref)

    def translate_subtract(self, raw_text: str, line_num: int, cobol_ref: str) -> None:
        """Translate COBOL SUBTRACT statement to Java.

        Examples:
            SUBTRACT 1 FROM J  ->  j = j - 1;
            SUBTRACT A FROM B  ->  b = b - a;  or  b = b.subtract(a);
            SUBTRACT A FROM B GIVING C  ->  c = b - a;
        """
        # raw_text is already stripped by generate_statement, use directly
        content = raw_text
        # Strip leading sequence numbers
        content = re.sub(r'^\d{6}\s+', '', content)
        content = re.sub(r'\.\s*$', '', content)
        content = re.sub(r'\s+\d{6}$', '', content)
        # Remove trailing codes like REQ01376, BUG01493, ID-599
        content = re.sub(r'\s+[A-Z]{2,}[-]?\d+$', '', content)
        content = re.sub(r'(\d)([A-Z]{3,}\d+)$', r'\1', content)

        # Pattern 1: SUBTRACT a FROM b GIVING c
        giving_match = re.match(
            r'SUBTRACT\s+(.+?)\s+FROM\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)\s+GIVING\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)',
            content, re.IGNORECASE)
        if giving_match:
            subtrahend_cobol = giving_match.group(1).strip()
            minuend_cobol = giving_match.group(2).strip()
            target_cobol = giving_match.group(3).strip()

            subtrahend_java = self.cobol_to_java_name(subtrahend_cobol)
            minuend_java = self.cobol_to_java_name(minuend_cobol)
            target_java = self.cobol_to_java_name(target_cobol)
            target_type = self.get_field_type(target_java)

            if target_type == 'BigDecimal':
                # Check if subtrahend is a numeric literal
                sub_type = self.get_field_type(subtrahend_java)
                if subtrahend_java.replace('.', '').replace('-', '').isdigit():
                    sub_expr = f'BigDecimal.valueOf({subtrahend_java})'
                elif sub_type == 'BigDecimal':
                    sub_expr = subtrahend_java
                else:
                    sub_expr = f'BigDecimal.valueOf({subtrahend_java})'
                self.emit(f'{target_java} = {minuend_java}.subtract({sub_expr});',
                          line_num, cobol_ref)
            else:
                self.emit(f'{target_java} = {minuend_java} - {subtrahend_java};',
                          line_num, cobol_ref)
            return

        # Pattern 2: SUBTRACT a FROM b  (b = b - a)
        from_match = re.match(
            r'SUBTRACT\s+(.+?)\s+FROM\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)',
            content, re.IGNORECASE)
        if from_match:
            subtrahend_cobol = from_match.group(1).strip()
            target_cobol = from_match.group(2).strip()

            subtrahend_java = self.cobol_to_java_name(subtrahend_cobol)
            target_java = self.cobol_to_java_name(target_cobol)
            target_type = self.get_field_type(target_java)

            if target_type == 'BigDecimal':
                sub_type = self.get_field_type(subtrahend_java)
                if subtrahend_java.isdigit():
                    self.emit(f'{target_java} = {target_java}.subtract(BigDecimal.valueOf({subtrahend_java}));',
                              line_num, cobol_ref)
                elif sub_type == 'BigDecimal':
                    self.emit(f'{target_java} = {target_java}.subtract({subtrahend_java});',
                              line_num, cobol_ref)
                else:
                    self.emit(f'{target_java} = {target_java}.subtract(BigDecimal.valueOf({subtrahend_java}));',
                              line_num, cobol_ref)
            else:
                self.emit(f'{target_java} = {target_java} - {subtrahend_java};', line_num, cobol_ref)
            return

        self.emit(f'// SUBTRACT parse failed: {content}', line_num, cobol_ref)

    def translate_multiply(self, raw_text: str, line_num: int, cobol_ref: str) -> None:
        """Translate COBOL MULTIPLY statement to Java.

        Examples:
            MULTIPLY A BY B  ->  b = b * a;  or  b = b.multiply(a);
            MULTIPLY A BY B GIVING C  ->  c = a * b;
            MULTIPLY A BY B GIVING C ROUNDED  ->  c = a.multiply(b).setScale(2, RoundingMode.HALF_UP);
        """
        # raw_text is already stripped by generate_statement, use directly
        content = raw_text
        # Strip leading sequence numbers
        content = re.sub(r'^\d{6}\s+', '', content)
        content = re.sub(r'\.\s*$', '', content)
        content = re.sub(r'\s+\d{6}$', '', content)
        # Remove trailing codes like REQ01376, BUG01493, ID-599
        content = re.sub(r'\s+[A-Z]{2,}[-]?\d+$', '', content)
        content = re.sub(r'(\d)([A-Z]{3,}\d+)$', r'\1', content)

        # Check for ROUNDED
        rounded = 'ROUNDED' in content.upper()
        content = re.sub(r'\s+ROUNDED', '', content, flags=re.IGNORECASE)

        # Pattern 1: MULTIPLY a BY b GIVING c
        giving_match = re.match(
            r'MULTIPLY\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)\s+BY\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)\s+GIVING\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)',
            content, re.IGNORECASE)
        if giving_match:
            op1_cobol = giving_match.group(1).strip()
            op2_cobol = giving_match.group(2).strip()
            target_cobol = giving_match.group(3).strip()

            op1_java = self.cobol_to_java_name(op1_cobol)
            op2_java = self.cobol_to_java_name(op2_cobol)
            target_java = self.cobol_to_java_name(target_cobol)
            target_type = self.get_field_type(target_java)

            if target_type == 'BigDecimal':
                # Wrap numeric literals and int types in BigDecimal.valueOf() - can't call .multiply() on int
                op1_type = self.get_field_type(op1_java)
                if op1_java.replace('.', '').replace('-', '').isdigit():
                    op1_expr = f'BigDecimal.valueOf({op1_java})'
                elif op1_type in ('int', 'short', 'long'):
                    op1_expr = f'BigDecimal.valueOf({op1_java})'
                else:
                    op1_expr = op1_java
                op2_type = self.get_field_type(op2_java)
                if op2_java.replace('.', '').replace('-', '').isdigit():
                    op2_expr = f'BigDecimal.valueOf({op2_java})'
                elif op2_type in ('int', 'short', 'long'):
                    op2_expr = f'BigDecimal.valueOf({op2_java})'
                else:
                    op2_expr = op2_java
                expr = f'{op1_expr}.multiply({op2_expr})'
                if rounded:
                    expr = f'({expr}).setScale(2, RoundingMode.HALF_UP)'
                self.emit(f'{target_java} = {expr};', line_num, cobol_ref)
            else:
                self.emit(f'{target_java} = {op1_java} * {op2_java};', line_num, cobol_ref)
            return

        # Pattern 2: MULTIPLY a BY b  (b = b * a)
        by_match = re.match(
            r'MULTIPLY\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)\s+BY\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)',
            content, re.IGNORECASE)
        if by_match:
            multiplier_cobol = by_match.group(1).strip()
            target_cobol = by_match.group(2).strip()

            # Check if target is a numeric literal (invalid COBOL - can't store into literal)
            if target_cobol.replace('.', '').replace('-', '').isdigit():
                self.emit(f'// MULTIPLY invalid target (literal): {content}', line_num, cobol_ref)
                return

            multiplier_java = self.cobol_to_java_name(multiplier_cobol)
            target_java = self.cobol_to_java_name(target_cobol)
            target_type = self.get_field_type(target_java)

            if target_type == 'BigDecimal':
                mult_type = self.get_field_type(multiplier_java)
                if multiplier_java.replace('.', '').isdigit():
                    expr = f'{target_java}.multiply(BigDecimal.valueOf({multiplier_java}))'
                elif mult_type == 'BigDecimal':
                    expr = f'{target_java}.multiply({multiplier_java})'
                else:
                    expr = f'{target_java}.multiply(BigDecimal.valueOf({multiplier_java}))'
                if rounded:
                    expr = f'({expr}).setScale(2, RoundingMode.HALF_UP)'
                self.emit(f'{target_java} = {expr};', line_num, cobol_ref)
            else:
                self.emit(f'{target_java} = {target_java} * {multiplier_java};', line_num, cobol_ref)
            return

        self.emit(f'// MULTIPLY parse failed: {content}', line_num, cobol_ref)

    def translate_divide(self, raw_text: str, line_num: int, cobol_ref: str) -> None:
        """Translate COBOL DIVIDE statement to Java.

        Examples:
            DIVIDE A INTO B  ->  b = b / a;
            DIVIDE A BY B GIVING C  ->  c = a / b;
            DIVIDE A INTO B GIVING C REMAINDER D  ->  c = b / a; d = b % a;
        """
        # raw_text is already stripped by generate_statement, use directly
        content = raw_text
        # Strip leading sequence numbers
        content = re.sub(r'^\d{6}\s+', '', content)
        content = re.sub(r'\.\s*$', '', content)
        content = re.sub(r'\s+\d{6}$', '', content)
        # Remove trailing codes like REQ01376, BUG01493, ID-599
        content = re.sub(r'\s+[A-Z]{2,}[-]?\d+$', '', content)
        content = re.sub(r'(\d)([A-Z]{3,}\d+)$', r'\1', content)

        # Check for ROUNDED
        rounded = 'ROUNDED' in content.upper()
        content = re.sub(r'\s+ROUNDED', '', content, flags=re.IGNORECASE)

        # Check for REMAINDER
        remainder_match = re.search(r'\s+REMAINDER\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)', content, re.IGNORECASE)
        remainder_target = None
        if remainder_match:
            remainder_target = self.cobol_to_java_name(remainder_match.group(1).strip())
            content = re.sub(r'\s+REMAINDER\s+[A-Z0-9-]+(?:\s*\([^)]+\))?', '', content, flags=re.IGNORECASE)

        # Pattern 1: DIVIDE a BY b GIVING c
        by_giving_match = re.match(
            r'DIVIDE\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)\s+BY\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)\s+GIVING\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)',
            content, re.IGNORECASE)
        if by_giving_match:
            dividend_cobol = by_giving_match.group(1).strip()
            divisor_cobol = by_giving_match.group(2).strip()
            target_cobol = by_giving_match.group(3).strip()

            dividend_java = self.cobol_to_java_name(dividend_cobol)
            divisor_java = self.cobol_to_java_name(divisor_cobol)
            target_java = self.cobol_to_java_name(target_cobol)
            target_type = self.get_field_type(target_java)

            if target_type == 'BigDecimal':
                # Wrap numeric literals in BigDecimal.valueOf()
                dividend_wrapped = f'BigDecimal.valueOf({dividend_java})' if dividend_java.replace('.', '').replace('-', '').isdigit() else dividend_java
                divisor_wrapped = f'BigDecimal.valueOf({divisor_java})' if divisor_java.replace('.', '').replace('-', '').isdigit() else divisor_java
                expr = f'{dividend_wrapped}.divide({divisor_wrapped}, 10, RoundingMode.HALF_UP)'
                if rounded:
                    expr = f'({expr}).setScale(2, RoundingMode.HALF_UP)'
                self.emit(f'{target_java} = {expr};', line_num, cobol_ref)
            else:
                self.emit(f'{target_java} = {dividend_java} / {divisor_java};', line_num, cobol_ref)

            if remainder_target:
                self.emit(f'{remainder_target} = {dividend_java} % {divisor_java};', line_num, 'REMAINDER')
            return

        # Pattern 2: DIVIDE a INTO b GIVING c
        into_giving_match = re.match(
            r'DIVIDE\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)\s+INTO\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)\s+GIVING\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)',
            content, re.IGNORECASE)
        if into_giving_match:
            divisor_cobol = into_giving_match.group(1).strip()
            dividend_cobol = into_giving_match.group(2).strip()
            target_cobol = into_giving_match.group(3).strip()

            divisor_java = self.cobol_to_java_name(divisor_cobol)
            dividend_java = self.cobol_to_java_name(dividend_cobol)
            target_java = self.cobol_to_java_name(target_cobol)
            target_type = self.get_field_type(target_java)

            if target_type == 'BigDecimal':
                # Wrap numeric literals in BigDecimal.valueOf()
                dividend_wrapped = f'BigDecimal.valueOf({dividend_java})' if dividend_java.replace('.', '').replace('-', '').isdigit() else dividend_java
                divisor_wrapped = f'BigDecimal.valueOf({divisor_java})' if divisor_java.replace('.', '').replace('-', '').isdigit() else divisor_java
                expr = f'{dividend_wrapped}.divide({divisor_wrapped}, 10, RoundingMode.HALF_UP)'
                if rounded:
                    expr = f'({expr}).setScale(2, RoundingMode.HALF_UP)'
                self.emit(f'{target_java} = {expr};', line_num, cobol_ref)
            else:
                self.emit(f'{target_java} = {dividend_java} / {divisor_java};', line_num, cobol_ref)

            if remainder_target:
                self.emit(f'{remainder_target} = {dividend_java} % {divisor_java};', line_num, 'REMAINDER')
            return

        # Pattern 3: DIVIDE a INTO b  (b = b / a)
        into_match = re.match(
            r'DIVIDE\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)\s+INTO\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)',
            content, re.IGNORECASE)
        if into_match:
            divisor_cobol = into_match.group(1).strip()
            target_cobol = into_match.group(2).strip()

            # Check if target is a numeric literal (invalid COBOL - can't store into literal)
            if target_cobol.replace('.', '').replace('-', '').isdigit():
                self.emit(f'// DIVIDE invalid target (literal): {content}', line_num, cobol_ref)
                return

            divisor_java = self.cobol_to_java_name(divisor_cobol)
            target_java = self.cobol_to_java_name(target_cobol)
            target_type = self.get_field_type(target_java)

            if target_type == 'BigDecimal':
                # Wrap numeric literals in BigDecimal.valueOf()
                divisor_wrapped = f'BigDecimal.valueOf({divisor_java})' if divisor_java.replace('.', '').replace('-', '').isdigit() else divisor_java
                expr = f'{target_java}.divide({divisor_wrapped}, 10, RoundingMode.HALF_UP)'
                if rounded:
                    expr = f'({expr}).setScale(2, RoundingMode.HALF_UP)'
                self.emit(f'{target_java} = {expr};', line_num, cobol_ref)
            else:
                self.emit(f'{target_java} = {target_java} / {divisor_java};', line_num, cobol_ref)
            return

        # Pattern 4: DIVIDE a BY b (result back to a) - common in some COBOL dialects
        by_match = re.match(
            r'DIVIDE\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)\s+BY\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)',
            content, re.IGNORECASE)
        if by_match:
            dividend_cobol = by_match.group(1).strip()
            divisor_cobol = by_match.group(2).strip()

            dividend_java = self.cobol_to_java_name(dividend_cobol)
            divisor_java = self.cobol_to_java_name(divisor_cobol)
            dividend_type = self.get_field_type(dividend_java)

            if dividend_type == 'BigDecimal':
                divisor_wrapped = f'BigDecimal.valueOf({divisor_java})' if divisor_java.replace('.', '').replace('-', '').isdigit() else divisor_java
                expr = f'{dividend_java}.divide({divisor_wrapped}, 10, RoundingMode.HALF_UP)'
                if rounded:
                    expr = f'({expr}).setScale(2, RoundingMode.HALF_UP)'
                self.emit(f'{dividend_java} = {expr};', line_num, cobol_ref)
            else:
                self.emit(f'{dividend_java} = {dividend_java} / {divisor_java};', line_num, cobol_ref)

            if remainder_target:
                self.emit(f'{remainder_target} = {dividend_java} % {divisor_java};', line_num, 'REMAINDER')
            return

        self.emit(f'// DIVIDE parse failed: {content}', line_num, cobol_ref)

    def translate_set(self, raw_text: str, line_num: int, cobol_ref: str) -> None:
        """Translate COBOL SET statement to Java.

        Patterns:
            SET var TO value  ->  var = value;
            SET var TO var2   ->  var = var2;
            SET idx UP BY n   ->  idx = idx + n;
            SET idx DOWN BY n ->  idx = idx - n;
        """
        content = raw_text.strip()
        content = re.sub(r'^\d{6}\s+', '', content)  # Strip leading sequence numbers
        content = re.sub(r'\s+[A-Z]{2,}\d+$', '', content)  # Strip trailing codes like REQ01461
        content = re.sub(r'\s+\d{6}$', '', content)   # Strip trailing numbers
        content = content.strip()                     # Strip whitespace
        content = re.sub(r'\.\s*$', '', content)      # Strip trailing period

        # Pattern 1: SET var UP BY n
        up_match = re.match(r'SET\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)\s+UP\s+BY\s+(\d+)', content, re.IGNORECASE)
        if up_match:
            var_cobol = up_match.group(1).strip()
            increment = up_match.group(2)
            var_java = self.cobol_to_java_name(var_cobol)
            self.emit(f'{var_java} = {var_java} + {increment};', line_num, cobol_ref)
            return

        # Pattern 2: SET var DOWN BY n
        down_match = re.match(r'SET\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)\s+DOWN\s+BY\s+(\d+)', content, re.IGNORECASE)
        if down_match:
            var_cobol = down_match.group(1).strip()
            decrement = down_match.group(2)
            var_java = self.cobol_to_java_name(var_cobol)
            self.emit(f'{var_java} = {var_java} - {decrement};', line_num, cobol_ref)
            return

        # Pattern 3: SET var TO value/var2
        to_match = re.match(r'SET\s+([A-Z0-9-]+(?:\s*\([^)]+\))?)\s+TO\s+(.+)', content, re.IGNORECASE)
        if to_match:
            var_cobol = to_match.group(1).strip()
            value_str = to_match.group(2).strip()
            var_java = self.cobol_to_java_name(var_cobol)
            var_type = self.get_field_type(var_java)

            # If target variable type is unknown, fall back to comment
            if not var_type or var_type == 'unknown':
                self.emit(f'// {cobol_ref}', line_num, 'SET')
                return

            # Check if value is a number or another variable
            if value_str.isdigit():
                if var_type == 'BigDecimal':
                    self.emit(f'{var_java} = BigDecimal.valueOf({value_str});', line_num, cobol_ref)
                else:
                    self.emit(f'{var_java} = {value_str};', line_num, cobol_ref)
            else:
                value_java = self.cobol_to_java_name(value_str)
                value_type = self.get_field_type(value_java)

                # If source variable type is unknown, fall back to comment
                if not value_type or value_type == 'unknown':
                    self.emit(f'// {cobol_ref}', line_num, 'SET')
                    return

                # Type conversion if needed
                if var_type == 'BigDecimal' and value_type != 'BigDecimal':
                    self.emit(f'{var_java} = BigDecimal.valueOf({value_java});', line_num, cobol_ref)
                elif var_type != 'BigDecimal' and value_type == 'BigDecimal':
                    self.emit(f'{var_java} = {value_java}.intValue();', line_num, cobol_ref)
                else:
                    self.emit(f'{var_java} = {value_java};', line_num, cobol_ref)
            return

        # Fallback - comment the unparsed SET
        self.emit(f'// SET parse failed: {content}', line_num, cobol_ref)

    def translate_initialize(self, raw_text: str, line_num: int, cobol_ref: str) -> None:
        """Translate COBOL INITIALIZE statement to Java.

        INITIALIZE sets all fields in a group to their default values:
        - Alphanumeric fields: spaces
        - Numeric fields: zeros

        Pattern: INITIALIZE group-name [group-name2 ...]
        """
        content = raw_text.strip()
        content = re.sub(r'^\d{6}\s+', '', content)  # Strip leading sequence numbers
        content = re.sub(r'\s+[A-Z]{2,}\d+$', '', content)  # Strip trailing codes like REQ01461
        content = re.sub(r'\s+\d{6}$', '', content)   # Strip trailing numbers
        content = content.strip()                     # Strip whitespace
        content = re.sub(r'\.\s*$', '', content)      # Strip trailing period

        # Extract group names after INITIALIZE
        match = re.match(r'INITIALIZE\s+(.+)', content, re.IGNORECASE)
        if not match:
            self.emit(f'// INITIALIZE parse failed: {content}', line_num, cobol_ref)
            return

        groups_str = match.group(1).strip()
        # Split by spaces or commas (multiple groups can be initialized)
        group_names = re.split(r'[\s,]+', groups_str)

        for group_cobol in group_names:
            if not group_cobol:
                continue
            group_java = self.cobol_to_java_name(group_cobol)

            # Check if this group has children we can initialize
            if group_cobol in self.children_by_parent:
                children = self.children_by_parent[group_cobol]
                self.emit(f'// Initialize {group_cobol}', line_num, cobol_ref)
                for child in children:
                    if child.get('is_filler'):
                        continue
                    child_java = child.get('java_name', self.cobol_to_java_name(child['cobol_name']))
                    child_type = child.get('java_type', 'String')

                    # Set to type-appropriate default
                    if child_type == 'String':
                        self.emit(f'{child_java} = "";')
                    elif child_type == 'BigDecimal':
                        self.emit(f'{child_java} = BigDecimal.ZERO;')
                    elif child_type in ('int', 'short', 'long'):
                        self.emit(f'{child_java} = 0;')
                    elif '[]' in child_type:
                        # Array - would need to loop, just comment for now
                        self.emit(f'// {child_java} - array initialization needed')
                    else:
                        self.emit(f'{child_java} = null;')
            else:
                # No children found - just reset the single variable
                var_type = self.get_field_type(group_java)
                if var_type == 'String':
                    self.emit(f'{group_java} = "";', line_num, cobol_ref)
                elif var_type == 'BigDecimal':
                    self.emit(f'{group_java} = BigDecimal.ZERO;', line_num, cobol_ref)
                elif var_type in ('int', 'short', 'long'):
                    self.emit(f'{group_java} = 0;', line_num, cobol_ref)
                else:
                    # Unknown type - emit a reset comment
                    self.emit(f'// {group_java} = default; // INITIALIZE {group_cobol}', line_num, cobol_ref)

    def translate_string(self, raw_text: str, line_num: int, cobol_ref: str) -> None:
        """Translate COBOL STRING statement to Java.

        Pattern: STRING src1 DELIMITED BY delim src2 DELIMITED BY delim ... INTO target

        Examples:
            STRING "ERROR: " DELIMITED SIZE DED-CODE DELIMITED SIZE INTO MESSAGE-O
            -> messageO = "ERROR: " + dedCode;
        """
        content = raw_text.strip()
        content = re.sub(r'^\d{6}\s+', '', content)  # Strip leading sequence numbers
        content = re.sub(r'\s+[A-Z]{2,}\d+$', '', content)  # Strip trailing codes like REQ01461
        content = re.sub(r'\s+\d{6}$', '', content)   # Strip trailing numbers
        content = content.strip()                     # Strip whitespace
        content = re.sub(r'\.\s*$', '', content)      # Strip trailing period

        # Find the INTO clause to get the target
        into_match = re.search(r'\s+INTO\s+([A-Z0-9-]+)', content, re.IGNORECASE)
        if not into_match:
            self.emit(f'// STRING parse failed (no INTO): {content[:50]}...', line_num, cobol_ref)
            return

        target_cobol = into_match.group(1).strip()
        target_java = self.cobol_to_java_name(target_cobol)

        # Extract everything before INTO
        before_into = content[:into_match.start()]

        # Remove STRING keyword
        before_into = re.sub(r'^STRING\s+', '', before_into, flags=re.IGNORECASE)

        # Parse the sources - split by DELIMITED BY/SIZE
        # Remove DELIMITED BY xxx patterns to isolate the sources (including trailing comma)
        sources_str = re.sub(r',?\s*DELIMITED\s+(BY\s+)?(SIZE|SPACE|SPACES|[A-Z0-9-]+),?', ' ', before_into, flags=re.IGNORECASE)

        # Normalize subscripts: NAME (I) -> NAME(I)
        sources_str = re.sub(r'\s+\(', '(', sources_str)

        # Remove stray commas (used as delimiters in COBOL but not needed in Java concat)
        sources_str = re.sub(r',', ' ', sources_str)

        # Parse sources properly - handle quoted strings with spaces
        # Can't just split() because "HELLO WORLD" would become ["HELLO", "WORLD"]
        java_parts = []
        i = 0
        sources_str = sources_str.strip()
        while i < len(sources_str):
            # Skip whitespace
            while i < len(sources_str) and sources_str[i] in ' \t':
                i += 1
            if i >= len(sources_str):
                break

            # Check for quoted string (double or single quotes)
            if sources_str[i] in '"\'':
                quote_char = sources_str[i]
                end_quote = sources_str.find(quote_char, i + 1)
                if end_quote == -1:
                    end_quote = len(sources_str)
                quoted_str = sources_str[i:end_quote + 1]
                # Convert to Java double-quoted string
                if quote_char == "'":
                    java_parts.append('"' + quoted_str[1:-1] + '"')
                else:
                    java_parts.append(quoted_str)
                i = end_quote + 1
            else:
                # It's a variable - read until whitespace
                start = i
                while i < len(sources_str) and sources_str[i] not in ' \t"\'':
                    i += 1
                var_name = sources_str[start:i].strip()
                if var_name:
                    java_parts.append(self.cobol_to_java_name(var_name))

        if java_parts:
            concat_expr = ' + '.join(java_parts)
            self.emit(f'{target_java} = {concat_expr};', line_num, cobol_ref)
        else:
            self.emit(f'// STRING parse failed: {content[:50]}...', line_num, cobol_ref)

    def translate_arithmetic_expression(self, expr: str, target_type: str) -> str:
        """Translate a COBOL arithmetic expression to Java.

        Handles operators: +, -, *, /, ** (power)
        Handles parentheses for grouping.

        For BigDecimal targets, uses .add(), .subtract(), .multiply(), .divide()
        For numeric targets, uses standard operators.
        """
        # Convert COBOL names to Java names
        # Pattern matches COBOL field names (possibly with subscripts)
        def convert_operand(m):
            name = m.group(0)
            # Don't convert operators or numbers
            if name in ('+', '-', '*', '/', '**', '(', ')'):
                return name
            if name.replace('.', '').replace('-', '').isdigit():
                return name
            return self.cobol_to_java_name(name)

        # First, convert all COBOL names to Java names
        result = re.sub(r'[A-Z][A-Z0-9-]*(?:\s*\([^)]+\))?', convert_operand, expr, flags=re.IGNORECASE)

        # Handle ** (power) -> Math.pow()
        result = re.sub(r'(\w+)\s*\*\*\s*(\w+)', r'Math.pow(\1, \2)', result)

        if target_type == 'BigDecimal':
            # For BigDecimal, recursively convert to method calls
            return self._convert_expr_to_bigdecimal(result.strip())

        # For numeric types, return as-is with Java operators
        return result

    def _convert_expr_to_bigdecimal(self, expr: str) -> str:
        """Recursively convert an arithmetic expression to BigDecimal method calls.

        Handles: +, -, *, /, parentheses, and nested expressions.
        """
        expr = expr.strip()

        # Handle parenthesized expression
        if expr.startswith('(') and expr.endswith(')'):
            # Check if the entire expression is parenthesized
            depth = 0
            all_inside = True
            for i, c in enumerate(expr):
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                if depth == 0 and i < len(expr) - 1:
                    all_inside = False
                    break
            if all_inside:
                return self._convert_expr_to_bigdecimal(expr[1:-1])

        # Find the lowest precedence operator at the top level (not inside parens)
        # Precedence: + and - (lowest), * and / (higher)
        depth = 0
        last_add_sub = -1
        last_mul_div = -1

        for i, c in enumerate(expr):
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            elif depth == 0:
                if c in ('+', '-') and i > 0:
                    # Make sure it's an operator, not a sign (look back past spaces)
                    j = i - 1
                    while j >= 0 and expr[j] == ' ':
                        j -= 1
                    if j >= 0:
                        prev_char = expr[j]
                        # It's an operator if preceded by alphanumeric, ), or ]
                        if prev_char.isalnum() or prev_char in ')]':
                            last_add_sub = i
                elif c in ('*', '/'):
                    last_mul_div = i

        # Split on lowest precedence operator
        if last_add_sub > 0:
            left = expr[:last_add_sub].strip()
            op = expr[last_add_sub]
            right = expr[last_add_sub+1:].strip()

            left_expr = self._convert_expr_to_bigdecimal(left)
            right_expr = self._convert_expr_to_bigdecimal(right)

            if op == '+':
                return f'({left_expr}).add({right_expr})'
            else:  # '-'
                return f'({left_expr}).subtract({right_expr})'

        if last_mul_div > 0:
            left = expr[:last_mul_div].strip()
            op = expr[last_mul_div]
            right = expr[last_mul_div+1:].strip()

            left_expr = self._convert_expr_to_bigdecimal(left)
            right_expr = self._convert_expr_to_bigdecimal(right)

            if op == '*':
                return f'({left_expr}).multiply({right_expr})'
            else:  # '/'
                return f'({left_expr}).divide({right_expr}, 10, RoundingMode.HALF_UP)'

        # Base case: single operand (variable or number)
        if expr.replace('.', '').replace('-', '').isdigit():
            return f'BigDecimal.valueOf({expr})'

        # Check if it's a variable that needs wrapping
        field_type = self.get_field_type(expr)
        if field_type != 'BigDecimal':
            return f'BigDecimal.valueOf({expr})'

        return expr

    def _build_add_expression(self, operands: list, target_type: str) -> str:
        """Build an addition expression from multiple operands."""
        if not operands:
            return '0'

        if target_type == 'BigDecimal':
            result = operands[0]
            op_type = self.get_field_type(operands[0])
            if operands[0].replace('.', '').isdigit():
                result = f'BigDecimal.valueOf({operands[0]})'
            elif op_type != 'BigDecimal':
                result = f'BigDecimal.valueOf({operands[0]})'

            for op in operands[1:]:
                op_type = self.get_field_type(op)
                if op.replace('.', '').isdigit():
                    result = f'{result}.add(BigDecimal.valueOf({op}))'
                elif op_type == 'BigDecimal':
                    result = f'{result}.add({op})'
                else:
                    result = f'{result}.add(BigDecimal.valueOf({op}))'
            return result
        else:
            return ' + '.join(operands)

    def _parse_operands(self, operands_str: str) -> list:
        """Parse operands from a COBOL statement, keeping subscripts with their variables.

        Handles: NAME, NAME(subscript), NAME(subscript1, subscript2)
        Separators: commas and spaces outside parentheses

        Examples:
            'A B' -> ['A', 'B']
            'A, B' -> ['A', 'B']
            'HRS-CPP-SUM(I)' -> ['HRS-CPP-SUM(I)']
            'HRS-CPP-SUM (CLN-XSICK-SEQ01)' -> ['HRS-CPP-SUM(CLN-XSICK-SEQ01)']
            'A B(I) C' -> ['A', 'B(I)', 'C']
        """
        operands = []
        current = ''
        depth = 0

        # Normalize: remove space BEFORE opening parenthesis (NAME (I) -> NAME(I))
        # Do NOT remove space AFTER closing parenthesis - that's the operand separator!
        operands_str = re.sub(r'\s+\(', '(', operands_str)

        for char in operands_str:
            if char == '(':
                depth += 1
                current += char
            elif char == ')':
                depth -= 1
                current += char
            elif char in ', ' and depth == 0:
                if current.strip():
                    operands.append(current.strip())
                current = ''
            else:
                current += char

        if current.strip():
            operands.append(current.strip())

        return operands

    # =========================================================================
    # END ARITHMETIC TRANSLATION
    # =========================================================================

    def generate_condition_to_java(self, condition: str) -> str:
        """Convert COBOL condition to Java.

        Handles complex COBOL patterns including array subscripts.
        Pattern for Java field with optional array: [a-zA-Z][a-zA-Z0-9_]*(?:\[[^\]]+\])?
        """
        if not condition:
            return "true"

        result = condition

        # Java field pattern: identifier with optional array subscript
        # For now, don't try to match method calls - they're too complex with nested parens
        # Let the cleanup steps handle unconverted patterns
        JAVA_FIELD = r'[a-zA-Z][a-zA-Z0-9_]*(?:\[[^\]]+\])?'
        # COBOL field pattern: uppercase with hyphens
        COBOL_FIELD = r'[A-Z][A-Z0-9-]*'

        # Step 0: Convert array subscripts FIELD(I) or FIELD(I, J) to field[i] or field[i][j]
        # Always use array syntax - fields used with subscripts will be declared as arrays
        def replace_array_subscript(m):
            field = m.group(1)
            subscripts_str = m.group(2)
            field_java = self.cobol_to_java_name(field)

            # Handle comma-separated subscripts: FIELD(I, J) -> field[i][j]
            subscript_parts = [s.strip() for s in subscripts_str.split(',')]
            java_subscripts = ''
            for idx in subscript_parts:
                # Handle numeric subscripts (COBOL is 1-based, Java is 0-based)
                if idx.isdigit():
                    idx_java = str(int(idx) - 1)  # Convert to 0-based
                else:
                    idx_java = self.cobol_to_java_name(idx)
                    # If subscript is BigDecimal, convert to int for array access
                    idx_type = self.get_field_type(idx_java)
                    if idx_type == 'BigDecimal':
                        idx_java = f'{idx_java}.intValue()'
                java_subscripts += f'[{idx_java}]'

            return field_java + java_subscripts

        # Match FIELD(I) or FIELD(I, J) - subscripts must be identifiers or numbers, comma-separated
        # Don't match conditions like (FIELD = "X") which are grouped expressions
        SUBSCRIPT_PATTERN = r'[A-Z0-9][A-Z0-9-]*(?:\s*,\s*[A-Z0-9][A-Z0-9-]*)*|\d+(?:\s*,\s*\d+)*'
        result = re.sub(
            rf'({COBOL_FIELD})\s*\(\s*({SUBSCRIPT_PATTERN})\s*\)',
            replace_array_subscript,
            result,
            flags=re.IGNORECASE
        )

        # Step 1: Handle NOT comparisons and COBOL keywords FIRST
        result = re.sub(r'\bNOT\s*>', '<=', result, flags=re.IGNORECASE)
        result = re.sub(r'\bNOT\s*<', '>=', result, flags=re.IGNORECASE)
        result = re.sub(r'\bNOT\s+LESS\b', '>=', result, flags=re.IGNORECASE)
        result = re.sub(r'\bNOT\s+GREATER\b', '<=', result, flags=re.IGNORECASE)
        # Convert COBOL comparison keywords to operators
        # IMPORTANT: Don't convert when part of hyphenated field name (e.g., ERN-CPP-GRS-LESS-TX-SUM)
        result = re.sub(r'\bGREATER\s+THAN\b', '>', result, flags=re.IGNORECASE)
        result = re.sub(r'\bLESS\s+THAN\b', '<', result, flags=re.IGNORECASE)
        # Only convert standalone GREATER/LESS (not preceded or followed by hyphen)
        result = re.sub(r'(?<!-)\bGREATER\b(?!-)', '>', result, flags=re.IGNORECASE)
        result = re.sub(r'(?<!-)\bLESS\b(?!-)', '<', result, flags=re.IGNORECASE)
        result = re.sub(r'\bEQUAL\s+TO\b', '==', result, flags=re.IGNORECASE)
        result = re.sub(r'\bEQUAL\b', '==', result, flags=re.IGNORECASE)

        # Combined field pattern - match either COBOL (hyphenated) or Java (already converted)
        FIELD_PATTERN = rf'({COBOL_FIELD}|{JAVA_FIELD})'

        # Step 2: Handle multi-value NOT = comparisons FIRST
        # COBOL shorthand patterns:
        #   FIELD NOT = "A" AND "B" means FIELD NOT = "A" AND FIELD NOT = "B"
        #   FIELD NOT = "A" AND NOT = "B" means same thing (with repeated NOT)
        def expand_multi_value_not(m):
            field = m.group(1)
            values_str = m.group(2)
            # Convert COBOL field name to Java
            if '-' in field:
                field = self.cobol_to_java_name(field)
            # Extract all quoted values
            values = re.findall(r'"([^"]*)"', values_str)
            if values:
                checks = [f'!"{v}".equals({field})' for v in values]
                return ' && '.join(checks)
            # Fallback for non-string values
            return f'{field} != {values_str}'

        # Pattern 1: FIELD NOT = "A" AND NOT = "B" (with repeated NOT)
        # Use [^"]* instead of .*? to prevent greedy matching across quotes
        result = re.sub(
            rf'{FIELD_PATTERN}\s+NOT\s*=\s*("[^"]*"(?:\s+AND\s+NOT\s*=\s*"[^"]*")*)',
            expand_multi_value_not,
            result,
            flags=re.IGNORECASE
        )

        # Pattern 2: FIELD NOT = "A" AND "B" (without repeated NOT)
        # Use [^"]* instead of .*? to prevent greedy matching across quotes
        result = re.sub(
            rf'{FIELD_PATTERN}\s+NOT\s*=\s*("[^"]*"(?:\s+AND\s+"[^"]*")*)',
            expand_multi_value_not,
            result,
            flags=re.IGNORECASE
        )

        # Pattern 3: FIELD NOT = 2 AND 3 (numeric multi-value NOT)
        # Example: DED-OPT-NO-SUM(I) NOT = 2 AND 3 -> dedOptNoSum[i.intValue()] != 2 && dedOptNoSum[i.intValue()] != 3
        def expand_multi_value_not_numeric(m):
            field = m.group(1)
            values_str = m.group(2)
            if '-' in field:
                field = self.cobol_to_java_name(field)
            # Extract numeric values (supports digits, decimals)
            values = re.findall(r'(\d+(?:\.\d+)?)', values_str)
            if values:
                # Get field type to determine comparison method
                base_field = re.sub(r'\s*\[.*\]', '', field).strip()
                field_type = self.field_types.get(base_field, 'unknown')
                if field_type in ('BigDecimal', 'BigDecimal[]'):
                    checks = [f'{field}.compareTo(BigDecimal.valueOf({v})) != 0' for v in values]
                else:
                    checks = [f'{field} != {v}' for v in values]
                return ' && '.join(checks)
            return f'{field} != {values_str}'

        result = re.sub(
            rf'{FIELD_PATTERN}\s+NOT\s*=\s*(\d+(?:\s+AND\s+\d+)+)',
            expand_multi_value_not_numeric,
            result,
            flags=re.IGNORECASE
        )

        # Step 2b: Handle multi-value OR pattern
        # FIELD NOT = "A" OR "B" means FIELD NOT = "A" OR FIELD NOT = "B"
        def expand_multi_value_not_or(m):
            field = m.group(1)
            values_str = m.group(2)
            if '-' in field:
                field = self.cobol_to_java_name(field)
            values = re.findall(r'"([^"]*)"', values_str)
            if values:
                checks = [f'!"{v}".equals({field})' for v in values]
                return ' || '.join(checks)
            return f'{field} != {values_str}'

        result = re.sub(
            rf'{FIELD_PATTERN}\s+NOT\s*=\s*("[^"]*"(?:\s+OR\s+"[^"]*")*)',
            expand_multi_value_not_or,
            result,
            flags=re.IGNORECASE
        )

        # Step 2c: Handle single NOT = comparison
        def replace_not_equals(m):
            field = m.group(1)
            value = m.group(2)
            if '-' in field:
                field = self.cobol_to_java_name(field)
            # If value is a string literal, use !equals
            if value.startswith('"'):
                val_inner = value.strip('"')
                return f'!"{val_inner}".equals({field})'
            # Otherwise use !=
            return f'{field} != {value}'

        result = re.sub(
            rf'{FIELD_PATTERN}\s+NOT\s*=\s*(\S+)',
            replace_not_equals,
            result,
            flags=re.IGNORECASE
        )

        # Step 3: Handle "AND NOT field" -> "&& !field" pattern
        result = re.sub(r'\bAND\s+NOT\s+', '&& !', result, flags=re.IGNORECASE)
        result = re.sub(r'\bOR\s+NOT\s+', '|| !', result, flags=re.IGNORECASE)

        # Step 3b: Handle standalone "NOT field" at start of condition or after (
        # (NOT TAX-EXEMPT -> (!taxExempt
        result = re.sub(r'\(\s*NOT\s+', '(!', result, flags=re.IGNORECASE)
        result = re.sub(r'^NOT\s+', '!', result, flags=re.IGNORECASE)

        # Step 4: Handle COBOL shorthand comparisons
        # FIELD < A OR > B means FIELD < A OR FIELD > B
        # FIELD > A AND < B means FIELD > A AND FIELD < B
        def expand_comparison_shorthand_or(m):
            field = m.group(1)
            op1 = m.group(2)
            val1 = m.group(3)
            op2 = m.group(4)
            val2 = m.group(5)
            if '-' in field:
                field = self.cobol_to_java_name(field)
            return f'{field} {op1} {val1} || {field} {op2} {val2}'

        def expand_comparison_shorthand_and(m):
            field = m.group(1)
            op1 = m.group(2)
            val1 = m.group(3)
            op2 = m.group(4)
            val2 = m.group(5)
            if '-' in field:
                field = self.cobol_to_java_name(field)
            return f'{field} {op1} {val1} && {field} {op2} {val2}'

        # Number pattern that matches integers and decimals
        NUM_PATTERN = r'[\d.]+'

        # Pattern: FIELD < A OR > B
        result = re.sub(
            rf'{FIELD_PATTERN}\s*([<>]=?)\s*({NUM_PATTERN})\s+OR\s+([<>]=?)\s*({NUM_PATTERN})',
            expand_comparison_shorthand_or,
            result,
            flags=re.IGNORECASE
        )

        # Pattern: FIELD > A AND < B (already has && from earlier conversion)
        result = re.sub(
            rf'{FIELD_PATTERN}\s*([<>]=?)\s*({NUM_PATTERN})\s+AND\s+([<>]=?)\s*({NUM_PATTERN})',
            expand_comparison_shorthand_and,
            result,
            flags=re.IGNORECASE
        )

        # Also handle post-conversion pattern: FIELD > A && < B
        result = re.sub(
            rf'{FIELD_PATTERN}\s*([<>]=?)\s*({NUM_PATTERN})\s*&&\s*([<>]=?)\s*({NUM_PATTERN})',
            expand_comparison_shorthand_and,
            result,
            flags=re.IGNORECASE
        )

        # Step 5: Handle multi-value positive string comparisons FIRST (before OR→||)
        # FIELD = "A" OR "B" means FIELD = "A" OR FIELD = "B"
        def expand_multi_value_equals(m):
            field = m.group(1)
            values_str = m.group(2)
            if field[0].islower() or '[' in field:
                java_field = field
            else:
                java_field = self.cobol_to_java_name(field)
            values = re.findall(r'"([^"]*)"', values_str)
            if values:
                checks = [f'"{v}".equals({java_field})' for v in values]
                # Wrap in parens to preserve grouping when combined with other conditions
                return '(' + ' || '.join(checks) + ')'
            return f'"{values_str}".equals({java_field})'

        result = re.sub(
            rf'({JAVA_FIELD}|{COBOL_FIELD})\s*=\s*("[^"]*"(?:\s+OR\s+"[^"]*")+)',
            expand_multi_value_equals,
            result,
            flags=re.IGNORECASE
        )

        # Step 5b: Handle multi-value AND pattern for NOT equals
        # FIELD NOT = "A" AND "B" means FIELD NOT = "A" AND FIELD NOT = "B"
        def expand_multi_value_not_and(m):
            field = m.group(1)
            values_str = m.group(2)
            if field[0].islower() or '[' in field:
                java_field = field
            else:
                java_field = self.cobol_to_java_name(field)
            values = re.findall(r'"([^"]*)"', values_str)
            if values:
                checks = [f'!"{v}".equals({java_field})' for v in values]
                return ' && '.join(checks)
            return f'!"{values_str}".equals({java_field})'

        result = re.sub(
            rf'({JAVA_FIELD}|{COBOL_FIELD})\s+NOT\s*=\s*("[^"]*"(?:\s+AND\s+"[^"]*")+)',
            expand_multi_value_not_and,
            result,
            flags=re.IGNORECASE
        )

        # Step 5c: Replace remaining COBOL operators with Java operators
        # IMPORTANT: Don't convert OR when it's part of a hyphenated field name (OR-FIELD)
        # Use word boundary that doesn't match hyphen
        result = re.sub(r'\bAND\b(?!-)', '&&', result, flags=re.IGNORECASE)
        result = re.sub(r'(?<!-)\bOR\b(?!-)', '||', result, flags=re.IGNORECASE)

        # Step 5d: Fix dangling string literals after && or ||
        # Pattern: !"a".equals(field) && "b" -> !"a".equals(field) && !"b".equals(field)
        # This handles cases where parentheses prevented earlier pattern matching
        def find_balanced_parens(text, start):
            """Find the content inside balanced parentheses starting at position start"""
            if text[start] != '(':
                return None
            depth = 0
            end = start
            for i in range(start, len(text)):
                if text[i] == '(':
                    depth += 1
                elif text[i] == ')':
                    depth -= 1
                    if depth == 0:
                        return text[start+1:i]  # Return content without outer parens
            return None

        def fix_dangling_and_literals(result_text):
            # Repeatedly fix && "literal" patterns until no more changes
            # Pattern: ...".equals(field) && "literal" -> ...".equals(field) && !"literal".equals(field)
            max_iterations = 500  # Safety limit
            for _ in range(max_iterations):
                # Find pattern: .equals(field) && "literal" (not followed by .equals)
                # Use a simpler approach: find && "literal" that's NOT already converted
                m = re.search(r'\.equals\(([^)]*(?:\([^)]*\))*[^)]*)\)\s*(&&)\s*"([^"]*)"(?!\s*\.equals)', result_text)
                if not m:
                    break
                field = m.group(1)
                literal = m.group(3)
                # Replace just && "literal" with && !"literal".equals(field)
                old = m.group(0)
                new = f'.equals({field}) && !"{literal}".equals({field})'
                result_text = result_text.replace(old, new, 1)
            return result_text

        def fix_dangling_or_literals(result_text):
            # Repeatedly fix || "literal" patterns until no more changes
            max_iterations = 500
            for _ in range(max_iterations):
                m = re.search(r'\.equals\(([^)]*(?:\([^)]*\))*[^)]*)\)\s*(\|\|)\s*"([^"]*)"(?!\s*\.equals)', result_text)
                if not m:
                    break
                field = m.group(1)
                literal = m.group(3)
                old = m.group(0)
                new = f'.equals({field}) || !"{literal}".equals({field})'
                result_text = result_text.replace(old, new, 1)
            return result_text

        result = fix_dangling_and_literals(result)
        result = fix_dangling_or_literals(result)

        # Step 5b: Handle single string comparisons (equals)
        # FIELD = "value" -> "value".equals(field)
        def replace_string_compare(m):
            field = m.group(1)
            value = m.group(2)
            # Check if field is already Java (has lowercase or brackets)
            if field[0].islower() or '[' in field:
                java_field = field
            else:
                java_field = self.cobol_to_java_name(field)
            return f'"{value}".equals({java_field})'

        result = re.sub(
            rf'({JAVA_FIELD}|{COBOL_FIELD})\s*=\s*"([^"]*)"',
            replace_string_compare,
            result
        )

        # Step 6: Handle field = field comparisons (use == for primitives)
        def replace_field_compare(m):
            field1 = m.group(1)
            field2 = m.group(2)
            # Skip if already Java (lowercase start)
            if not (field1[0].islower() or '[' in field1):
                field1 = self.cobol_to_java_name(field1)
            if not (field2[0].islower() or '[' in field2):
                field2 = self.cobol_to_java_name(field2)
            return f'{field1} == {field2}'

        # IMPORTANT: Try COBOL_FIELD first (with hyphens) before JAVA_FIELD
        # Otherwise WS-PRELIM-PROFILE matches only WS as JAVA_FIELD
        result = re.sub(
            rf'({COBOL_FIELD}|{JAVA_FIELD})\s*=\s*({COBOL_FIELD}|{JAVA_FIELD})',
            replace_field_compare,
            result
        )

        # Step 7: Handle numeric comparisons with operators
        def replace_numeric_compare(m):
            field = m.group(1)
            op = m.group(2)
            value = m.group(3)
            if not (field[0].islower() or '[' in field):
                field = self.cobol_to_java_name(field)
            return f'{field} {op} {value}'

        result = re.sub(
            rf'({JAVA_FIELD}|{COBOL_FIELD})\s*([<>]=?)\s*(\d+)',
            replace_numeric_compare,
            result
        )

        # Step 7b: Handle field = number (COBOL equality to Java ==)
        # For String fields, compare numeric literal as string using .equals()
        def replace_numeric_equals(m):
            field = m.group(1)
            value = m.group(2)
            if not (field[0].islower() or '[' in field):
                field = self.cobol_to_java_name(field)
            # Check if field is String type - if so, compare as string
            base_field = re.sub(r'\s*\[.*\]', '', field).strip()
            field_type = self.field_types.get(base_field, 'unknown')
            if field_type in ('String', 'String[]'):
                return f'"{value}".equals({field})'
            return f'{field} == {value}'

        result = re.sub(
            rf'({JAVA_FIELD}|{COBOL_FIELD})\s*=\s*(\d+)\b',
            replace_numeric_equals,
            result
        )

        # Step 8: Convert COBOL literals to Java equivalents
        # Must do this BEFORE field name conversion
        result = re.sub(r'\bSPACES?\b', '""', result, flags=re.IGNORECASE)
        result = re.sub(r'\bZERO(?:S|ES)?\b', '0', result, flags=re.IGNORECASE)
        result = re.sub(r'\bLOW-VALUES?\b', 'LOW_VALUE', result, flags=re.IGNORECASE)
        result = re.sub(r'\bHIGH-VALUES?\b', 'HIGH_VALUE', result, flags=re.IGNORECASE)

        # Step 9: Convert any remaining COBOL field names to Java
        def replace_field_name(m):
            cobol_name = m.group(0)
            # Skip Java keywords, COBOL keywords, and already converted names
            skip_words = ['true', 'false', 'null', 'equals', 'not', 'and', 'or']
            if cobol_name.lower() in skip_words:
                return cobol_name  # Keep as-is (will be handled later)
            if cobol_name[0].islower():
                return cobol_name  # Already converted
            return self.cobol_to_java_name(cobol_name)

        result = re.sub(rf'\b({COBOL_FIELD})\b', replace_field_name, result)

        # Step 9: Clean up spacing issues
        result = re.sub(r'\s+', ' ', result)  # Multiple spaces to single
        result = result.strip()

        # Step 10: Fix leading zeros in numeric literals (Java interprets as octal)
        # 009 -> 9, 08 -> 8, etc.
        def fix_octal(m):
            num = m.group(1).lstrip('0') or '0'
            return num

        result = re.sub(r'\b0+(\d+)\b', fix_octal, result)

        # Step 11: Final cleanup - convert remaining COBOL NOT = to !=
        # This catches cases where the NOT = wasn't part of a recognized pattern
        # Also handle cases where earlier conversion created "not ==" or "!= ="
        result = re.sub(r'\bNOT\s*=\s*', '!= ', result, flags=re.IGNORECASE)
        result = re.sub(r'\bnot\s+==\s*', '!= ', result)  # Fix "not ==" artifacts
        result = re.sub(r'!=\s*=\s*', '!= ', result)  # Fix "!= =" artifacts

        # Step 12: Convert remaining = "string" to .equals("string")
        # This handles method().call = "value" patterns
        # IMPORTANT: Use negative lookbehind to avoid matching != or ==
        def replace_equals_string(m):
            before = m.group(1)
            value = m.group(2)
            return f'{value}.equals({before})'

        result = re.sub(
            r'(\w+(?:\([^)]*\))?)\s*(?<![!=])=(?![=])\s*(".*?")',
            replace_equals_string,
            result
        )

        # Step 13: Fix BigDecimal comparisons - must use compareTo()
        # BigDecimal cannot use ==, !=, <, >, <=, >= directly
        # Pattern: field (op) 0 where field is BigDecimal -> field.compareTo(BigDecimal.ZERO) (op) 0
        # Pattern: field (op) number -> field.compareTo(BigDecimal.valueOf(number)) (op) 0
        # Pattern: field (op) field2 -> field.compareTo(field2) (op) 0

        def fix_bigdecimal_comparison(m):
            field = m.group(1)
            op = m.group(2)
            value = m.group(3)

            # Extract base field names (without array subscript) to check types
            base_field = re.sub(r'\s*\[.*\]', '', field).strip()
            field_type = self.field_types.get(base_field, 'unknown')

            base_value = re.sub(r'\s*\[.*\]', '', value).strip()
            value_type = self.field_types.get(base_value, 'unknown')

            # Check if either operand is BigDecimal
            field_is_bigdecimal = field_type in ('BigDecimal', 'BigDecimal[]')
            # Numeric hint only applies if the actual type is unknown or numeric (not String)
            field_is_numeric_hint = (field_type not in ('String', 'String[]') and
                                     (base_field.endswith('Sum') or base_field.endswith('Amt') or base_field.endswith('Limit')))
            value_is_bigdecimal = value_type in ('BigDecimal', 'BigDecimal[]')
            value_is_numeric_hint = (value_type not in ('String', 'String[]') and
                                     (base_value.endswith('Sum') or base_value.endswith('Amt') or base_value.endswith('Limit')))

            # If neither is BigDecimal, leave as-is
            if not (field_is_bigdecimal or field_is_numeric_hint or value_is_bigdecimal or value_is_numeric_hint):
                return m.group(0)

            # If first operand is BigDecimal (or should be), use compareTo
            if field_is_bigdecimal or field_is_numeric_hint:
                # Convert the value for compareTo
                if value == '0':
                    compare_to = 'BigDecimal.ZERO'
                elif re.match(r'^-?(\d+\.?\d*|\.?\d+)$', value):
                    compare_to = f'BigDecimal.valueOf({value})'
                elif value_type in ('int', 'short', 'long', 'int[]', 'short[]', 'long[]'):
                    # Wrap primitive numeric in BigDecimal.valueOf()
                    compare_to = f'BigDecimal.valueOf({value})'
                elif value_is_bigdecimal:
                    # Already BigDecimal, use directly
                    compare_to = value
                else:
                    compare_to = value
                return f'{field}.compareTo({compare_to}) {op} 0'

            # If second operand is BigDecimal but first is not, wrap first appropriately
            if value_is_bigdecimal or value_is_numeric_hint:
                # String needs new BigDecimal(), primitives need BigDecimal.valueOf()
                if field_type in ('String', 'String[]'):
                    return f'new BigDecimal({field}).compareTo({value}) {op} 0'
                else:
                    return f'BigDecimal.valueOf({field}).compareTo({value}) {op} 0'

            return m.group(0)

        # Match patterns: field != 0, field == 0, field > 0, etc.
        # Also field != field2, field < field2, etc.
        # Number pattern includes .1 style decimals (like .01, .1)
        JAVA_FIELD = r'[a-zA-Z][a-zA-Z0-9_]*(?:\[[^\]]+\])?'
        NUMBER = r'-?\d+\.?\d*|\.?\d+'  # matches 0, 123, 1.5, .1, .01
        result = re.sub(
            rf'({JAVA_FIELD})\s*(!=|==|<=|>=|<|>)\s*({NUMBER}|{JAVA_FIELD})',
            fix_bigdecimal_comparison,
            result
        )

        # Step 13b: Fix String field comparisons with relational operators
        # String fields need to use .compareTo() for < > <= >= != comparisons
        # Also handle mixed int/String comparisons (COBOL allows this implicitly)
        def fix_string_comparison(m):
            field1 = m.group(1)
            op = m.group(2)
            field2 = m.group(3)

            # Get types
            base_field1 = re.sub(r'\s*\[.*\]', '', field1).strip()
            base_field2 = re.sub(r'\s*\[.*\]', '', field2).strip()
            type1 = self.field_types.get(base_field1, 'unknown')
            type2 = self.field_types.get(base_field2, 'unknown')

            # Check if either operand is String or numeric
            is_string1 = type1 in ('String', 'String[]')
            is_string2 = type2 in ('String', 'String[]')
            is_numeric1 = type1 in ('int', 'int[]', 'short', 'short[]', 'long', 'long[]')
            is_numeric2 = type2 in ('int', 'int[]', 'short', 'short[]', 'long', 'long[]')

            # If both are strings and we have relational operator, use compareTo
            if is_string1 and is_string2 and op in ('>', '<', '>=', '<=', '!='):
                java_op_map = {'>': '> 0', '<': '< 0', '>=': '>= 0', '<=': '<= 0', '!=': '!= 0'}
                return f'{field1}.compareTo({field2}) {java_op_map[op]}'

            # Mixed int/String comparison - convert int to String and use equals/compareTo
            if (is_string1 and is_numeric2) or (is_numeric1 and is_string2):
                # Convert numeric to String and compare
                if is_string1 and is_numeric2:
                    str_field = field1
                    int_field = field2
                else:
                    str_field = field2
                    int_field = field1
                    # Swap comparison direction for != and ==
                    if op in ('!=', '=='):
                        pass  # direction doesn't matter for equality
                    else:
                        # Reverse the comparison operator
                        op_reverse = {'>': '<', '<': '>', '>=': '<=', '<=': '>='}
                        op = op_reverse.get(op, op)

                if op in ('!=', '=='):
                    # Use .equals() for equality comparison
                    if op == '==':
                        return f'{str_field}.equals(String.valueOf({int_field}))'
                    else:
                        return f'!{str_field}.equals(String.valueOf({int_field}))'
                else:
                    # Use compareTo for relational operators
                    java_op_map = {'>': '> 0', '<': '< 0', '>=': '>= 0', '<=': '<= 0'}
                    return f'{str_field}.compareTo(String.valueOf({int_field})) {java_op_map[op]}'

            return m.group(0)

        # Only apply to field vs field comparisons (not field vs number)
        result = re.sub(
            rf'({JAVA_FIELD})\s*(!=|<=|>=|<|>)\s*({JAVA_FIELD})',
            fix_string_comparison,
            result
        )

        # Step 14: Balance parentheses
        # OR expansion can create unbalanced parens when COBOL has (FIELD = "A" OR "B")
        # The expansion produces ("a".equals(field) || "b".equals(field)) but original
        # outer parens may remain, causing )) issues
        open_count = result.count('(')
        close_count = result.count(')')
        if close_count > open_count:
            # Remove excess close parens from the end
            excess = close_count - open_count
            # Find trailing close parens and remove excess
            result = result.rstrip()
            while excess > 0 and result.endswith(')'):
                result = result[:-1].rstrip()
                excess -= 1

        # Step 15: Fix COBOL "= SPACES OR ZEROES" pattern
        # For numeric fields, this should just be "== 0"
        # Pattern: field == "" || 0 -> field == 0
        result = re.sub(r'(\w+(?:\[[^\]]+\])?)\s*==\s*""\s*\|\|\s*0\)', r'\1 == 0)', result)

        # Also fix pattern: (field == "" || field == 0)
        result = re.sub(r'\((\w+(?:\[[^\]]+\])?)\s*==\s*""\s*\|\|\s*\1\s*==\s*0\)', r'(\1 == 0)', result)

        # Step 16: Fix String fields used in boolean context
        # COBOL: IF FIELD means "if field is not SPACES"
        # Pattern: && stringField && or && stringField)
        def fix_string_boolean_context(m):
            prefix = m.group(1)  # && or ( or if (
            field = m.group(2)
            suffix = m.group(3)  # && or )
            base_field = re.sub(r'\s*\[.*\]', '', field).strip()
            field_type = self.field_types.get(base_field, 'unknown')
            if field_type in ('String', 'String[]'):
                # String field in boolean context: test if not empty
                return f'{prefix}!{field}.isEmpty(){suffix}'
            return m.group(0)

        # Match patterns: (&& field &&), (&& field)), (( field &&)
        JAVA_FIELD_PATTERN = r'[a-zA-Z][a-zA-Z0-9_]*(?:\[[^\]]+\])?'
        result = re.sub(
            rf'(&&\s*)({JAVA_FIELD_PATTERN})(\s*&&)',
            fix_string_boolean_context,
            result
        )
        result = re.sub(
            rf'(&&\s*)({JAVA_FIELD_PATTERN})(\s*\))',
            fix_string_boolean_context,
            result
        )

        return result

    def generate_imports(self):
        """Generate import statements."""
        # Add imports based on data model
        for imp in self.data_model.get('imports_needed', []):
            self.imports.add(imp)

        # Standard imports we might need
        self.imports.add('java.math.BigDecimal')
        self.imports.add('java.math.RoundingMode')

        self.emit("package com.modernizeit.generated;")
        self.emit_blank()

        for imp in sorted(self.imports):
            self.emit(f"import {imp};")
        self.emit_blank()

    def generate_class_header(self):
        """Generate class declaration."""
        self.emit("/**")
        self.emit(f" * {self.class_name} - COBOL to Java Translation")
        self.emit(f" * Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.emit(f" * Source: {self.class_name}.CBL")
        self.emit(" * ")
        self.emit(" * Line references (L:nnn) map to original COBOL source.")
        self.emit(" */")
        self.emit(f"public class {self.class_name} {{")
        self.indent_level += 1
        self.emit_blank()

    def generate_test_harness(self):
        """Generate main() method for IntelliJ testing - NOT part of transformation flow."""
        self.emit("// ============================================================================")
        self.emit("// TEST HARNESS - NOT PART OF TRANSFORMATION FLOW")
        self.emit("// ============================================================================")
        self.emit("// This main() is auto-generated for IntelliJ exploration/debugging.")
        self.emit("// Limitations: File I/O stubbed, external CALLs empty, default data values.")
        self.emit(f"// To run: Right-click this file in IntelliJ -> Run '{self.class_name}.main()'")
        self.emit("// ============================================================================")
        self.emit('public static void main(String[] args) {')
        self.indent_level += 1
        self.emit(f'System.out.println("=== {self.class_name} Test Harness ===");')
        self.emit('System.out.println("COBOL-to-Java translation. File I/O and CALLs are stubbed.");')
        self.emit(f'{self.class_name} program = new {self.class_name}();')
        self.emit('try {')
        self.indent_level += 1
        self.emit('System.out.println("Calling 000-MAIN-CONTROL...");')
        self.emit('program.mainControl_000();')
        self.emit('System.out.println("Program completed.");')
        self.indent_level -= 1
        self.emit('} catch (Exception e) {')
        self.indent_level += 1
        self.emit('System.out.println("Exception: " + e.getMessage());')
        self.emit('e.printStackTrace();')
        self.indent_level -= 1
        self.emit('}')
        self.indent_level -= 1
        self.emit('}')
        self.emit("// ============================================================================")
        self.emit_blank()

    def generate_constants(self):
        """Generate constants from 77-level items with VALUE."""
        self.emit("// === CONSTANTS ===")
        # Add COBOL literal constants
        self.emit('private static final String LOW_VALUE = "\\u0000";')
        self.emit('private static final String HIGH_VALUE = "\\u00FF";')
        self.emit_blank()

        for field in self.data_model.get('fields', []):
            if field.get('level') == 77 and field.get('value'):
                name = field['cobol_name'].replace('-', '_').upper()
                value = field['value']
                java_type = field.get('java_type', 'String')

                if java_type == 'String':
                    self.emit(f'private static final String {name} = "{value}";',
                              field.get('line_num'), field['cobol_name'])
                elif java_type in ('int', 'short', 'long'):
                    self.emit(f'private static final {java_type} {name} = {value};',
                              field.get('line_num'), field['cobol_name'])
        self.emit_blank()

    def generate_external_field_stubs(self):
        """Generate placeholder fields for external file records and COPY members."""
        self.emit("// === EXTERNAL FILE RECORD FIELDS (Stubs) ===")
        self.emit("// These fields come from file records or COPY members - need proper FD parsing")

        # Known external field patterns from compilation errors
        external_fields = [
            # CL1 record fields (client options)
            ('cl1ClientNo', 'String', '""'),
            ('cl1OptNo', 'int', '0'),
            ('cl1OptValue', 'String', '""'),
            # CLN fields
            ('clnOpt62Ws', 'String', '""'),
            ('cln4K90RegOptWs', 'String', '""'),
            # Calendar/period fields
            ('calCdeCycle', 'String', '""'),
            ('calNumber', 'int', '0'),
            ('calPrdNo', 'int', '0'),
            ('calYear', 'int', '0'),
            ('endOfQtr', 'String', '""'),
            ('endOfYr', 'String', '""'),
            # Profile fields
            ('prelimProfile', 'String', '""'),
            ('profOpt', 'String', '""'),
            ('wsProfile', 'String', '""'),
            # Client environment
            ('cClientEnv', 'String', '""'),
            # Option switches
            ('wsCliOpt608Sw', 'String', '""'),
            ('wsCliOpt630Sw', 'String', '""'),
            ('wsClientDedOpt30Sw', 'String', '""'),
            ('wsClientDedOpt36Sw', 'String', '""'),
            # Status/flag fields
            ('gtnEnd', 'String', '"N"'),
            ('expandDedArrearsSw', 'String', '""'),
            ('notOkLit', 'String', '"NO"'),
            ('purgeError', 'boolean', 'false'),
            # SD record fields (earnings/deductions)
            ('sdbfnu', 'String', '""'),
            ('sdexco', 'String', '""'),
            ('sdhgnu', 'String', '""'),
            ('sdhhnu', 'String', '""'),
            ('sdixsa', 'String', '""'),
            ('sdiysa', 'String', '""'),
            ('sdmznu', 'String', '""'),
            # S0 record fields
            ('s0bfnu', 'String', '""'),
            ('s0cwte', 'String', '""'),
            ('s0hdnu', 'String', '""'),
            ('s0henu', 'String', '""'),
            ('s0hfnu', 'String', '""'),
            # Misc
            ('ws', 'String', '""'),
            ('c', 'String', '""'),
            # Loop index variables (PERFORM VARYING)
            ('i', 'int', '0'),
            ('I', 'int', '0'),
            # TIM record fields (PAYTIMFILE)
            ('timCheckType', 'String', '""'),
            ('timTblElement', 'int', '0'),
            ('timNoCycles', 'int', '0'),
            ('timGroup', 'String', '""'),
            ('timCode', 'String', '""'),
            ('timClientNo', 'short', '(short)0'),
            ('timAmount', 'BigDecimal', 'BigDecimal.ZERO'),
            ('timDateEnd', 'int', '0'),
            ('timCheckNo', 'int', '0'),
            ('timCdeCycle', 'String', '""'),
            # IO status fields (COBOL file status codes like "00", "10", etc.)
            ('ioOk', 'String', '"00"'),
            ('io', 'String', '""'),
            ('ok', 'boolean', 'false'),
            # Tax fields
            ('taxastt', 'String', '""'),
            ('taxafed', 'String', '""'),
            ('taxaerr', 'String', '""'),
            # Calendar fields
            ('calClrQtd', 'String', '""'),
            # Additional TIM fields
            ('timType', 'String', '""'),
            ('timEmpNo', 'int', '0'),
            # Additional tax fields
            ('taxasuca', 'BigDecimal', 'BigDecimal.ZERO'),
            ('taxaoth', 'BigDecimal', 'BigDecimal.ZERO'),
            ('taxaloc', 'BigDecimal', 'BigDecimal.ZERO'),
            ('taxafuta', 'BigDecimal', 'BigDecimal.ZERO'),
            ('taxafica', 'BigDecimal', 'BigDecimal.ZERO'),
            ('taxacit', 'BigDecimal', 'BigDecimal.ZERO'),
            ('taxaern', 'BigDecimal', 'BigDecimal.ZERO'),
            # Tax code workspace
            ('cdeTaxWs', 'String', '""'),
            # Literal fields
            ('sttLiteral', 'String', '""'),
            ('othLiteral', 'String', '""'),
            ('locLiteral', 'String', '""'),
            ('citLiteral', 'String', '""'),
            # S0 additional fields
            ('s0l4sa', 'BigDecimal', 'BigDecimal.ZERO'),
            ('s0l3sa', 'BigDecimal', 'BigDecimal.ZERO'),
            # AT END status (COBOL file status codes)
            ('atEnd', 'String', '"10"'),
            ('ioAtEnd', 'String', '"10"'),
            # Error counters
            ('grossNetErrorCntWs', 'int', '0'),
            # PER (PAYPERFILE) fields
            ('per', 'String', '""'),
            ('perCdeCycle', 'String', '""'),
            ('perMarStatStt', 'String', '""'),
            ('perMarStatFed', 'String', '""'),
            ('perExmTable', 'String', '""'),
            ('wsPerExmTable', 'String', '""'),
            ('perExmFed', 'int', '0'),
            ('perEmpNo', 'int', '0'),
            ('perClientNo', 'short', '(short)0'),
            ('perActive', 'String', '""'),
            # ERN (PAYERNFILE) fields
            ('ernEmpNo', 'int', '0'),
            ('ernClientNo', 'short', '(short)0'),
            # BEN (PAYBENFILE) fields
            ('benEmpNo', 'int', '0'),
            ('benClientNo', 'short', '(short)0'),
            # Common key fields
            ('empNo', 'int', '0'),
            ('clientNo', 'short', '(short)0'),
            # Additional TIM work fields
            ('timStoreWrk', 'String', '""'),
            ('timDeptWrk', 'String', '""'),
            ('timCorpWrk', 'String', '""'),
            # CNL (Control) fields
            ('cnl', 'String', '""'),
            ('cnlParaYn', 'String', '""'),
            ('cnlActYn', 'String', '""'),
            ('cnlSub', 'int', '0'),
            ('cnlIdxWs', 'int', '0'),
            ('cnlAssocDedNoWs', 'int[]', 'new int[100]'),
            # BEN additional fields (arrays for OCCURS)
            ('benDedNo', 'int[]', 'new int[100]'),
            # BEN-DED arrays (COBOL tables)
            ('benDedPara', 'String[]', 'new String[100]'),
            ('benDedPercent', 'BigDecimal[]', 'new BigDecimal[100]'),
            ('benDedAmt', 'BigDecimal[]', 'new BigDecimal[100]'),
            ('benArrsCtr', 'BigDecimal[]', 'new BigDecimal[100]'),  # COMP-3 from copybook
            ('benDedTktn', 'int[]', 'new int[100]'),
            ('benDedBal', 'BigDecimal[]', 'new BigDecimal[100]'),
            # CLN additional fields
            ('clnCycle', 'String', '""'),
            # Status literals
            ('okLit', 'String', '"OK"'),
            # Loop indices (lowercase and uppercase variants)
            ('j', 'int', '0'),
            ('J', 'int', '0'),
            ('k', 'int', '0'),
            # Cycle fields
            ('wsCycleDefault', 'String', '""'),
            # BEN date fields (arrays - OCCURS in COBOL)
            ('benBegDate', 'BigDecimal[]', 'new BigDecimal[100]'),
            ('benEndDate', 'BigDecimal[]', 'new BigDecimal[100]'),
            # Take deduction switches
            ('takeWkDed', 'boolean', 'false'),
            ('takeSmDed', 'boolean', 'false'),
            ('takeBwDed', 'boolean', 'false'),
            ('takeMtDed', 'boolean', 'false'),
            # WS balance flags
            ('wsBalFlg', 'String', '""'),
            # Note: cnlOptNoWs and cnlTypeWs are already in data model
            # Case variation (CnlIdxWs vs cnlIdxWs)
            ('CnlIdxWs', 'int', '0'),
            # Additional BEN fields (arrays)
            ('benOrderNo', 'int[]', 'new int[100]'),
            # Control flag
            ('dedRoutineError', 'boolean', 'false'),
            # Additional missing fields
            ('setArrears', 'boolean', 'false'),
            # Note: cnlFreqWs, cnlSetArrWs, cnlTaxblFicaWs, cnlAssocDedNoWs, cnlActFlgWs already in data model
            # Note: dedNoSum, dedParaSum already in data model

            # === TCP (Transaction Current Period) record fields ===
            ('tcpCode', 'String', '""'),
            ('tcpAmount', 'BigDecimal', 'BigDecimal.ZERO'),
            ('tcpType', 'String', '""'),
            ('tcpHours', 'BigDecimal', 'BigDecimal.ZERO'),
            ('tcpRate', 'BigDecimal', 'BigDecimal.ZERO'),
            ('tcpFileSeq', 'int', '0'),
            ('tcpStoreWrk', 'String', '""'),
            ('tcpDeptWrk', 'String', '""'),
            ('tcpCorpWrk', 'String', '""'),
            ('tcpSeqNo', 'int', '0'),
            ('tcpDirDepVoucher', 'String', '""'),
            ('tcpDocumentNo', 'String', '""'),
            ('tcpDocumentDate', 'int', '0'),
            ('tcpStoreNo', 'int', '0'),
            ('tcpDeptNo', 'int', '0'),
            ('tcpCorpNo', 'int', '0'),
            ('tcpSubGroup', 'String', '""'),
            ('tcpStoreGl', 'String', '""'),
            ('tcpGroup', 'String', '""'),
            ('tcpEmpNo', 'int', '0'),
            ('tcpEmpName', 'String', '""'),
            ('tcpDeptGl', 'String', '""'),
            ('tcpDateEnd', 'int', '0'),
            ('tcpCompNo', 'int', '0'),
            ('tcpClientNo', 'short', '(short)0'),
            ('tcpCheckType', 'String', '""'),
            ('tcpCheckNo', 'int', '0'),
            ('tcpCdeCycle', 'String', '""'),
            ('tcpAcctGl', 'String', '""'),

            # === TBL (Table) record fields ===
            ('tblIdx', 'int', '0'),
            ('tblWorkKey', 'String', '""'),
            ('tblLevel', 'int', '0'),
            ('tblFicaPct', 'BigDecimal', 'BigDecimal.ZERO'),
            ('tblWageLimitYtd', 'BigDecimal', 'BigDecimal.ZERO'),
            ('tblTaxLimitYtd', 'BigDecimal', 'BigDecimal.ZERO'),
            ('tblMarStatus', 'String', '""'),
            ('tblFlatTaxAmt', 'BigDecimal', 'BigDecimal.ZERO'),
            ('tblFicaLimit', 'BigDecimal', 'BigDecimal.ZERO'),
            ('tblCdeTax', 'String', '""'),
            ('wsTblKey', 'String[]', 'new String[100]'),

            # === TB1 (Table Option) record fields ===
            ('tb1OptId', 'int', '0'),
            ('tb1OptValue', 'String', '""'),
            ('tb1CdeTax', 'String', '""'),
            ('tb1MarStatus', 'String', '""'),

            # === PER (Personnel) additional fields ===
            ('perTaxPara', 'BigDecimal[]', 'new BigDecimal[10]'),  # PIC S9(7)V99 COMP-3 from copybook
            ('perTaxFlg', 'String[]', 'new String[20]'),
            ('perStoreNo', 'int', '0'),
            ('perCorpNo', 'int', '0'),
            ('perDeptNo', 'int', '0'),
            ('perCdeStt', 'String', '""'),
            ('perRteSalary', 'BigDecimal', 'BigDecimal.ZERO'),
            ('perCdeOth', 'String', '""'),
            ('perSchdlHrs', 'BigDecimal', 'BigDecimal.ZERO'),
            ('perTaxFlgFed', 'String', '""'),
            ('perRteHourly', 'BigDecimal', 'BigDecimal.ZERO'),
            ('perBankDepAmt', 'BigDecimal[]', 'new BigDecimal[5]'),
            ('perSchdl', 'String', '""'),
            ('perBankPnFlag', 'String[]', 'new String[5]'),
            ('perBankAcctType', 'String[]', 'new String[5]'),
            ('perExmStt', 'int', '0'),
            ('perEmpName', 'String', '""'),
            ('perCdeTax', 'String[]', 'new String[20]'),
            ('perExmCnt', 'int[]', 'new int[20]'),
            ('perCompNo', 'int', '0'),
            ('perKey', 'String', '""'),
            ('perJobClass', 'String', '""'),
            ('perBankAbaNo', 'int[]', 'new int[5]'),
            ('perBankAcct', 'String[]', 'new String[5]'),
            ('perCdeCit', 'String', '""'),
            ('perCdeLoc', 'String', '""'),
            ('perTaxFlgCit', 'String', '""'),
            ('perTaxFlgFica', 'String', '""'),
            ('perTaxFlgLoc', 'String', '""'),
            ('perTaxFlgOth', 'String', '""'),
            ('perTaxFlgStt', 'String', '""'),
            ('wsPerExemptCnt', 'int[]', 'new int[50]'),

            # === PE1 (Personnel Index) record fields ===
            ('pe1Inx', 'int', '0'),
            ('pe1Ok', 'String', '""'),
            ('pe1ClientNo', 'short', '(short)0'),
            ('pe1EmpNo', 'int', '0'),
            ('pe1MarStat', 'String', '""'),
            ('pe1SeqNo', 'int', '0'),
            ('pe1TaxCde', 'String', '""'),
            ('pe1TaxExm', 'int', '0'),
            ('pe1TaxFlg', 'String', '""'),
            ('pe1TaxPara', 'String', '""'),
            ('pe1TaxQtd', 'BigDecimal', 'BigDecimal.ZERO'),
            ('pe1TaxYtd', 'BigDecimal', 'BigDecimal.ZERO'),

            # === PE3 (Personnel 3) record fields ===
            ('pe3ClientNo', 'short', '(short)0'),
            ('pe3DiffAmt', 'BigDecimal', 'BigDecimal.ZERO'),
            ('pe3DiffFlg', 'String', '""'),
            ('pe3EmpNo', 'int', '0'),
            ('pe3Multiplier', 'BigDecimal', 'BigDecimal.ZERO'),
            ('pe3SeqNo', 'int', '0'),

            # === CL2 (Client 2) record fields ===
            ('cl2AnnlHrs', 'BigDecimal', 'BigDecimal.ZERO'),
            ('cl2ClientNo', 'short', '(short)0'),
            ('cl2LvClass', 'String', '""'),
            ('cl2LvFormula', 'String', '""'),
            ('cl2PersHrs', 'BigDecimal', 'BigDecimal.ZERO'),
            ('cl2SickHrs', 'BigDecimal', 'BigDecimal.ZERO'),

            # === CL3 (Client 3) record fields ===
            ('cl3ActFlg', 'String', '""'),
            ('cl3ClientNo', 'short', '(short)0'),
            ('cl3DiffAmt', 'BigDecimal', 'BigDecimal.ZERO'),
            ('cl3DiffFlg', 'String', '""'),
            ('cl3ErnCode', 'String', '""'),
            ('cl3ErnSeq', 'int', '0'),
            ('cl3Multiplier', 'BigDecimal', 'BigDecimal.ZERO'),
            ('cl3Ok', 'String', '""'),
            ('cl3TaxblCit', 'String', '""'),
            ('cl3TaxblFed', 'String', '""'),
            ('cl3TaxblFica', 'String', '""'),
            ('cl3TaxblFuta', 'String', '""'),
            ('cl3TaxblLoc', 'String', '""'),
            ('cl3TaxblOth', 'String', '""'),
            ('cl3TaxblStt', 'String', '""'),
            ('cl3TaxblSuca', 'String', '""'),

            # === CLN (Control Line) additional fields ===
            ('clnActFlg', 'String[]', 'new String[50]'),
            ('clnBankCode', 'String', '""'),
            ('clnBankCompNo', 'int', '0'),
            ('clnCalNo', 'int', '0'),
            ('clnCalYr', 'int', '0'),
            ('clnClientNo', 'short', '(short)0'),
            ('clnCompNo', 'int', '0'),
            ('clnCppNo', 'int', '0'),
            ('clnDiffAmt', 'BigDecimal[]', 'new BigDecimal[50]'),
            ('clnDiffFlg', 'String[]', 'new String[50]'),
            ('clnErnCode', 'String[]', 'new String[50]'),
            ('clnMultiplier', 'BigDecimal[]', 'new BigDecimal[50]'),
            ('clnTaxblCit', 'String[]', 'new String[50]'),
            ('clnTaxblFed', 'String[]', 'new String[50]'),
            ('clnTaxblFica', 'String[]', 'new String[50]'),
            ('clnTaxblFuta', 'String[]', 'new String[50]'),
            ('clnTaxblLoc', 'String[]', 'new String[50]'),
            ('clnTaxblOth', 'String[]', 'new String[50]'),
            ('clnTaxblStt', 'String[]', 'new String[50]'),
            ('clnTaxblSuca', 'String[]', 'new String[50]'),

            # === CN1 (Client Option 1) record fields ===
            ('cn1ClientNo', 'short', '(short)0'),
            ('cn1DedNo', 'String', '""'),
            ('cn1IdxWs', 'int', '0'),
            ('cn1OptNo', 'int', '0'),
            ('cn1OptValue', 'String', '""'),

            # === CNL (Control) additional fields ===
            ('cnlActFlg', 'String', '""'),
            ('cnlAssocDedNo', 'String', '""'),
            ('cnlClientNo', 'short', '(short)0'),
            ('cnlCycleFreq', 'String', '""'),
            ('cnlDedNo', 'String', '""'),
            ('cnlOrderNo', 'int', '0'),
            ('cnlSetArrFlg', 'String', '""'),
            ('cnlTaxblCit', 'String', '""'),
            ('cnlTaxblFed', 'String', '""'),
            ('cnlTaxblFica', 'String', '""'),
            ('cnlTaxblLoc', 'String', '""'),
            ('cnlTaxblOth', 'String', '""'),
            ('cnlTaxblStt', 'String', '""'),
            ('cnlTaxblTableWs', 'String[]', 'new String[100]'),
            ('cnlTypeTable', 'String', '""'),
            ('cnlTypeTableWs', 'String[]', 'new String[100]'),
            ('cnlYtdPrt', 'String', '""'),

            # === BEN (Benefit) additional fields ===
            ('benAccQtd', 'BigDecimal[]', 'new BigDecimal[100]'),
            ('benAccYtd', 'BigDecimal[]', 'new BigDecimal[100]'),
            ('benAnnlAccRte', 'BigDecimal', 'BigDecimal.ZERO'),
            ('benAnnlAcrdYtd', 'BigDecimal', 'BigDecimal.ZERO'),
            ('benAnnlBal', 'BigDecimal', 'BigDecimal.ZERO'),
            ('benAnnlClass', 'String', '""'),
            ('benAnnlLimit', 'BigDecimal', 'BigDecimal.ZERO'),
            ('benDedOpt', 'BigDecimal[]', 'new BigDecimal[100]'),
            ('benKey', 'String', '""'),
            ('benPersAccRte', 'BigDecimal', 'BigDecimal.ZERO'),
            ('benPersBal', 'BigDecimal', 'BigDecimal.ZERO'),
            ('benPersClass', 'String', '""'),
            ('benPersLimit', 'BigDecimal', 'BigDecimal.ZERO'),
            ('benSeqNo', 'int[]', 'new int[100]'),
            ('benSickAccRte', 'BigDecimal', 'BigDecimal.ZERO'),
            ('benSickBal', 'BigDecimal', 'BigDecimal.ZERO'),
            ('benSickClass', 'String', '""'),
            ('benSickLimit', 'BigDecimal', 'BigDecimal.ZERO'),

            # === CAL (Calendar) additional fields ===
            ('calDedFlgs', 'String', '""'),

            # === ERN (Earnings) additional fields ===
            ('ernCode', 'String[]', 'new String[50]'),
            ('ernCppSum', 'BigDecimal[]', 'new BigDecimal[50]'),
            ('ernDatePaidLst', 'int', '0'),
            ('ernEarnQtd', 'BigDecimal[]', 'new BigDecimal[50]'),
            ('ernEarnYtd', 'BigDecimal[]', 'new BigDecimal[50]'),
            ('ernErnYtdGross', 'BigDecimal', 'BigDecimal.ZERO'),
            ('ernHrsQtd', 'BigDecimal[]', 'new BigDecimal[50]'),
            ('ernHrsYtd', 'BigDecimal[]', 'new BigDecimal[50]'),
            ('ernHrsYtdGross', 'BigDecimal', 'BigDecimal.ZERO'),
            ('ernKey', 'String', '""'),
            ('ernTaxQtd', 'BigDecimal[]', 'new BigDecimal[20]'),
            ('ernTaxYtd', 'BigDecimal[]', 'new BigDecimal[20]'),
            ('ernTaxYtdCit', 'BigDecimal', 'BigDecimal.ZERO'),
            ('ernTaxYtdFed', 'BigDecimal', 'BigDecimal.ZERO'),
            ('ernTaxYtdFica', 'BigDecimal', 'BigDecimal.ZERO'),
            ('ernTaxYtdLoc', 'BigDecimal', 'BigDecimal.ZERO'),
            ('ernTaxYtdOth', 'BigDecimal', 'BigDecimal.ZERO'),
            ('ernTaxYtdStt', 'BigDecimal', 'BigDecimal.ZERO'),
            ('ernYtdAdveic', 'BigDecimal', 'BigDecimal.ZERO'),
            ('hrsCppSum', 'BigDecimal[]', 'new BigDecimal[50]'),

            # === TAX fields ===
            ('taxExempt', 'boolean', 'false'),
            ('taxKeyFound', 'boolean', 'false'),
            ('taxName', 'String[]', 'new String[50]'),
            ('taxRoutineOk', 'boolean', 'false'),
            ('addlTax', 'boolean', 'false'),
            ('fedPctTax', 'boolean', 'false'),
            ('fixedTax', 'boolean', 'false'),
            ('lessTax', 'boolean', 'false'),
            ('pctWageTax', 'boolean', 'false'),
            ('piggyBackTax', 'boolean', 'false'),
            ('advEicTax', 'boolean', 'false'),

            # === DEP (Deposit) record fields ===
            ('depAcctType', 'String', '""'),
            ('depAllotAmt', 'BigDecimal', 'BigDecimal.ZERO'),
            ('depBkAba', 'String', '""'),
            ('depBkAccount', 'String', '""'),
            ('depCheckDate', 'int', '0'),
            ('depCheckNo', 'int', '0'),
            ('depClientNo', 'short', '(short)0'),
            ('depDepositNo', 'int', '0'),
            ('depEmpName', 'String', '""'),
            ('depEmpNo', 'int', '0'),
            ('depPnFlag', 'String', '""'),
            ('depSeqNo', 'int', '0'),
            ('depTransAmt', 'BigDecimal', 'BigDecimal.ZERO'),
            ('depTransCode', 'String', '""'),
            ('depTransSign', 'String', '""'),

            # === GTN (Gross-to-Net) record fields ===
            ('gtnClientNo', 'short', '(short)0'),
            ('gtnEmpNo', 'int', '0'),
            ('gtnEndDate', 'int', '0'),
            ('gtnErrorType', 'String', '""'),
            ('gtnProfile', 'String', '""'),
            ('gtnSeqNo', 'int', '0'),
            ('gtnText', 'String', '""'),

            # === TIM additional fields ===
            ('timHours', 'BigDecimal', 'BigDecimal.ZERO'),
            ('timRate', 'BigDecimal', 'BigDecimal.ZERO'),

            # === JJ (Option Percent) record fields ===
            ('jjaapt', 'BigDecimal', 'BigDecimal.ZERO'),
            ('jjabpt', 'BigDecimal', 'BigDecimal.ZERO'),
            ('jjacpt', 'BigDecimal', 'BigDecimal.ZERO'),
            ('jjadpt', 'BigDecimal', 'BigDecimal.ZERO'),
            ('jjbfnu', 'String', '""'),
            ('jjbhco', 'String', '""'),
            ('jjf7nu', 'String', '""'),

            # === OJ (QTD-YTD-FICM) record fields ===
            ('ojacnu', 'String', '""'),
            ('ojbfnu', 'String', '""'),
            ('ojewsb', 'BigDecimal', 'BigDecimal.ZERO'),
            ('ojnlvu', 'BigDecimal', 'BigDecimal.ZERO'),
            ('ojt3co', 'String', '""'),

            # === Misc workspace fields ===
            ('dedTaxblTableSum', 'String[]', 'new String[165]'),
            ('endMultiply', 'BigDecimal', 'BigDecimal.ZERO'),
            ('lvFlagsWs', 'String[]', 'new String[50]'),
            ('purgeOk', 'boolean', 'false'),
            ('payrollCurrentTransRecord', 'String', '""'),
            ('payrollTaxTableRecord', 'String', '""'),

            # === Additional missing fields (Session 3) ===
            ('taxKeyNotFound', 'boolean', 'false'),
            ('taxRoutineError', 'boolean', 'false'),
            ('taxSubGroup', 'String[]', 'new String[50]'),
            ('tb1Level', 'int', '0'),
            ('tblExemptAddlAmt', 'BigDecimal', 'BigDecimal.ZERO'),
            ('tblKey', 'String', '""'),
            ('tblLowerWageLimit', 'BigDecimal', 'BigDecimal.ZERO'),
            ('tblTaxLimitCpp', 'BigDecimal', 'BigDecimal.ZERO'),
            ('tcpBankCode', 'String', '""'),
            ('tcpBankComp', 'int', '0'),
            ('tcpCorpGl', 'String', '""'),
            ('tcpJobClass', 'String', '""'),
            ('tcpUpdateYn', 'String', '""'),
            ('timCompNo', 'int', '0'),
            ('timCorpNo', 'int', '0'),
            ('timDeptNo', 'int', '0'),
            ('timSeqNo', 'int', '0'),
            ('timStoreNo', 'int', '0'),
            ('workTimCode', 'String', '""'),
            ('wsMwTblCdeStKey', 'String', '""'),
            ('wsTblRecord', 'String[]', 'new String[100]'),
        ]

        # Get all field names from data model to avoid duplicates
        data_model_fields = {f.get('java_name') for f in self.data_model.get('fields', [])}

        for field_name, java_type, init_value in external_fields:
            # Skip if field is already defined in data model
            if field_name in data_model_fields:
                continue
            self.emit(f'private {java_type} {field_name} = {init_value};')
            # Also add to field_types map so MOVE statements know the type
            self.field_types[field_name] = java_type

        self.emit_blank()

    def generate_fields(self):
        """Generate instance fields from data model."""
        self.emit("// === WORKING STORAGE FIELDS ===")

        # Generate ALL fields except FILLER
        # Note: COBOL VALUE clause is just an initializer, not a constant declaration
        all_fields = [f for f in self.data_model.get('fields', [])
                      if not f.get('is_filler')]

        for field in all_fields:  # Generate ALL fields
            java_name = field.get('java_name', self.cobol_to_java_name(field['cobol_name']))

            # Use corrected type if available (parser got some copybook fields wrong)
            if hasattr(self, 'type_corrections') and java_name in self.type_corrections:
                java_type = self.type_corrections[java_name]
            else:
                java_type = field.get('java_type', 'Object')

            cobol_value = field.get('value')

            # Initialize with COBOL VALUE if present, otherwise use type defaults
            if cobol_value is not None:
                # Use the COBOL VALUE clause for initialization
                if java_type == 'String':
                    # String value - quote it
                    init = f' = "{cobol_value}"'
                elif java_type in ('int', 'short', 'long'):
                    # Numeric value
                    if java_type == 'short':
                        init = f' = (short){cobol_value}'
                    else:
                        init = f' = {cobol_value}'
                elif java_type == 'BigDecimal':
                    # Handle both numeric 0 and COBOL literals ZERO/ZEROS/ZEROES
                    if cobol_value == 0 or str(cobol_value).upper() in ('ZERO', 'ZEROS', 'ZEROES'):
                        init = ' = BigDecimal.ZERO'
                    else:
                        init = f' = BigDecimal.valueOf({cobol_value})'
                else:
                    init = ''
            elif java_type == 'String':
                init = ' = ""'
            elif java_type in ('int', 'short', 'long'):
                init = ' = 0'
            elif java_type == 'BigDecimal':
                init = ' = BigDecimal.ZERO'
            elif '[]' in java_type:
                # Check if both occurs and inherited_occurs exist -> 2D array
                has_occurs = field.get('occurs')
                has_inherited = field.get('inherited_occurs')
                if has_occurs and has_inherited:
                    # 2D array: field is inside an OCCURS group and has its own OCCURS
                    base = java_type.replace('[]', '')
                    java_type = f'{base}[][]'  # Upgrade to 2D array
                    init = f' = new {base}[{has_inherited}][{has_occurs}]'
                else:
                    # 1D array: Use occurs or inherited_occurs for array size
                    size = has_occurs or has_inherited or 10
                    base = java_type.replace('[]', '')
                    init = f' = new {base}[{size}]'
            else:
                init = ''

            self.emit(f'private {java_type} {java_name}{init};',
                      field.get('line_num'), field['cobol_name'])

        # Generate missing fields (multi-line COBOL definitions not captured by parser)
        if hasattr(self, 'missing_fields') and self.missing_fields:
            self.emit_blank()
            self.emit("// === MISSING FIELDS (multi-line COBOL definitions) ===")
            for java_name, java_type in self.missing_fields.items():
                if '[]' in java_type:
                    base = java_type.replace('[]', '')
                    init = f' = new {base}[10]'  # Default size 10 for arrays
                elif java_type == 'BigDecimal':
                    init = ' = BigDecimal.ZERO'
                else:
                    init = ''
                self.emit(f'private {java_type} {java_name}{init};')

        self.emit_blank()

    def generate_groups_as_classes(self):
        """Generate inner classes for COBOL groups."""
        self.emit("// === GROUP STRUCTURES (Inner Classes) ===")
        self.emit_blank()

        # Generate ALL groups as inner classes
        for group in self.data_model.get('groups', []):
            class_name = group.get('java_class_name', self.cobol_to_class_name(group['cobol_name']))
            cobol_name = group['cobol_name']
            self.emit(f'public static class {class_name} {{',
                      group.get('line_num'), cobol_name)
            self.indent_level += 1

            # Get children for this group from the parent->children map
            children = self.children_by_parent.get(cobol_name, [])

            if children:
                for child in children:
                    if child.get('is_filler'):
                        continue  # Skip FILLER fields

                    child_java_name = child.get('java_name', self.cobol_to_java_name(child['cobol_name']))
                    child_java_type = child.get('java_type', 'String')
                    child_value = child.get('value')

                    # Upgrade 1D array to 2D if both occurs and inherited_occurs exist
                    if '[]' in child_java_type:
                        has_occurs = child.get('occurs')
                        has_inherited = child.get('inherited_occurs')
                        if has_occurs and has_inherited:
                            base = child_java_type.replace('[]', '')
                            child_java_type = f'{base}[][]'

                    # Generate initialization based on type
                    init = self._get_field_initializer(child_java_type, child_value, child)

                    self.emit(f'public {child_java_type} {child_java_name}{init};',
                              child.get('line_num'), child['cobol_name'])
            else:
                self.emit("// No child fields")

            self.indent_level -= 1
            self.emit("}")
            self.emit_blank()

    def _get_field_initializer(self, java_type: str, cobol_value, field: dict) -> str:
        """Get the initializer string for a field based on its type and COBOL VALUE."""
        if cobol_value is not None:
            # Use the COBOL VALUE clause for initialization
            if java_type == 'String':
                return f' = "{cobol_value}"'
            elif java_type in ('int', 'short', 'long'):
                if java_type == 'short':
                    return f' = (short){cobol_value}'
                return f' = {cobol_value}'
            elif java_type == 'BigDecimal':
                if cobol_value == 0 or str(cobol_value).upper() in ('ZERO', 'ZEROS', 'ZEROES'):
                    return ' = BigDecimal.ZERO'
                return f' = BigDecimal.valueOf({cobol_value})'
            return ''

        # No VALUE clause - use type defaults
        if java_type == 'String':
            return ' = ""'
        elif java_type in ('int', 'short', 'long'):
            return ' = 0'
        elif java_type == 'BigDecimal':
            return ' = BigDecimal.ZERO'
        elif '[]' in java_type:
            has_occurs = field.get('occurs')
            has_inherited = field.get('inherited_occurs')
            base = java_type.replace('[]', '').replace('[]', '')  # Remove all []
            if has_occurs and has_inherited:
                return f' = new {base}[{has_inherited}][{has_occurs}]'
            size = has_occurs or has_inherited or 10
            return f' = new {base}[{size}]'
        return ''

    def generate_condition_accessors(self):
        """Generate boolean accessors for 88-level conditions."""
        self.emit("// === CONDITION ACCESSORS (88-level) ===")

        for cond in self.data_model.get('conditions', []):  # Generate ALL conditions
            accessor = cond.get('java_accessor', 'isCondition')
            parent = cond.get('parent_field') or cond.get('parent', '')
            parent_java = self.cobol_to_java_name(parent) if parent else 'parentField'
            values = cond.get('values', [])

            if values:
                check = ' || '.join(f'"{v}".equals({parent_java})' for v in values)
            else:
                check = 'false'

            self.emit(f'public boolean {accessor}() {{',
                      cond.get('line_num'), cond['cobol_name'])
            self.indent_level += 1
            self.emit(f'return {check};')
            self.indent_level -= 1
            self.emit('}')
            self.emit_blank()

    def generate_run_method(self):
        """Generate the main run method with USING parameters."""
        # Find the first paragraph to call - typically 000-MAIN-CONTROL or similar
        first_para_method = "mainControl_000"  # Default
        paragraphs = self.procedure_model.get('paragraphs', [])
        if paragraphs:
            first_para = paragraphs[0].get('name', '')
            if first_para:
                first_para_method = self.cobol_to_method_name(first_para)

        self.emit("// === ENTRY POINT ===")
        self.emit("/**")
        self.emit(" * Main entry point - corresponds to PROCEDURE DIVISION USING.")
        self.emit(" */")
        self.emit("public void run(String parmProfile, String parmSeq, String parmClient) {", 1667, "PROCEDURE DIVISION USING")
        self.indent_level += 1
        self.emit(f"{first_para_method}();")
        self.indent_level -= 1
        self.emit("}")
        self.emit_blank()

    def generate_statement(self, stmt: Dict):
        """Generate Java code for a single COBOL statement."""
        line_num = stmt.get('line_num')
        classification = stmt.get('classification', '')
        raw_text = stmt.get('raw_text', '').strip()
        semantic = stmt.get('semantic', {})

        # Truncate raw_text for comment
        cobol_ref = raw_text[:40] + '...' if len(raw_text) > 40 else raw_text

        if classification == 'PERFORM':
            target = semantic.get('target', 'unknown')
            thru = semantic.get('thru')
            method_name = self.cobol_to_method_name(target)

            if thru:
                self.emit(f'{method_name}();', line_num, f'PERFORM {target} THRU {thru}')
            else:
                self.emit(f'{method_name}();', line_num, f'PERFORM {target}')

        elif classification == 'MOVE':
            source = semantic.get('source') or 'unknown'
            targets = semantic.get('targets') or []

            # Preprocess targets: recombine split array subscripts
            # Parser bug splits "FIELD-NAME (I)" into ["FIELD-NAME", "(I)"]
            # Recombine to ["FIELD-NAME(I)"]
            processed_targets = []
            i = 0
            while i < len(targets):
                target = targets[i]
                # Check if next element is an orphan subscript
                if i + 1 < len(targets) and re.match(r'^\([^)]+\)$', targets[i + 1]):
                    # Combine field name with subscript
                    processed_targets.append(target + targets[i + 1])
                    i += 2
                else:
                    processed_targets.append(target)
                    i += 1
            targets = processed_targets

            # Parser bug: line continuation may join two field names with space instead of comma
            # Example: "DED-AMT-LVL2-WS DED-MAX-LVL2-WS" should be split into two targets
            # Split targets that contain space-separated COBOL field names
            split_targets = []
            for t in targets:
                # Check if target contains space-separated field names (but not subscripts)
                if ' ' in t and not re.search(r'\([^)]+\)', t):
                    # Split on spaces, but only if parts look like COBOL field names
                    parts = t.split()
                    if all(re.match(r'^[A-Z][A-Z0-9-]*$', p, re.IGNORECASE) for p in parts):
                        split_targets.extend(parts)
                    else:
                        split_targets.append(t)
                else:
                    split_targets.append(t)
            targets = split_targets

            # Handle source: could be string literal, numeric, COBOL literal, or field name
            source_upper = source.upper()
            source_type = None  # Track source type for type-safe assignment

            if source.startswith('"') or source.startswith("'"):
                source_java = source  # Keep string literal as-is
                source_type = 'STRING_LITERAL'
            elif source_upper in ('SPACES', 'SPACE'):
                source_java = '""'  # SPACES = empty string
                source_type = 'SPACES'
            elif source_upper in ('ZEROS', 'ZEROES', 'ZERO'):
                source_java = '0'  # ZEROS = 0
                source_type = 'ZEROS'
            elif source_upper in ('LOW-VALUES', 'LOW-VALUE'):
                source_java = 'LOW_VALUE'  # LOW-VALUES = null character constant
                source_type = 'LOW_VALUE'
            elif source_upper in ('HIGH-VALUES', 'HIGH-VALUE'):
                source_java = 'HIGH_VALUE'  # HIGH-VALUES = max character constant
                source_type = 'HIGH_VALUE'
            elif source.replace('.', '').replace('-', '').isdigit():
                # Numeric - strip leading zeros to avoid Java octal interpretation
                source_java = source.lstrip('0') or '0'
                source_type = 'NUMERIC'
            else:
                source_java = self.cobol_to_java_name(source)
                source_type = 'FIELD'

            for target in targets:
                # Skip FILLER fields (FILLER, *----, etc.)
                if target.upper() == 'FILLER' or target.startswith('*'):
                    self.emit(f'// MOVE to FILLER skipped', line_num, f'MOVE {source} TO {target}')
                    continue
                # Skip orphan subscripts like (I), (J) - parser bug splits array subscripts
                if re.match(r'^\([^)]+\)$', target):
                    continue
                target_java = self.cobol_to_java_name(target)
                cobol_ref = f'MOVE {source} TO {target}'
                # Use type-safe assignment for proper type conversion
                self.generate_type_safe_assignment(target_java, source_java, source_type, line_num, cobol_ref)

        elif classification == 'IF':
            condition = semantic.get('condition', 'true')
            java_cond = self.generate_condition_to_java(condition)
            self.emit(f'if ({java_cond}) {{', line_num, cobol_ref)
            self.indent_level += 1

        elif classification == 'ELSE':
            # ELSE handling is now primarily done in generate_paragraph_method
            # which passes has_matching_if based on indentation analysis.
            # This fallback supports both old and new calling conventions.
            has_matching_if = getattr(self, '_else_has_matching_if', None)
            if has_matching_if is None:
                # Fallback to old counter-based approach if not set
                has_matching_if = getattr(self, 'open_if_blocks', 0) > 0

            # Check if this is ELSE IF (condition on same line)
            raw_upper = raw_text.upper()
            is_else_if = ' IF ' in raw_upper or raw_upper.strip().startswith('ELSE IF')

            if is_else_if:
                # Extract the IF condition
                if_match = re.search(r'ELSE\s+IF\s+(.+)', raw_upper)
                if if_match:
                    condition = if_match.group(1).strip()
                    java_cond = self.generate_condition_to_java(condition)
                    if has_matching_if:
                        self.indent_level -= 1
                        self.emit(f'}} else if ({java_cond}) {{', line_num, cobol_ref)
                        self.indent_level += 1
                    else:
                        # No matching IF - emit as orphan comment
                        self.emit(f'// ORPHAN ELSE-IF: {cobol_ref}', line_num, 'ELSE IF')
                else:
                    # Failed to parse ELSE IF condition
                    if has_matching_if:
                        self.indent_level -= 1
                        self.emit('} else {', line_num, 'ELSE')
                        self.indent_level += 1
                    else:
                        self.emit('// ORPHAN ELSE (no matching IF)', line_num, 'ELSE')
            else:
                # Standalone ELSE (not ELSE IF)
                if has_matching_if:
                    self.indent_level -= 1
                    self.emit('} else {', line_num, 'ELSE')
                    self.indent_level += 1
                else:
                    # Orphaned ELSE - comment it out to avoid compilation error
                    self.emit('// ORPHAN ELSE (no matching IF)', line_num, 'ELSE')

        elif classification == 'END_IF':
            self.indent_level -= 1
            self.emit('}', line_num, 'END-IF')

        elif classification == 'GOTO':
            target = semantic.get('target', 'unknown')
            # Translate GO TO - emit as comment to avoid unreachable code errors
            # (COBOL GO TO is often inside conditional blocks with following code)
            if isinstance(target, str):
                target_upper = target.upper()
                if 'EXIT' in target_upper:
                    # GO TO xxx-EXIT -> comment (would cause unreachable code if return;)
                    self.emit(f'// GO TO {target} - early exit', line_num, f'GO TO {target}')
                else:
                    # GO TO another paragraph -> call method (control returns unlike COBOL)
                    method_name = self.cobol_to_method_name(target)
                    self.emit(f'{method_name}();', line_num, f'GO TO {target}')
            else:
                # GO TO with DEPENDING ON (array of targets) - comment for now
                self.emit(f'// GO TO DEPENDING - not translated', line_num, f'GO TO {target}')

        elif classification == 'CALL':
            program = semantic.get('program', 'UNKNOWN')
            self.emit(f'// CALL {program}', line_num, cobol_ref)
            self.emit(f'call{self.cobol_to_class_name(program)}();')

        elif classification == 'COMPUTE':
            self.translate_compute(raw_text, line_num, cobol_ref)

        elif classification == 'ADD':
            self.translate_add(raw_text, line_num, cobol_ref)

        elif classification == 'SUBTRACT':
            self.translate_subtract(raw_text, line_num, cobol_ref)

        elif classification == 'MULTIPLY':
            self.translate_multiply(raw_text, line_num, cobol_ref)

        elif classification == 'DIVIDE':
            self.translate_divide(raw_text, line_num, cobol_ref)

        elif classification == 'SET':
            self.translate_set(raw_text, line_num, cobol_ref)

        elif classification == 'INITIALIZE':
            self.translate_initialize(raw_text, line_num, cobol_ref)

        elif classification == 'STRING':
            self.translate_string(raw_text, line_num, cobol_ref)

        else:
            # Generic comment for unhandled statements
            if raw_text and not raw_text.startswith('*'):
                self.emit(f'// {cobol_ref}', line_num, classification)

    def get_cobol_indent(self, raw_text: str) -> int:
        """Extract the indentation level (leading spaces) from COBOL raw_text.

        This is critical for matching IF/ELSE blocks in COBOL, which uses
        indentation-based nesting rather than explicit END-IF in many cases.
        """
        if not raw_text:
            return 0
        # Count leading spaces (after the 6-char sequence number area)
        # COBOL columns: 1-6 = sequence, 7 = indicator, 8-72 = code, 73-80 = comment
        # Our raw_text typically starts at column 7
        match = re.match(r'^(\s*)', raw_text)
        if match:
            return len(match.group(1))
        return 0

    def generate_paragraph_method(self, paragraph: Dict):
        """Generate a Java method for a COBOL paragraph.

        Uses indentation-based IF/ELSE matching to handle COBOL's implicit
        block nesting. In COBOL, ELSE matches the closest IF at the same
        or lower indentation level, not necessarily the most recent IF.
        """
        name = paragraph.get('name', 'unknown')
        start_line = paragraph.get('start_line')
        statements = paragraph.get('statements', [])

        method_name = self.cobol_to_method_name(name)

        # Reset indent to class level (1) before starting method
        self.indent_level = 1
        self.emit(f'private void {method_name}() {{', start_line, name)
        self.indent_level = 2  # Inside method

        # Track open IF blocks with their indentation: [(cobol_indent, line_num, has_else), ...]
        # This allows us to match ELSE to the correct IF based on COBOL indentation
        if_stack = []

        for stmt in statements:
            classification = stmt.get('classification', '')
            raw_text = stmt.get('raw_text', '')
            line_num = stmt.get('line_num', 0)
            cobol_indent = self.get_cobol_indent(raw_text)

            if classification == 'IF':
                # Push this IF onto the stack with its indentation
                if_stack.append({'indent': cobol_indent, 'line': line_num, 'has_else': False})
                self.generate_statement(stmt)

            elif classification == 'ELSE':
                # Find the matching IF by indentation
                # ELSE matches the closest IF at same or lower indentation level
                matched_idx = -1
                for i in range(len(if_stack) - 1, -1, -1):
                    if if_stack[i]['indent'] <= cobol_indent and not if_stack[i]['has_else']:
                        matched_idx = i
                        break

                if matched_idx >= 0:
                    # Close any inner IFs that weren't matched (they don't have ELSE)
                    while len(if_stack) > matched_idx + 1:
                        # Pop and close the inner IF
                        if_stack.pop()
                        self.indent_level -= 1
                        self.emit('}  // auto-close inner IF')

                    # Check if this is an ELSE IF - if so, it's part of an if-else-if chain
                    raw_upper = raw_text.upper()
                    is_else_if = ' IF ' in raw_upper or raw_upper.strip().startswith('ELSE IF')

                    if is_else_if:
                        # ELSE IF continues the same block - don't mark has_else yet
                        # because subsequent ELSE IFs should also match this same IF
                        # Just generate the else-if code
                        self._else_has_matching_if = True
                        self.generate_statement(stmt)
                        self._else_has_matching_if = None
                    else:
                        # Plain ELSE - mark this IF as having an ELSE
                        # so no more ELSE/ELSE-IF can match it
                        if_stack[matched_idx]['has_else'] = True
                        self._else_has_matching_if = True
                        self.generate_statement(stmt)
                        self._else_has_matching_if = None
                else:
                    # No matching IF found - this is an orphan ELSE
                    # Tell generate_statement to comment it out
                    self._else_has_matching_if = False
                    self.generate_statement(stmt)
                    self._else_has_matching_if = None

            elif classification == 'END_IF':
                if if_stack:
                    if_stack.pop()
                    self.generate_statement(stmt)
                else:
                    # Orphan END-IF - skip to avoid extra }
                    pass

            else:
                self.generate_statement(stmt)

                # Check if this statement ends with a period (COBOL sentence terminator)
                # A period terminates all open IF blocks in COBOL
                if raw_text.rstrip().endswith('.'):
                    # Close all remaining IFs on the stack
                    while if_stack:
                        if_stack.pop()
                        self.indent_level -= 1
                        self.emit('}  // period ends IF scope')

        # Close any remaining unclosed blocks (shouldn't happen if periods handled correctly)
        while if_stack:
            if_stack.pop()
            self.indent_level -= 1
            self.emit('}  // auto-close unclosed IF')

        # Backward compatibility: set open_if_blocks for other code that checks it
        self.open_if_blocks = len(if_stack)

        # Close method
        self.indent_level = 1
        self.emit('}')
        self.emit_blank()

    def generate_methods(self):
        """Generate all methods from procedure model."""
        self.emit("// === PARAGRAPH METHODS ===")
        self.emit_blank()

        paragraphs = self.procedure_model.get('paragraphs', [])

        for para in paragraphs:
            self.generate_paragraph_method(para)

    def generate_stub_methods(self):
        """Generate stub methods for external CALLs.

        DYNAMIC GENERATION - reads call_targets from procedure model.
        These are external programs that need separate COBOL→Java conversion.
        """
        call_targets = self.procedure_model.get('control_flow', {}).get('call_targets', {})

        # Handle both dict and list formats
        if isinstance(call_targets, dict):
            programs = list(call_targets.keys())
        elif isinstance(call_targets, list):
            programs = call_targets
        else:
            programs = []

        if not programs:
            return

        self.emit("// === EXTERNAL PROGRAM STUBS ===")
        self.emit("// These are external programs that need separate conversion")
        self.emit_blank()

        for program in sorted(programs):
            if isinstance(program, str) and program:
                method_name = f'call{self.cobol_to_class_name(program)}'
                self.emit(f'protected void {method_name}() {{')
                self.indent_level += 1
                self.emit(f'// External program: {program}')
                self.indent_level -= 1
                self.emit('}')
                self.emit_blank()

    def generate_missing_paragraph_stubs(self):
        """Generate stub methods for paragraphs not in the procedure model.

        DYNAMIC GENERATION - not hardcoded!
        Looks at PERFORM and GO TO targets from:
        1. control_flow summary (main file)
        2. ALL statements in ALL paragraphs (including merged COPYBOOK paragraphs)
        """
        # Build set of existing paragraph method names to avoid duplicates
        existing_paragraphs = set()
        for para in self.procedure_model.get('paragraphs', []):
            cobol_name = para.get('name')
            if cobol_name:
                method_name = self.cobol_to_method_name(cobol_name)
                existing_paragraphs.add(method_name)

        # Collect all referenced paragraphs from control flow
        control_flow = self.procedure_model.get('control_flow', {})

        # Get PERFORM targets from control_flow
        perform_targets = control_flow.get('perform_targets', {})

        # Get GO TO targets from control_flow
        goto_targets = control_flow.get('goto_targets', {})

        # ALSO scan ALL statements in ALL paragraphs for PERFORM targets
        # This catches targets inside merged COPYBOOK paragraphs
        import re
        for para in self.procedure_model.get('paragraphs', []):
            for stmt in para.get('statements', []):
                raw_text = stmt.get('raw_text', '')
                # Look for PERFORM xxx patterns
                perform_match = re.search(r'PERFORM\s+([A-Z0-9][-A-Z0-9]+)', raw_text, re.IGNORECASE)
                if perform_match:
                    target = perform_match.group(1).strip()
                    if target and target not in perform_targets:
                        perform_targets[target] = 1

        # Combine all referenced paragraph names
        referenced_paragraphs = set()
        for target in perform_targets.keys():
            if target:
                referenced_paragraphs.add(target)
        for target in goto_targets.keys():
            if isinstance(target, str) and target:
                referenced_paragraphs.add(target)

        # Find missing paragraphs (referenced but not parsed)
        missing_paragraphs = []
        for cobol_name in sorted(referenced_paragraphs):
            method_name = self.cobol_to_method_name(cobol_name)
            if method_name not in existing_paragraphs:
                # Skip EXIT paragraphs - they're just return points
                if 'EXIT' not in cobol_name.upper():
                    missing_paragraphs.append((method_name, cobol_name))

        # Only emit section if there are missing paragraphs
        if missing_paragraphs:
            self.emit("// === REFERENCED PARAGRAPH STUBS ===")
            self.emit("// These paragraphs are called but not yet parsed from COBOL")
            self.emit_blank()

            for method_name, cobol_name in missing_paragraphs:
                self.emit(f'protected void {method_name}() {{')
                self.indent_level += 1
                self.emit(f'// Referenced: {cobol_name}')
                self.indent_level -= 1
                self.emit('}')
                self.emit_blank()

    def detect_copybook_variables(self):
        """Detect COPYBOOK variables and register them in field_types.

        Must be called BEFORE generate_methods() so type info is available.
        """
        import re
        declared_fields = set(self.field_types.keys())
        used_vars = set()

        for para in self.procedure_model.get('paragraphs', []):
            for stmt in para.get('statements', []):
                raw_text = stmt.get('raw_text', '')
                matches = re.findall(r'\b([A-Z][A-Z0-9-]+)(?:\s*\([^)]+\))?', raw_text, re.IGNORECASE)
                for m in matches:
                    java_name = self.cobol_to_java_name(m)
                    base_name = re.sub(r'\[.*\]', '', java_name)
                    if base_name not in declared_fields:
                        used_vars.add((m, base_name))

        # Store detected vars for later emission
        # Be CONSERVATIVE - only detect obvious COPYBOOK patterns to avoid duplicates
        self._copybook_vars = []
        for cobol_name, java_name in used_vars:
            upper = cobol_name.upper()
            # File status flags: BEN-OK, BE1-OK, ER1-OK, PE2-OK (3-4 chars before -OK)
            if upper.endswith('-OK') and len(cobol_name) <= 8:
                java_type = 'String'
            # Year-to-date accumulators from COPYBOOK files (specific pattern)
            elif '-ACRD-YTD' in upper or '-SICK-ACRD' in upper:
                java_type = 'BigDecimal'
            # Entity name arrays (TAX-ENTITY-NAME pattern)
            elif upper == 'TAX-ENTITY-NAME':
                java_type = 'String[]'
            else:
                continue
            self._copybook_vars.append((cobol_name, java_name, java_type))
            # Register in field_types NOW so COMPUTE/MULTIPLY know the type
            self.field_types[java_name] = java_type

    def generate_copybook_variable_stubs(self):
        """Emit stub declarations for COPYBOOK variables."""
        if hasattr(self, '_copybook_vars') and self._copybook_vars:
            self.emit("// === COPYBOOK VARIABLE STUBS ===")
            self.emit("// These variables are from COPYBOOKs that aren't available")
            for cobol_name, java_name, java_type in sorted(set(self._copybook_vars)):
                if '[]' in java_type:
                    self.emit(f'private {java_type} {java_name} = new String[10];  // COPYBOOK: {cobol_name}')
                elif java_type == 'BigDecimal':
                    self.emit(f'private {java_type} {java_name} = BigDecimal.ZERO;  // COPYBOOK: {cobol_name}')
                else:
                    self.emit(f'private {java_type} {java_name} = "";  // COPYBOOK: {cobol_name}')
            self.emit_blank()

    def generate_class_footer(self):
        """Close the class."""
        self.indent_level -= 1
        self.emit("}")

    def generate(self) -> List[str]:
        """Generate complete Java class."""
        self.generate_imports()
        self.generate_class_header()
        self.generate_test_harness()  # Add main() for IntelliJ testing
        self.generate_constants()
        self.generate_external_field_stubs()  # Stubs for external file records
        # Detect COPYBOOK variables AFTER external stubs (which add to field_types)
        self.detect_copybook_variables()
        self.generate_copybook_variable_stubs()  # Stubs for COPYBOOK variables
        self.generate_fields()
        self.generate_groups_as_classes()
        self.generate_condition_accessors()
        self.generate_run_method()
        self.generate_methods()
        self.generate_stub_methods()
        self.generate_missing_paragraph_stubs()  # Stubs for unparsed paragraphs
        self.generate_class_footer()

        return self.output


def _cobol_name_to_java(cobol_name: str) -> str:
    """Convert COBOL-NAME to javaName."""
    if not cobol_name:
        return "unknown"
    # Remove leading numbers and convert to camelCase
    name = re.sub(r'^\d+-', '', cobol_name)
    parts = name.lower().split('-')
    if len(parts) == 1:
        return parts[0]
    return parts[0] + ''.join(p.title() for p in parts[1:])


def _pic_to_java_type(pic: str, comp: str = None) -> str:
    """Convert PIC clause to Java type."""
    if not pic:
        return 'String'  # Groups default to String

    pic_upper = pic.upper()

    # Check for COMP types
    if comp:
        comp_upper = comp.upper()
        if 'COMP-3' in comp_upper or 'PACKED' in comp_upper:
            return 'BigDecimal'
        if 'COMP' in comp_upper:
            # COMP/COMP-4/COMP-5 - size determines type
            digits = sum(1 for c in pic_upper if c == '9')
            if digits <= 4:
                return 'short'
            elif digits <= 9:
                return 'int'
            else:
                return 'long'

    # Alphanumeric
    if 'X' in pic_upper or 'A' in pic_upper:
        return 'String'

    # Numeric with decimal
    if 'V' in pic_upper or '.' in pic_upper:
        return 'BigDecimal'

    # Signed numeric
    if 'S' in pic_upper:
        return 'BigDecimal'

    # Plain numeric - count digits
    digits = sum(1 for c in pic_upper if c == '9')
    if digits <= 4:
        return 'int'
    elif digits <= 9:
        return 'int'
    else:
        return 'BigDecimal'


def load_copybook_types(reports_dir: Path) -> dict:
    """Load type information from comprehensive parse results (copybooks).

    Returns a dict mapping java_name -> java_type for all copybook fields.
    This enables automatic type correction without hardcoding.
    """
    comprehensive_path = reports_dir / "comprehensive_parse_results.json"
    if not comprehensive_path.exists():
        return {}

    with open(comprehensive_path) as f:
        comp_data = json.load(f)

    items = comp_data.get('unified_data_model', {}).get('items', [])
    copybook_types = {}

    for item in items:
        # Only process copybook items (not main program)
        source = item.get('source_file', '')
        if source == 'IFPR321.CBL':
            continue

        name = item.get('name', '')
        if not name or name.upper() == 'FILLER':
            continue

        pic = item.get('pic')
        raw_text = item.get('raw_text', '')
        occurs = item.get('occurs')

        # Detect COMP type from raw text
        comp = None
        if 'COMP-3' in raw_text.upper():
            comp = 'COMP-3'
        elif 'COMP' in raw_text.upper():
            comp = 'COMP'

        java_type = _pic_to_java_type(pic, comp)

        # Check for OCCURS (array)
        if occurs or 'OCCURS' in raw_text.upper():
            java_type = java_type + '[]'

        java_name = _cobol_name_to_java(name)
        copybook_types[java_name] = java_type

    return copybook_types


def load_models(reports_dir: Path, base_name: str = "ifpr321") -> tuple:
    """Load semantic models from reports directory.

    Uses the original data model (main program only) because the comprehensive
    model introduces too many complexity issues (FILLERs, REDEFINES duplicates).
    Copybook field types are auto-loaded via load_copybook_types().
    """
    # Load original data model (stable, tested approach)
    data_model_path = reports_dir / f"{base_name}_complete_data_model.json"
    with open(data_model_path) as f:
        data_model = json.load(f)

    # Load copybook types for auto-correction
    copybook_types = load_copybook_types(reports_dir)
    data_model['copybook_types'] = copybook_types

    print(f"  Loaded {len(data_model.get('fields', []))} fields from main program")
    print(f"  Loaded {len(copybook_types)} type hints from copybooks")

    procedure_model_path = reports_dir / f"{base_name}_procedure_model.json"
    with open(procedure_model_path) as f:
        procedure_model = json.load(f)

    return data_model, procedure_model


if __name__ == '__main__':
    print("=" * 60)
    print("Clean Java Generator")
    print("=" * 60)

    # Load models
    reports_dir = Path('reports')
    data_model, procedure_model = load_models(reports_dir)

    print(f"Data model: {len(data_model.get('fields', []))} fields, {len(data_model.get('groups', []))} groups")
    print(f"Procedure model: {len(procedure_model.get('paragraphs', []))} paragraphs")

    # Generate
    generator = CleanJavaGenerator(data_model, procedure_model)
    output = generator.generate()

    # Write output
    output_path = reports_dir / "IFPR321.java"
    with open(output_path, 'w') as f:
        f.write('\n'.join(output))

    print(f"\nGenerated: {output_path}")
    print(f"Lines: {len(output)}")

    # Show sample
    print("\n" + "=" * 60)
    print("SAMPLE OUTPUT (first 80 lines)")
    print("=" * 60)
    for line in output[:80]:
        print(line)
