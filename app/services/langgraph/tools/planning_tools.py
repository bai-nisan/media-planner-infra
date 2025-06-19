"""
Planning Tools for LangGraph Multi-Agent System

Tools for budget optimization, campaign planning, strategy generation, and performance prediction.
"""

import logging
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Base class for all planning tools."""
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """Execute the tool."""
        pass


class BudgetOptimizer(BaseTool):
    """Tool for optimizing budget allocation across channels and campaigns."""
    
    def __init__(self):
        self.name = "budget_optimizer"
        self.description = "Optimizes budget allocation using historical performance data and constraints"
        self.optimization_methods = ["performance_based", "equal_distribution", "weighted_allocation"]
    
    async def optimize_budget(
        self, 
        total_budget: float,
        campaigns: List[Dict[str, Any]],
        performance_data: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Optimize budget allocation across campaigns."""
        try:
            logger.info(f"Optimizing budget of ${total_budget} across {len(campaigns)} campaigns")
            
            # Default constraints
            default_constraints = {
                "min_budget_per_campaign": total_budget * 0.05,  # 5% minimum
                "max_budget_per_campaign": total_budget * 0.6,   # 60% maximum
                "platform_limits": {
                    "Google Ads": total_budget * 0.7,  # Max 70%
                    "Meta Ads": total_budget * 0.7,   # Max 70%
                    "LinkedIn Ads": total_budget * 0.3  # Max 30%
                }
            }
            
            constraints = {**default_constraints, **(constraints or {})}
            
            # Performance-based allocation if data available
            if performance_data and performance_data.get("historical_performance"):
                allocation = await self._performance_based_allocation(
                    total_budget, campaigns, performance_data, constraints
                )
            else:
                # Equal distribution with platform weighting
                allocation = await self._weighted_allocation(
                    total_budget, campaigns, constraints
                )
            
            # Validate allocation
            validation_result = await self._validate_allocation(allocation, constraints)
            
            return {
                "optimized_allocation": allocation,
                "validation": validation_result,
                "optimization_method": "performance_based" if performance_data else "weighted_allocation",
                "total_allocated": sum(camp["allocated_budget"] for camp in allocation),
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "total_budget": total_budget,
                    "campaign_count": len(campaigns),
                    "constraints_applied": list(constraints.keys())
                }
            }
            
        except Exception as e:
            logger.error(f"Error optimizing budget: {e}")
            raise
    
    async def _performance_based_allocation(
        self, 
        total_budget: float, 
        campaigns: List[Dict[str, Any]], 
        performance_data: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Allocate budget based on historical performance."""
        # Mock performance-based calculation
        historical_data = performance_data.get("historical_performance", {})
        
        allocation = []
        remaining_budget = total_budget
        
        for campaign in campaigns:
            campaign_id = campaign.get("id", campaign.get("name"))
            platform = campaign.get("platform", "Unknown")
            
            # Get historical ROAS or default to 2.0
            historical_roas = historical_data.get(campaign_id, {}).get("roas", 2.0)
            
            # Calculate performance score (higher ROAS = more budget)
            performance_score = min(historical_roas / 2.0, 3.0)  # Cap at 3x multiplier
            
            # Base allocation with performance multiplier
            base_allocation = total_budget / len(campaigns)
            performance_allocation = base_allocation * performance_score
            
            # Apply constraints
            min_budget = constraints["min_budget_per_campaign"]
            max_budget = constraints["max_budget_per_campaign"]
            platform_limit = constraints["platform_limits"].get(platform, total_budget)
            
            allocated_budget = max(
                min_budget,
                min(performance_allocation, max_budget, platform_limit, remaining_budget)
            )
            
            allocation.append({
                "campaign_id": campaign_id,
                "campaign_name": campaign.get("name", campaign_id),
                "platform": platform,
                "allocated_budget": round(allocated_budget, 2),
                "performance_score": round(performance_score, 2),
                "historical_roas": historical_roas,
                "allocation_percentage": round((allocated_budget / total_budget) * 100, 1)
            })
            
            remaining_budget -= allocated_budget
        
        return allocation
    
    async def _weighted_allocation(
        self, 
        total_budget: float, 
        campaigns: List[Dict[str, Any]], 
        constraints: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Allocate budget using platform weighting."""
        platform_weights = {
            "Google Ads": 0.4,
            "Meta Ads": 0.35,
            "LinkedIn Ads": 0.15,
            "Twitter Ads": 0.1
        }
        
        allocation = []
        
        # Group campaigns by platform
        campaigns_by_platform = {}
        for campaign in campaigns:
            platform = campaign.get("platform", "Unknown")
            if platform not in campaigns_by_platform:
                campaigns_by_platform[platform] = []
            campaigns_by_platform[platform].append(campaign)
        
        # Allocate budget per platform
        for platform, platform_campaigns in campaigns_by_platform.items():
            platform_weight = platform_weights.get(platform, 0.1)
            platform_budget = total_budget * platform_weight
            budget_per_campaign = platform_budget / len(platform_campaigns)
            
            for campaign in platform_campaigns:
                campaign_id = campaign.get("id", campaign.get("name"))
                
                # Apply constraints
                min_budget = constraints["min_budget_per_campaign"]
                max_budget = constraints["max_budget_per_campaign"]
                
                allocated_budget = max(min_budget, min(budget_per_campaign, max_budget))
                
                allocation.append({
                    "campaign_id": campaign_id,
                    "campaign_name": campaign.get("name", campaign_id),
                    "platform": platform,
                    "allocated_budget": round(allocated_budget, 2),
                    "platform_weight": platform_weight,
                    "allocation_percentage": round((allocated_budget / total_budget) * 100, 1)
                })
        
        return allocation
    
    async def _validate_allocation(
        self, 
        allocation: List[Dict[str, Any]], 
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate budget allocation against constraints."""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "summary": {}
        }
        
        total_allocated = sum(camp["allocated_budget"] for camp in allocation)
        
        # Check total budget
        validation_result["summary"]["total_allocated"] = total_allocated
        validation_result["summary"]["campaign_count"] = len(allocation)
        
        # Check individual campaign constraints
        min_budget = constraints["min_budget_per_campaign"]
        max_budget = constraints["max_budget_per_campaign"]
        
        for campaign in allocation:
            budget = campaign["allocated_budget"]
            
            if budget < min_budget:
                validation_result["errors"].append(
                    f"Campaign {campaign['campaign_name']} budget ${budget} below minimum ${min_budget}"
                )
                validation_result["is_valid"] = False
            
            if budget > max_budget:
                validation_result["warnings"].append(
                    f"Campaign {campaign['campaign_name']} budget ${budget} above recommended maximum ${max_budget}"
                )
        
        # Check platform limits
        platform_totals = {}
        for campaign in allocation:
            platform = campaign["platform"]
            platform_totals[platform] = platform_totals.get(platform, 0) + campaign["allocated_budget"]
        
        for platform, total in platform_totals.items():
            limit = constraints["platform_limits"].get(platform)
            if limit and total > limit:
                validation_result["warnings"].append(
                    f"Platform {platform} total ${total} exceeds limit ${limit}"
                )
        
        return validation_result
    
    async def execute(
        self, 
        total_budget: float,
        campaigns: List[Dict[str, Any]],
        performance_data: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute budget optimization."""
        return await self.optimize_budget(total_budget, campaigns, performance_data, constraints)


class CampaignPlanner(BaseTool):
    """Tool for developing campaign strategies and timelines."""
    
    def __init__(self):
        self.name = "campaign_planner"
        self.description = "Creates comprehensive campaign plans with timelines and milestones"
    
    async def create_campaign_plan(
        self,
        campaign_objectives: Dict[str, Any],
        budget_allocation: Dict[str, Any],
        timeline_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a comprehensive campaign plan."""
        try:
            logger.info(f"Creating campaign plan for objectives: {campaign_objectives.get('primary_goal')}")
            
            # Default timeline constraints
            default_timeline = {
                "campaign_duration_weeks": 8,
                "setup_phase_days": 7,
                "optimization_phase_days": 14,
                "reporting_frequency": "weekly"
            }
            
            timeline_constraints = {**default_timeline, **(timeline_constraints or {})}
            
            # Generate campaign phases
            phases = await self._generate_campaign_phases(timeline_constraints)
            
            # Create milestone timeline
            milestones = await self._create_milestones(phases, campaign_objectives)
            
            # Generate KPIs and success metrics
            kpis = await self._define_kpis(campaign_objectives)
            
            # Create execution checklist
            checklist = await self._create_execution_checklist(phases, budget_allocation)
            
            return {
                "campaign_plan": {
                    "objectives": campaign_objectives,
                    "phases": phases,
                    "milestones": milestones,
                    "kpis": kpis,
                    "execution_checklist": checklist,
                    "timeline_summary": {
                        "total_duration_weeks": timeline_constraints["campaign_duration_weeks"],
                        "start_date": datetime.utcnow().date().isoformat(),
                        "estimated_end_date": (datetime.utcnow() + timedelta(weeks=timeline_constraints["campaign_duration_weeks"])).date().isoformat()
                    }
                },
                "metadata": {
                    "created_at": datetime.utcnow().isoformat(),
                    "planning_method": "strategic_phased_approach",
                    "total_budget": budget_allocation.get("total_budget", 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating campaign plan: {e}")
            raise
    
    async def _generate_campaign_phases(self, timeline_constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate campaign execution phases."""
        total_weeks = timeline_constraints["campaign_duration_weeks"]
        
        phases = [
            {
                "phase": "Setup & Launch",
                "duration_days": timeline_constraints["setup_phase_days"],
                "activities": [
                    "Campaign setup and configuration",
                    "Creative asset preparation",
                    "Audience targeting setup",
                    "Tracking and analytics setup",
                    "Campaign launch"
                ],
                "deliverables": [
                    "Live campaigns across selected platforms",
                    "Tracking dashboard configured",
                    "Initial performance baseline"
                ]
            },
            {
                "phase": "Optimization",
                "duration_days": timeline_constraints["optimization_phase_days"],
                "activities": [
                    "Performance monitoring",
                    "A/B testing implementation",
                    "Budget reallocation based on performance",
                    "Creative optimization",
                    "Audience refinement"
                ],
                "deliverables": [
                    "Optimized campaign performance",
                    "Performance improvement report",
                    "Refined targeting parameters"
                ]
            },
            {
                "phase": "Scale & Maintain",
                "duration_days": (total_weeks * 7) - timeline_constraints["setup_phase_days"] - timeline_constraints["optimization_phase_days"],
                "activities": [
                    "Scaled campaign execution",
                    "Continuous performance monitoring",
                    "Regular optimization cycles",
                    "Performance reporting",
                    "ROI analysis"
                ],
                "deliverables": [
                    "Sustained campaign performance",
                    "Regular performance reports",
                    "Final campaign analysis"
                ]
            }
        ]
        
        # Calculate phase dates
        current_date = datetime.utcnow()
        for phase in phases:
            phase["start_date"] = current_date.date().isoformat()
            phase["end_date"] = (current_date + timedelta(days=phase["duration_days"])).date().isoformat()
            current_date += timedelta(days=phase["duration_days"])
        
        return phases
    
    async def _create_milestones(
        self, 
        phases: List[Dict[str, Any]], 
        objectives: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create campaign milestones."""
        milestones = []
        
        # Phase-based milestones
        for i, phase in enumerate(phases):
            if phase["phase"] == "Setup & Launch":
                milestones.append({
                    "milestone": "Campaign Launch Complete",
                    "date": phase["end_date"],
                    "success_criteria": [
                        "All campaigns live and running",
                        "Tracking properly configured",
                        "Initial impressions recorded"
                    ],
                    "phase": phase["phase"]
                })
            
            elif phase["phase"] == "Optimization":
                milestones.append({
                    "milestone": "Optimization Phase Complete",
                    "date": phase["end_date"],
                    "success_criteria": [
                        "Performance improvement vs baseline",
                        "Optimized budget allocation",
                        "A/B tests concluded"
                    ],
                    "phase": phase["phase"]
                })
            
            elif phase["phase"] == "Scale & Maintain":
                # Add weekly milestones for this phase
                phase_start = datetime.fromisoformat(phase["start_date"])
                phase_duration = phase["duration_days"]
                
                for week in range(0, phase_duration, 7):
                    milestone_date = (phase_start + timedelta(days=week)).date().isoformat()
                    milestones.append({
                        "milestone": f"Week {week//7 + 1} Performance Review",
                        "date": milestone_date,
                        "success_criteria": [
                            "Performance metrics reviewed",
                            "Budget utilization on track",
                            "KPIs progress assessed"
                        ],
                        "phase": phase["phase"]
                    })
        
        # Objective-based milestones
        primary_goal = objectives.get("primary_goal")
        if primary_goal == "lead_generation":
            milestones.append({
                "milestone": "Lead Generation Target",
                "date": phases[-1]["end_date"],
                "success_criteria": [
                    f"Target leads generated: {objectives.get('target_leads', 'TBD')}",
                    f"Cost per lead under: ${objectives.get('max_cpl', 'TBD')}",
                    "Lead quality meets requirements"
                ],
                "phase": "Campaign Completion"
            })
        
        elif primary_goal == "brand_awareness":
            milestones.append({
                "milestone": "Brand Awareness Target",
                "date": phases[-1]["end_date"],
                "success_criteria": [
                    f"Target impressions: {objectives.get('target_impressions', 'TBD')}",
                    f"Brand lift: {objectives.get('target_brand_lift', 'TBD')}%",
                    "Reach target achieved"
                ],
                "phase": "Campaign Completion"
            })
        
        return sorted(milestones, key=lambda x: x["date"])
    
    async def _define_kpis(self, objectives: Dict[str, Any]) -> Dict[str, Any]:
        """Define KPIs based on campaign objectives."""
        primary_goal = objectives.get("primary_goal", "awareness")
        
        # Base KPIs for all campaigns
        base_kpis = {
            "reach_metrics": {
                "impressions": {"target": objectives.get("target_impressions"), "unit": "count"},
                "reach": {"target": objectives.get("target_reach"), "unit": "unique_users"},
                "frequency": {"target": "2-3", "unit": "avg_frequency"}
            },
            "engagement_metrics": {
                "ctr": {"target": "2.5%", "unit": "percentage"},
                "engagement_rate": {"target": "3%", "unit": "percentage"},
                "video_completion_rate": {"target": "75%", "unit": "percentage"}
            },
            "efficiency_metrics": {
                "cpm": {"target": objectives.get("target_cpm", "$15"), "unit": "cost_per_mille"},
                "cpc": {"target": objectives.get("target_cpc", "$2.50"), "unit": "cost_per_click"}
            }
        }
        
        # Goal-specific KPIs
        goal_specific_kpis = {}
        
        if primary_goal == "lead_generation":
            goal_specific_kpis["conversion_metrics"] = {
                "leads_generated": {"target": objectives.get("target_leads"), "unit": "count"},
                "cost_per_lead": {"target": objectives.get("max_cpl"), "unit": "currency"},
                "lead_conversion_rate": {"target": "5%", "unit": "percentage"},
                "lead_quality_score": {"target": "7/10", "unit": "score"}
            }
        
        elif primary_goal == "sales":
            goal_specific_kpis["revenue_metrics"] = {
                "revenue_generated": {"target": objectives.get("target_revenue"), "unit": "currency"},
                "roas": {"target": objectives.get("target_roas", "4:1"), "unit": "ratio"},
                "cost_per_acquisition": {"target": objectives.get("max_cpa"), "unit": "currency"},
                "conversion_rate": {"target": "3%", "unit": "percentage"}
            }
        
        elif primary_goal == "brand_awareness":
            goal_specific_kpis["awareness_metrics"] = {
                "brand_lift": {"target": objectives.get("target_brand_lift", "10%"), "unit": "percentage"},
                "share_of_voice": {"target": "15%", "unit": "percentage"},
                "brand_mention_increase": {"target": "25%", "unit": "percentage"}
            }
        
        return {**base_kpis, **goal_specific_kpis}
    
    async def _create_execution_checklist(
        self, 
        phases: List[Dict[str, Any]], 
        budget_allocation: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Create execution checklist organized by phase."""
        checklist = {}
        
        for phase in phases:
            phase_name = phase["phase"]
            checklist[phase_name] = []
            
            if phase_name == "Setup & Launch":
                checklist[phase_name] = [
                    {"task": "Set up Google Ads campaigns", "priority": "high", "estimated_hours": 4},
                    {"task": "Configure Meta Ads campaigns", "priority": "high", "estimated_hours": 3},
                    {"task": "Prepare creative assets", "priority": "high", "estimated_hours": 8},
                    {"task": "Set up conversion tracking", "priority": "critical", "estimated_hours": 2},
                    {"task": "Configure analytics dashboards", "priority": "medium", "estimated_hours": 3},
                    {"task": "Launch campaigns", "priority": "critical", "estimated_hours": 1},
                    {"task": "Verify tracking and attribution", "priority": "critical", "estimated_hours": 2}
                ]
            
            elif phase_name == "Optimization":
                checklist[phase_name] = [
                    {"task": "Daily performance monitoring", "priority": "high", "estimated_hours": 1},
                    {"task": "Weekly performance analysis", "priority": "high", "estimated_hours": 3},
                    {"task": "A/B test creative variations", "priority": "medium", "estimated_hours": 4},
                    {"task": "Optimize audience targeting", "priority": "high", "estimated_hours": 2},
                    {"task": "Adjust budget allocation", "priority": "high", "estimated_hours": 1},
                    {"task": "Optimize bidding strategies", "priority": "medium", "estimated_hours": 2}
                ]
            
            elif phase_name == "Scale & Maintain":
                checklist[phase_name] = [
                    {"task": "Scale high-performing campaigns", "priority": "high", "estimated_hours": 2},
                    {"task": "Regular performance reviews", "priority": "high", "estimated_hours": 2},
                    {"task": "Prepare weekly reports", "priority": "medium", "estimated_hours": 3},
                    {"task": "Continuous optimization", "priority": "medium", "estimated_hours": 2},
                    {"task": "Monitor competitive landscape", "priority": "low", "estimated_hours": 1},
                    {"task": "Prepare final campaign analysis", "priority": "high", "estimated_hours": 4}
                ]
        
        return checklist
    
    async def execute(
        self,
        campaign_objectives: Dict[str, Any],
        budget_allocation: Dict[str, Any],
        timeline_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute campaign planning."""
        return await self.create_campaign_plan(campaign_objectives, budget_allocation, timeline_constraints) 