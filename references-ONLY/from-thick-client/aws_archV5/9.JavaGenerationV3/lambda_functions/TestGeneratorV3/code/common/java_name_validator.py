"""
Java Name Validator
Utility for normalizing and validating Java entity/class/field names
Reads rules from S3: shared/rules/java_naming_rules.json
"""

import json
import boto3
import re
from typing import Dict, Any, Optional


class JavaNameValidator:
    """Validates and normalizes Java names according to Java naming conventions"""

    def __init__(self, bucket_name: str = 'code-transformation-v2'):
        """
        Initialize validator

        Args:
            bucket_name: S3 bucket containing rules
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3')
        self.rules = None
        self._load_rules()

    def _load_rules(self):
        """Load naming rules from S3"""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key='shared/rules/java_naming_rules.json'
            )
            self.rules = json.loads(response['Body'].read().decode('utf-8'))
            print(f"✓ Loaded Java naming rules v{self.rules.get('version', '1.0.0')}")
        except Exception as e:
            print(f"ERROR loading Java naming rules: {str(e)}")
            # Fallback to basic rules
            self.rules = self._get_default_rules()

    def _get_default_rules(self) -> Dict[str, Any]:
        """Fallback default rules if S3 read fails"""
        return {
            "entity_naming": {
                "convention": "PascalCase",
                "rules": {
                    "remove_underscores": True,
                    "capitalize_first_letter": True,
                    "capitalize_after_underscore": True,
                    "remove_special_chars": True
                },
                "reserved_words": ["Class", "Object", "String", "Integer"]
            }
        }

    def normalize_entity_name(self, name: str) -> str:
        """
        Normalize entity/class name to Java PascalCase convention

        Args:
            name: Original entity name (e.g., "financial_reports", "accounts")

        Returns:
            Normalized name (e.g., "FinancialReports", "Accounts")
        """
        if not name:
            return "UnknownEntity"

        entity_rules = self.rules.get('entity_naming', {}).get('rules', {})

        # Remove file extensions
        name = name.replace('.cbl', '').replace('.cobol', '').replace('.CBL', '')

        # Remove or replace special characters
        if entity_rules.get('remove_special_chars', True):
            # Replace hyphens with underscores first
            name = name.replace('-', '_')

        # Convert to PascalCase
        if entity_rules.get('remove_underscores', True) and '_' in name:
            # Split on underscores and capitalize each part
            parts = name.split('_')
            name = ''.join([part.capitalize() for part in parts if part])
        else:
            # Just capitalize first letter
            if entity_rules.get('capitalize_first_letter', True):
                name = name[0].upper() + name[1:] if len(name) > 1 else name.upper()

        # Remove any remaining special characters
        name = re.sub(r'[^A-Za-z0-9]', '', name)

        # Ensure first character is uppercase
        if name and not name[0].isupper():
            name = name[0].upper() + name[1:] if len(name) > 1 else name.upper()

        # Check for reserved words
        reserved_words = self.rules.get('entity_naming', {}).get('reserved_words', [])
        if name in reserved_words:
            name = name + "Entity"

        return name if name else "UnknownEntity"

    def normalize_field_name(self, name: str) -> str:
        """
        Normalize field name to Java camelCase convention

        Args:
            name: Original field name (e.g., "ACCT_NO", "first-name")

        Returns:
            Normalized name (e.g., "acctNo", "firstName")
        """
        if not name:
            return "field"

        field_rules = self.rules.get('field_naming', {}).get('rules', {})

        # Replace hyphens with underscores
        if field_rules.get('remove_hyphens', True):
            name = name.replace('-', '_')

        # Convert to camelCase
        parts = name.split('_')
        if len(parts) > 1:
            # First part lowercase, rest capitalized
            name = parts[0].lower() + ''.join([p.capitalize() for p in parts[1:] if p])
        else:
            name = name.lower()

        # Remove special characters
        if field_rules.get('remove_special_chars', True):
            name = re.sub(r'[^a-zA-Z0-9]', '', name)

        return name if name else "field"

    def validate_entity_name(self, name: str) -> Dict[str, Any]:
        """
        Validate entity name and return validation result

        Args:
            name: Entity name to validate

        Returns:
            Dict with 'valid' (bool), 'errors' (list), 'normalized' (str)
        """
        errors = []
        entity_rules = self.rules.get('entity_naming', {}).get('rules', {})

        # Check if empty
        if not name:
            errors.append("Entity name cannot be empty")
            return {'valid': False, 'errors': errors, 'normalized': self.normalize_entity_name(name)}

        # Check for underscores (should not have them in final name)
        if entity_rules.get('remove_underscores', True) and '_' in name:
            errors.append(f"Entity name '{name}' contains underscores (use PascalCase)")

        # Check first character is uppercase
        if entity_rules.get('capitalize_first_letter', True) and not name[0].isupper():
            errors.append(f"Entity name '{name}' should start with uppercase letter")

        # Check for special characters
        if entity_rules.get('remove_special_chars', True):
            if re.search(r'[^A-Za-z0-9]', name):
                errors.append(f"Entity name '{name}' contains special characters")

        # Check reserved words
        reserved_words = self.rules.get('entity_naming', {}).get('reserved_words', [])
        if name in reserved_words:
            errors.append(f"Entity name '{name}' is a Java reserved word")

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'normalized': self.normalize_entity_name(name)
        }

    def get_entity_naming_convention(self) -> str:
        """Get the entity naming convention (e.g., 'PascalCase')"""
        return self.rules.get('entity_naming', {}).get('convention', 'PascalCase')

    def get_field_naming_convention(self) -> str:
        """Get the field naming convention (e.g., 'camelCase')"""
        return self.rules.get('field_naming', {}).get('convention', 'camelCase')
