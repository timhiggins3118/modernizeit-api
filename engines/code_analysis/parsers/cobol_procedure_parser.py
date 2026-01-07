"""
COBOL Procedure Division Semantic Model Parser

Parses PROCEDURE DIVISION from line inventory and builds semantic procedure model.
Works with ANY COBOL file - not hardcoded to specific files.

Input: Line inventory JSON (from cobol_parse_export.py)
Output: Procedure model JSON with:
  - Paragraphs (name, lines, statements)
  - Sections (if any)
  - Control flow (PERFORM targets, GOTO targets)
  - Statement semantics (what each line does)

Date: December 2025
"""

import json
import re
from pathlib import Path
from typing import Optional, List
from datetime import datetime


class StatementParser:
    """Parse COBOL statements and extract semantic information."""

    @staticmethod
    def parse_perform(text: str) -> dict:
        """Parse PERFORM statement."""
        result = {
            'type': 'PERFORM',
            'target': None,
            'thru': None,
            'times': None,
            'until': None,
            'varying': None
        }

        upper = text.upper().strip()

        # PERFORM para THRU para2
        thru_match = re.search(r'PERFORM\s+([A-Z0-9][-A-Z0-9]*)\s+(?:THRU|THROUGH)\s+([A-Z0-9][-A-Z0-9]*)', upper)
        if thru_match:
            result['target'] = thru_match.group(1)
            result['thru'] = thru_match.group(2)
            return result

        # PERFORM para TIMES
        times_match = re.search(r'PERFORM\s+([A-Z0-9][-A-Z0-9]*)\s+(\d+)\s+TIMES', upper)
        if times_match:
            result['target'] = times_match.group(1)
            result['times'] = int(times_match.group(2))
            return result

        # PERFORM para UNTIL condition
        until_match = re.search(r'PERFORM\s+([A-Z0-9][-A-Z0-9]*)\s+UNTIL\s+(.+)', upper)
        if until_match:
            result['target'] = until_match.group(1)
            result['until'] = until_match.group(2).strip()
            return result

        # PERFORM para VARYING var FROM x BY y UNTIL condition
        varying_match = re.search(r'PERFORM\s+([A-Z0-9][-A-Z0-9]*)\s+VARYING', upper)
        if varying_match:
            result['target'] = varying_match.group(1)
            result['varying'] = True  # Simplified - could extract details
            return result

        # Simple PERFORM para
        simple_match = re.search(r'PERFORM\s+([A-Z0-9][-A-Z0-9]*)', upper)
        if simple_match:
            result['target'] = simple_match.group(1)
            return result

        return result

    @staticmethod
    def parse_move(text: str) -> dict:
        """Parse MOVE statement.

        Handles:
        - MOVE source TO target1, target2
        - MOVE "string literal with spaces" TO target
        - MOVE source TO target1 target2
        """
        result = {
            'type': 'MOVE',
            'source': None,
            'targets': []
        }

        upper = text.upper().strip()

        # Check for quoted string source first (need to preserve the string)
        # Pattern: MOVE "..." TO ... or MOVE '...' TO ...
        quoted_match = re.search(r'MOVE\s+(["\'][^"\']*["\'])\s+TO\s+(.+)', text, re.IGNORECASE)
        if quoted_match:
            result['source'] = quoted_match.group(1).strip()
            targets_str = quoted_match.group(2).strip().rstrip('.')
        else:
            # Non-quoted source: MOVE source TO target
            # Find the LAST occurrence of " TO " to handle sources like "NOTHING FOUND"
            # that might contain TO as part of the literal
            match = re.search(r'MOVE\s+(.+)\s+TO\s+(\S.*)$', upper)
            if match:
                source = match.group(1).strip()
                targets_str = match.group(2).strip().rstrip('.')

                # Check if source contains an unbalanced quote (indicates TO is in string)
                if source.count('"') == 1:
                    # The TO was inside a string, re-parse to find the right TO
                    # Look for pattern: MOVE "...TO..." TO target
                    full_match = re.search(r'MOVE\s+"([^"]+)"\s+TO\s+(\S+)', upper)
                    if full_match:
                        result['source'] = f'"{full_match.group(1)}"'
                        targets_str = full_match.group(2).strip().rstrip('.')
                    else:
                        result['source'] = source
                else:
                    result['source'] = source
            else:
                return result

        # Parse targets
        if ',' in targets_str:
            result['targets'] = [t.strip() for t in targets_str.split(',') if t.strip()]
        else:
            result['targets'] = [t.strip() for t in re.split(r'\s+', targets_str) if t.strip()]

        return result

    @staticmethod
    def parse_if(text: str) -> dict:
        """Parse IF statement.

        COBOL IF can have inline actions:
          IF X > Y MOVE A TO B.
          IF X = "A" GO TO PARA-EXIT.

        We need to extract just the condition, stopping at action verbs.
        """
        result = {
            'type': 'IF',
            'condition': None,
            'negated': False
        }

        upper = text.upper().strip()

        # IF NOT condition
        if ' IF NOT ' in upper or upper.startswith('IF NOT '):
            result['negated'] = True
            upper = upper.replace(' NOT ', ' ', 1)

        # Extract everything after IF
        match = re.search(r'IF\s+(.+)', upper)
        if match:
            condition_text = match.group(1).strip()

            # Stop at inline action verbs (MOVE, GO, PERFORM, ADD, etc.)
            # These indicate the start of the THEN clause on the same line
            action_verbs = [
                r'\s+MOVE\s+', r'\s+GO\s+TO\s+', r'\s+PERFORM\s+',
                r'\s+ADD\s+', r'\s+SUBTRACT\s+', r'\s+MULTIPLY\s+',
                r'\s+DIVIDE\s+', r'\s+COMPUTE\s+', r'\s+CALL\s+',
                r'\s+READ\s+', r'\s+WRITE\s+', r'\s+SET\s+',
                r'\s+INITIALIZE\s+', r'\s+STRING\s+', r'\s+INSPECT\s+',
                r'\s+DISPLAY\s+', r'\s+CONTINUE\s*\.', r'\s+NEXT\s+SENTENCE'
            ]

            for verb_pattern in action_verbs:
                verb_match = re.search(verb_pattern, condition_text)
                if verb_match:
                    # Truncate at the verb
                    condition_text = condition_text[:verb_match.start()].strip()
                    break

            # Remove trailing period if present
            condition_text = condition_text.rstrip('.')

            result['condition'] = condition_text

        return result

    @staticmethod
    def parse_call(text: str) -> dict:
        """Parse CALL statement."""
        result = {
            'type': 'CALL',
            'program': None,
            'using': []
        }

        # CALL "program" USING param1 param2 ...
        prog_match = re.search(r'CALL\s+["\']([^"\']+)["\']', text, re.IGNORECASE)
        if prog_match:
            result['program'] = prog_match.group(1)

        using_match = re.search(r'USING\s+(.+)', text, re.IGNORECASE)
        if using_match:
            params = using_match.group(1).strip().rstrip('.')
            # Split by comma or space
            result['using'] = [p.strip() for p in re.split(r'[,\s]+', params) if p.strip()]

        return result

    @staticmethod
    def parse_goto(text: str) -> dict:
        """Parse GO TO statement."""
        result = {
            'type': 'GOTO',
            'target': None,
            'depending': None
        }

        upper = text.upper().strip()

        # GO TO para DEPENDING ON var
        depending_match = re.search(r'GO\s*TO\s+(.+?)\s+DEPENDING\s+ON\s+([A-Z0-9][-A-Z0-9]*)', upper)
        if depending_match:
            targets = depending_match.group(1).strip()
            result['target'] = [t.strip() for t in re.split(r'\s+', targets)]
            result['depending'] = depending_match.group(2)
            return result

        # Simple GO TO para
        simple_match = re.search(r'GO\s*TO\s+([A-Z0-9][-A-Z0-9]*)', upper)
        if simple_match:
            result['target'] = simple_match.group(1)

        return result

    @staticmethod
    def parse_compute(text: str) -> dict:
        """Parse COMPUTE statement."""
        result = {
            'type': 'COMPUTE',
            'target': None,
            'expression': None
        }

        # COMPUTE target = expression
        match = re.search(r'COMPUTE\s+([A-Z0-9][-A-Z0-9()]*)\s*=\s*(.+)', text, re.IGNORECASE)
        if match:
            result['target'] = match.group(1).strip()
            result['expression'] = match.group(2).strip().rstrip('.')

        return result

    @staticmethod
    def parse_arithmetic(text: str, verb: str) -> dict:
        """Parse ADD, SUBTRACT, MULTIPLY, DIVIDE statements."""
        result = {
            'type': verb.upper(),
            'operands': [],
            'target': None,
            'giving': None
        }

        upper = text.upper().strip()

        # ADD/SUBTRACT x TO y GIVING z
        giving_match = re.search(rf'{verb}\s+(.+?)\s+(?:TO|FROM|BY|INTO)\s+(.+?)\s+GIVING\s+([A-Z0-9][-A-Z0-9]*)', upper)
        if giving_match:
            result['operands'] = [giving_match.group(1).strip(), giving_match.group(2).strip()]
            result['giving'] = giving_match.group(3)
            return result

        # ADD x TO y / SUBTRACT x FROM y
        simple_match = re.search(rf'{verb}\s+(.+?)\s+(?:TO|FROM|BY|INTO)\s+([A-Z0-9][-A-Z0-9]*)', upper)
        if simple_match:
            result['operands'] = [simple_match.group(1).strip()]
            result['target'] = simple_match.group(2)

        return result

    @staticmethod
    def parse_read(text: str) -> dict:
        """Parse READ statement."""
        result = {
            'type': 'READ',
            'file': None,
            'into': None,
            'at_end': False,
            'invalid_key': False,
            'next': False
        }

        upper = text.upper().strip()

        # READ file [NEXT] [INTO var] [AT END ...] [INVALID KEY ...]
        file_match = re.search(r'READ\s+([A-Z0-9][-A-Z0-9]*)', upper)
        if file_match:
            result['file'] = file_match.group(1)

        if ' NEXT ' in upper or upper.endswith(' NEXT'):
            result['next'] = True

        into_match = re.search(r'INTO\s+([A-Z0-9][-A-Z0-9]*)', upper)
        if into_match:
            result['into'] = into_match.group(1)

        if 'AT END' in upper:
            result['at_end'] = True
        if 'INVALID KEY' in upper:
            result['invalid_key'] = True

        return result

    @staticmethod
    def parse_write(text: str) -> dict:
        """Parse WRITE statement."""
        result = {
            'type': 'WRITE',
            'record': None,
            'from_var': None
        }

        upper = text.upper().strip()

        # WRITE record FROM var
        match = re.search(r'WRITE\s+([A-Z0-9][-A-Z0-9]*)', upper)
        if match:
            result['record'] = match.group(1)

        from_match = re.search(r'FROM\s+([A-Z0-9][-A-Z0-9]*)', upper)
        if from_match:
            result['from_var'] = from_match.group(1)

        return result

    @staticmethod
    def parse_open(text: str) -> dict:
        """Parse OPEN statement."""
        result = {
            'type': 'OPEN',
            'mode': None,
            'files': []
        }

        upper = text.upper().strip()

        # OPEN INPUT file1 file2 / OPEN OUTPUT file / OPEN I-O file
        if 'OPEN INPUT' in upper:
            result['mode'] = 'INPUT'
        elif 'OPEN OUTPUT' in upper:
            result['mode'] = 'OUTPUT'
        elif 'OPEN I-O' in upper or 'OPEN I/O' in upper:
            result['mode'] = 'I-O'
        elif 'OPEN EXTEND' in upper:
            result['mode'] = 'EXTEND'

        # Extract file names (simplified)
        files_match = re.search(r'OPEN\s+(?:INPUT|OUTPUT|I-O|I/O|EXTEND)\s+(.+)', upper)
        if files_match:
            files_str = files_match.group(1).strip().rstrip('.')
            result['files'] = [f.strip() for f in re.split(r'\s+', files_str) if f.strip() and f.upper() not in ('INPUT', 'OUTPUT', 'I-O')]

        return result

    @staticmethod
    def parse_close(text: str) -> dict:
        """Parse CLOSE statement."""
        result = {
            'type': 'CLOSE',
            'files': []
        }

        upper = text.upper().strip()

        match = re.search(r'CLOSE\s+(.+)', upper)
        if match:
            files_str = match.group(1).strip().rstrip('.')
            result['files'] = [f.strip() for f in re.split(r'\s+', files_str) if f.strip()]

        return result


