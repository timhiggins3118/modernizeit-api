"""
COBOL PIC Clause to SQL Type Mapper

Maps COBOL PIC clauses to SQL data types with full precision/scale/length.
"""

import re
from typing import Dict, Any, Optional, Tuple


class TypeMapper:
    """
    Maps COBOL PIC clauses to SQL data types with precision.

    Examples:
        X(50) -> VARCHAR(50)
        9(7)V99 -> DECIMAL(9, 2)
        S9(5) -> INTEGER
        9(18) COMP-3 -> DECIMAL(18, 0)
    """

    def map_pic_to_sql(self, pic_clause: str, usage: Optional[str] = None) -> Dict[str, Any]:
        """
        Map COBOL PIC clause to SQL type with full details.

        Args:
            pic_clause: COBOL PIC clause (e.g., "X(50)", "9(7)V99", "S9(5)")
            usage: Optional USAGE clause (e.g., "COMP", "COMP-3", "BINARY")

        Returns:
            Dict with sql_type, length, precision, scale, java_type
        """
        if not pic_clause or pic_clause == 'N/A':
            return {
                'sql_type': 'VARCHAR',
                'java_type': 'String',
                'length': 255
            }

        pic_upper = pic_clause.upper().strip('.')

        # Handle COMP/BINARY types
        if usage:
            usage_upper = usage.upper()
            if 'COMP-3' in usage_upper:
                # Packed decimal
                precision, scale = self._parse_numeric_pic(pic_upper)
                return {
                    'sql_type': 'DECIMAL',
                    'java_type': 'BigDecimal',
                    'precision': precision,
                    'scale': scale,
                    'storage': 'packed_decimal'
                }
            elif 'COMP' in usage_upper or 'BINARY' in usage_upper:
                # Binary integer
                digits = self._count_numeric_digits(pic_upper)
                return {
                    'sql_type': 'BIGINT' if digits > 9 else 'INTEGER',
                    'java_type': 'long' if digits > 9 else 'int',
                    'storage': 'binary'
                }

        # Check for alphanumeric (X)
        if 'X' in pic_upper:
            length = self._parse_alphanumeric_length(pic_upper)
            return {
                'sql_type': f'VARCHAR({length})',
                'java_type': 'String',
                'length': length
            }

        # Check for alphabetic (A)
        if pic_upper.startswith('A') and '9' not in pic_upper:
            length = self._parse_alphanumeric_length(pic_upper)
            return {
                'sql_type': f'VARCHAR({length})',
                'java_type': 'String',
                'length': length
            }

        # Check for numeric with decimal (V or .)
        if 'V' in pic_upper or '.' in pic_upper:
            precision, scale = self._parse_numeric_pic(pic_upper)
            return {
                'sql_type': f'DECIMAL({precision}, {scale})',
                'java_type': 'BigDecimal',
                'precision': precision,
                'scale': scale
            }

        # Check for edited numeric ($, Z, *, ,)
        if any(c in pic_upper for c in ['$', 'Z', '*', ',']):
            # Edited fields - treat as VARCHAR for storage
            length = self._count_edit_positions(pic_upper)
            return {
                'sql_type': f'VARCHAR({length})',
                'java_type': 'String',
                'length': length,
                'is_edited': True
            }

        # Pure numeric (9)
        if '9' in pic_upper or 'S9' in pic_upper:
            digits = self._count_numeric_digits(pic_upper)
            if digits > 18:
                return {
                    'sql_type': f'DECIMAL({digits}, 0)',
                    'java_type': 'BigDecimal',
                    'precision': digits,
                    'scale': 0
                }
            elif digits > 9:
                return {
                    'sql_type': 'BIGINT',
                    'java_type': 'long',
                    'precision': digits
                }
            else:
                return {
                    'sql_type': 'INTEGER',
                    'java_type': 'int',
                    'precision': digits
                }

        # Default fallback
        return {
            'sql_type': 'VARCHAR(255)',
            'java_type': 'String',
            'length': 255
        }

    def _parse_alphanumeric_length(self, pic: str) -> int:
        """Parse length from alphanumeric PIC clause."""
        # Handle X(50) format
        match = re.search(r'X\((\d+)\)', pic)
        if match:
            return int(match.group(1))

        # Handle A(50) format
        match = re.search(r'A\((\d+)\)', pic)
        if match:
            return int(match.group(1))

        # Handle XXXX format (count X's)
        x_count = pic.count('X')
        if x_count > 0:
            return x_count

        # Handle AAAA format
        a_count = pic.count('A')
        if a_count > 0:
            return a_count

        return 1

    def _parse_numeric_pic(self, pic: str) -> Tuple[int, int]:
        """
        Parse precision and scale from numeric PIC clause.

        Returns:
            Tuple of (precision, scale)
        """
        # Remove sign indicator
        pic = pic.replace('S', '')

        # Count integer digits (before V or .)
        # Count decimal digits (after V or .)

        integer_digits = 0
        decimal_digits = 0

        # Split by V or .
        if 'V' in pic:
            parts = pic.split('V')
        elif '.' in pic:
            parts = pic.split('.')
        else:
            parts = [pic]

        # Count integer part
        integer_digits = self._count_digits_in_part(parts[0])

        # Count decimal part if exists
        if len(parts) > 1:
            decimal_digits = self._count_digits_in_part(parts[1])

        precision = integer_digits + decimal_digits
        scale = decimal_digits

        return max(precision, 1), scale

    def _count_digits_in_part(self, part: str) -> int:
        """Count digit positions in a PIC part."""
        count = 0

        # Handle 9(n) format
        matches = re.findall(r'9\((\d+)\)', part)
        for match in matches:
            count += int(match)

        # Handle 99999 format (consecutive 9s not in parens)
        # Remove the (n) parts first
        remaining = re.sub(r'9\(\d+\)', '', part)
        count += remaining.count('9')

        return count

    def _count_numeric_digits(self, pic: str) -> int:
        """Count total numeric digit positions."""
        precision, scale = self._parse_numeric_pic(pic)
        return precision

    def _count_edit_positions(self, pic: str) -> int:
        """Count positions in an edited PIC clause."""
        count = 0
        i = 0

        while i < len(pic):
            char = pic[i]

            # Handle (n) repetition
            if i + 1 < len(pic) and pic[i + 1] == '(':
                end = pic.find(')', i + 2)
                if end > 0:
                    count += int(pic[i + 2:end])
                    i = end + 1
                    continue

            # Count individual positions
            if char in '9XAZB0/*+-$.,':
                count += 1

            i += 1

        return max(count, 1)

    def get_simple_type(self, pic_clause: str, usage: Optional[str] = None) -> str:
        """Get simple SQL type name without precision details."""
        result = self.map_pic_to_sql(pic_clause, usage)
        sql_type = result.get('sql_type', 'VARCHAR')

        # Strip precision for simple type
        if '(' in sql_type:
            return sql_type.split('(')[0]
        return sql_type


# Global instance for convenience
type_mapper = TypeMapper()


def map_cobol_to_sql(pic_clause: str, usage: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function to map PIC clause to SQL type."""
    return type_mapper.map_pic_to_sql(pic_clause, usage)
