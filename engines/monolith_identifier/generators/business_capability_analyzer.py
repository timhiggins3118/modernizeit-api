"""
Business Capability Analyzer for Monolith Identifier

Identifies business capabilities in source code based on:
- Program/class naming patterns
- Data structure names
- File I/O patterns
- Method/paragraph naming
- Domain keywords

Maps programs to business capabilities for decomposition planning.
"""

import re
from typing import Any, Dict, List, Set, Tuple


# Common business capability keywords
CAPABILITY_KEYWORDS = {
    "customer": {
        "capability": "Customer Management",
        "description": "Customer data operations, validation, lookup",
        "keywords": ["customer", "cust", "client", "member", "subscriber", "account"],
        "data_patterns": ["customer-rec", "cust-rec", "client-rec", "member-rec"]
    },
    "order": {
        "capability": "Order Processing",
        "description": "Order creation, validation, fulfillment",
        "keywords": ["order", "ord", "purchase", "basket", "cart", "checkout"],
        "data_patterns": ["order-rec", "ord-rec", "purchase-rec"]
    },
    "inventory": {
        "capability": "Inventory Management",
        "description": "Stock tracking, availability, warehouse operations",
        "keywords": ["inventory", "inv", "stock", "warehouse", "product", "item"],
        "data_patterns": ["inventory-rec", "inv-rec", "stock-rec", "product-rec"]
    },
    "billing": {
        "capability": "Billing & Invoicing",
        "description": "Invoice generation, payment processing",
        "keywords": ["bill", "invoice", "payment", "charge", "fee", "price"],
        "data_patterns": ["bill-rec", "invoice-rec", "payment-rec"]
    },
    "reporting": {
        "capability": "Reporting",
        "description": "Report generation, data aggregation, analytics",
        "keywords": ["report", "rpt", "summary", "analytics", "dashboard", "stats"],
        "data_patterns": ["report-rec", "rpt-rec"]
    },
    "validation": {
        "capability": "Data Validation",
        "description": "Input validation, business rule enforcement",
        "keywords": ["valid", "check", "verify", "validate", "edit", "audit"],
        "data_patterns": ["error-rec", "valid-rec"]
    },
    "shipping": {
        "capability": "Shipping & Logistics",
        "description": "Delivery scheduling, tracking, fulfillment",
        "keywords": ["ship", "deliver", "logistics", "freight", "carrier", "track"],
        "data_patterns": ["ship-rec", "delivery-rec"]
    },
    "notification": {
        "capability": "Notification Service",
        "description": "Email, SMS, alerts, communications",
        "keywords": ["notify", "alert", "email", "sms", "message", "comm"],
        "data_patterns": ["notif-rec", "message-rec"]
    },
    "auth": {
        "capability": "Authentication & Security",
        "description": "User authentication, authorization, security",
        "keywords": ["auth", "login", "security", "password", "user", "session"],
        "data_patterns": ["user-rec", "auth-rec", "session-rec"]
    },
    "config": {
        "capability": "Configuration Management",
        "description": "System configuration, parameters, settings",
        "keywords": ["config", "param", "setting", "option", "pref"],
        "data_patterns": ["config-rec", "param-rec"]
    }
}


