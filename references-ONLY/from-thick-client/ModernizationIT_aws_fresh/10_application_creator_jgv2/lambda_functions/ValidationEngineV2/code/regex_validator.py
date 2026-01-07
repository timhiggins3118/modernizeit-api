"""
Regex Pattern Validator
Phase 3 validation: Pattern-based validation for common issues
"""

from typing import List, Dict
import re


class RegexValidator:
    """Validates Java code using regex patterns for common anti-patterns"""

    def __init__(self, valid_entity_names: List[str]):
        """
        Initialize with validated entity names

        Args:
            valid_entity_names: List of exact entity class names
        """
        self.valid_entity_names = valid_entity_names

        # Define validation patterns
        self.patterns = [
            {
                'name': 'record_immutability_violation',
                'pattern': r'\b(\w+)\.(\w+)\s*=',
                'message': 'Potential Record immutability violation: assignment to field',
                'severity': 'warning',
                'check_func': self._check_record_assignment
            },
            {
                'name': 'javax_persistence',
                'pattern': r'import\s+javax\.persistence',
                'message': 'Using javax.persistence instead of jakarta.persistence (Spring Boot 3+)',
                'severity': 'error',
                'fix_suggestion': lambda m: m.group(0).replace('javax.persistence', 'jakarta.persistence')
            },
            {
                'name': 'varchar_identity',
                'pattern': r'@Id.*@GeneratedValue.*strategy\s*=\s*GenerationType\.IDENTITY.*private\s+String',
                'message': 'String/VARCHAR cannot use IDENTITY generation strategy',
                'severity': 'error'
            },
            {
                'name': 'missing_semicolon',
                'pattern': r'^\s*(public|private|protected|return|throw)\s+[^;{]*$',
                'message': 'Possible missing semicolon',
                'severity': 'warning'
            }
        ]

        print(f"Regex validator initialized with {len(self.patterns)} patterns")

    def validate(self, java_code: str, file_path: str) -> List[Dict]:
        """
        Validate Java code using regex patterns

        Returns:
            List of error dictionaries
        """
        errors = []
        lines = java_code.split('\n')

        for pattern_def in self.patterns:
            pattern = pattern_def['pattern']
            name = pattern_def['name']

            # Search in full code
            for match in re.finditer(pattern, java_code, re.MULTILINE | re.DOTALL):
                # Find line number
                line_num = java_code[:match.start()].count('\n') + 1

                # Get context
                context = lines[line_num - 1].strip() if line_num <= len(lines) else ''

                error = {
                    'file': file_path.split('/')[-1],
                    'line': line_num,
                    'column': 0,
                    'message': pattern_def['message'],
                    'type': name,
                    'severity': pattern_def['severity'],
                    'context': context
                }

                # Add fix suggestion if available
                if 'fix_suggestion' in pattern_def:
                    if callable(pattern_def['fix_suggestion']):
                        error['fix_suggestion'] = pattern_def['fix_suggestion'](match)
                    else:
                        error['fix_suggestion'] = pattern_def['fix_suggestion']

                # Run custom check function if available
                if 'check_func' in pattern_def:
                    if pattern_def['check_func'](match, java_code):
                        errors.append(error)
                else:
                    errors.append(error)

        return errors

    def _check_record_assignment(self, match, java_code: str) -> bool:
        """
        Check if this is actually a Record field assignment

        Only flag if:
        1. Variable name matches a known entity (likely a Record)
        2. Not in a constructor or setter method
        """
        variable_name = match.group(1)

        # Check if variable name suggests it's an entity instance
        # (e.g., "clientsPerState", "accountData")
        for entity_name in self.valid_entity_names:
            if entity_name.lower() in variable_name.lower():
                # Check context - is this in a constructor or setter?
                # Get surrounding context
                start = max(0, match.start() - 200)
                end = min(len(java_code), match.end() + 200)
                context = java_code[start:end]

                # If we see constructor or setter keywords nearby, it's probably OK
                if 'new ' in context or 'set' in context.lower():
                    return False

                return True  # Flag this as suspicious

        return False  # Not related to entities, probably fine
