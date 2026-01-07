"""
Decomposition Strategist for Monolith Identifier

Generates microservice decomposition recommendations:
- Recommended services based on business capabilities
- God Object decomposition plans
- Extraction effort estimates
- Strangler Fig migration roadmap
"""

from typing import Any, Dict, List, Optional, Tuple


class DecompositionStrategist:
    """
    Generates decomposition strategy for monolithic codebases.
    """

    # Effort multipliers based on complexity
    EFFORT_BASE_WEEKS_PER_KLOC = 1.0  # 1 week per 1000 LOC base
    COMPLEXITY_MULTIPLIER_HIGH = 1.5
    COMPLEXITY_MULTIPLIER_MEDIUM = 1.2
    COMPLEXITY_MULTIPLIER_LOW = 1.0

    def strategize(
        self,
        static_analysis: Dict[str, Any],
        patterns: Dict[str, Any],
        modularity: Dict[str, Any],
        capabilities: Dict[str, Any],
        source_type: str = "cobol"
    ) -> Dict[str, Any]:
        """
        Generate decomposition strategy.

        Args:
            static_analysis: Static analysis results
            patterns: Detected patterns
            modularity: Modularity metrics
            capabilities: Business capabilities

        Returns:
            Decomposition strategy with services, roadmap, priorities
        """
        # Build recommended services from capabilities
        recommended_services = self._build_recommended_services(
            capabilities, modularity, patterns, static_analysis
        )

        # Build God Object decomposition plans
        god_object_decomposition = self._build_god_object_plans(
            patterns, capabilities, modularity
        )

        # Build migration strategy
        migration_strategy = self._build_migration_strategy(
            recommended_services, god_object_decomposition
        )

        # Build refactoring priorities
        refactoring_priorities = self._build_refactoring_priorities(
            patterns, modularity, god_object_decomposition
        )

        # Calculate summary
        total_effort = sum(s["estimated_effort_weeks"] for s in recommended_services)
        god_count = len(god_object_decomposition)

        return {
            "recommended_services": recommended_services,
            "god_object_decomposition": god_object_decomposition,
            "migration_strategy": migration_strategy,
            "refactoring_priorities": refactoring_priorities,
            "summary": {
                "recommended_services_count": len(recommended_services),
                "god_objects_to_decompose": god_count,
                "total_effort_weeks": total_effort,
                "estimated_timeline": self._estimate_timeline(total_effort),
                "migration_approach": "Strangler Fig Pattern"
            }
        }

    def _build_recommended_services(
        self,
        capabilities: Dict[str, Any],
        modularity: Dict[str, Any],
        patterns: Dict[str, Any],
        static_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build recommended microservices from business capabilities."""
        services = []

        # Get modularity lookup
        modularity_lookup = {}
        for m in modularity.get("by_program", []):
            modularity_lookup[m["program"]] = m

        # Get patterns lookup
        god_objects = set()
        for p in patterns.get("patterns", []):
            if p["pattern_type"] == "GOD_OBJECT":
                god_objects.add(p["program"])

        # Build services from capabilities
        for cap in capabilities.get("capabilities", []):
            capability_name = cap["capability"]
            programs = cap["programs"]
            total_loc = cap["total_loc"]

            # Determine which programs are from God Objects
            extracted_from = [p for p in programs if p in god_objects]

            # Calculate extraction complexity
            complexity, effort = self._calculate_extraction_effort(
                programs, modularity_lookup, total_loc
            )

            # Find dependencies (simplified - based on coupling)
            dependencies = self._find_service_dependencies(
                programs, capabilities.get("capabilities", [])
            )

            # Find shared data (simplified)
            shared_data = self._find_shared_data(capability_name)

            services.append({
                "service_name": self._generate_service_name(capability_name),
                "business_capability": capability_name,
                "programs": programs,
                "extracted_from_god_objects": extracted_from,
                "total_loc": total_loc,
                "extraction_complexity": complexity,
                "estimated_effort_weeks": effort,
                "dependencies": dependencies,
                "shared_data": shared_data
            })

        # Sort by effort (smallest first for phased approach)
        services.sort(key=lambda x: x["estimated_effort_weeks"])

        return services

    def _calculate_extraction_effort(
        self,
        programs: List[str],
        modularity_lookup: Dict[str, Dict],
        total_loc: int
    ) -> Tuple[str, int]:
        """Calculate extraction complexity and effort."""
        # Get average maintainability
        maintainability_scores = []
        for prog in programs:
            if prog in modularity_lookup:
                maintainability_scores.append(
                    modularity_lookup[prog].get("maintainability_index", 50)
                )

        avg_maintainability = (
            sum(maintainability_scores) / len(maintainability_scores)
            if maintainability_scores else 50
        )

        # Determine complexity based on maintainability
        if avg_maintainability < 40:
            complexity = "high"
            multiplier = self.COMPLEXITY_MULTIPLIER_HIGH
        elif avg_maintainability < 70:
            complexity = "medium"
            multiplier = self.COMPLEXITY_MULTIPLIER_MEDIUM
        else:
            complexity = "low"
            multiplier = self.COMPLEXITY_MULTIPLIER_LOW

        # Calculate effort (weeks)
        kloc = total_loc / 1000.0
        effort = int(kloc * self.EFFORT_BASE_WEEKS_PER_KLOC * multiplier)
        effort = max(2, effort)  # Minimum 2 weeks

        return complexity, effort

    def _find_service_dependencies(
        self,
        programs: List[str],
        all_capabilities: List[Dict]
    ) -> List[str]:
        """Find other services this service depends on."""
        dependencies = []

        # Simplified: assume services with shared data have dependencies
        for cap in all_capabilities:
            if cap["capability"] in ["Data Validation", "Utilities", "Configuration Management"]:
                service_name = self._generate_service_name(cap["capability"])
                if service_name not in dependencies:
                    dependencies.append(service_name)

        return dependencies[:3]  # Limit to 3 dependencies

    def _find_shared_data(self, capability: str) -> List[str]:
        """Find shared data structures for a capability."""
        # Simplified mapping
        shared_data_map = {
            "Customer Management": ["CUSTOMER-RECORD", "CustomerEntity"],
            "Order Processing": ["ORDER-RECORD", "OrderEntity", "CUSTOMER-RECORD"],
            "Inventory Management": ["INVENTORY-RECORD", "ProductEntity"],
            "Billing & Invoicing": ["INVOICE-RECORD", "PaymentEntity"],
            "Reporting": ["REPORT-DATA", "AggregatedMetrics"],
            "Data Validation": ["ERROR-RECORD", "ValidationResult"],
            "Shipping & Logistics": ["SHIPPING-RECORD", "DeliveryEntity"],
        }

        return shared_data_map.get(capability, [])

    def _generate_service_name(self, capability: str) -> str:
        """Generate a service name from capability."""
        # Remove special characters and create PascalCase
        words = capability.replace("&", "And").replace("/", "").split()
        return "".join(w.capitalize() for w in words) + "Service"

    def _build_god_object_plans(
        self,
        patterns: Dict[str, Any],
        capabilities: Dict[str, Any],
        modularity: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build decomposition plans for God Objects."""
        plans = []

        # Get capability mapping
        program_caps = capabilities.get("program_capability_map", {})

        # Get modularity lookup
        modularity_lookup = {}
        for m in modularity.get("by_program", []):
            modularity_lookup[m["program"]] = m

        # Find God Objects
        for pattern in patterns.get("patterns", []):
            if pattern["pattern_type"] != "GOD_OBJECT":
                continue

            program = pattern["program"]
            current_caps = program_caps.get(program, [])

            # If program has only one capability, estimate based on size
            if len(current_caps) <= 1:
                # Estimate capabilities from metrics
                metrics = modularity_lookup.get(program, {})
                estimated_caps = metrics.get("estimated_capabilities", 2)
                if estimated_caps > 1:
                    current_caps = [f"Capability {i+1}" for i in range(estimated_caps)]

            # Build recommended split
            recommended_split = []
            for cap in current_caps:
                recommended_split.append({
                    "capability": cap,
                    "target_service": self._generate_service_name(cap)
                })

            # Calculate effort
            metrics = modularity_lookup.get(program, {})
            maintainability = metrics.get("maintainability_index", 50)

            if maintainability < 40:
                complexity = "high"
                effort = len(current_caps) * 4  # 4 weeks per capability
            elif maintainability < 70:
                complexity = "medium"
                effort = len(current_caps) * 3
            else:
                complexity = "low"
                effort = len(current_caps) * 2

            plans.append({
                "program": program,
                "current_capabilities": current_caps,
                "recommended_split": recommended_split,
                "refactoring_complexity": complexity,
                "estimated_effort_weeks": effort
            })

        return plans

    def _build_migration_strategy(
        self,
        services: List[Dict[str, Any]],
        god_objects: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build Strangler Fig migration strategy."""
        phases = []
        total_effort = 0

        # Phase 0: Foundation (if God Objects exist)
        if god_objects:
            god_effort = sum(g["estimated_effort_weeks"] for g in god_objects)
            phases.append({
                "phase": 0,
                "name": "Foundation - God Object Refactoring",
                "description": "Refactor God Objects into separate modules before service extraction",
                "programs": [g["program"] for g in god_objects],
                "services": [],
                "effort_weeks": god_effort,
                "risk": "HIGH"
            })
            total_effort += god_effort

        # Group services into phases by complexity/effort
        low_complexity = [s for s in services if s["extraction_complexity"] == "low"]
        medium_complexity = [s for s in services if s["extraction_complexity"] == "medium"]
        high_complexity = [s for s in services if s["extraction_complexity"] == "high"]

        phase_num = len(phases)

        # Phase: Low complexity services (quick wins)
        if low_complexity:
            phase_num += 1
            phase_effort = sum(s["estimated_effort_weeks"] for s in low_complexity)
            phases.append({
                "phase": phase_num,
                "name": "Quick Wins",
                "description": "Extract low-complexity services with minimal dependencies",
                "programs": [],
                "services": [s["service_name"] for s in low_complexity],
                "effort_weeks": phase_effort,
                "risk": "LOW"
            })
            total_effort += phase_effort

        # Phase: Medium complexity services (core services)
        if medium_complexity:
            phase_num += 1
            phase_effort = sum(s["estimated_effort_weeks"] for s in medium_complexity)
            phases.append({
                "phase": phase_num,
                "name": "Core Services",
                "description": "Extract core business services",
                "programs": [],
                "services": [s["service_name"] for s in medium_complexity],
                "effort_weeks": phase_effort,
                "risk": "MEDIUM"
            })
            total_effort += phase_effort

        # Phase: High complexity services (critical path)
        if high_complexity:
            phase_num += 1
            phase_effort = sum(s["estimated_effort_weeks"] for s in high_complexity)
            phases.append({
                "phase": phase_num,
                "name": "Complex Extractions",
                "description": "Extract high-complexity services requiring careful planning",
                "programs": [],
                "services": [s["service_name"] for s in high_complexity],
                "effort_weeks": phase_effort,
                "risk": "HIGH"
            })
            total_effort += phase_effort

        return {
            "approach": "Strangler Fig Pattern",
            "description": "Gradually replace monolith by extracting services one at a time",
            "phases": phases,
            "total_effort_weeks": total_effort,
            "estimated_timeline": self._estimate_timeline(total_effort)
        }

    def _build_refactoring_priorities(
        self,
        patterns: Dict[str, Any],
        modularity: Dict[str, Any],
        god_objects: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build prioritized refactoring list."""
        priorities = []
        priority_num = 0

        # Priority 1: God Objects (must be decomposed first)
        for god in god_objects:
            priority_num += 1
            priorities.append({
                "priority": priority_num,
                "program": god["program"],
                "pattern": "GOD_OBJECT",
                "reason": f"Contains {len(god['current_capabilities'])} business capabilities, blocking service extraction",
                "action": "Decompose into separate programs before microservice extraction",
                "effort_weeks": god["estimated_effort_weeks"]
            })

        # Priority 2: Big Ball of Mud (needs structure before extraction)
        for pattern in patterns.get("patterns", []):
            if pattern["pattern_type"] == "BIG_BALL_OF_MUD":
                priority_num += 1
                priorities.append({
                    "priority": priority_num,
                    "program": pattern["program"],
                    "pattern": "BIG_BALL_OF_MUD",
                    "reason": "Tangled code structure makes extraction risky",
                    "action": "Establish clear boundaries and reduce coupling before extraction",
                    "effort_weeks": 4
                })

        # Priority 3: Low maintainability programs
        for m in modularity.get("by_program", []):
            if m["classification"] == "LOW":
                # Skip if already in priorities
                if any(p["program"] == m["program"] for p in priorities):
                    continue

                priority_num += 1
                priorities.append({
                    "priority": priority_num,
                    "program": m["program"],
                    "pattern": "LOW_MAINTAINABILITY",
                    "reason": f"Maintainability index: {m['maintainability_index']:.1f} (below 40)",
                    "action": "Improve code quality before including in service extraction",
                    "effort_weeks": 2
                })

        return priorities

    def _estimate_timeline(self, effort_weeks: int) -> str:
        """Estimate timeline from effort weeks."""
        if effort_weeks <= 4:
            return "1 month"
        elif effort_weeks <= 12:
            months = effort_weeks // 4
            return f"{months} months"
        else:
            months = effort_weeks // 4
            return f"{months} months ({effort_weeks} weeks)"
