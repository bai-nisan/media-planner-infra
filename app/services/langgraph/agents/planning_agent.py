"""
Planning Agent for LangGraph Multi-Agent System

Handles budget optimization, campaign planning, strategy generation, and timeline management.
"""

import logging
from typing import Any, Dict, List, Optional

from langgraph.graph import MessagesState
from langgraph.types import Command

from ..base_agent import BaseAgent
from ..tools.planning_tools import BudgetOptimizer, CampaignPlanner

logger = logging.getLogger(__name__)


class PlanningAgent(BaseAgent):
    """Agent responsible for campaign planning and budget optimization."""

    def __init__(self, config, supabase_client=None):
        super().__init__(config=config, supabase_client=supabase_client)
        self.description = "Specialized in budget optimization, campaign planning, and strategic timeline development"

        # Initialize tools
        self.budget_optimizer = BudgetOptimizer()
        self.campaign_planner = CampaignPlanner()

        # Define agent capabilities
        self.capabilities = [
            "budget_optimization",
            "campaign_strategy_development",
            "timeline_planning",
            "resource_allocation",
            "roi_forecasting",
            "milestone_planning",
        ]

        logger.info(
            f"Initialized {self.config.name} with capabilities: {', '.join(self.capabilities)}"
        )

    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize planning-specific tools."""
        from ..tools.planning_tools import BudgetOptimizer, CampaignPlanner

        tools = {
            "budget_optimizer": BudgetOptimizer(),
            "campaign_planner": CampaignPlanner(),
        }

        # Store tools as instance attributes for easy access
        self.budget_optimizer = tools["budget_optimizer"]
        self.campaign_planner = tools["campaign_planner"]

        return tools

    async def process_task(self, state: MessagesState) -> Command:
        """Process planning tasks and generate strategic recommendations."""
        try:
            # Extract task information from messages
            latest_message = state["messages"][-1] if state["messages"] else {}
            task_type = latest_message.get("task_type", "general_planning")
            task_data = latest_message.get("data", {})

            logger.info(f"Processing planning task: {task_type}")

            # Route to appropriate planning function
            if task_type == "budget_optimization":
                result = await self._handle_budget_optimization(task_data)
            elif task_type == "campaign_planning":
                result = await self._handle_campaign_planning(task_data)
            elif task_type == "timeline_planning":
                result = await self._handle_timeline_planning(task_data)
            elif task_type == "resource_allocation":
                result = await self._handle_resource_allocation(task_data)
            else:
                result = await self._handle_general_planning(task_data)

            # Create response message
            response_message = {
                "role": "assistant",
                "content": f"Planning task completed: {task_type}",
                "agent": self.name,
                "task_type": task_type,
                "result": result,
                "timestamp": self._get_timestamp(),
            }

            return Command(
                update={"messages": state["messages"] + [response_message]},
                goto="supervisor_agent",  # Return control to supervisor
            )

        except Exception as e:
            logger.error(f"Error processing planning task: {e}")
            error_message = {
                "role": "assistant",
                "content": f"Error in planning task: {str(e)}",
                "agent": self.name,
                "error": str(e),
                "timestamp": self._get_timestamp(),
            }

            return Command(
                update={"messages": state["messages"] + [error_message]},
                goto="supervisor_agent",
            )

    async def _handle_budget_optimization(
        self, task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle budget optimization requests."""
        logger.info("Executing budget optimization")

        # Extract parameters
        total_budget = task_data.get("total_budget", 50000)
        campaigns = task_data.get("campaigns", [])
        performance_data = task_data.get("performance_data")
        constraints = task_data.get("constraints")

        # Default campaigns if none provided
        if not campaigns:
            campaigns = [
                {
                    "id": "search_campaign",
                    "name": "Search Campaign",
                    "platform": "Google Ads",
                },
                {
                    "id": "social_campaign",
                    "name": "Social Media Campaign",
                    "platform": "Meta Ads",
                },
                {
                    "id": "linkedin_campaign",
                    "name": "LinkedIn Professional",
                    "platform": "LinkedIn Ads",
                },
            ]

        # Execute budget optimization
        optimization_result = await self.budget_optimizer.execute(
            total_budget=total_budget,
            campaigns=campaigns,
            performance_data=performance_data,
            constraints=constraints,
        )

        # Add strategic recommendations
        strategic_recommendations = await self._generate_budget_strategy(
            optimization_result
        )

        return {
            "optimization_result": optimization_result,
            "strategic_recommendations": strategic_recommendations,
            "execution_status": "completed",
            "recommendations_summary": {
                "primary_recommendation": (
                    strategic_recommendations[0] if strategic_recommendations else None
                ),
                "estimated_improvement": optimization_result.get(
                    "estimated_improvement", "15-25%"
                ),
                "implementation_complexity": "low",
            },
        }

    async def _handle_campaign_planning(
        self, task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle comprehensive campaign planning."""
        logger.info("Executing campaign planning")

        # Extract parameters
        campaign_objectives = task_data.get(
            "objectives",
            {
                "primary_goal": "lead_generation",
                "target_leads": 500,
                "max_cpl": 50,
                "campaign_duration_weeks": 8,
            },
        )

        budget_allocation = task_data.get(
            "budget_allocation", {"total_budget": 40000, "allocated_campaigns": []}
        )

        timeline_constraints = task_data.get("timeline_constraints")

        # Execute campaign planning
        planning_result = await self.campaign_planner.execute(
            campaign_objectives=campaign_objectives,
            budget_allocation=budget_allocation,
            timeline_constraints=timeline_constraints,
        )

        # Add implementation roadmap
        implementation_roadmap = await self._create_implementation_roadmap(
            planning_result
        )

        return {
            "planning_result": planning_result,
            "implementation_roadmap": implementation_roadmap,
            "execution_status": "completed",
            "next_steps": await self._define_next_steps(planning_result),
        }

    async def _handle_timeline_planning(
        self, task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle timeline and milestone planning."""
        logger.info("Executing timeline planning")

        # Extract parameters
        project_scope = task_data.get("project_scope", {})
        duration_weeks = task_data.get("duration_weeks", 12)
        key_deliverables = task_data.get("deliverables", [])
        resource_constraints = task_data.get("resource_constraints", {})

        # Generate timeline
        timeline_result = await self._generate_project_timeline(
            project_scope, duration_weeks, key_deliverables, resource_constraints
        )

        return {
            "timeline_result": timeline_result,
            "execution_status": "completed",
            "critical_path": timeline_result.get("critical_path", []),
            "risk_assessment": await self._assess_timeline_risks(timeline_result),
        }

    async def _handle_resource_allocation(
        self, task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle resource allocation planning."""
        logger.info("Executing resource allocation planning")

        # Extract parameters
        available_resources = task_data.get("available_resources", {})
        project_requirements = task_data.get("project_requirements", {})
        priority_matrix = task_data.get("priority_matrix", {})

        # Generate resource allocation
        allocation_result = await self._optimize_resource_allocation(
            available_resources, project_requirements, priority_matrix
        )

        return {
            "allocation_result": allocation_result,
            "execution_status": "completed",
            "utilization_metrics": allocation_result.get("utilization_metrics", {}),
            "optimization_opportunities": allocation_result.get("opportunities", []),
        }

    async def _handle_general_planning(
        self, task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle general planning requests."""
        logger.info("Executing general planning")

        # Analyze the request and provide comprehensive planning
        planning_context = task_data.get("context", "")
        requirements = task_data.get("requirements", [])
        constraints = task_data.get("constraints", [])

        # Generate comprehensive plan
        general_plan = await self._create_comprehensive_plan(
            planning_context, requirements, constraints
        )

        return {
            "general_plan": general_plan,
            "execution_status": "completed",
            "planning_methodology": "comprehensive_strategic_analysis",
            "confidence_level": "high",
        }

    async def _generate_budget_strategy(
        self, optimization_result: Dict[str, Any]
    ) -> List[str]:
        """Generate strategic recommendations based on budget optimization."""
        recommendations = []

        optimized_allocation = optimization_result.get("optimized_allocation", [])

        # Analyze allocation patterns
        platform_performance = {}
        for campaign in optimized_allocation:
            platform = campaign.get("platform", "Unknown")
            budget = campaign.get("allocated_budget", 0)
            percentage = campaign.get("allocation_percentage", 0)

            if platform not in platform_performance:
                platform_performance[platform] = {
                    "budget": 0,
                    "percentage": 0,
                    "campaigns": 0,
                }

            platform_performance[platform]["budget"] += budget
            platform_performance[platform]["percentage"] += percentage
            platform_performance[platform]["campaigns"] += 1

        # Generate platform-specific recommendations
        for platform, data in platform_performance.items():
            if data["percentage"] > 40:
                recommendations.append(
                    f"Consider diversifying from {platform} dependency ({data['percentage']:.1f}% allocation) "
                    f"to reduce platform risk"
                )
            elif data["percentage"] < 10:
                recommendations.append(
                    f"Evaluate expanding {platform} presence ({data['percentage']:.1f}% allocation) "
                    f"if performance metrics support increased investment"
                )

        # General optimization recommendations
        recommendations.extend(
            [
                "Implement 2-week budget reallocation cycles based on performance data",
                "Establish performance thresholds for automatic budget scaling",
                "Create contingency budget reserves (10-15%) for high-opportunity moments",
            ]
        )

        return recommendations[:5]  # Return top 5 recommendations

    async def _create_implementation_roadmap(
        self, planning_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create implementation roadmap from planning results."""
        campaign_plan = planning_result.get("campaign_plan", {})
        phases = campaign_plan.get("phases", [])

        roadmap = {
            "implementation_phases": [],
            "dependencies": [],
            "resource_requirements": {},
            "risk_mitigation": [],
        }

        # Process each phase
        for i, phase in enumerate(phases):
            roadmap_phase = {
                "phase_number": i + 1,
                "phase_name": phase.get("phase", f"Phase {i + 1}"),
                "duration": phase.get("duration_days", 7),
                "start_date": phase.get("start_date"),
                "end_date": phase.get("end_date"),
                "key_activities": phase.get("activities", []),
                "success_criteria": phase.get("deliverables", []),
                "resource_requirements": await self._estimate_phase_resources(phase),
            }
            roadmap["implementation_phases"].append(roadmap_phase)

        # Add dependencies
        for i in range(len(phases)):
            if i > 0:
                roadmap["dependencies"].append(
                    {
                        "prerequisite": f"Phase {i}",
                        "dependent": f"Phase {i + 1}",
                        "dependency_type": "finish_to_start",
                    }
                )

        return roadmap

    async def _define_next_steps(
        self, planning_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Define immediate next steps from planning results."""
        next_steps = []

        campaign_plan = planning_result.get("campaign_plan", {})
        phases = campaign_plan.get("phases", [])

        if phases:
            first_phase = phases[0]
            activities = first_phase.get("activities", [])

            # Convert first phase activities to actionable steps
            for i, activity in enumerate(activities[:3]):  # Top 3 activities
                next_steps.append(
                    {
                        "step_number": i + 1,
                        "action": activity,
                        "priority": "high" if i == 0 else "medium",
                        "estimated_duration": "1-2 days",
                        "assigned_to": "campaign_team",
                        "dependencies": [],
                        "success_metrics": [f"Complete {activity.lower()}"],
                    }
                )

        # Add strategic next steps
        next_steps.extend(
            [
                {
                    "step_number": len(next_steps) + 1,
                    "action": "Set up performance tracking dashboard",
                    "priority": "high",
                    "estimated_duration": "1 day",
                    "assigned_to": "analytics_team",
                    "dependencies": ["Campaign setup completion"],
                    "success_metrics": [
                        "Dashboard operational",
                        "Real-time data flowing",
                    ],
                },
                {
                    "step_number": len(next_steps) + 2,
                    "action": "Schedule first optimization review",
                    "priority": "medium",
                    "estimated_duration": "30 minutes",
                    "assigned_to": "planning_team",
                    "dependencies": ["Campaign launch"],
                    "success_metrics": [
                        "Review meeting scheduled",
                        "Success criteria defined",
                    ],
                },
            ]
        )

        return next_steps

    async def _generate_project_timeline(
        self,
        project_scope: Dict[str, Any],
        duration_weeks: int,
        deliverables: List[str],
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate comprehensive project timeline."""
        from datetime import datetime, timedelta

        timeline = {
            "project_overview": {
                "total_duration_weeks": duration_weeks,
                "start_date": datetime.utcnow().date().isoformat(),
                "end_date": (datetime.utcnow() + timedelta(weeks=duration_weeks))
                .date()
                .isoformat(),
                "total_deliverables": len(deliverables),
            },
            "phases": [],
            "milestones": [],
            "critical_path": [],
            "resource_timeline": {},
        }

        # Generate phases based on duration
        phase_duration = max(1, duration_weeks // 3)  # Divide into 3 main phases

        phases = [
            {
                "name": "Initiation & Setup",
                "activities": [
                    "Project kickoff",
                    "Resource allocation",
                    "Initial setup",
                ],
            },
            {
                "name": "Execution & Development",
                "activities": ["Core implementation", "Testing", "Optimization"],
            },
            {
                "name": "Delivery & Closure",
                "activities": [
                    "Final delivery",
                    "Performance review",
                    "Project closure",
                ],
            },
        ]

        current_date = datetime.utcnow()
        for i, phase in enumerate(phases):
            phase_start = current_date + timedelta(weeks=i * phase_duration)
            phase_end = phase_start + timedelta(weeks=phase_duration)

            timeline["phases"].append(
                {
                    "phase_number": i + 1,
                    "phase_name": phase["name"],
                    "start_date": phase_start.date().isoformat(),
                    "end_date": phase_end.date().isoformat(),
                    "duration_weeks": phase_duration,
                    "activities": phase["activities"],
                    "deliverables": (
                        deliverables[i::3] if deliverables else []
                    ),  # Distribute deliverables
                }
            )

        # Generate milestones
        for i, phase in enumerate(timeline["phases"]):
            timeline["milestones"].append(
                {
                    "milestone_name": f"{phase['phase_name']} Complete",
                    "date": phase["end_date"],
                    "description": f"Completion of {phase['phase_name'].lower()} phase",
                    "success_criteria": phase["deliverables"],
                }
            )

        # Mock critical path
        timeline["critical_path"] = [
            {"activity": "Project setup", "duration_days": 3, "float": 0},
            {"activity": "Core implementation", "duration_days": 14, "float": 0},
            {"activity": "Testing & optimization", "duration_days": 7, "float": 2},
            {"activity": "Final delivery", "duration_days": 3, "float": 0},
        ]

        return timeline

    async def _optimize_resource_allocation(
        self,
        available_resources: Dict[str, Any],
        requirements: Dict[str, Any],
        priority_matrix: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Optimize resource allocation across projects."""
        allocation = {
            "resource_assignments": {},
            "utilization_metrics": {},
            "optimization_score": 0.85,
            "opportunities": [],
        }

        # Mock resource allocation optimization
        resource_types = ["budget", "personnel", "technology", "time"]

        for resource_type in resource_types:
            available = available_resources.get(resource_type, 100)
            required = requirements.get(resource_type, 80)

            utilization = min(required / available, 1.0) if available > 0 else 0

            allocation["resource_assignments"][resource_type] = {
                "available": available,
                "allocated": min(required, available),
                "utilization_percentage": round(utilization * 100, 1),
                "remaining": max(0, available - required),
            }

            allocation["utilization_metrics"][resource_type] = {
                "efficiency_score": round(utilization * 10, 1),
                "optimization_potential": (
                    "high"
                    if utilization < 0.7
                    else "medium" if utilization < 0.9 else "low"
                ),
            }

            # Generate opportunities
            if utilization < 0.7:
                allocation["opportunities"].append(
                    {
                        "resource_type": resource_type,
                        "opportunity": f"Underutilized {resource_type} - consider reallocation",
                        "potential_improvement": f"{round((0.85 - utilization) * 100, 1)}% increase possible",
                    }
                )
            elif utilization > 0.95:
                allocation["opportunities"].append(
                    {
                        "resource_type": resource_type,
                        "opportunity": f"Over-allocated {resource_type} - risk of bottleneck",
                        "potential_improvement": "Consider additional resources or scope adjustment",
                    }
                )

        return allocation

    async def _create_comprehensive_plan(
        self, context: str, requirements: List[str], constraints: List[str]
    ) -> Dict[str, Any]:
        """Create comprehensive strategic plan."""
        plan = {
            "executive_summary": "Comprehensive strategic plan based on provided context and requirements",
            "objectives": [],
            "strategy": {},
            "implementation": {},
            "success_metrics": [],
            "risk_assessment": {},
        }

        # Generate objectives from requirements
        for i, requirement in enumerate(requirements[:5]):  # Limit to 5 objectives
            plan["objectives"].append(
                {
                    "objective_id": f"OBJ-{i+1}",
                    "description": requirement,
                    "priority": "high" if i < 2 else "medium",
                    "success_criteria": [f"Achieve {requirement.lower()}"],
                    "timeline": "short_term" if i < 2 else "medium_term",
                }
            )

        # Strategy framework
        plan["strategy"] = {
            "approach": "phased_implementation",
            "key_strategies": [
                "Data-driven decision making",
                "Iterative optimization",
                "Risk mitigation focus",
                "Stakeholder alignment",
            ],
            "differentiation": "Leveraging analytics and automation for competitive advantage",
        }

        # Implementation framework
        plan["implementation"] = {
            "methodology": "agile_project_management",
            "phases": [
                {"phase": "Planning & Setup", "duration": "2 weeks"},
                {"phase": "Implementation", "duration": "6-8 weeks"},
                {"phase": "Optimization", "duration": "2-4 weeks"},
            ],
            "resource_requirements": {
                "team_size": "3-5 people",
                "technology_stack": "Analytics platform, automation tools",
                "budget_estimate": "$25,000 - $50,000",
            },
        }

        # Success metrics
        plan["success_metrics"] = [
            {"metric": "ROI", "target": "4:1 minimum", "measurement": "monthly"},
            {
                "metric": "Performance improvement",
                "target": "25% increase",
                "measurement": "quarterly",
            },
            {
                "metric": "Efficiency gains",
                "target": "30% time savings",
                "measurement": "ongoing",
            },
        ]

        # Risk assessment
        plan["risk_assessment"] = {
            "high_risks": ["Budget constraints", "Resource availability"],
            "medium_risks": ["Technology integration", "Stakeholder alignment"],
            "mitigation_strategies": [
                "Regular stakeholder communication",
                "Phased implementation approach",
                "Contingency planning",
            ],
        }

        return plan

    async def _estimate_phase_resources(self, phase: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate resources required for a phase."""
        activities = phase.get("activities", [])
        duration_days = phase.get("duration_days", 7)

        # Basic resource estimation
        base_hours_per_activity = 8
        total_hours = len(activities) * base_hours_per_activity

        return {
            "estimated_hours": total_hours,
            "team_size_required": max(1, total_hours // (duration_days * 8)),
            "skill_requirements": [
                "project_management",
                "digital_marketing",
                "analytics",
            ],
            "tools_required": ["project_management_software", "analytics_platform"],
            "budget_estimate": total_hours * 75,  # $75/hour rate
        }

    async def _assess_timeline_risks(
        self, timeline_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess risks in the project timeline."""
        risks = {
            "high_risks": [],
            "medium_risks": [],
            "low_risks": [],
            "mitigation_strategies": [],
        }

        # Analyze critical path
        critical_path = timeline_result.get("critical_path", [])
        phases = timeline_result.get("phases", [])

        # Check for tight timelines
        total_weeks = timeline_result.get("project_overview", {}).get(
            "total_duration_weeks", 12
        )
        if total_weeks < 8:
            risks["high_risks"].append(
                {
                    "risk": "Compressed timeline",
                    "impact": "High",
                    "probability": "Medium",
                    "description": "Limited time may affect quality and thoroughness",
                }
            )

        # Check critical path
        if len(critical_path) > 4:
            risks["medium_risks"].append(
                {
                    "risk": "Complex critical path",
                    "impact": "Medium",
                    "probability": "Medium",
                    "description": "Multiple critical activities increase delay risk",
                }
            )

        # Resource risks
        if len(phases) > 3:
            risks["medium_risks"].append(
                {
                    "risk": "Resource coordination complexity",
                    "impact": "Medium",
                    "probability": "High",
                    "description": "Multiple phases require careful resource coordination",
                }
            )

        # Mitigation strategies
        risks["mitigation_strategies"] = [
            "Build 10-15% buffer time into critical activities",
            "Identify alternative resources for key activities",
            "Implement weekly progress reviews and early warning systems",
            "Prepare contingency plans for high-risk activities",
        ]

        return risks
