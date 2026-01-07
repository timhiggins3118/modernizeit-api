"""
Type Mapping Templates Library
Provides type conversion templates for various language pairs

This module contains REFERENCE templates that document how to convert
data types from one programming language to another. These templates
are used during the ingest phase to create type mapping files that
downstream flows can use for code generation.

CRITICAL: The COBOL→Java template MUST match the AWS Lambda version exactly
for AWS compatibility.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any


# ============================================================================
# COBOL → Java Type Mapping
# ============================================================================
# This template is COPIED EXACTLY from AWS Lambda IngestUploadHandlerv2
# Source: ModernizationIT_aws_fresh/01_ingesting/.../ingest_upload_handler.py
# Lines: 31-81
# DO NOT MODIFY - Must remain identical to AWS Lambda for compatibility
# ============================================================================

COBOL_TO_JAVA_TYPE_MAPPING = {
    "version": "1.0",
    "source_language": "COBOL",
    "target_language": "Java",
    "mappings": {
        "numeric_with_decimal": {
            "description": "Numeric fields with decimal places",
            "detection_rules": [
                "contains 'V' (implied decimal point)",
                "contains '.' (explicit decimal point)",
                "contains '$' (currency symbol)",
                "contains 'Z' (zero suppression with decimal)",
                "contains ',' (grouping with decimal)"
            ],
            "sql_type": "DECIMAL",
            "java_type": "BigDecimal",
            "examples": ["9(7)V99", "S9(5)V9(2)", "$$,$$$,$$9.99", "ZZZ,ZZ9.99"]
        },
        "numeric_integer": {
            "description": "Whole number fields without decimals",
            "detection_rules": [
                "9(n) with no V or .",
                "S9(n) with no V or .",
                "COMP or COMP-3 or BINARY"
            ],
            "sql_type": "INTEGER",
            "java_type": "Integer",
            "examples": ["9(5)", "S9(9)", "9(4) COMP", "COMP-3"]
        },
        "alphanumeric": {
            "description": "Text fields",
            "detection_rules": ["X(n)", "A(n)"],
            "sql_type": "VARCHAR",
            "java_type": "String",
            "examples": ["X(50)", "A(20)"]
        },
        "date": {
            "description": "Date fields (8 digits YYYYMMDD)",
            "detection_rules": ["9(8)", "PIC 9(8)"],
            "sql_type": "DATE",
            "java_type": "LocalDate",
            "examples": ["9(8)"]
        }
    },
    "default_mapping": {
        "sql_type": "VARCHAR",
        "java_type": "String"
    }
}


# ============================================================================
# C++ → .NET Type Mapping
# ============================================================================
# Maps C++ primitive and STL types to .NET Framework types
# ============================================================================

CPP_TO_DOTNET_TYPE_MAPPING = {
    "version": "1.0",
    "source_language": "C++",
    "target_language": ".NET",
    "mappings": {
        "integer_types": {
            "description": "Integer types",
            "mappings": {
                "int": {
                    "dotnet_type": "int",
                    "dotnet_full_type": "System.Int32",
                    "sql_type": "INT"
                },
                "long": {
                    "dotnet_type": "long",
                    "dotnet_full_type": "System.Int64",
                    "sql_type": "BIGINT"
                },
                "short": {
                    "dotnet_type": "short",
                    "dotnet_full_type": "System.Int16",
                    "sql_type": "SMALLINT"
                },
                "unsigned int": {
                    "dotnet_type": "uint",
                    "dotnet_full_type": "System.UInt32",
                    "sql_type": "INT"
                },
                "unsigned long": {
                    "dotnet_type": "ulong",
                    "dotnet_full_type": "System.UInt64",
                    "sql_type": "BIGINT"
                }
            }
        },
        "floating_point_types": {
            "description": "Floating point types",
            "mappings": {
                "float": {
                    "dotnet_type": "float",
                    "dotnet_full_type": "System.Single",
                    "sql_type": "REAL"
                },
                "double": {
                    "dotnet_type": "double",
                    "dotnet_full_type": "System.Double",
                    "sql_type": "FLOAT"
                }
            }
        },
        "boolean_type": {
            "description": "Boolean type",
            "mappings": {
                "bool": {
                    "dotnet_type": "bool",
                    "dotnet_full_type": "System.Boolean",
                    "sql_type": "BIT"
                }
            }
        },
        "character_types": {
            "description": "Character types",
            "mappings": {
                "char": {
                    "dotnet_type": "char",
                    "dotnet_full_type": "System.Char",
                    "sql_type": "CHAR(1)"
                },
                "wchar_t": {
                    "dotnet_type": "char",
                    "dotnet_full_type": "System.Char",
                    "sql_type": "NCHAR(1)"
                }
            }
        },
        "string_types": {
            "description": "String types",
            "mappings": {
                "std::string": {
                    "dotnet_type": "string",
                    "dotnet_full_type": "System.String",
                    "sql_type": "VARCHAR"
                },
                "std::wstring": {
                    "dotnet_type": "string",
                    "dotnet_full_type": "System.String",
                    "sql_type": "NVARCHAR"
                }
            }
        },
        "container_types": {
            "description": "STL container types",
            "mappings": {
                "std::vector<T>": {
                    "dotnet_type": "List<T>",
                    "dotnet_full_type": "System.Collections.Generic.List<T>",
                    "sql_type": "Not directly mappable - use separate table"
                },
                "std::list<T>": {
                    "dotnet_type": "LinkedList<T>",
                    "dotnet_full_type": "System.Collections.Generic.LinkedList<T>",
                    "sql_type": "Not directly mappable - use separate table"
                },
                "std::map<K,V>": {
                    "dotnet_type": "Dictionary<K,V>",
                    "dotnet_full_type": "System.Collections.Generic.Dictionary<K,V>",
                    "sql_type": "Not directly mappable - use separate table"
                },
                "std::set<T>": {
                    "dotnet_type": "HashSet<T>",
                    "dotnet_full_type": "System.Collections.Generic.HashSet<T>",
                    "sql_type": "Not directly mappable - use separate table"
                }
            }
        },
        "smart_pointers": {
            "description": "Smart pointer types",
            "mappings": {
                "std::unique_ptr<T>": {
                    "dotnet_type": "T (reference type)",
                    "dotnet_full_type": "T",
                    "sql_type": "Depends on T"
                },
                "std::shared_ptr<T>": {
                    "dotnet_type": "T (reference type)",
                    "dotnet_full_type": "T",
                    "sql_type": "Depends on T"
                }
            }
        }
    },
    "default_mapping": {
        "dotnet_type": "object",
        "dotnet_full_type": "System.Object",
        "sql_type": "VARBINARY"
    }
}


# ============================================================================
# C++ → Java Type Mapping
# ============================================================================
# Maps C++ primitive and STL types to Java types
# ============================================================================

CPP_TO_JAVA_TYPE_MAPPING = {
    "version": "1.0",
    "source_language": "C++",
    "target_language": "Java",
    "mappings": {
        "integer_types": {
            "description": "Integer types",
            "mappings": {
                "int": {
                    "java_type": "int",
                    "java_wrapper": "Integer",
                    "sql_type": "INT"
                },
                "long": {
                    "java_type": "long",
                    "java_wrapper": "Long",
                    "sql_type": "BIGINT"
                },
                "short": {
                    "java_type": "short",
                    "java_wrapper": "Short",
                    "sql_type": "SMALLINT"
                },
                "unsigned int": {
                    "java_type": "long",
                    "java_wrapper": "Long",
                    "sql_type": "BIGINT",
                    "note": "Java has no unsigned types - use larger signed type"
                },
                "unsigned long": {
                    "java_type": "BigInteger",
                    "java_wrapper": "BigInteger",
                    "sql_type": "DECIMAL",
                    "note": "Java has no unsigned long - use BigInteger"
                }
            }
        },
        "floating_point_types": {
            "description": "Floating point types",
            "mappings": {
                "float": {
                    "java_type": "float",
                    "java_wrapper": "Float",
                    "sql_type": "REAL"
                },
                "double": {
                    "java_type": "double",
                    "java_wrapper": "Double",
                    "sql_type": "FLOAT"
                }
            }
        },
        "boolean_type": {
            "description": "Boolean type",
            "mappings": {
                "bool": {
                    "java_type": "boolean",
                    "java_wrapper": "Boolean",
                    "sql_type": "BOOLEAN"
                }
            }
        },
        "character_types": {
            "description": "Character types",
            "mappings": {
                "char": {
                    "java_type": "char",
                    "java_wrapper": "Character",
                    "sql_type": "CHAR(1)"
                },
                "wchar_t": {
                    "java_type": "char",
                    "java_wrapper": "Character",
                    "sql_type": "NCHAR(1)",
                    "note": "Java char is Unicode by default"
                }
            }
        },
        "string_types": {
            "description": "String types",
            "mappings": {
                "std::string": {
                    "java_type": "String",
                    "java_wrapper": "String",
                    "sql_type": "VARCHAR"
                },
                "std::wstring": {
                    "java_type": "String",
                    "java_wrapper": "String",
                    "sql_type": "NVARCHAR",
                    "note": "Java String is Unicode by default"
                }
            }
        },
        "container_types": {
            "description": "STL container types",
            "mappings": {
                "std::vector<T>": {
                    "java_type": "ArrayList<T>",
                    "java_wrapper": "ArrayList<T>",
                    "sql_type": "Not directly mappable - use separate table"
                },
                "std::list<T>": {
                    "java_type": "LinkedList<T>",
                    "java_wrapper": "LinkedList<T>",
                    "sql_type": "Not directly mappable - use separate table"
                },
                "std::map<K,V>": {
                    "java_type": "HashMap<K,V>",
                    "java_wrapper": "HashMap<K,V>",
                    "sql_type": "Not directly mappable - use separate table"
                },
                "std::set<T>": {
                    "java_type": "HashSet<T>",
                    "java_wrapper": "HashSet<T>",
                    "sql_type": "Not directly mappable - use separate table"
                }
            }
        },
        "smart_pointers": {
            "description": "Smart pointer types",
            "mappings": {
                "std::unique_ptr<T>": {
                    "java_type": "T",
                    "java_wrapper": "T",
                    "sql_type": "Depends on T",
                    "note": "Java uses garbage collection - no smart pointers needed"
                },
                "std::shared_ptr<T>": {
                    "java_type": "T",
                    "java_wrapper": "T",
                    "sql_type": "Depends on T",
                    "note": "Java uses garbage collection - no smart pointers needed"
                }
            }
        }
    },
    "default_mapping": {
        "java_type": "Object",
        "java_wrapper": "Object",
        "sql_type": "VARBINARY"
    }
}


# ============================================================================
# Template Registry
# ============================================================================

TEMPLATE_REGISTRY = {
    'cobol_java': COBOL_TO_JAVA_TYPE_MAPPING,
    'cpp_dotnet': CPP_TO_DOTNET_TYPE_MAPPING,
    'cpp_.net': CPP_TO_DOTNET_TYPE_MAPPING,  # Alias
    'cpp_java': CPP_TO_JAVA_TYPE_MAPPING,
}


# ============================================================================
# Public API
# ============================================================================

def get_template(source_lang: str, target_lang: str) -> Optional[Dict[str, Any]]:
    """
    Get type mapping template for a language pair

    Args:
        source_lang: Source language (e.g., 'cobol', 'cpp', 'c++')
        target_lang: Target language (e.g., 'java', 'dotnet', '.net')

    Returns:
        Type mapping template dictionary, or None if not found

    Example:
        >>> template = get_template('cobol', 'java')
        >>> print(template['source_language'])  # 'COBOL'
        >>> print(template['target_language'])  # 'Java'
    """
    # Normalize language names
    source = source_lang.lower().strip()
    target = target_lang.lower().strip()

    # Handle aliases
    if source == 'c++':
        source = 'cpp'
    if target in ['.net', 'dotnet']:
        target = 'dotnet'

    # Build key
    key = f"{source}_{target}"

    # Look up template
    template = TEMPLATE_REGISTRY.get(key)

    if template:
        # Return a deep copy to prevent modifications
        import copy
        return copy.deepcopy(template)

    return None


def get_available_mappings() -> list:
    """
    Get list of available language pair mappings

    Returns:
        List of tuples: [(source, target), ...]

    Example:
        >>> mappings = get_available_mappings()
        >>> print(mappings)
        [('COBOL', 'Java'), ('C++', '.NET'), ('C++', 'Java')]
    """
    mappings = []
    seen = set()

    for key, template in TEMPLATE_REGISTRY.items():
        if '_' not in key:
            continue

        source = template.get('source_language', '')
        target = template.get('target_language', '')

        if source and target:
            pair = (source, target)
            if pair not in seen:
                mappings.append(pair)
                seen.add(pair)

    return sorted(mappings)


def generate_type_mapping_file(source_lang: str, target_lang: str,
                               source_hash: str) -> Optional[Dict[str, Any]]:
    """
    Generate a complete type mapping file with metadata

    This function replicates the AWS Lambda behavior exactly.

    Args:
        source_lang: Source language
        target_lang: Target language
        source_hash: SHA-256 hash of uploaded files

    Returns:
        Complete type mapping dictionary ready to save as JSON, or None if template not found

    Example:
        >>> mapping = generate_type_mapping_file('cobol', 'java', 'abc123...')
        >>> with open('cobol_to_java.json', 'w') as f:
        ...     json.dump(mapping, f, indent=2)
    """
    template = get_template(source_lang, target_lang)

    if not template:
        return None

    # Add metadata (matches AWS Lambda behavior)
    template['generated_at'] = datetime.now(timezone.utc).isoformat()
    template['source_hash'] = source_hash

    return template
