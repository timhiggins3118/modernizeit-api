"""
Error Fixer
Auto-fixes common errors with retry logic
"""

from typing import List, Dict
import boto3
import os
import re


class ErrorFixer:
    """Automatically fixes common validation errors"""

    def __init__(self, valid_entity_names: List[str], enable_ai: bool = True):
        """
        Initialize error fixer

        Args:
            valid_entity_names: List of validated entity names
            enable_ai: Whether to use AI for complex fixes
        """
        self.valid_entity_names = valid_entity_names
        self.enable_ai = enable_ai
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.environ.get('BUCKET_NAME', 'code-transformation-v2')

        if enable_ai:
            self.bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')
            self.bedrock_model_id = 'anthropic.claude-3-5-sonnet-20240620-v1:0'

        print(f"Error fixer initialized (AI: {enable_ai})")

    def fix_errors(self, errors: List[Dict], error_phase: str, project_base_s3: str, max_attempts: int = 1) -> int:
        """
        Fix errors with retry logic

        Args:
            errors: List of error dictionaries
            error_phase: Phase name ('syntax', 'ast', 'pattern', 'compilation')
            project_base_s3: S3 base path for project
            max_attempts: Max attempts to fix (default 1 for fast phases, 3 for compilation)

        Returns:
            Number of errors successfully fixed
        """
        fixed_count = 0

        for attempt in range(1, max_attempts + 1):
            if not errors:
                break

            print(f"    Fix attempt {attempt}/{max_attempts}...")

            for error in errors:
                if self._fix_single_error(error, error_phase, project_base_s3):
                    fixed_count += 1

            # If this is last attempt, stop
            if attempt == max_attempts:
                break

            # Re-validate to see if fixes worked
            # (In real implementation, would re-run validation phase)

        return fixed_count

    def _fix_single_error(self, error: Dict, error_phase: str, project_base_s3: str) -> bool:
        """
        Fix a single error

        Returns:
            True if fixed successfully
        """
        error_type = error.get('type', '')
        file_path = error.get('file', '')

        # Build full S3 path
        s3_key = self._find_file_s3_key(project_base_s3, file_path)
        if not s3_key:
            print(f"      WARNING: Could not find S3 key for {file_path}")
            return False

        # Read current file content
        file_content = self._read_s3_file(s3_key)
        if not file_content:
            return False

        # Apply fix based on error type
        fixed_content = None

        if error_type == 'class_name_mismatch':
            fixed_content = self._fix_class_name_mismatch(file_content, error)

        elif error_type == 'unknown_type':
            fixed_content = self._fix_unknown_type(file_content, error)

        elif error_type == 'class_declaration_mismatch':
            fixed_content = self._fix_class_declaration_mismatch(file_content, error)

        elif error_type == 'javax_persistence':
            fixed_content = self._fix_javax_import(file_content)

        elif error_type == 'missing_symbol':
            fixed_content = self._fix_missing_symbol(file_content, error)

        elif error_type == 'immutability_violation':
            fixed_content = self._fix_immutability_violation(file_content, error)

        # Write fixed content back to S3
        if fixed_content and fixed_content != file_content:
            self._write_s3_file(s3_key, fixed_content)
            print(f"      ✓ Fixed {error_type} in {file_path}")
            return True

        return False

    def _fix_class_name_mismatch(self, content: str, error: Dict) -> str:
        """Fix class name case mismatch"""
        if 'fix_suggestion' in error:
            find = error['fix_suggestion']['find']
            replace = error['fix_suggestion']['replace']
            # Replace all occurrences
            return content.replace(find, replace)
        return content

    def _fix_unknown_type(self, content: str, error: Dict) -> str:
        """Fix unknown type reference"""
        if 'fix_suggestion' in error:
            find = error['fix_suggestion']['find']
            replace = error['fix_suggestion']['replace']
            # Replace all occurrences (class names)
            return content.replace(find, replace)
        return content

    def _fix_class_declaration_mismatch(self, content: str, error: Dict) -> str:
        """Fix class/interface declaration name mismatch"""
        if 'fix_suggestion' in error:
            find = error['fix_suggestion']['find']
            replace = error['fix_suggestion']['replace']

            # Extract class/interface names from find/replace
            # find: "class accounts" or "interface accountsRepository"
            # replace: "class Accounts" or "interface AccountsRepository"
            find_parts = find.split()
            replace_parts = replace.split()

            if len(find_parts) >= 2 and len(replace_parts) >= 2:
                keyword = find_parts[0]  # "class" or "interface"
                old_name = find_parts[1]
                new_name = replace_parts[1]

                print(f"      DEBUG: Fixing '{keyword} {old_name}' -> '{keyword} {new_name}'")

                # Use regex to match (public|private|protected)?\s*(class|interface)\s+OldName
                # This handles: "public class accounts", "class accounts", etc.
                pattern = rf'(public|private|protected)?\s*{re.escape(keyword)}\s+{re.escape(old_name)}\b'

                print(f"      DEBUG: Pattern = {pattern}")
                print(f"      DEBUG: Searching in {len(content)} chars")

                # Custom replacement function to handle optional access modifier
                def replace_func(match):
                    access_modifier = match.group(1)
                    matched_text = match.group(0)
                    print(f"      DEBUG: Matched '{matched_text}' with access_modifier='{access_modifier}'")
                    if access_modifier:
                        result = f'{access_modifier} {keyword} {new_name}'
                    else:
                        result = f'{keyword} {new_name}'
                    print(f"      DEBUG: Replacing with '{result}'")
                    return result

                result = re.sub(pattern, replace_func, content)

                if result != content:
                    print(f"      DEBUG: Content changed!")
                else:
                    print(f"      DEBUG: NO CHANGE - regex didn't match anything!")

                return result

            # Fallback to simple replace if parsing fails
            return content.replace(find, replace)
        return content

    def _fix_javax_import(self, content: str) -> str:
        """Fix javax.persistence imports to jakarta.persistence"""
        return content.replace('javax.persistence', 'jakarta.persistence')

    def _fix_missing_symbol(self, content: str, error: Dict) -> str:
        """
        Fix missing symbol errors

        Common causes:
        - Missing import
        - Typo in class name
        """
        # If we have a fix suggestion, use it
        if 'fix_suggestion' in error:
            find = error['fix_suggestion']['find']
            replace = error['fix_suggestion']['replace']
            return content.replace(find, replace)

        # Otherwise, try to detect if it's a missing import
        message = error.get('message', '')
        if 'symbol:   class' in message or 'symbol: class' in message:
            # Extract class name from error message
            class_match = re.search(r'class\s+(\w+)', message)
            if class_match:
                class_name = class_match.group(1)
                # Check if this is a known entity
                if class_name in self.valid_entity_names:
                    # Add import at top of file
                    return self._add_import(content, class_name)

        return content

    def _fix_immutability_violation(self, content: str, error: Dict) -> str:
        """
        Fix Record immutability violations

        This is complex - would ideally use AI
        For now, just flag and return unchanged
        """
        if self.enable_ai:
            # TODO: Use AI to rewrite code with builder pattern
            pass

        return content

    def _add_import(self, content: str, class_name: str) -> str:
        """Add import statement for a class"""
        # Assume base package is com.modernized.modernizedapplication
        # (In real implementation, would get from project metadata)
        import_statement = f"import com.modernized.modernizedapplication.entities.{class_name};\n"

        # Find where to insert (after package statement, before class declaration)
        lines = content.split('\n')
        insert_index = 0

        for i, line in enumerate(lines):
            if line.strip().startswith('package '):
                insert_index = i + 1
            elif line.strip().startswith('import '):
                insert_index = i + 1

        # Insert import
        lines.insert(insert_index, import_statement)
        return '\n'.join(lines)

    def _find_file_s3_key(self, project_base: str, file_name: str) -> str:
        """Find full S3 key for a file name"""
        try:
            # List all files in project
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=project_base)

            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        if key.endswith(file_name):
                            return key

        except Exception as e:
            print(f"      ERROR finding file {file_name}: {str(e)}")

        return None

    def _read_s3_file(self, s3_key: str) -> str:
        """Read file from S3"""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return response['Body'].read().decode('utf-8')
        except Exception as e:
            print(f"      ERROR reading {s3_key}: {str(e)}")
            return None

    def _write_s3_file(self, s3_key: str, content: str):
        """Write file to S3"""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=content,
                ContentType='text/plain'
            )
        except Exception as e:
            print(f"      ERROR writing {s3_key}: {str(e)}")
