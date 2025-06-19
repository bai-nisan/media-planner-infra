"""
Domain Services

Services that encapsulate complex business logic that doesn't naturally fit
within a single entity or value object. These services orchestrate operations
across multiple domain objects.
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple

from .entities import Budget, BudgetAllocation, Campaign, MediaChannel
from .exceptions import BudgetExceededError, InsufficientDataError, OptimizationError
from .value_objects import Money, Percentage


class AllocationStrategy(str, Enum):
    """Budget allocation strategies available in the system."""

    EQUAL_SPLIT = "equal_split"
    PERFORMANCE_WEIGHTED = "performance_weighted"
    MANUAL = "manual"
    COST_EFFICIENCY = "cost_efficiency"
    REACH_WEIGHTED = "reach_weighted"


class OptimizationType(str, Enum):
    """Types of campaign optimizations available."""

    BUDGET_REALLOCATION = "budget_reallocation"
    CHANNEL_OPTIMIZATION = "channel_optimization"
    PERFORMANCE_IMPROVEMENT = "performance_improvement"
    COST_REDUCTION = "cost_reduction"


class BudgetAllocationService:
    """
    Domain service for complex budget allocation operations.
    
    Handles multi-channel budget allocation using various strategies
    and business rules that span multiple entities.
    """

    def allocate_budget(
        self,
        budget: Budget,
        channels: List[MediaChannel],
        strategy: AllocationStrategy,
        performance_data: Optional[Dict[str, Dict[str, float]]] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[BudgetAllocation]:
        """
        Allocate budget across multiple channels using the specified strategy.
        
        Args:
            budget: The budget to allocate
            channels: List of media channels to allocate to
            strategy: Allocation strategy to use
            performance_data: Historical performance data for channels
            constraints: Additional constraints (min/max allocations, etc.)
        
        Returns:
            List of budget allocations
            
        Raises:
            BudgetExceededError: If allocations exceed available budget
            InsufficientDataError: If required data is missing for strategy
        """
        if not channels:
            raise ValueError("Cannot allocate budget to empty channel list")

        # Filter out inactive channels
        active_channels = [ch for ch in channels if ch.is_active]
        if not active_channels:
            raise ValueError("No active channels available for allocation")

        constraints = constraints or {}
        
        if strategy == AllocationStrategy.EQUAL_SPLIT:
            return self._allocate_equal_split(budget, active_channels)
        
        elif strategy == AllocationStrategy.PERFORMANCE_WEIGHTED:
            if not performance_data:
                raise InsufficientDataError(
                    "Performance data required for performance-weighted allocation",
                    required_fields=["performance_data"],
                    missing_fields=["performance_data"],
                )
            return self._allocate_performance_weighted(
                budget, active_channels, performance_data, constraints
            )
        
        elif strategy == AllocationStrategy.COST_EFFICIENCY:
            if not performance_data:
                raise InsufficientDataError(
                    "Performance data required for cost-efficiency allocation",
                    required_fields=["performance_data"],
                    missing_fields=["performance_data"],
                )
            return self._allocate_cost_efficiency(
                budget, active_channels, performance_data, constraints
            )
        
        elif strategy == AllocationStrategy.REACH_WEIGHTED:
            return self._allocate_reach_weighted(budget, active_channels, constraints)
        
        else:
            raise ValueError(f"Unsupported allocation strategy: {strategy}")

    def _allocate_equal_split(
        self, budget: Budget, channels: List[MediaChannel]
    ) -> List[BudgetAllocation]:
        """Allocate budget equally across all channels."""
        remaining_budget = budget.get_remaining_budget()
        amount_per_channel = remaining_budget.divide(len(channels))
        
        allocations = []
        for channel in channels:
            allocation = budget.add_allocation(channel, amount_per_channel)
            allocations.append(allocation)
        
        return allocations

    def _allocate_performance_weighted(
        self,
        budget: Budget,
        channels: List[MediaChannel],
        performance_data: Dict[str, Dict[str, float]],
        constraints: Dict[str, Any],
    ) -> List[BudgetAllocation]:
        """Allocate budget based on historical performance metrics."""
        # Calculate performance scores for each channel
        channel_scores = {}
        total_score = 0
        
        for channel in channels:
            channel_data = performance_data.get(channel.name, {})
            
            # Default performance metrics if not available
            conversion_rate = channel_data.get("conversion_rate", 0.01)
            click_through_rate = channel_data.get("click_through_rate", 0.02)
            cost_per_acquisition = channel_data.get("cost_per_acquisition", 100.0)
            
            # Calculate composite performance score
            # Higher conversion rate and CTR are better, lower CPA is better
            performance_score = (
                conversion_rate * 0.4 +
                click_through_rate * 0.3 +
                (1.0 / max(cost_per_acquisition, 1.0)) * 100 * 0.3
            )
            
            channel_scores[channel.name] = performance_score
            total_score += performance_score

        if total_score == 0:
            # Fallback to equal split if no performance data
            return self._allocate_equal_split(budget, channels)

        # Allocate based on performance weights
        remaining_budget = budget.get_remaining_budget()
        allocations = []
        
        for channel in channels:
            weight = channel_scores[channel.name] / total_score
            
            # Apply min/max constraints if specified
            min_percentage = constraints.get(f"{channel.name}_min_percentage", 0.05)  # 5% minimum
            max_percentage = constraints.get(f"{channel.name}_max_percentage", 0.60)  # 60% maximum
            
            weight = max(min_percentage, min(weight, max_percentage))
            allocation_amount = remaining_budget.multiply(weight)
            
            allocation = budget.add_allocation(channel, allocation_amount)
            allocations.append(allocation)
        
        return allocations

    def _allocate_cost_efficiency(
        self,
        budget: Budget,
        channels: List[MediaChannel],
        performance_data: Dict[str, Dict[str, float]],
        constraints: Dict[str, Any],
    ) -> List[BudgetAllocation]:
        """Allocate budget based on cost efficiency (lowest cost per acquisition)."""
        channel_efficiency = {}
        
        for channel in channels:
            channel_data = performance_data.get(channel.name, {})
            cost_per_acquisition = channel_data.get("cost_per_acquisition", 100.0)
            
            # Lower CPA = higher efficiency
            efficiency = 1.0 / max(cost_per_acquisition, 1.0)
            channel_efficiency[channel.name] = efficiency

        total_efficiency = sum(channel_efficiency.values())
        if total_efficiency == 0:
            return self._allocate_equal_split(budget, channels)

        remaining_budget = budget.get_remaining_budget()
        allocations = []
        
        for channel in channels:
            weight = channel_efficiency[channel.name] / total_efficiency
            allocation_amount = remaining_budget.multiply(weight)
            
            allocation = budget.add_allocation(channel, allocation_amount)
            allocations.append(allocation)
        
        return allocations

    def _allocate_reach_weighted(
        self,
        budget: Budget,
        channels: List[MediaChannel],
        constraints: Dict[str, Any],
    ) -> List[BudgetAllocation]:
        """Allocate budget based on potential reach of each channel."""
        # Default reach multipliers by channel type
        reach_multipliers = {
            "social": 1.2,
            "search": 1.0,
            "display": 0.8,
            "video": 1.1,
            "email": 0.6,
            "print": 0.4,
        }
        
        channel_reach = {}
        total_reach = 0
        
        for channel in channels:
            multiplier = reach_multipliers.get(channel.channel_type, 1.0)
            # Apply custom reach data if provided in constraints
            custom_reach = constraints.get(f"{channel.name}_reach_multiplier")
            if custom_reach:
                multiplier = custom_reach
            
            channel_reach[channel.name] = multiplier
            total_reach += multiplier

        remaining_budget = budget.get_remaining_budget()
        allocations = []
        
        for channel in channels:
            weight = channel_reach[channel.name] / total_reach
            allocation_amount = remaining_budget.multiply(weight)
            
            allocation = budget.add_allocation(channel, allocation_amount)
            allocations.append(allocation)
        
        return allocations

    def rebalance_allocations(
        self,
        budget: Budget,
        new_performance_data: Dict[str, Dict[str, float]],
        strategy: AllocationStrategy = AllocationStrategy.PERFORMANCE_WEIGHTED,
    ) -> List[BudgetAllocation]:
        """
        Rebalance existing budget allocations based on new performance data.
        
        This removes existing allocations and creates new ones based on
        updated performance metrics.
        """
        # Get current channels
        current_allocations = budget.get_all_allocations()
        channels = [alloc.channel for alloc in current_allocations]
        
        # Clear existing allocations
        for allocation in current_allocations:
            budget.remove_allocation(allocation.channel)
        
        # Reallocate with new strategy and data
        return self.allocate_budget(
            budget=budget,
            channels=channels,
            strategy=strategy,
            performance_data=new_performance_data,
        )


class CampaignOptimizationService:
    """
    Domain service for campaign optimization operations.
    
    Analyzes campaign performance and suggests or implements optimizations
    across campaigns, budgets, and channels.
    """

    def __init__(self, budget_allocation_service: BudgetAllocationService):
        self.budget_allocation_service = budget_allocation_service

    def analyze_campaign_performance(
        self, campaign: Campaign
    ) -> Dict[str, Any]:
        """
        Analyze campaign performance and identify optimization opportunities.
        
        Returns a comprehensive analysis including metrics, issues, and recommendations.
        """
        analysis = {
            "campaign_id": campaign.campaign_id,
            "campaign_name": campaign.name,
            "current_status": campaign.status.value,
            "budget_utilization": float(campaign.get_budget_utilization().value),
            "issues": [],
            "recommendations": [],
            "performance_score": 0.0,
        }

        # Analyze budget utilization
        utilization = campaign.get_budget_utilization()
        if utilization.value > 90:
            analysis["issues"].append("High budget utilization - risk of overspend")
            analysis["recommendations"].append("Consider increasing budget or pausing low-performing channels")
        elif utilization.value < 20:
            analysis["issues"].append("Low budget utilization - underperforming campaign")
            analysis["recommendations"].append("Review targeting and channel allocations")

        # Analyze channel performance
        allocations = campaign.budget.get_all_allocations()
        if len(allocations) > 1:
            analysis["recommendations"].append("Consider rebalancing budget based on channel performance")

        # Calculate overall performance score (0-100)
        metrics = campaign.get_all_performance_metrics()
        if metrics:
            # Example scoring based on common metrics
            conversion_rate = metrics.get("conversion_rate", 0.01)
            click_through_rate = metrics.get("click_through_rate", 0.02)
            cost_per_acquisition = metrics.get("cost_per_acquisition", 100.0)
            
            # Normalize and weight metrics (this is a simplified example)
            score = min(100, (conversion_rate * 1000 * 0.4) + (click_through_rate * 500 * 0.3) + 
                       (max(0, 100 - cost_per_acquisition) * 0.3))
            analysis["performance_score"] = round(score, 2)
        
        return analysis

    def optimize_campaign(
        self,
        campaign: Campaign,
        optimization_type: OptimizationType,
        performance_data: Optional[Dict[str, Dict[str, float]]] = None,
        target_metrics: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Implement campaign optimization based on the specified type.
        
        Returns a summary of the optimization actions taken.
        """
        if not campaign.status.can_be_modified():
            raise OptimizationError(
                f"Cannot optimize campaign in {campaign.status.value} status",
                optimization_type=optimization_type.value,
                campaign_id=campaign.campaign_id,
                reason="Campaign status does not allow modifications",
            )

        optimization_result = {
            "campaign_id": campaign.campaign_id,
            "optimization_type": optimization_type.value,
            "actions_taken": [],
            "estimated_improvement": {},
            "warnings": [],
        }

        if optimization_type == OptimizationType.BUDGET_REALLOCATION:
            result = self._optimize_budget_allocation(campaign, performance_data)
            optimization_result.update(result)
        
        elif optimization_type == OptimizationType.CHANNEL_OPTIMIZATION:
            result = self._optimize_channels(campaign, performance_data, target_metrics)
            optimization_result.update(result)
        
        elif optimization_type == OptimizationType.PERFORMANCE_IMPROVEMENT:
            result = self._optimize_performance(campaign, target_metrics)
            optimization_result.update(result)
        
        elif optimization_type == OptimizationType.COST_REDUCTION:
            result = self._optimize_costs(campaign, performance_data)
            optimization_result.update(result)
        
        else:
            raise OptimizationError(
                f"Unsupported optimization type: {optimization_type.value}",
                optimization_type=optimization_type.value,
                campaign_id=campaign.campaign_id,
            )

        # Record optimization in campaign history
        campaign.add_optimization_record(
            optimization_type.value,
            optimization_result
        )

        return optimization_result

    def _optimize_budget_allocation(
        self, campaign: Campaign, performance_data: Optional[Dict[str, Dict[str, float]]]
    ) -> Dict[str, Any]:
        """Optimize budget allocation across channels."""
        result = {"actions_taken": [], "estimated_improvement": {}}
        
        if not performance_data:
            result["warnings"].append("No performance data available for optimization")
            return result

        try:
            # Rebalance allocations based on performance
            new_allocations = self.budget_allocation_service.rebalance_allocations(
                campaign.budget,
                performance_data,
                AllocationStrategy.PERFORMANCE_WEIGHTED
            )
            
            result["actions_taken"].append(f"Rebalanced budget across {len(new_allocations)} channels")
            result["estimated_improvement"]["budget_efficiency"] = 15.0  # Example improvement
            
        except Exception as e:
            result["warnings"].append(f"Budget reallocation failed: {str(e)}")
        
        return result

    def _optimize_channels(
        self,
        campaign: Campaign,
        performance_data: Optional[Dict[str, Dict[str, float]]],
        target_metrics: Optional[Dict[str, float]],
    ) -> Dict[str, Any]:
        """Optimize channel selection and configuration."""
        result = {"actions_taken": [], "estimated_improvement": {}}
        
        if not performance_data:
            result["warnings"].append("No performance data available for channel optimization")
            return result

        # Identify underperforming channels
        allocations = campaign.budget.get_all_allocations()
        underperforming = []
        
        for allocation in allocations:
            channel_data = performance_data.get(allocation.channel.name, {})
            conversion_rate = channel_data.get("conversion_rate", 0.01)
            
            target_conversion = target_metrics.get("conversion_rate", 0.02) if target_metrics else 0.02
            if conversion_rate < target_conversion * 0.5:  # Less than 50% of target
                underperforming.append(allocation.channel)

        if underperforming:
            result["actions_taken"].append(f"Identified {len(underperforming)} underperforming channels")
            result["estimated_improvement"]["conversion_rate"] = 10.0
        
        return result

    def _optimize_performance(
        self, campaign: Campaign, target_metrics: Optional[Dict[str, float]]
    ) -> Dict[str, Any]:
        """Optimize overall campaign performance."""
        result = {"actions_taken": [], "estimated_improvement": {}}
        
        current_metrics = campaign.get_all_performance_metrics()
        if not current_metrics:
            result["warnings"].append("No current performance metrics available")
            return result

        # Example performance optimization logic
        current_ctr = current_metrics.get("click_through_rate", 0.02)
        target_ctr = target_metrics.get("click_through_rate", 0.03) if target_metrics else 0.03
        
        if current_ctr < target_ctr:
            result["actions_taken"].append("Recommended creative optimization for improved CTR")
            improvement = (target_ctr - current_ctr) / current_ctr * 100
            result["estimated_improvement"]["click_through_rate"] = round(improvement, 2)
        
        return result

    def _optimize_costs(
        self, campaign: Campaign, performance_data: Optional[Dict[str, Dict[str, float]]]
    ) -> Dict[str, Any]:
        """Optimize campaign costs while maintaining performance."""
        result = {"actions_taken": [], "estimated_improvement": {}}
        
        if not performance_data:
            result["warnings"].append("No performance data available for cost optimization")
            return result

        # Reallocate to more cost-efficient channels
        try:
            new_allocations = self.budget_allocation_service.rebalance_allocations(
                campaign.budget,
                performance_data,
                AllocationStrategy.COST_EFFICIENCY
            )
            
            result["actions_taken"].append("Reallocated budget to more cost-efficient channels")
            result["estimated_improvement"]["cost_per_acquisition"] = -12.0  # Negative = cost reduction
            
        except Exception as e:
            result["warnings"].append(f"Cost optimization failed: {str(e)}")
        
        return result

    def compare_campaigns(
        self, campaigns: List[Campaign]
    ) -> Dict[str, Any]:
        """
        Compare multiple campaigns and provide optimization recommendations.
        
        Useful for portfolio-level optimization decisions.
        """
        if len(campaigns) < 2:
            raise ValueError("Need at least 2 campaigns for comparison")

        comparison = {
            "total_campaigns": len(campaigns),
            "campaign_summaries": [],
            "portfolio_recommendations": [],
            "best_performers": {},
            "optimization_opportunities": [],
        }

        # Analyze each campaign
        for campaign in campaigns:
            summary = {
                "campaign_id": campaign.campaign_id,
                "name": campaign.name,
                "status": campaign.status.value,
                "budget_utilization": float(campaign.get_budget_utilization().value),
                "total_budget": str(campaign.budget.total_amount),
                "metrics": campaign.get_all_performance_metrics(),
            }
            comparison["campaign_summaries"].append(summary)

        # Identify best performers
        if comparison["campaign_summaries"]:
            # Best budget utilization
            best_utilization = max(
                comparison["campaign_summaries"],
                key=lambda x: x["budget_utilization"]
            )
            comparison["best_performers"]["budget_utilization"] = {
                "campaign_id": best_utilization["campaign_id"],
                "value": best_utilization["budget_utilization"],
            }

        # Portfolio-level recommendations
        total_campaigns = len(campaigns)
        active_campaigns = len([c for c in campaigns if c.status.is_active()])
        
        if active_campaigns / total_campaigns < 0.5:
            comparison["portfolio_recommendations"].append(
                "Low percentage of active campaigns - consider activating more campaigns"
            )

        return comparison 