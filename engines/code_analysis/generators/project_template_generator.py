"""
Project Template Generator for ModernizeIT CLI

Creates a complete, runnable Maven/IntelliJ project structure
for COBOL-to-Java translated code.

Design Principles (from thick-client):
- NO HARDCODING - template-driven
- Complete project that "just works" in IntelliJ
- Maven for dependency management and building
"""

from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from jinja2 import Template


# =============================================================================
# POM.XML TEMPLATE
# =============================================================================
POM_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>{{ group_id }}</groupId>
    <artifactId>{{ artifact_id }}</artifactId>
    <version>{{ version }}</version>
    <packaging>jar</packaging>

    <name>{{ project_name }}</name>
    <description>{{ description }}</description>

    <properties>
        <java.version>17</java.version>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>

    <dependencies>
        <!-- JUnit 5 for testing -->
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>5.10.0</version>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.11.0</version>
                <configuration>
                    <source>17</source>
                    <target>17</target>
                </configuration>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-jar-plugin</artifactId>
                <version>3.3.0</version>
                <configuration>
                    <archive>
                        <manifest>
                            <mainClass>{{ main_class }}</mainClass>
                        </manifest>
                    </archive>
                </configuration>
            </plugin>
            <plugin>
                <groupId>org.codehaus.mojo</groupId>
                <artifactId>exec-maven-plugin</artifactId>
                <version>3.1.0</version>
                <configuration>
                    <mainClass>{{ main_class }}</mainClass>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
"""


# =============================================================================
# INTELLIJ .IML TEMPLATE
# =============================================================================
IML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<module type="JAVA_MODULE" version="4">
  <component name="NewModuleRootManager" inherit-compiler-output="true">
    <exclude-output />
    <content url="file://$MODULE_DIR$">
      <sourceFolder url="file://$MODULE_DIR$/src/main/java" isTestSource="false" />
      <sourceFolder url="file://$MODULE_DIR$/src/test/java" isTestSource="true" />
      <excludeFolder url="file://$MODULE_DIR$/target" />
    </content>
    <orderEntry type="inheritedJdk" />
    <orderEntry type="sourceFolder" forTests="false" />
  </component>
</module>
"""


# =============================================================================
# IDEA MISC.XML TEMPLATE (JDK Configuration)
# =============================================================================
MISC_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="ProjectRootManager" version="2" languageLevel="JDK_17" default="true" project-jdk-name="17" project-jdk-type="JavaSDK">
    <output url="file://$PROJECT_DIR$/target/classes" />
  </component>
</project>
"""


# =============================================================================
# IDEA MODULES.XML TEMPLATE
# =============================================================================
MODULES_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="ProjectModuleManager">
    <modules>
      <module fileurl="file://$PROJECT_DIR$/{{ module_name }}.iml" filepath="$PROJECT_DIR$/{{ module_name }}.iml" />
    </modules>
  </component>
</project>
"""


# =============================================================================
# README TEMPLATE
# =============================================================================
README_TEMPLATE = """# {{ project_name }}

## Overview

COBOL-to-Java translation of **{{ cobol_program }}**.

Generated by ModernizeIT CLI on {{ generated_date }}.

## Source Statistics

| Metric | Value |
|--------|-------|
| COBOL Source Lines | {{ cobol_lines }} |
| Java Output Lines | {{ java_lines }} |
| Paragraphs | {{ paragraph_count }} |
| Data Fields | {{ field_count }} |

## Running the Application

### Using Maven

```bash
# Compile
mvn compile

# Run
mvn exec:java

# Package as JAR
mvn package

# Run JAR
java -jar target/{{ artifact_id }}-{{ version }}.jar
```

### Using IntelliJ

1. Open this folder as a project in IntelliJ
2. Wait for Maven to sync dependencies
3. Navigate to `src/main/java/{{ package_path }}/{{ class_name }}.java`
4. Right-click -> Run '{{ class_name }}.main()'

## Project Structure

```
{{ artifact_id }}/
├── pom.xml                          # Maven build configuration
├── src/
│   └── main/
│       └── java/
│           └── {{ package_path }}/
│               └── {{ class_name }}.java    # Translated COBOL program
└── README.md
```

## Important Notes

- **File I/O**: File operations are stubbed (no actual file reads/writes)
- **External CALLs**: CALL statements to external programs are stubbed
- **Data Initialization**: Fields initialized to defaults (spaces/zeros)

To enable real file I/O, implement the stubbed methods:
- `openFile()`, `readFile()`, `writeFile()`, `closeFile()`

## Generated Code Structure

The Java class follows COBOL structure:
- **Inner classes**: Represent COBOL record structures (groups)
- **Fields**: Translated from WORKING-STORAGE and FILE SECTION
- **Methods**: One method per COBOL paragraph (e.g., `mainControl_000()`)
- **Line references**: Comments reference original COBOL line numbers

---

Generated by ModernizeIT CLI
"""


