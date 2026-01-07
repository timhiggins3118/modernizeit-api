"""
TreeSitter Syntax Validator
Phase 1 validation: Fast syntax checking using TreeSitter
"""

from typing import List, Dict
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava


class TreeSitterValidator:
    """Validates Java syntax using TreeSitter"""

    def __init__(self):
        """Initialize TreeSitter with Java grammar"""
        try:
            self.parser = Parser()
            JAVA_LANGUAGE = Language(tsjava.language(), "java")
            self.parser.set_language(JAVA_LANGUAGE)
            self.enabled = True
            print("TreeSitter validator initialized successfully")
        except Exception as e:
            print(f"WARNING: TreeSitter initialization failed: {str(e)}")
            self.enabled = False

    def validate(self, java_code: str, file_path: str) -> List[Dict]:
        """
        Validate Java syntax

        Args:
            java_code: Java source code as string
            file_path: S3 path for error reporting

        Returns:
            List of error dictionaries:
            [
                {
                    'file': 'Foo.java',
                    'line': 123,
                    'column': 45,
                    'message': 'Syntax error: unexpected token',
                    'type': 'syntax_error',
                    'severity': 'error'
                }
            ]
        """
        if not self.enabled:
            return []

        errors = []

        try:
            # Parse the code
            tree = self.parser.parse(bytes(java_code, "utf8"))
            root_node = tree.root_node

            # Check for syntax errors
            if root_node.has_error:
                errors.extend(self._find_error_nodes(root_node, java_code, file_path))

        except Exception as e:
            print(f"ERROR in TreeSitter validation for {file_path}: {str(e)}")
            errors.append({
                'file': file_path.split('/')[-1],
                'line': 0,
                'column': 0,
                'message': f'TreeSitter parsing failed: {str(e)}',
                'type': 'syntax_error',
                'severity': 'error'
            })

        return errors

    def _find_error_nodes(self, node, code: str, file_path: str) -> List[Dict]:
        """Recursively find all ERROR nodes in the syntax tree"""
        errors = []

        if node.type == 'ERROR' or node.is_missing:
            # Get line and column
            start_point = node.start_point
            line = start_point[0] + 1  # 0-indexed to 1-indexed
            column = start_point[1] + 1

            # Get code context
            lines = code.split('\n')
            context = lines[line - 1] if line <= len(lines) else ''

            errors.append({
                'file': file_path.split('/')[-1],
                'line': line,
                'column': column,
                'message': f'Syntax error near: {context[:50]}...',
                'type': 'syntax_error',
                'severity': 'error',
                'context': context.strip()
            })

        # Recursively check children
        for child in node.children:
            errors.extend(self._find_error_nodes(child, code, file_path))

        return errors