class ProcedureDivisionParser:
    """Parse PROCEDURE DIVISION and build semantic model."""

    def __init__(self, line_inventory: dict):
        """Initialize parser with line inventory."""
        self.lines = line_inventory.get('lines', [])
        self.source_file = line_inventory.get('source_file', 'unknown')
        self.procedure_model = {
            'source_file': self.source_file,
            'generated': datetime.now().isoformat(),
            'sections': [],
            'paragraphs': [],
            'control_flow': {
                'perform_targets': {},
                'goto_targets': {},
                'call_targets': {}
            },
            'summary': {}
        }

    def find_procedure_division_bounds(self) -> tuple:
        """Find start and end line numbers of PROCEDURE DIVISION."""
        start_line = None
        end_line = None

        for line in self.lines:
            text = line['raw_text'].upper()
            line_num = line['line_num']

            if 'PROCEDURE DIVISION' in text and start_line is None:
                start_line = line_num

        if start_line:
            end_line = self.lines[-1]['line_num']

        return (start_line, end_line)

    def _cobol_to_java_name(self, cobol_name: str) -> str:
        """Convert COBOL name to Java identifier."""
        if not cobol_name:
            return 'unknown'

        name = cobol_name.strip().rstrip('.')

        # Handle names starting with numbers
        match = re.match(r'^(\d+[-\d]*)-(.+)$', name)
        if match:
            number_part = match.group(1).replace('-', '_')
            text_part = match.group(2)
            parts = text_part.lower().split('-')
            camel = parts[0] + ''.join(p.capitalize() for p in parts[1:])
            return f"{camel}_{number_part}"

        if name[0].isdigit():
            return f"para_{name.replace('-', '_').lower()}"

        parts = name.lower().split('-')
        return parts[0] + ''.join(p.capitalize() for p in parts[1:])

    def parse_statement(self, line: dict, continuation_text: str = '') -> dict:
        """Parse a statement line and extract semantic info.

        Args:
            line: The line dict from line inventory
            continuation_text: Text from continuation lines to append
        """
        classification = line.get('classification', 'CODE')
        raw_text = line['raw_text']
        content = raw_text[6:72].strip() if len(raw_text) > 6 else raw_text.strip()

        # Append any continuation text - handle COBOL literal continuation
        if continuation_text:
            # Check if content ends inside an unclosed quote
            quote_count = content.count('"') + content.count("'")
            inside_unclosed_quote = (quote_count % 2) == 1

            if inside_unclosed_quote and continuation_text and continuation_text[0] in '"\'':
                # COBOL literal continuation: remove the quote marker, join without space
                content = content + continuation_text[1:]
            else:
                content = content + ' ' + continuation_text

        # Store the FULL text (including continuation) in raw_text for Java generator
        # This ensures multi-line COBOL statements are passed as complete statements
        full_raw_text = content if continuation_text else raw_text.rstrip()

        statement = {
            'line_num': line['line_num'],
            'classification': classification,
            'raw_text': full_raw_text,
            'semantic': None
        }

        # Parse based on classification
        if classification == 'PERFORM':
            statement['semantic'] = StatementParser.parse_perform(content)
        elif classification == 'MOVE':
            statement['semantic'] = StatementParser.parse_move(content)
        elif classification == 'IF':
            statement['semantic'] = StatementParser.parse_if(content)
        elif classification == 'CALL':
            statement['semantic'] = StatementParser.parse_call(content)
        elif classification == 'GOTO':
            statement['semantic'] = StatementParser.parse_goto(content)
        elif classification == 'COMPUTE':
            statement['semantic'] = StatementParser.parse_compute(content)
        elif classification in ('ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE'):
            statement['semantic'] = StatementParser.parse_arithmetic(content, classification)
        elif classification == 'READ':
            statement['semantic'] = StatementParser.parse_read(content)
        elif classification == 'WRITE':
            statement['semantic'] = StatementParser.parse_write(content)
        elif classification == 'OPEN':
            statement['semantic'] = StatementParser.parse_open(content)
        elif classification == 'CLOSE':
            statement['semantic'] = StatementParser.parse_close(content)
        elif classification in ('ELSE', 'END_IF', 'END_PERFORM', 'END_EVALUATE'):
            statement['semantic'] = {'type': classification}
        elif classification == 'EXIT':
            if 'GOBACK' in content.upper():
                statement['semantic'] = {'type': 'GOBACK'}
            elif 'STOP RUN' in content.upper():
                statement['semantic'] = {'type': 'STOP_RUN'}
            else:
                statement['semantic'] = {'type': 'EXIT'}
        else:
            statement['semantic'] = {'type': classification}

        return statement

    def _is_statement_start(self, classification: str) -> bool:
        """Check if classification indicates a new statement."""
        return classification in (
            'PERFORM', 'MOVE', 'IF', 'ELSE', 'END_IF', 'CALL', 'GOTO',
            'COMPUTE', 'ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE',
            'READ', 'WRITE', 'OPEN', 'CLOSE', 'EXIT', 'INITIALIZE',
            'STRING', 'INSPECT', 'SET', 'EVALUATE', 'WHEN', 'END_EVALUATE',
            'PARAGRAPH', 'SECTION', 'CONTINUE'
        )

    def _line_ends_with_period(self, raw_text: str) -> bool:
        """Check if COBOL line ends with a period (statement terminator)."""
        # Get content area (columns 7-72)
        content = raw_text[6:72].strip() if len(raw_text) > 6 else raw_text.strip()
        return content.endswith('.')

    def _collect_continuation_lines(self, proc_lines: list, start_idx: int) -> tuple:
        """Collect continuation lines for a multi-line statement.

        Returns:
            Tuple of (continuation_text, end_index)
        """
        continuation_parts = []
        end_idx = start_idx

        for i in range(start_idx + 1, len(proc_lines)):
            line = proc_lines[i]
            classification = line.get('classification', 'CODE')
            raw_text = line['raw_text']

            # Skip comment lines (column 7 = *)
            if len(raw_text) > 6 and raw_text[6] == '*':
                continue

            # Extract code area - handle continuation indicator in column 7
            # Column 7 (index 6) = indicator area (-, *, D, etc.)
            # Column 8+ (index 7+) = actual code
            if len(raw_text) > 6 and raw_text[6] == '-':
                # Continuation line - skip the indicator, extract from column 8
                content = raw_text[7:72].strip() if len(raw_text) > 7 else ''
            else:
                content = raw_text[6:72].strip() if len(raw_text) > 6 else raw_text.strip()

            # Stop if we hit a new statement or paragraph
            if self._is_statement_start(classification):
                break

            # Skip empty continuation lines
            if not content:
                continue

            # This is a continuation line (CODE or CONTINUATION)
            continuation_parts.append(content)
            end_idx = i

            # Stop if this line ends with period
            if self._line_ends_with_period(raw_text):
                break

        # Smart joining for COBOL literal continuation
        # When a literal spans lines:
        #   - First line does NOT close the quote
        #   - Continuation line STARTS with a quote (continuation marker)
        #   - The literal continues WITHOUT a space
        # We must detect this and join properly
        if not continuation_parts:
            continuation_text = ''
        else:
            result = continuation_parts[0]
            for part in continuation_parts[1:]:
                # Count quotes in result so far (excluding escaped quotes)
                quote_count = result.count('"') + result.count("'")
                inside_unclosed_quote = (quote_count % 2) == 1

                if inside_unclosed_quote and part and part[0] in '"\'':
                    # COBOL continuation: remove the continuation quote marker, join without space
                    result += part[1:]
                else:
                    # Normal join with space
                    result += ' ' + part
            continuation_text = result
        return continuation_text, end_idx

    def build_model(self) -> dict:
        """Build complete semantic procedure model."""
        start, end = self.find_procedure_division_bounds()

        if not start:
            return self.procedure_model

        # Filter to PROCEDURE DIVISION lines
        proc_lines = [l for l in self.lines if start <= l['line_num'] <= end]

        current_paragraph = None
        paragraphs = []
        i = 0

        while i < len(proc_lines):
            line = proc_lines[i]
            classification = line.get('classification', 'CODE')
            raw_text = line['raw_text']

            # Check for paragraph header
            # Also check CODE lines - tree-sitter sometimes misclassifies paragraph headers
            is_paragraph_header = classification == 'PARAGRAPH'

            # Fallback: check if CODE line looks like a paragraph header
            # Pattern: starts at column 8, name followed by period, nothing else
            if not is_paragraph_header and classification == 'CODE':
                content = raw_text[7:72].strip() if len(raw_text) > 7 else raw_text.strip()
                # Paragraph header: NAME. or NAME. EXIT.
                if re.match(r'^[A-Z0-9][-A-Z0-9]*\.\s*(EXIT\.)?\s*$', content, re.IGNORECASE):
                    is_paragraph_header = True

            if is_paragraph_header:
                # Save previous paragraph
                if current_paragraph:
                    paragraphs.append(current_paragraph)

                # Start new paragraph
                content = raw_text[7:72].strip() if len(raw_text) > 7 else raw_text.strip()
                para_name = content.rstrip('.').strip()

                # Handle "para. EXIT." on same line
                if ' EXIT' in para_name.upper():
                    para_name = para_name.split()[0].rstrip('.')

                current_paragraph = {
                    'name': para_name,
                    'java_name': self._cobol_to_java_name(para_name),
                    'start_line': line['line_num'],
                    'end_line': None,
                    'statements': []
                }
                i += 1
            elif current_paragraph:
                # Check if this statement continues on following lines
                continuation_text = ''
                if self._is_statement_start(classification) and not self._line_ends_with_period(raw_text):
                    # Statement doesn't end - collect continuation lines
                    continuation_text, end_idx = self._collect_continuation_lines(proc_lines, i)
                    # Skip the continuation lines we just processed
                    skip_to = end_idx
                else:
                    skip_to = i

                # Parse the statement with any continuation text
                statement = self.parse_statement(line, continuation_text)
                current_paragraph['statements'].append(statement)

                # Track control flow
                if statement['semantic']:
                    sem = statement['semantic']
                    sem_type = sem.get('type', '')

                    if sem_type == 'PERFORM' and sem.get('target'):
                        target = sem['target']
                        if target not in self.procedure_model['control_flow']['perform_targets']:
                            self.procedure_model['control_flow']['perform_targets'][target] = []
                        self.procedure_model['control_flow']['perform_targets'][target].append({
                            'from_paragraph': current_paragraph['name'],
                            'line': line['line_num'],
                            'thru': sem.get('thru')
                        })

                    elif sem_type == 'GOTO' and sem.get('target'):
                        target = sem['target']
                        if isinstance(target, str):
                            if target not in self.procedure_model['control_flow']['goto_targets']:
                                self.procedure_model['control_flow']['goto_targets'][target] = []
                            self.procedure_model['control_flow']['goto_targets'][target].append({
                                'from_paragraph': current_paragraph['name'],
                                'line': line['line_num']
                            })

                    elif sem_type == 'CALL' and sem.get('program'):
                        prog = sem['program']
                        if prog not in self.procedure_model['control_flow']['call_targets']:
                            self.procedure_model['control_flow']['call_targets'][prog] = []
                        self.procedure_model['control_flow']['call_targets'][prog].append({
                            'from_paragraph': current_paragraph['name'],
                            'line': line['line_num'],
                            'using': sem.get('using', [])
                        })

                # Skip to after continuation lines (or just increment by 1)
                i = skip_to + 1
            else:
                i += 1

        # Save last paragraph
        if current_paragraph:
            paragraphs.append(current_paragraph)

        # Set paragraph end lines
        for i, para in enumerate(paragraphs):
            if i + 1 < len(paragraphs):
                para['end_line'] = paragraphs[i + 1]['start_line'] - 1
            else:
                para['end_line'] = end

        self.procedure_model['paragraphs'] = paragraphs

        # Build summary
        total_statements = sum(len(p['statements']) for p in paragraphs)
        self.procedure_model['summary'] = {
            'procedure_division_start': start,
            'procedure_division_end': end,
            'total_lines': end - start + 1 if start and end else 0,
            'paragraph_count': len(paragraphs),
            'total_statements': total_statements,
            'perform_targets': len(self.procedure_model['control_flow']['perform_targets']),
            'goto_targets': len(self.procedure_model['control_flow']['goto_targets']),
            'call_targets': len(self.procedure_model['control_flow']['call_targets'])
        }

        return self.procedure_model