class ProjectTemplateGenerator:
    """
    Generates a complete Maven/IntelliJ project structure.
    """

    def __init__(
        self,
        project_name: str,
        cobol_program: str,
        group_id: str = "com.modernizeit",
        artifact_id: Optional[str] = None,
        version: str = "1.0.0"
    ):
        self.project_name = project_name
        self.cobol_program = cobol_program
        self.group_id = group_id
        self.artifact_id = artifact_id or cobol_program.lower().replace('.', '_')
        self.version = version

        # Derived values
        self.package_name = f"{group_id}.generated"
        self.package_path = self.package_name.replace('.', '/')
        self.class_name = self._cobol_to_class_name(cobol_program)
        self.main_class = f"{self.package_name}.{self.class_name}"

    def _cobol_to_class_name(self, cobol_name: str) -> str:
        """Convert COBOL program name to Java class name."""
        # Remove extension
        name = cobol_name.replace('.CBL', '').replace('.cbl', '')
        # IFPR321 -> IFPR321 (keep as-is, it's already valid)
        return name

    def generate_project(
        self,
        output_dir: Path,
        java_content: str,
        stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate complete project structure.

        Args:
            output_dir: Base directory for project
            java_content: The generated Java source code
            stats: Statistics dict with cobol_lines, java_lines, etc.

        Returns:
            Dict with project paths and metadata
        """
        project_dir = output_dir / self.artifact_id

        # Create directory structure
        src_main_java = project_dir / "src" / "main" / "java" / self.package_path.replace('/', '/')
        src_test_java = project_dir / "src" / "test" / "java" / self.package_path.replace('/', '/')
        idea_dir = project_dir / ".idea"

        for d in [src_main_java, src_test_java, idea_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Generate pom.xml
        pom_content = self._render_pom()
        (project_dir / "pom.xml").write_text(pom_content)

        # Generate .iml file
        iml_content = self._render_iml()
        (project_dir / f"{self.artifact_id}.iml").write_text(iml_content)

        # Generate .idea/misc.xml (JDK config)
        misc_content = Template(MISC_XML_TEMPLATE).render()
        (idea_dir / "misc.xml").write_text(misc_content)

        # Generate .idea/modules.xml
        modules_content = Template(MODULES_XML_TEMPLATE).render(module_name=self.artifact_id)
        (idea_dir / "modules.xml").write_text(modules_content)

        # Write Java source file
        java_file = src_main_java / f"{self.class_name}.java"
        java_file.write_text(java_content)

        # Generate README.md
        readme_content = self._render_readme(stats)
        (project_dir / "README.md").write_text(readme_content)

        # Create .gitignore
        gitignore_content = """# Maven
target/

# IntelliJ
*.iml
.idea/
out/

# OS
.DS_Store
Thumbs.db
"""
        (project_dir / ".gitignore").write_text(gitignore_content)

        return {
            'project_dir': str(project_dir),
            'java_file': str(java_file),
            'pom_file': str(project_dir / "pom.xml"),
            'main_class': self.main_class,
            'package': self.package_name,
            'class_name': self.class_name,
            'artifact_id': self.artifact_id,
            'how_to_run': [
                f"cd {project_dir}",
                "mvn compile exec:java",
                "# Or open in IntelliJ and Run"
            ]
        }

    def _render_pom(self) -> str:
        """Render pom.xml from template."""
        template = Template(POM_TEMPLATE)
        return template.render(
            group_id=self.group_id,
            artifact_id=self.artifact_id,
            version=self.version,
            project_name=self.project_name,
            description=f"COBOL-to-Java translation of {self.cobol_program}",
            main_class=self.main_class
        )

    def _render_iml(self) -> str:
        """Render IntelliJ .iml file from template."""
        return Template(IML_TEMPLATE).render()

    def _render_readme(self, stats: Dict[str, Any]) -> str:
        """Render README.md from template."""
        template = Template(README_TEMPLATE)
        return template.render(
            project_name=self.project_name,
            cobol_program=self.cobol_program,
            generated_date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            cobol_lines=stats.get('cobol_lines', 0),
            java_lines=stats.get('java_lines', 0),
            paragraph_count=stats.get('paragraph_count', 0),
            field_count=stats.get('field_count', 0),
            artifact_id=self.artifact_id,
            version=self.version,
            package_path=self.package_path,
            class_name=self.class_name
        )


def generate_project_from_java(
    output_dir: Path,
    java_content: str,
    cobol_program: str,
    stats: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convenience function to generate a complete project.

    Args:
        output_dir: Base directory for project output
        java_content: The generated Java source code
        cobol_program: Original COBOL program name (e.g., "IFPR321.CBL")
        stats: Statistics dict

    Returns:
        Dict with project paths and metadata
    """
    generator = ProjectTemplateGenerator(
        project_name=f"{cobol_program.replace('.CBL', '')} Modernized",
        cobol_program=cobol_program
    )

    return generator.generate_project(output_dir, java_content, stats)


# =============================================================================
# STANDALONE TEST
# =============================================================================
if __name__ == "__main__":
    # Test the generator
    test_java = """package com.modernizeit.generated;

public class IFPR321 {
    public static void main(String[] args) {
        System.out.println("Hello from IFPR321!");
    }
}
"""

    result = generate_project_from_java(
        output_dir=Path("/tmp/test_project"),
        java_content=test_java,
        cobol_program="IFPR321.CBL",
        stats={
            'cobol_lines': 10646,
            'java_lines': 7981,
            'paragraph_count': 100,
            'field_count': 607
        }
    )

    print("Project generated:")
    for key, value in result.items():
        print(f"  {key}: {value}")
