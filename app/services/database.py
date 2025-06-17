"""
Database service module for AI workflow data access.

Provides minimal Supabase read access for AI context and workflow data.
Implements efficient caching and read-only patterns.
"""

import logging
from typing import Dict, List, Optional, Any
from functools import lru_cache
import asyncio

from supabase import create_client, Client
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class DatabaseBridge:
    """
    Lightweight database bridge for AI workflow data access.
    
    Focuses on read-only operations with efficient caching for AI context retrieval.
    """
    
    def __init__(self):
        """Initialize the database bridge with Supabase client."""
        self.settings = get_settings()
        self._client: Optional[Client] = None
        self._health_status: Dict[str, Any] = {}
        
    @property
    def client(self) -> Client:
        """Get or create Supabase client instance."""
        if self._client is None:
            self._client = create_client(
                self.settings.SUPABASE_URL,
                self.settings.SUPABASE_KEY
            )
        return self._client
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform database health check.
        
        Returns:
            Dict containing health status and connection info
        """
        try:
            # Simple health check - attempt to access auth users (should be available)
            response = self.client.auth.get_user()
            
            self._health_status = {
                "status": "healthy",
                "database": "connected",
                "url": self.settings.SUPABASE_URL.replace(
                    self.settings.SUPABASE_URL.split("//")[1].split(".")[0], 
                    "***"
                ),  # Mask the project ID for security
                "timestamp": asyncio.get_event_loop().time(),
                "message": "Database connection successful"
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            self._health_status = {
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time(),
                "message": "Database connection failed"
            }
            
        return self._health_status
    
    @lru_cache(maxsize=128)
    def get_campaign_context(self, campaign_id: str, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Get campaign context data for AI workflows.
        
        Args:
            campaign_id: Campaign identifier
            tenant_id: Tenant identifier (optional)
            
        Returns:
            Campaign context data or None if not found
        """
        try:
            # Read campaign data from campaigns table
            query = self.client.table('campaigns').select('*').eq('id', campaign_id)
            
            if tenant_id:
                query = query.eq('tenant_id', tenant_id)
                
            response = query.execute()
            
            if response.data:
                campaign_data = response.data[0]
                logger.info(f"Retrieved campaign context for ID: {campaign_id}")
                return {
                    "campaign_id": campaign_data.get("id"),
                    "name": campaign_data.get("name"),
                    "budget": campaign_data.get("budget"),
                    "status": campaign_data.get("status"),
                    "target_audience": campaign_data.get("target_audience"),
                    "objectives": campaign_data.get("objectives"),
                    "channels": campaign_data.get("channels", []),
                    "created_at": campaign_data.get("created_at"),
                    "tenant_id": campaign_data.get("tenant_id")
                }
            else:
                logger.warning(f"No campaign found for ID: {campaign_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving campaign context: {str(e)}")
            return None
    
    @lru_cache(maxsize=64)
    def get_tenant_context(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tenant context data for AI workflows.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Tenant context data or None if not found
        """
        try:
            response = self.client.table('tenants').select('*').eq('id', tenant_id).execute()
            
            if response.data:
                tenant_data = response.data[0]
                logger.info(f"Retrieved tenant context for ID: {tenant_id}")
                return {
                    "tenant_id": tenant_data.get("id"),
                    "name": tenant_data.get("name"),
                    "industry": tenant_data.get("industry"),
                    "preferences": tenant_data.get("preferences", {}),
                    "subscription_tier": tenant_data.get("subscription_tier"),
                    "created_at": tenant_data.get("created_at")
                }
            else:
                logger.warning(f"No tenant found for ID: {tenant_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving tenant context: {str(e)}")
            return None
    
    def get_workflow_history(self, workflow_type: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent workflow execution history for AI learning.
        
        Args:
            workflow_type: Type of workflow to retrieve history for
            limit: Maximum number of records to return
            
        Returns:
            List of workflow execution records
        """
        try:
            response = (
                self.client
                .table('workflow_executions')
                .select('*')
                .eq('workflow_type', workflow_type)
                .order('created_at', desc=True)
                .limit(limit)
                .execute()
            )
            
            if response.data:
                logger.info(f"Retrieved {len(response.data)} workflow history records")
                return [
                    {
                        "execution_id": record.get("id"),
                        "workflow_type": record.get("workflow_type"),
                        "status": record.get("status"),
                        "input_data": record.get("input_data", {}),
                        "output_data": record.get("output_data", {}),
                        "execution_time": record.get("execution_time"),
                        "created_at": record.get("created_at")
                    }
                    for record in response.data
                ]
            else:
                logger.info(f"No workflow history found for type: {workflow_type}")
                return []
                
        except Exception as e:
            logger.error(f"Error retrieving workflow history: {str(e)}")
            return []
    
    def clear_cache(self):
        """Clear all cached data."""
        self.get_campaign_context.cache_clear()
        self.get_tenant_context.cache_clear()
        logger.info("Database cache cleared")


# Global database bridge instance
db_bridge = DatabaseBridge()


def get_database_bridge() -> DatabaseBridge:
    """Get database bridge instance - useful for dependency injection."""
    return db_bridge 