def parse_procedure_division(line_inventory_path: Path, output_path: Path) -> dict:
    """Parse PROCEDURE DIVISION and output semantic model."""
    with open(line_inventory_path) as f:
        inventory = json.load(f)

    parser = ProcedureDivisionParser(inventory)
    model = parser.build_model()

    with open(output_path, 'w') as f:
        json.dump(model, f, indent=2, ensure_ascii=False)

    return {
        'output_path': str(output_path),
        'summary': model['summary']
    }


if __name__ == '__main__':
    import sys

    inventory_path = Path("reports/ifpr321_line_inventory.json")
    output_path = Path("reports/ifpr321_procedure_model.json")

    if len(sys.argv) >= 3:
        inventory_path = Path(sys.argv[1])
        output_path = Path(sys.argv[2])

    if not inventory_path.exists():
        print(f"ERROR: {inventory_path} not found")
        sys.exit(1)

    print("=" * 60)
    print("COBOL Procedure Division Parser")
    print("=" * 60)
    print(f"\nInput:  {inventory_path}")
    print(f"Output: {output_path}")

    result = parse_procedure_division(inventory_path, output_path)

    print(f"\n=== PROCEDURE MODEL SUMMARY ===")
    for key, value in result['summary'].items():
        print(f"  {key}: {value}")

    print(f"\nOutput written to: {output_path}")
    print("=" * 60)
