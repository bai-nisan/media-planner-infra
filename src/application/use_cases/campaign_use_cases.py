"""
Campaign Use Cases for the Media Planning Platform.

Use cases orchestrate complex business workflows by coordinating
multiple commands, queries, and domain services.
"""

import logging
from typing import Dict, List, Any, Optional
from uuid import UUID

from src.domain.services import CampaignOptimizationService, OptimizationType
from src.domain.exceptions import DomainError, InvalidCampaignError

from ..commands.handlers import (
    CreateCampaignHandler,
    UpdateCampaignHandler,
    AllocateBudgetHandler,
    ActivateCampaignHandler
)
from ..commands.dto import (
    CreateCampaignCommand,
    AllocateBudgetCommand,
    ActivateCampaignCommand
)
from ..queries.handlers import (
    GetCampaignHandler,
    GetCampaignMetricsHandler,
    ListCampaignsHandler
)
from ..queries.dto import (
    GetCampaignQuery,
    GetCampaignMetricsQuery,
    ListCampaignsQuery
)

logger = logging.getLogger(__name__)


class CreateCampaignUseCase:
    """
    Use case for creating a complete campaign with initial setup.
    
    Orchestrates campaign creation, budget setup, and optional initial allocation.
    """
    
    def __init__(
        self,
        create_campaign_handler: CreateCampaignHandler,
        allocate_budget_handler: AllocateBudgetHandler,
        get_campaign_handler: GetCampaignHandler
    ):
        self.create_campaign_handler = create_campaign_handler
        self.allocate_budget_handler = allocate_budget_handler
        self.get_campaign_handler = get_campaign_handler

    async def execute(
        self,
        campaign_data: CreateCampaignCommand,
        initial_allocations: Optional[List[Dict[str, Any]]] = None,
        auto_activate: bool = False
    ) -> Dict[str, Any]:
        """
        Create a complete campaign with optional initial budget allocation.
        
        Args:
            campaign_data: Campaign creation data
            initial_allocations: Optional initial budget allocations
            auto_activate: Whether to activate campaign immediately
            
        Returns:
            Complete campaign data with creation results
        """
        logger.info(f"Creating complete campaign: {campaign_data.name}")
        
        try:
            # Step 1: Create the campaign and budget
            creation_result = await self.create_campaign_handler.handle(campaign_data)
            campaign_id = creation_result["campaign_id"]
            budget_id = creation_result["budget_id"]
            
            logger.info(f"Campaign created: {campaign_id}")
            
            # Step 2: Allocate budget if provided
            allocation_result = None
            if initial_allocations:
                allocation_command = AllocateBudgetCommand(
                    campaign_id=campaign_id,
                    budget_id=budget_id,
                    allocations=initial_allocations,
                    strategy="manual",
                    tenant_id=campaign_data.tenant_id,
                    allocated_by=campaign_data.created_by
                )
                
                allocation_result = await self.allocate_budget_handler.handle(allocation_command)
                logger.info(f"Budget allocated: {allocation_result['allocations_count']} channels")
            
            # Step 3: Activate if requested
            activation_result = None
            if auto_activate:
                activation_command = ActivateCampaignCommand(
                    campaign_id=campaign_id,
                    tenant_id=campaign_data.tenant_id,
                    activated_by=campaign_data.created_by
                )
                
                activation_result = await self.activate_campaign_handler.handle(activation_command)
                logger.info(f"Campaign activated: {campaign_id}")
            
            # Step 4: Get complete campaign data
            campaign_query = GetCampaignQuery(
                campaign_id=campaign_id,
                tenant_id=campaign_data.tenant_id,
                include_allocations=True,
                include_performance=False
            )
            
            campaign_details = await self.get_campaign_handler.handle(campaign_query)
            
            # Combine results
            result = {
                "campaign": campaign_details,
                "creation_result": creation_result,
                "allocation_result": allocation_result,
                "activation_result": activation_result,
                "workflow_completed": True,
                "message": "Campaign created successfully with complete setup"
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Campaign creation use case failed: {str(e)}")
            raise DomainError(f"Complete campaign creation failed: {str(e)}")


class OptimizeBudgetUseCase:
    """
    Use case for optimizing campaign budget allocations.
    
    Analyzes current performance and redistributes budget for better ROI.
    """
    
    def __init__(
        self,
        get_campaign_handler: GetCampaignHandler,
        get_campaign_metrics_handler: GetCampaignMetricsHandler,
        allocate_budget_handler: AllocateBudgetHandler,
        optimization_service: CampaignOptimizationService
    ):
        self.get_campaign_handler = get_campaign_handler
        self.get_campaign_metrics_handler = get_campaign_metrics_handler
        self.allocate_budget_handler = allocate_budget_handler
        self.optimization_service = optimization_service

    async def execute(
        self,
        campaign_id: UUID,
        tenant_id: UUID,
        optimization_strategy: str,
        user_id: str,
        target_metrics: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Optimize budget allocation based on performance data.
        
        Args:
            campaign_id: Campaign to optimize
            tenant_id: Tenant context
            optimization_strategy: Type of optimization to perform
            user_id: User performing optimization
            target_metrics: Optional target performance metrics
            
        Returns:
            Optimization results and new allocations
        """
        logger.info(f"Optimizing budget for campaign: {campaign_id}")
        
        try:
            # Step 1: Get current campaign data
            campaign_query = GetCampaignQuery(
                campaign_id=campaign_id,
                tenant_id=tenant_id,
                include_allocations=True,
                include_performance=True
            )
            
            campaign_data = await self.get_campaign_handler.handle(campaign_query)
            
            # Step 2: Get detailed performance metrics
            metrics_query = GetCampaignMetricsQuery(
                campaign_id=campaign_id,
                tenant_id=tenant_id,
                include_spend=True,
                include_impressions=True,
                include_clicks=True,
                include_conversions=True
            )
            
            performance_data = await self.get_campaign_metrics_handler.handle(metrics_query)
            
            # Step 3: Analyze and get optimization recommendations
            # This would use the domain service to analyze performance
            optimization_analysis = {
                "current_performance": performance_data["metrics"],
                "recommendations": [
                    "Increase allocation to high-performing channels",
                    "Reduce spend on underperforming channels",
                    "Consider pausing channels with poor ROI"
                ],
                "estimated_improvement": {
                    "conversion_rate": 15.0,
                    "cost_efficiency": 12.0
                }
            }
            
            # Step 4: Generate new allocation strategy
            if optimization_strategy == "performance_weighted":
                # Create new allocations based on performance
                new_allocations = await self._calculate_performance_allocations(
                    campaign_data, performance_data
                )
            elif optimization_strategy == "cost_efficiency":
                new_allocations = await self._calculate_cost_efficient_allocations(
                    campaign_data, performance_data
                )
            else:
                raise InvalidCampaignError(
                    f"Unknown optimization strategy: {optimization_strategy}",
                    field="optimization_strategy",
                    value=optimization_strategy
                )
            
            # Step 5: Apply new allocations
            if new_allocations:
                allocation_command = AllocateBudgetCommand(
                    campaign_id=campaign_id,
                    budget_id=campaign_data["budget_id"],  # Would need to include this in response
                    allocations=new_allocations,
                    strategy=optimization_strategy,
                    tenant_id=tenant_id,
                    allocated_by=user_id
                )
                
                allocation_result = await self.allocate_budget_handler.handle(allocation_command)
            else:
                allocation_result = {"message": "No reallocation needed"}
            
            # Step 6: Compile results
            result = {
                "campaign_id": campaign_id,
                "optimization_strategy": optimization_strategy,
                "analysis": optimization_analysis,
                "new_allocations": new_allocations,
                "allocation_result": allocation_result,
                "optimization_completed": True,
                "message": "Budget optimization completed successfully"
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Budget optimization use case failed: {str(e)}")
            raise DomainError(f"Budget optimization failed: {str(e)}")

    async def _calculate_performance_allocations(
        self, campaign_data: Dict, performance_data: Dict
    ) -> List[Dict[str, Any]]:
        """Calculate new allocations based on performance."""
        # Simplified logic - in reality this would use domain services
        allocations = []
        for allocation in campaign_data.get("allocations", []):
            channel_name = allocation["channel_name"]
            current_amount = allocation["allocated_amount"]
            
            # Increase allocation for high-performing channels
            performance_score = 1.0  # Would calculate from actual metrics
            new_amount = current_amount * performance_score
            
            allocations.append({channel_name: new_amount})
        
        return allocations

    async def _calculate_cost_efficient_allocations(
        self, campaign_data: Dict, performance_data: Dict
    ) -> List[Dict[str, Any]]:
        """Calculate new allocations based on cost efficiency."""
        # Simplified logic for cost-efficient reallocation
        allocations = []
        total_budget = sum(a["allocated_amount"] for a in campaign_data.get("allocations", []))
        
        for allocation in campaign_data.get("allocations", []):
            channel_name = allocation["channel_name"]
            # Redistribute based on cost efficiency
            efficiency_score = 1.0  # Would calculate from cost per conversion
            new_amount = (total_budget / len(campaign_data.get("allocations", []))) * efficiency_score
            
            allocations.append({channel_name: new_amount})
        
        return allocations


class CampaignPerformanceAnalysisUseCase:
    """
    Use case for comprehensive campaign performance analysis.
    
    Provides detailed insights across multiple campaigns and time periods.
    """
    
    def __init__(
        self,
        list_campaigns_handler: ListCampaignsHandler,
        get_campaign_metrics_handler: GetCampaignMetricsHandler,
        optimization_service: CampaignOptimizationService
    ):
        self.list_campaigns_handler = list_campaigns_handler
        self.get_campaign_metrics_handler = get_campaign_metrics_handler
        self.optimization_service = optimization_service

    async def execute(
        self,
        tenant_id: UUID,
        analysis_type: str = "comprehensive",
        campaign_ids: Optional[List[UUID]] = None,
        time_period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Perform comprehensive campaign performance analysis.
        
        Args:
            tenant_id: Tenant context
            analysis_type: Type of analysis to perform
            campaign_ids: Specific campaigns to analyze (optional)
            time_period_days: Analysis time period
            
        Returns:
            Comprehensive performance analysis results
        """
        logger.info(f"Performing {analysis_type} analysis for tenant: {tenant_id}")
        
        try:
            # Step 1: Get campaigns to analyze
            if campaign_ids:
                campaigns_data = []
                for campaign_id in campaign_ids:
                    campaign_query = GetCampaignQuery(
                        campaign_id=campaign_id,
                        tenant_id=tenant_id,
                        include_allocations=True,
                        include_performance=True
                    )
                    campaign_data = await self.get_campaign_handler.handle(campaign_query)
                    campaigns_data.append(campaign_data)
            else:
                campaigns_query = ListCampaignsQuery(
                    tenant_id=tenant_id,
                    page=1,
                    page_size=100,  # Adjust based on needs
                    status="active"  # Focus on active campaigns
                )
                campaigns_result = await self.list_campaigns_handler.handle(campaigns_query)
                campaigns_data = campaigns_result["items"]
            
            # Step 2: Gather performance metrics for each campaign
            performance_analysis = []
            for campaign in campaigns_data:
                metrics_query = GetCampaignMetricsQuery(
                    campaign_id=campaign["id"],
                    tenant_id=tenant_id,
                    include_spend=True,
                    include_impressions=True,
                    include_clicks=True,
                    include_conversions=True
                )
                
                metrics = await self.get_campaign_metrics_handler.handle(metrics_query)
                
                campaign_analysis = {
                    "campaign_id": campaign["id"],
                    "campaign_name": campaign["name"],
                    "performance_score": self._calculate_performance_score(metrics),
                    "metrics": metrics["metrics"],
                    "efficiency_rating": self._calculate_efficiency_rating(metrics),
                    "recommendations": self._generate_recommendations(campaign, metrics)
                }
                
                performance_analysis.append(campaign_analysis)
            
            # Step 3: Portfolio-level analysis
            portfolio_analysis = {
                "total_campaigns": len(campaigns_data),
                "total_budget": sum(c.get("budget_amount", 0) for c in campaigns_data),
                "average_performance_score": sum(
                    c["performance_score"] for c in performance_analysis
                ) / len(performance_analysis) if performance_analysis else 0,
                "top_performers": sorted(
                    performance_analysis, 
                    key=lambda x: x["performance_score"], 
                    reverse=True
                )[:3],
                "underperformers": sorted(
                    performance_analysis, 
                    key=lambda x: x["performance_score"]
                )[:3],
                "portfolio_recommendations": self._generate_portfolio_recommendations(
                    performance_analysis
                )
            }
            
            # Step 4: Generate insights and action items
            insights = {
                "key_findings": [
                    "Top performing channels across portfolio",
                    "Budget reallocation opportunities",
                    "Campaigns requiring immediate attention"
                ],
                "action_items": [
                    "Optimize budget allocation for underperforming campaigns",
                    "Scale successful strategies across portfolio",
                    "Review and update targeting for low-performing segments"
                ],
                "optimization_opportunities": self._identify_optimization_opportunities(
                    performance_analysis
                )
            }
            
            result = {
                "analysis_type": analysis_type,
                "time_period_days": time_period_days,
                "campaigns_analyzed": len(campaigns_data),
                "campaign_performance": performance_analysis,
                "portfolio_analysis": portfolio_analysis,
                "insights": insights,
                "generated_at": "2024-01-20T10:00:00Z",  # Would use actual timestamp
                "analysis_completed": True
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Performance analysis use case failed: {str(e)}")
            raise DomainError(f"Performance analysis failed: {str(e)}")

    def _calculate_performance_score(self, metrics: Dict) -> float:
        """Calculate overall performance score for a campaign."""
        spend_metrics = metrics["metrics"].get("spend", {})
        click_metrics = metrics["metrics"].get("clicks", {})
        conversion_metrics = metrics["metrics"].get("conversions", {})
        
        # Simplified scoring algorithm
        utilization = spend_metrics.get("utilization_percentage", 0) / 100
        ctr = click_metrics.get("click_through_rate", 0) / 100
        conversion_rate = conversion_metrics.get("conversion_rate", 0) / 100
        
        # Weighted score (0-100)
        score = (utilization * 0.3 + ctr * 0.3 + conversion_rate * 0.4) * 100
        return round(score, 2)

    def _calculate_efficiency_rating(self, metrics: Dict) -> str:
        """Calculate efficiency rating based on metrics."""
        conversion_metrics = metrics["metrics"].get("conversions", {})
        cost_per_conversion = conversion_metrics.get("cost_per_conversion", 0)
        
        if cost_per_conversion == 0:
            return "Not Available"
        elif cost_per_conversion < 50:
            return "Excellent"
        elif cost_per_conversion < 100:
            return "Good"
        elif cost_per_conversion < 200:
            return "Average"
        else:
            return "Poor"

    def _generate_recommendations(self, campaign: Dict, metrics: Dict) -> List[str]:
        """Generate specific recommendations for a campaign."""
        recommendations = []
        
        performance_score = self._calculate_performance_score(metrics)
        
        if performance_score < 30:
            recommendations.append("Consider pausing this campaign and reviewing strategy")
            recommendations.append("Analyze targeting and creative performance")
        elif performance_score < 60:
            recommendations.append("Optimize budget allocation between channels")
            recommendations.append("Test new creative variations")
        else:
            recommendations.append("Scale successful elements to other campaigns")
            recommendations.append("Consider increasing budget allocation")
        
        return recommendations

    def _generate_portfolio_recommendations(self, performance_analysis: List[Dict]) -> List[str]:
        """Generate portfolio-level recommendations."""
        recommendations = []
        
        avg_score = sum(c["performance_score"] for c in performance_analysis) / len(performance_analysis)
        
        if avg_score < 50:
            recommendations.append("Overall portfolio needs significant optimization")
            recommendations.append("Consider consolidating budgets to top performers")
        else:
            recommendations.append("Portfolio showing good performance overall")
            recommendations.append("Focus on scaling successful strategies")
        
        return recommendations

    def _identify_optimization_opportunities(self, performance_analysis: List[Dict]) -> List[Dict]:
        """Identify specific optimization opportunities."""
        opportunities = []
        
        for campaign in performance_analysis:
            if campaign["performance_score"] < 40:
                opportunities.append({
                    "type": "budget_reallocation",
                    "campaign_id": campaign["campaign_id"],
                    "description": "Low performing campaign needs budget optimization",
                    "priority": "high"
                })
        
        return opportunities 