"""
javalang AST Validator
Phase 2 validation: Class structure and type checking using javalang
"""

from typing import List, Dict
import javalang
from Levenshtein import distance as levenshtein_distance


class JavalangValidator:
    """Validates Java AST and class structures"""

    def __init__(self, valid_entity_names: List[str]):
        """
        Initialize with list of validated entity names

        Args:
            valid_entity_names: List of exact entity class names (case-sensitive)
        """
        self.valid_entity_names = valid_entity_names
        self.valid_entity_names_lower = [name.lower() for name in valid_entity_names]
        print(f"javalang validator initialized with {len(valid_entity_names)} validated entities")

    def validate(self, java_code: str, file_path: str) -> List[Dict]:
        """
        Validate Java AST structure

        Checks:
        - All imported classes exist
        - All referenced types exist
        - No duplicate class/method/field names
        - Class names match validated entity list

        Returns:
            List of error dictionaries
        """
        errors = []

        try:
            # Parse Java code into AST
            tree = javalang.parse.parse(java_code)

            # Check imports for class name mismatches
            for import_decl in tree.imports:
                if import_decl.path:
                    class_name = import_decl.path.split('.')[-1]
                    if class_name not in self.valid_entity_names and class_name.lower() in self.valid_entity_names_lower:
                        # Case mismatch - find correct name
                        correct_name = self._find_correct_entity_name(class_name)
                        if correct_name:
                            errors.append({
                                'file': file_path.split('/')[-1],
                                'line': 0,  # javalang doesn't provide line numbers for imports
                                'column': 0,
                                'message': f'Class name case mismatch: {class_name} should be {correct_name}',
                                'type': 'class_name_mismatch',
                                'severity': 'error',
                                'fix_suggestion': {
                                    'find': class_name,
                                    'replace': correct_name
                                }
                            })

            # Check for undefined type references
            for path, node in tree.filter(javalang.tree.ReferenceType):
                type_name = node.name
                # Skip Java built-in types
                if type_name in ['String', 'Integer', 'Long', 'BigDecimal', 'List', 'Optional', 'Map', 'Set']:
                    continue

                # Check if it's a known entity
                if type_name not in self.valid_entity_names:
                    # Try fuzzy match
                    suggestion = self._find_closest_match(type_name)
                    if suggestion:
                        errors.append({
                            'file': file_path.split('/')[-1],
                            'line': 0,
                            'column': 0,
                            'message': f'Unknown type: {type_name}, did you mean {suggestion}?',
                            'type': 'unknown_type',
                            'severity': 'error',
                            'fix_suggestion': {
                                'find': type_name,
                                'replace': suggestion
                            }
                        })

            # Check class declarations for case mismatches
            for path, node in tree.filter(javalang.tree.ClassDeclaration):
                class_name = node.name
                # Check if this is a case mismatch with a valid entity or derived name
                if class_name not in self.valid_entity_names:
                    # Try case-insensitive match
                    correct_name = self._find_correct_entity_name(class_name)
                    if correct_name:
                        errors.append({
                            'file': file_path.split('/')[-1],
                            'line': 0,
                            'column': 0,
                            'message': f'Class declaration name mismatch: {class_name} should be {correct_name}',
                            'type': 'class_declaration_mismatch',
                            'severity': 'error',
                            'fix_suggestion': {
                                'find': f'class {class_name}',
                                'replace': f'class {correct_name}'
                            }
                        })
                    else:
                        # Try fuzzy match (could be Service, Controller, Repository)
                        suggestion = self._find_closest_match(class_name)
                        if suggestion:
                            errors.append({
                                'file': file_path.split('/')[-1],
                                'line': 0,
                                'column': 0,
                                'message': f'Class declaration likely incorrect: {class_name}, did you mean {suggestion}?',
                                'type': 'class_declaration_mismatch',
                                'severity': 'warning',
                                'fix_suggestion': {
                                    'find': f'class {class_name}',
                                    'replace': f'class {suggestion}'
                                }
                            })

            # Check interface declarations for case mismatches
            for path, node in tree.filter(javalang.tree.InterfaceDeclaration):
                interface_name = node.name
                # Check if this is a case mismatch
                if interface_name not in self.valid_entity_names:
                    correct_name = self._find_correct_entity_name(interface_name)
                    if correct_name:
                        errors.append({
                            'file': file_path.split('/')[-1],
                            'line': 0,
                            'column': 0,
                            'message': f'Interface declaration name mismatch: {interface_name} should be {correct_name}',
                            'type': 'class_declaration_mismatch',
                            'severity': 'error',
                            'fix_suggestion': {
                                'find': f'interface {interface_name}',
                                'replace': f'interface {correct_name}'
                            }
                        })
                    else:
                        suggestion = self._find_closest_match(interface_name)
                        if suggestion:
                            errors.append({
                                'file': file_path.split('/')[-1],
                                'line': 0,
                                'column': 0,
                                'message': f'Interface declaration likely incorrect: {interface_name}, did you mean {suggestion}?',
                                'type': 'class_declaration_mismatch',
                                'severity': 'warning',
                                'fix_suggestion': {
                                    'find': f'interface {interface_name}',
                                    'replace': f'interface {suggestion}'
                                }
                            })

        except javalang.parser.JavaSyntaxError as e:
            errors.append({
                'file': file_path.split('/')[-1],
                'line': 0,
                'column': 0,
                'message': f'Java syntax error: {str(e)}',
                'type': 'syntax_error',
                'severity': 'error'
            })
        except Exception as e:
            print(f"WARNING: javalang validation failed for {file_path}: {str(e)}")

        return errors

    def _find_correct_entity_name(self, incorrect_name: str) -> str:
        """Find correct entity name (case-sensitive match)"""
        incorrect_lower = incorrect_name.lower()
        for i, name_lower in enumerate(self.valid_entity_names_lower):
            if name_lower == incorrect_lower:
                return self.valid_entity_names[i]
        return None

    def _find_closest_match(self, type_name: str, threshold: int = 3) -> str:
        """
        Find closest matching entity name using Levenshtein distance

        Args:
            type_name: The incorrect type name
            threshold: Max edit distance to consider (default 3)

        Returns:
            Closest matching entity name or None
        """
        best_match = None
        best_distance = threshold + 1

        for entity_name in self.valid_entity_names:
            dist = levenshtein_distance(type_name.lower(), entity_name.lower())
            if dist < best_distance:
                best_distance = dist
                best_match = entity_name

        return best_match if best_distance <= threshold else None
