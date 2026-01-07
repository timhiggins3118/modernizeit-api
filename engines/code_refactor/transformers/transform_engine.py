"""
Transform Engine

Orchestrates the application of refactoring recipes to Java code.
"""

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class TransformResult:
    """Result of transformation."""
    success: bool
    changes: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    files_created: List[str] = field(default_factory=list)


class TransformEngine:
    """
    Applies refactoring recipes to Java code.

    Supported recipe types:
    - extract_class: Split methods/fields into new class
    - rename_elements: Rename methods/fields to modern names
    - decompose_method: Split complex methods
    - implement_control_flow: Replace GO TO patterns
    """

    def __init__(self, output_dir: str):
        """
        Initialize transform engine.

        Args:
            output_dir: Directory to write transformed files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def apply_recipes(
        self,
        java_file: str,
        recipes: List[Dict[str, Any]]
    ) -> TransformResult:
        """
        Apply recipes to Java file.

        Args:
            java_file: Path to source Java file
            recipes: List of recipes to apply

        Returns:
            TransformResult with changes made
        """
        try:
            java_path = Path(java_file)
            if not java_path.exists():
                return TransformResult(
                    success=False,
                    error=f"Java file not found: {java_file}"
                )

            # Read source
            java_content = java_path.read_text()
            class_name = java_path.stem

            changes = []
            files_created = []

            # Group recipes by type
            extract_class_recipes = [r for r in recipes if r.get("type") == "extract_class"]
            rename_recipes = [r for r in recipes if r.get("type") in ("rename_elements", "rename_methods")]
            decompose_recipes = [r for r in recipes if r.get("type") == "decompose_method"]
            control_flow_recipes = [r for r in recipes if r.get("type") == "implement_control_flow"]

            # Apply extract_class recipes
            # Each recipe may have multiple "changes" (one per class to extract)
            for recipe in extract_class_recipes:
                proposed = recipe.get("proposed_change", {})
                recipe_changes = proposed.get("changes", [])

                for change_idx, change in enumerate(recipe_changes):
                    result = self._apply_extract_class_single(java_content, class_name, recipe, change)
                    if result["success"]:
                        java_content = result["modified_content"]
                        changes.append({
                            "recipe_id": f"{recipe.get('id')}_{change_idx}",
                            "type": "extract_class",
                            "details": result["details"]
                        })
                        if result.get("new_file"):
                            files_created.append(result["new_file"])

            # Apply rename recipes
            for recipe in rename_recipes:
                result = self._apply_rename(java_content, recipe)
                if result["success"]:
                    java_content = result["modified_content"]
                    changes.append({
                        "recipe_id": recipe.get("id"),
                        "type": "rename",
                        "details": result["details"]
                    })

            # Apply decompose recipes
            for recipe in decompose_recipes:
                result = self._apply_decompose(java_content, recipe)
                if result["success"]:
                    java_content = result["modified_content"]
                    changes.append({
                        "recipe_id": recipe.get("id"),
                        "type": "decompose",
                        "details": result["details"]
                    })

            # Apply control flow recipes
            for recipe in control_flow_recipes:
                result = self._apply_control_flow(java_content, recipe)
                if result["success"]:
                    java_content = result["modified_content"]
                    changes.append({
                        "recipe_id": recipe.get("id"),
                        "type": "control_flow",
                        "details": result["details"]
                    })

            # Write transformed main file
            output_file = self.output_dir / f"{class_name}.java"
            output_file.write_text(java_content)
            files_created.insert(0, str(output_file))

            return TransformResult(
                success=True,
                changes=changes,
                files_created=files_created
            )

        except Exception as e:
            return TransformResult(
                success=False,
                error=str(e)
            )

    def _apply_extract_class_single(
        self,
        java_content: str,
        original_class: str,
        recipe: Dict[str, Any],
        change: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract methods/fields into a new class for a single change."""
        try:
            if not change:
                return {"success": False, "details": "No change specified"}

            new_class_name = change.get("new_class") or change.get("details", {}).get("prefix", "Extracted") + "Service"

            # Get methods - could be "methods_to_move" list or "methods" string description
            methods_to_move = change.get("methods_to_move", [])
            methods_description = change.get("methods", "")

            # Clean method names - remove () if present
            if isinstance(methods_to_move, list):
                methods_to_move = [m.replace("()", "") if isinstance(m, str) else m for m in methods_to_move]

            # If methods_to_move is empty but we have a description, parse it
            if not methods_to_move and isinstance(methods_description, str):
                # Extract pattern like "200" from "200-series methods..." or "200-prefix methods..."
                pattern_match = re.search(r'(\d+)[-_]?(?:series|prefix)', methods_description)
                if pattern_match:
                    prefix = pattern_match.group(1)
                    # Find all methods with this prefix pattern
                    # COBOL methods are named like: grossToNet_200, processControl_200_010, exit_200_100
                    # Pattern: method names containing _{prefix} or _{prefix}_
                    method_pattern = rf'(?:private|public|protected)\s+(?:void|[\w<>\[\]]+)\s+(\w+_{prefix}(?:_\d+)?)\s*\('
                    methods_to_move = re.findall(method_pattern, java_content)
                    # Limit to avoid extracting too many at once
                    methods_to_move = methods_to_move[:50]
                    print(f"[Transform] Found {len(methods_to_move)} methods with _{prefix} pattern: {methods_to_move[:5]}...")

            # If methods_to_move is a string like "300-series methods" or "300-prefix methods", find by pattern
            if isinstance(methods_to_move, str):
                pattern_match = re.search(r'(\d+)[-_]?(?:series|prefix)', methods_to_move)
                if pattern_match:
                    prefix = pattern_match.group(1)
                    # Same pattern as above: matches _{prefix} or _{prefix}_XXX
                    method_pattern = rf'(?:private|public|protected)\s+(?:void|[\w<>\[\]]+)\s+(\w+_{prefix}(?:_\d+)?)\s*\('
                    methods_to_move = re.findall(method_pattern, java_content)[:50]
                else:
                    methods_to_move = []

            if not methods_to_move:
                # Get from target elements
                elements = recipe.get("target", {}).get("elements", [])
                # Filter to actual method names (not descriptions like "114 methods with '300' prefix")
                methods_to_move = [
                    e.replace("()", "") for e in elements
                    if isinstance(e, str) and not e.startswith("//")
                    and "methods with" not in e.lower()
                    and "series" not in e.lower()
                    and "_" in e  # Likely a method name like calculate_300_000
                ][:20]

            if not methods_to_move:
                return {"success": False, "details": "No methods to extract"}

            # Find all method positions first
            method_positions = []
            for method_name in methods_to_move:
                pattern = rf'((?:/\*\*[\s\S]*?\*/\s*)?(?:public|private|protected)?\s*(?:static\s+)?(?:void|[\w<>\[\]]+)\s+{re.escape(method_name)}\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{{)'
                match = re.search(pattern, java_content)

                if match:
                    start = match.start()
                    brace_count = 0
                    end = start
                    in_method = False

                    for i, char in enumerate(java_content[start:], start):
                        if char == '{':
                            brace_count += 1
                            in_method = True
                        elif char == '}':
                            brace_count -= 1
                            if in_method and brace_count == 0:
                                end = i + 1
                                break

                    if end > start:
                        method_body = java_content[start:end]
                        method_positions.append({
                            "name": method_name,
                            "start": start,
                            "end": end,
                            "body": method_body
                        })

            # Sort by position descending (process from end to start to avoid position shifts)
            method_positions.sort(key=lambda x: x["start"], reverse=True)

            # Extract and replace
            extracted_methods = []
            modified_content = java_content

            # Collect all field names from original class for parent. prefixing
            field_pattern = r'(?:private|protected|public)\s+(?:final\s+)?[\w<>\[\]]+\s+(\w+)\s*[;=]'
            all_fields = set(re.findall(field_pattern, java_content))

            # Collect all method names for parent. prefixing
            method_pattern_all = r'(?:private|public|protected)\s+(?:void|[\w<>\[\]]+)\s+(\w+)\s*\('
            all_methods = set(re.findall(method_pattern_all, java_content))
            extracted_method_names = set(mp["name"] for mp in method_positions)
            other_methods = all_methods - extracted_method_names

            for mp in method_positions:
                method_body = mp["body"]

                # Add parent. prefix to field references
                # Skip single-character fields to avoid matching inside string literals
                # Also exclude matches inside quotes
                for field in all_fields:
                    # Skip very short field names (1-2 chars) as they cause false matches in strings
                    if len(field) <= 2:
                        continue
                    # Prefix field references (not preceded by . or word char or quote, not followed by ( or word char or quote)
                    method_body = re.sub(
                        rf'(?<![.\w"])({re.escape(field)})(?![(\w"])',
                        r'parent.\1',
                        method_body
                    )

                # Add parent. prefix to calls to non-extracted methods
                for other_method in other_methods:
                    # Skip short method names
                    if len(other_method) <= 2:
                        continue
                    method_body = re.sub(
                        rf'(?<![.\w"])({re.escape(other_method)})\s*\(',
                        r'parent.\1(',
                        method_body
                    )

                extracted_methods.append(method_body)

                # Replace original method with delegation
                delegation = f'''    // Delegated to {new_class_name}
    private void {mp["name"]}() {{
        {new_class_name[0].lower() + new_class_name[1:]}.{mp["name"]}();
    }}
'''
                modified_content = modified_content[:mp["start"]] + delegation + modified_content[mp["end"]:]

            if not extracted_methods:
                return {"success": False, "details": "Could not extract any methods"}

            # Add service field to original class
            service_var = new_class_name[0].lower() + new_class_name[1:]
            service_field = f"    private final {new_class_name} {service_var} = new {new_class_name}(this);\n"
            class_pattern = rf'public class {re.escape(original_class)}\s*\{{'
            class_match = re.search(class_pattern, modified_content)
            if class_match:
                insert_pos = class_match.end()
                modified_content = modified_content[:insert_pos] + "\n" + service_field + modified_content[insert_pos:]

            # Make fields protected so service can access them
            modified_content = re.sub(r'(\n\s+)private\s+((?:final\s+)?[\w<>\[\]]+\s+\w+\s*[;=])', r'\1protected \2', modified_content)

            # Make methods protected so service can call them
            modified_content = re.sub(r'(\n\s+)private\s+(void\s+\w+\s*\()', r'\1protected \2', modified_content)

            # Generate new class file
            new_class_content = self._generate_class_file(
                new_class_name,
                extracted_methods,
                original_class
            )

            new_file_path = self.output_dir / f"{new_class_name}.java"
            new_file_path.write_text(new_class_content)

            return {
                "success": True,
                "modified_content": modified_content,
                "new_file": str(new_file_path),
                "details": f"Extracted {len(extracted_methods)} methods to {new_class_name}"
            }

        except Exception as e:
            return {"success": False, "details": str(e)}

    def _generate_class_file(
        self,
        class_name: str,
        methods: List[str],
        original_class: str
    ) -> str:
        """Generate a new Java class file with parent reference."""
        lines = [
            "package com.modernizeit.generated;",
            "",
            "import java.math.BigDecimal;",
            "import java.math.RoundingMode;",
            "import java.util.*;",
            "",
            "/**",
            f" * Extracted from {original_class}",
            " * Generated by ModernizeIT Code Refactor",
            " */",
            f"public class {class_name} {{",
            "",
            f"    private final {original_class} parent;",
            "",
            f"    public {class_name}({original_class} parent) {{",
            "        this.parent = parent;",
            "    }",
            "",
        ]

        for method in methods:
            # Make methods public
            method = re.sub(r'^(\s*)private\s+', r'\1public ', method)
            lines.append(method)
            lines.append("")

        lines.append("}")

        return "\n".join(lines)

    def _apply_rename(
        self,
        java_content: str,
        recipe: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Rename methods/fields to modern names."""
        try:
            elements = recipe.get("target", {}).get("elements", [])
            renames_made = 0
            modified = java_content

            for element in elements[:10]:  # Limit for safety
                # Generate modern name
                old_name = element
                new_name = self._modernize_name(old_name)

                if old_name != new_name:
                    # Replace all occurrences
                    pattern = rf'\b{re.escape(old_name)}\b'
                    modified = re.sub(pattern, new_name, modified)
                    renames_made += 1

            return {
                "success": renames_made > 0,
                "modified_content": modified,
                "details": f"Renamed {renames_made} elements"
            }

        except Exception as e:
            return {"success": False, "details": str(e)}

    def _modernize_name(self, cobol_name: str) -> str:
        """Convert COBOL-style name to modern Java name."""
        # Remove numeric prefixes like "200_" or "300_"
        name = re.sub(r'^\d+_', '', cobol_name)

        # Remove common COBOL prefixes
        prefixes = ['WS_', 'WK_', 'SW_', 'FL_', 'FD_']
        for prefix in prefixes:
            if name.upper().startswith(prefix):
                name = name[len(prefix):]
                break

        # Convert underscores to camelCase
        parts = name.split('_')
        if len(parts) > 1:
            result = parts[0].lower()
            for part in parts[1:]:
                if part:
                    result += part.capitalize()
            return result

        return name

    def _apply_decompose(
        self,
        java_content: str,
        recipe: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Decompose complex methods into smaller ones."""
        try:
            elements = recipe.get("target", {}).get("elements", [])

            # For now, add TODO comments for manual decomposition
            modified = java_content
            for method_name in elements[:5]:
                pattern = rf'((?:public|private|protected)?\s*(?:void|[\w<>\[\]]+)\s+{re.escape(method_name)}\s*\([^)]*\)\s*\{{)'
                replacement = rf'// TODO: Decompose this complex method\n    \1'
                modified = re.sub(pattern, replacement, modified)

            return {
                "success": True,
                "modified_content": modified,
                "details": f"Marked {len(elements)} methods for decomposition"
            }

        except Exception as e:
            return {"success": False, "details": str(e)}

    def _apply_control_flow(
        self,
        java_content: str,
        recipe: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Replace GO TO patterns with proper control flow."""
        try:
            # Find GO TO comments and replace with state machine pattern
            goto_pattern = r'// GO TO (\w+) - (.+)'

            def replace_goto(match):
                target = match.group(1)
                description = match.group(2)
                return f'// STATE: {target} - {description}\n        // TODO: Implement proper control flow'

            modified = re.sub(goto_pattern, replace_goto, java_content)

            goto_count = len(re.findall(goto_pattern, java_content))

            return {
                "success": goto_count > 0,
                "modified_content": modified,
                "details": f"Processed {goto_count} GO TO patterns"
            }

        except Exception as e:
            return {"success": False, "details": str(e)}
