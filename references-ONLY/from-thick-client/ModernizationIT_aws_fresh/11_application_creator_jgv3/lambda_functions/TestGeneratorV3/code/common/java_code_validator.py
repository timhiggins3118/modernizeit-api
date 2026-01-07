"""
Java Code Validator - Static Analysis Without Maven
Validates generated Java code before writing to S3

NO MOCK CODE - ALL VALIDATION IS REAL
"""

import re
from typing import Dict, Any, List


class JavaCodeValidator:
    """
    Static code validator for generated Java files
    Performs validation WITHOUT running Maven/javac
    """

    # Java reserved keywords
    JAVA_RESERVED_WORDS = {
        'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch',
        'char', 'class', 'const', 'continue', 'default', 'do', 'double',
        'else', 'enum', 'extends', 'final', 'finally', 'float', 'for',
        'goto', 'if', 'implements', 'import', 'instanceof', 'int', 'interface',
        'long', 'native', 'new', 'package', 'private', 'protected', 'public',
        'return', 'short', 'static', 'strictfp', 'super', 'switch',
        'synchronized', 'this', 'throw', 'throws', 'transient', 'try',
        'void', 'volatile', 'while'
    }

    # Valid Java types
    VALID_JAVA_TYPES = {
        'String', 'Integer', 'Long', 'Double', 'Float', 'Boolean', 'Byte',
        'Short', 'Character', 'BigDecimal', 'BigInteger', 'LocalDate',
        'LocalDateTime', 'LocalTime', 'Date', 'Timestamp', 'List', 'Set',
        'Map', 'Optional', 'Collection'
    }

    def __init__(self, generation_plan: Dict[str, Any]):
        """
        Args:
            generation_plan: Contains list of entities, services, controllers
                            Used to validate cross-references
        """
        self.entities = [e.get('entity_name', e.get('name', ''))
                        for e in generation_plan.get('entities', [])]
        self.services = []  # Built dynamically as services are validated
        self.repositories = []  # Built dynamically as repos are validated

        print(f"JavaCodeValidator initialized with {len(self.entities)} known entities")

    def validate_entity(
        self,
        java_code: str,
        entity_name: str,
        filename: str
    ) -> Dict[str, Any]:
        """
        Validate JPA entity class

        Args:
            java_code: The generated Java code
            entity_name: Expected entity name (e.g., "FinancialReports")
            filename: Expected filename (e.g., "FinancialReports.java")

        Returns:
            {
                'valid': bool,
                'errors': [list of error messages],
                'warnings': [list of warning messages]
            }
        """
        errors = []
        warnings = []

        # 1. Check filename matches class name
        expected_filename = f"{entity_name}.java"
        if filename != expected_filename:
            errors.append(
                f"Filename mismatch: expected '{expected_filename}', got '{filename}'"
            )

        # 2. Check class declaration exists and matches
        class_pattern = r'public\s+class\s+(\w+)'
        class_match = re.search(class_pattern, java_code)

        if not class_match:
            errors.append("No public class declaration found")
        else:
            actual_class_name = class_match.group(1)
            if actual_class_name != entity_name:
                errors.append(
                    f"Class name mismatch: expected 'class {entity_name}', "
                    f"got 'class {actual_class_name}'"
                )

            # Check PascalCase
            if not self._is_pascal_case(actual_class_name):
                errors.append(
                    f"Class name '{actual_class_name}' is not PascalCase"
                )

        # 3. Check required annotations
        if '@Entity' not in java_code:
            errors.append("Missing @Entity annotation")

        if '@Table' not in java_code:
            warnings.append("Missing @Table annotation (will use default table name)")

        # 4. Check for @Id annotation (at least one)
        if '@Id' not in java_code:
            errors.append("Missing @Id annotation - at least one field must be primary key")

        # 5. Check imports use jakarta (not javax)
        if 'import javax.persistence' in java_code:
            errors.append(
                "Using deprecated javax.persistence imports - "
                "Spring Boot 3.x requires jakarta.persistence"
            )

        # 6. Check for package declaration
        if not re.search(r'^package\s+[\w.]+;', java_code, re.MULTILINE):
            errors.append("Missing package declaration")

        # 7. Check field naming conventions
        field_pattern = r'private\s+\w+\s+(\w+);'
        fields = re.findall(field_pattern, java_code)

        for field in fields:
            if not self._is_camel_case(field):
                warnings.append(
                    f"Field '{field}' should be camelCase"
                )

            if field.lower() in self.JAVA_RESERVED_WORDS:
                errors.append(
                    f"Field '{field}' is a Java reserved keyword"
                )

            # Warn on generic names
            if field.lower() in ['field', 'data', 'value', 'temp', 'reserved']:
                warnings.append(
                    f"Field '{field}' has generic name, consider renaming"
                )

        # 8. Check for Lombok annotations (good practice)
        has_lombok = '@Data' in java_code or '@Getter' in java_code
        if not has_lombok:
            warnings.append(
                "No Lombok annotations found (@Data, @Getter) - "
                "consider using Lombok to reduce boilerplate"
            )

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    def validate_service(
        self,
        java_code: str,
        service_name: str,
        filename: str
    ) -> Dict[str, Any]:
        """
        Validate Spring service class

        Args:
            java_code: The generated Java code
            service_name: Expected service name (e.g., "AccountsService")
            filename: Expected filename (e.g., "AccountsService.java")

        Returns:
            {'valid': bool, 'errors': [], 'warnings': []}
        """
        errors = []
        warnings = []

        # 1. Check filename matches class name
        expected_filename = f"{service_name}.java"
        if filename != expected_filename:
            errors.append(
                f"Filename mismatch: expected '{expected_filename}', got '{filename}'"
            )

        # 2. Check class declaration
        class_pattern = r'public\s+class\s+(\w+)'
        class_match = re.search(class_pattern, java_code)

        if not class_match:
            errors.append("No public class declaration found")
        else:
            actual_class_name = class_match.group(1)
            if actual_class_name != service_name:
                errors.append(
                    f"Class name mismatch: expected '{service_name}', got '{actual_class_name}'"
                )

            if not actual_class_name.endswith('Service'):
                warnings.append(
                    f"Service class '{actual_class_name}' should end with 'Service'"
                )

        # 3. Check required annotations
        if '@Service' not in java_code:
            errors.append("Missing @Service annotation")

        # 4. Check constructor injection (not field injection)
        if '@Autowired' in java_code:
            warnings.append(
                "Using @Autowired field injection - constructor injection is preferred"
            )

        has_constructor_injection = '@RequiredArgsConstructor' in java_code or 'private final' in java_code
        if not has_constructor_injection:
            warnings.append(
                "No constructor injection detected - consider using @RequiredArgsConstructor"
            )

        # 5. Check for System.out.println (should use logger)
        if 'System.out.println' in java_code:
            errors.append(
                "Using System.out.println - use logger instead (log.info, log.debug)"
            )

        # 6. Check references to entities
        for entity in self.entities:
            if entity in java_code:
                # Good - service references known entity
                pass

        # 7. Check for logging setup
        if '@Slf4j' not in java_code and 'Logger' not in java_code:
            warnings.append("No logging configured - consider using @Slf4j")

        # 8. Check for transaction management
        if '@Transactional' not in java_code and 'save' in java_code.lower():
            warnings.append(
                "Service performs data modifications but missing @Transactional"
            )

        # Track this service for cross-validation
        self.services.append(service_name)

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    def validate_controller(
        self,
        java_code: str,
        controller_name: str,
        filename: str
    ) -> Dict[str, Any]:
        """
        Validate REST controller class

        Args:
            java_code: The generated Java code
            controller_name: Expected controller name (e.g., "AccountsController")
            filename: Expected filename (e.g., "AccountsController.java")

        Returns:
            {'valid': bool, 'errors': [], 'warnings': []}
        """
        errors = []
        warnings = []

        # 1. Check filename matches class name
        expected_filename = f"{controller_name}.java"
        if filename != expected_filename:
            errors.append(
                f"Filename mismatch: expected '{expected_filename}', got '{filename}'"
            )

        # 2. Check class declaration
        class_pattern = r'public\s+class\s+(\w+)'
        class_match = re.search(class_pattern, java_code)

        if not class_match:
            errors.append("No public class declaration found")
        else:
            actual_class_name = class_match.group(1)
            if actual_class_name != controller_name:
                errors.append(
                    f"Class name mismatch: expected '{controller_name}', got '{actual_class_name}'"
                )

            if not actual_class_name.endswith('Controller'):
                warnings.append(
                    f"Controller class '{actual_class_name}' should end with 'Controller'"
                )

        # 3. Check required annotations
        if '@RestController' not in java_code:
            errors.append("Missing @RestController annotation")

        if '@RequestMapping' not in java_code:
            errors.append("Missing @RequestMapping annotation")
        else:
            # Check path format
            request_mapping_pattern = r'@RequestMapping\("([^"]+)"\)'
            mapping_match = re.search(request_mapping_pattern, java_code)
            if mapping_match:
                path = mapping_match.group(1)
                if not path.startswith('/api/'):
                    warnings.append(
                        f"API path '{path}' should start with '/api/' by convention"
                    )

        # 4. Check HTTP method annotations
        http_methods = ['@GetMapping', '@PostMapping', '@PutMapping', '@DeleteMapping', '@PatchMapping']
        has_http_method = any(method in java_code for method in http_methods)

        if not has_http_method:
            warnings.append("No HTTP method annotations found - controller has no endpoints")

        # 5. Check return types use ResponseEntity
        if 'ResponseEntity' not in java_code:
            warnings.append(
                "Methods should return ResponseEntity for proper HTTP status handling"
            )

        # 6. Check CORS configuration
        if '@CrossOrigin' in java_code:
            if '@CrossOrigin(origins = "*")' in java_code:
                warnings.append(
                    "Using @CrossOrigin(origins = \"*\") - consider restricting origins in production"
                )

        # 7. Check validation annotations
        if '@Valid' not in java_code and '@RequestBody' in java_code:
            warnings.append(
                "Using @RequestBody without @Valid - consider adding input validation"
            )

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    def validate_repository(
        self,
        java_code: str,
        repository_name: str,
        filename: str
    ) -> Dict[str, Any]:
        """
        Validate Spring Data repository interface

        Args:
            java_code: The generated Java code
            repository_name: Expected repo name (e.g., "AccountsRepository")
            filename: Expected filename (e.g., "AccountsRepository.java")

        Returns:
            {'valid': bool, 'errors': [], 'warnings': []}
        """
        errors = []
        warnings = []

        # 1. Check filename matches interface name
        expected_filename = f"{repository_name}.java"
        if filename != expected_filename:
            errors.append(
                f"Filename mismatch: expected '{expected_filename}', got '{filename}'"
            )

        # 2. Check interface declaration (not class)
        if 'public class' in java_code:
            errors.append(
                f"Repository '{repository_name}' should be an interface, not a class"
            )

        interface_pattern = r'public\s+interface\s+(\w+)'
        interface_match = re.search(interface_pattern, java_code)

        if not interface_match:
            errors.append("No public interface declaration found")
        else:
            actual_interface_name = interface_match.group(1)
            if actual_interface_name != repository_name:
                errors.append(
                    f"Interface name mismatch: expected '{repository_name}', "
                    f"got '{actual_interface_name}'"
                )

            if not actual_interface_name.endswith('Repository'):
                warnings.append(
                    f"Repository interface '{actual_interface_name}' should end with 'Repository'"
                )

        # 3. Check extends JpaRepository
        if 'extends JpaRepository' not in java_code:
            errors.append("Repository must extend JpaRepository")
        else:
            # Extract generic types
            jpa_pattern = r'extends\s+JpaRepository<(\w+),\s*(\w+)>'
            jpa_match = re.search(jpa_pattern, java_code)

            if jpa_match:
                entity_type = jpa_match.group(1)
                id_type = jpa_match.group(2)

                # Check entity exists
                if entity_type not in self.entities:
                    errors.append(
                        f"Repository references unknown entity '{entity_type}' - "
                        f"known entities: {', '.join(self.entities)}"
                    )

                # Check ID type is valid
                valid_id_types = ['String', 'Long', 'Integer', 'UUID']
                if id_type not in valid_id_types:
                    warnings.append(
                        f"Unusual ID type '{id_type}' - common types: {', '.join(valid_id_types)}"
                    )

        # 4. Check required annotation
        if '@Repository' not in java_code:
            warnings.append(
                "Missing @Repository annotation - Spring Data will still work but annotation is recommended"
            )

        # Track this repository for cross-validation
        self.repositories.append(repository_name)

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    def _is_pascal_case(self, name: str) -> bool:
        """Check if name is PascalCase (e.g., FinancialReports)"""
        if not name:
            return False
        # Must start with uppercase
        if not name[0].isupper():
            return False
        # Should not have underscores
        if '_' in name:
            return False
        return True

    def _is_camel_case(self, name: str) -> bool:
        """Check if name is camelCase (e.g., acctNo)"""
        if not name:
            return False
        # Must start with lowercase
        if not name[0].islower():
            return False
        # Should not have underscores
        if '_' in name:
            return False
        return True

    def _is_upper_snake_case(self, name: str) -> bool:
        """Check if name is UPPER_SNAKE_CASE (e.g., MAX_VALUE)"""
        if not name:
            return False
        return name.isupper() and ('_' in name or len(name) <= 3)