class BusinessCapabilityAnalyzer:
    """
    Analyzes source code to identify business capabilities.
    """

    def analyze(
        self,
        static_analysis: Dict[str, Any],
        source_type: str = "cobol"
    ) -> Dict[str, Any]:
        """
        Analyze business capabilities.

        Args:
            static_analysis: Results from static analyzer
            source_type: "cobol" or "java"

        Returns:
            Dictionary with capabilities and program mappings
        """
        programs = static_analysis.get("programs", [])

        # Detect capabilities for each program
        program_capabilities: Dict[str, List[str]] = {}
        capability_programs: Dict[str, Dict[str, Any]] = {}

        for program in programs:
            if source_type == "cobol":
                capabilities = self._analyze_cobol_program(program)
            else:
                capabilities = self._analyze_java_class(program)

            program_name = program.get("program", program.get("class_name", "UNKNOWN"))
            program_capabilities[program_name] = capabilities

            # Build reverse mapping
            for cap in capabilities:
                if cap not in capability_programs:
                    capability_programs[cap] = {
                        "programs": [],
                        "total_loc": 0,
                        "indicators": set()
                    }
                capability_programs[cap]["programs"].append(program_name)
                capability_programs[cap]["total_loc"] += program.get("loc", 0)

        # Build final capabilities list
        capabilities_data = self._build_capabilities_data(
            capability_programs, programs, source_type
        )

        # Summary
        programs_with_multiple = sum(
            1 for caps in program_capabilities.values() if len(caps) > 1
        )
        max_caps = max((len(caps) for caps in program_capabilities.values()), default=0)

        return {
            "capabilities": capabilities_data,
            "program_capability_map": program_capabilities,
            "summary": {
                "total_capabilities": len(capabilities_data),
                "programs_with_multiple_capabilities": programs_with_multiple,
                "max_capabilities_per_program": max_caps
            }
        }

    def _analyze_cobol_program(self, program: Dict[str, Any]) -> List[str]:
        """Identify business capabilities in a COBOL program."""
        capabilities = []
        program_name = program.get("program", "").upper()
        file_path = program.get("file_path", "").upper()

        # Check program name against capability keywords
        for cap_id, cap_info in CAPABILITY_KEYWORDS.items():
            for keyword in cap_info["keywords"]:
                if keyword.upper() in program_name or keyword.upper() in file_path:
                    if cap_info["capability"] not in capabilities:
                        capabilities.append(cap_info["capability"])
                    break

        # If no capabilities found from name, assign based on structure
        if not capabilities:
            # Large programs with many sections likely have multiple capabilities
            sections = program.get("sections", 0)
            loc = program.get("loc", 0)

            if loc > 5000 or sections > 50:
                # Assume a large program has common capabilities
                capabilities.append("Data Processing")
            else:
                capabilities.append("General Processing")

        return capabilities

    def _analyze_java_class(self, program: Dict[str, Any]) -> List[str]:
        """Identify business capabilities in a Java class."""
        capabilities = []
        class_name = program.get("class_name", program.get("program", "")).lower()
        package = program.get("package", "").lower()
        file_path = program.get("file_path", "").lower()

        # Combine for searching
        search_text = f"{class_name} {package} {file_path}"

        # Check against capability keywords
        for cap_id, cap_info in CAPABILITY_KEYWORDS.items():
            for keyword in cap_info["keywords"]:
                if keyword in search_text:
                    if cap_info["capability"] not in capabilities:
                        capabilities.append(cap_info["capability"])
                    break

        # Check common Java naming patterns
        if "controller" in class_name or "resource" in class_name:
            if "API Gateway" not in capabilities:
                capabilities.append("API Gateway")

        if "service" in class_name:
            if "Business Logic" not in capabilities:
                capabilities.append("Business Logic")

        if "repository" in class_name or "dao" in class_name:
            if "Data Access" not in capabilities:
                capabilities.append("Data Access")

        if "util" in class_name or "helper" in class_name:
            if "Utilities" not in capabilities:
                capabilities.append("Utilities")

        # If no capabilities found, assign generic
        if not capabilities:
            loc = program.get("loc", 0)
            methods = program.get("methods", 0)

            if loc > 3000 or methods > 30:
                capabilities.append("Core Processing")
            else:
                capabilities.append("General Processing")

        return capabilities

    def _build_capabilities_data(
        self,
        capability_programs: Dict[str, Dict[str, Any]],
        programs: List[Dict[str, Any]],
        source_type: str
    ) -> List[Dict[str, Any]]:
        """Build detailed capabilities data."""
        capabilities_data = []

        # Create program lookup for LOC
        program_loc = {}
        for p in programs:
            name = p.get("program", p.get("class_name", ""))
            program_loc[name] = p.get("loc", 0)

        for capability, info in capability_programs.items():
            # Find primary program (highest LOC)
            primary_program = None
            max_loc = 0
            for prog in info["programs"]:
                prog_loc = program_loc.get(prog, 0)
                if prog_loc > max_loc:
                    max_loc = prog_loc
                    primary_program = prog

            # Get description from keywords or generate
            description = self._get_capability_description(capability)

            # Build indicators based on source type
            indicators = self._generate_indicators(capability, source_type)

            capabilities_data.append({
                "capability": capability,
                "description": description,
                "programs": info["programs"],
                "program_count": len(info["programs"]),
                "total_loc": info["total_loc"],
                "primary_program": primary_program,
                "indicators": indicators
            })

        # Sort by program count descending
        capabilities_data.sort(key=lambda x: x["program_count"], reverse=True)

        return capabilities_data

    def _get_capability_description(self, capability: str) -> str:
        """Get description for a capability."""
        for cap_info in CAPABILITY_KEYWORDS.values():
            if cap_info["capability"] == capability:
                return cap_info["description"]

        # Default descriptions for generated capabilities
        descriptions = {
            "Data Processing": "General data transformation and processing",
            "General Processing": "General-purpose business logic",
            "API Gateway": "API endpoint handling and routing",
            "Business Logic": "Core business rules and workflows",
            "Data Access": "Database and storage operations",
            "Utilities": "Helper functions and common utilities",
            "Core Processing": "Main application processing logic"
        }

        return descriptions.get(capability, "Business capability")

    def _generate_indicators(self, capability: str, source_type: str) -> List[str]:
        """Generate indicators that led to capability identification."""
        for cap_id, cap_info in CAPABILITY_KEYWORDS.items():
            if cap_info["capability"] == capability:
                if source_type == "cobol":
                    return [
                        f"Keywords matched: {', '.join(cap_info['keywords'][:3])}",
                        f"Data patterns: {', '.join(cap_info['data_patterns'][:2])}"
                    ]
                else:
                    return [
                        f"Keywords matched: {', '.join(cap_info['keywords'][:3])}",
                        "Class/package naming pattern"
                    ]

        return ["Inferred from program structure"]
