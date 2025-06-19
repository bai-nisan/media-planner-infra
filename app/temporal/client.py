"""
Temporal client configuration and connection management.

This module provides the Temporal client setup with proper async connection
management, data converters, and integration with FastAPI lifecycle.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import timedelta

from temporalio.client import Client, WorkflowHandle
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.common import RetryPolicy
from temporalio.converter import DataConverter

from app.core.config import Settings

logger = logging.getLogger(__name__)


class TemporalClient:
    """
    Temporal client wrapper with connection management and utility methods.
    
    This class provides a high-level interface for interacting with Temporal
    workflows and activities, including connection management, error handling,
    and utility methods for common operations.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Optional[Client] = None
        self._connected = False
        
    async def connect(self) -> None:
        """
        Establish connection to Temporal server.
        
        Raises:
            Exception: If connection fails
        """
        if self._connected:
            logger.warning("Temporal client already connected")
            return
            
        try:
            logger.info(f"Connecting to Temporal server at {self.settings.temporal_address}")
            
            # Configure TLS if enabled
            tls_config = None
            if self.settings.TEMPORAL_TLS_ENABLED:
                # TLS configuration would go here for production
                pass
            
            # Configure data converter
            data_converter = self._get_data_converter()
            
            self._client = await Client.connect(
                target_host=self.settings.temporal_address,
                namespace=self.settings.TEMPORAL_NAMESPACE,
                tls=tls_config,
                data_converter=data_converter,
                # Client connect doesn't use retry_config parameter
            )
            
            self._connected = True
            logger.info(f"Successfully connected to Temporal namespace: {self.settings.TEMPORAL_NAMESPACE}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Temporal: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Temporal server."""
        if self._client:
            # Temporal client doesn't require explicit disconnection
            # but we can mark as disconnected for internal state
            self._connected = False
            self._client = None
            logger.info("Disconnected from Temporal server")
    
    @property
    def client(self) -> Client:
        """
        Get the Temporal client instance.
        
        Returns:
            Client: The Temporal client
            
        Raises:
            RuntimeError: If not connected
        """
        if not self._connected or not self._client:
            raise RuntimeError("Temporal client not connected. Call connect() first.")
        return self._client
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected and self._client is not None
    
    def _get_data_converter(self) -> Optional[DataConverter]:
        """
        Get the appropriate data converter based on settings.
        
        Returns:
            DataConverter or None for default
        """
        if self.settings.TEMPORAL_DATA_CONVERTER == "json":
            # Use JSON data converter for better debugging
            from temporalio.converter import JSONPlainPayloadConverter
            return DataConverter(
                payload_converter_class=JSONPlainPayloadConverter
            )
        elif self.settings.TEMPORAL_DATA_CONVERTER == "protobuf":
            # Use default protobuf converter (more efficient)
            return None
        else:
            # Use default converter
            return None
    
    async def start_workflow(
        self,
        workflow_class,
        *args,
        workflow_id: str,
        task_queue: str,
        workflow_execution_timeout: Optional[timedelta] = None,
        workflow_run_timeout: Optional[timedelta] = None,
        workflow_task_timeout: Optional[timedelta] = None,
        retry_policy: Optional[RetryPolicy] = None,
        memo: Optional[Dict[str, Any]] = None,
        search_attributes: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> WorkflowHandle:
        """
        Start a workflow execution.
        
        Args:
            workflow_class: The workflow class to execute
            *args: Positional arguments for the workflow
            workflow_id: Unique identifier for the workflow
            task_queue: Task queue name
            workflow_execution_timeout: Total execution timeout
            workflow_run_timeout: Single run timeout
            workflow_task_timeout: Task timeout
            retry_policy: Retry policy for the workflow
            memo: Memo data for the workflow
            search_attributes: Search attributes for visibility
            **kwargs: Additional keyword arguments
            
        Returns:
            WorkflowHandle: Handle to the started workflow
            
        Raises:
            WorkflowAlreadyStartedError: If workflow with same ID already exists
        """
        try:
            # Set default timeouts if not provided
            if workflow_execution_timeout is None:
                workflow_execution_timeout = timedelta(
                    hours=self.settings.DEFAULT_WORKFLOW_TIMEOUT_HOURS
                )
            
            # Set default retry policy if not provided
            if retry_policy is None:
                retry_policy = RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(minutes=1),
                    maximum_attempts=3,
                )
            
            handle = await self.client.start_workflow(
                workflow_class.run,
                *args,
                id=workflow_id,
                task_queue=task_queue,
                execution_timeout=workflow_execution_timeout,
                run_timeout=workflow_run_timeout,
                task_timeout=workflow_task_timeout,
                retry_policy=retry_policy,
                memo=memo,
                search_attributes=search_attributes,
                **kwargs
            )
            
            logger.info(f"Started workflow {workflow_id} on task queue {task_queue}")
            return handle
            
        except WorkflowAlreadyStartedError:
            logger.warning(f"Workflow {workflow_id} already started")
            # Return handle to existing workflow
            return self.client.get_workflow_handle(workflow_id)
        except Exception as e:
            logger.error(f"Failed to start workflow {workflow_id}: {e}")
            raise
    
    async def execute_workflow(
        self,
        workflow_class,
        *args,
        workflow_id: str,
        task_queue: str,
        **kwargs
    ) -> Any:
        """
        Execute a workflow and wait for result.
        
        Args:
            workflow_class: The workflow class to execute
            *args: Positional arguments for the workflow
            workflow_id: Unique identifier for the workflow
            task_queue: Task queue name
            **kwargs: Additional keyword arguments
            
        Returns:
            Any: The workflow result
        """
        handle = await self.start_workflow(
            workflow_class,
            *args,
            workflow_id=workflow_id,
            task_queue=task_queue,
            **kwargs
        )
        
        return await handle.result()
    
    async def get_workflow_handle(self, workflow_id: str) -> WorkflowHandle:
        """
        Get handle to an existing workflow.
        
        Args:
            workflow_id: The workflow ID
            
        Returns:
            WorkflowHandle: Handle to the workflow
        """
        return self.client.get_workflow_handle(workflow_id)
    
    async def list_workflows(
        self,
        query: Optional[str] = None,
        limit: int = 100
    ) -> list:
        """
        List workflows with optional filtering.
        
        Args:
            query: Optional filter query
            limit: Maximum number of results
            
        Returns:
            list: List of workflow executions
        """
        async for workflow in self.client.list_workflows(query or "", page_size=limit):
            yield workflow
    
    async def health_check(self) -> bool:
        """
        Check Temporal server health.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            if not self.is_connected:
                return False
                
            # Try to list workflows as a health check
            count = 0
            async for _ in self.client.list_workflows("", page_size=1):
                count += 1
                break
            
            return True
        except Exception as e:
            logger.error(f"Temporal health check failed: {e}")
            return False


# Global client instance
_temporal_client: Optional[TemporalClient] = None


async def get_temporal_client(settings: Settings) -> TemporalClient:
    """
    Get or create the global Temporal client instance.
    
    Args:
        settings: Application settings
        
    Returns:
        TemporalClient: The client instance
    """
    global _temporal_client
    
    if _temporal_client is None:
        _temporal_client = TemporalClient(settings)
        await _temporal_client.connect()
    
    return _temporal_client


async def close_temporal_client() -> None:
    """Close the global Temporal client instance."""
    global _temporal_client
    
    if _temporal_client:
        await _temporal_client.disconnect()


# Context manager for Temporal client
class TemporalClientManager:
    """Context manager for Temporal client lifecycle."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: Optional[TemporalClient] = None
    
    async def __aenter__(self) -> TemporalClient:
        """Enter async context and connect to Temporal."""
        self.client = TemporalClient(self.settings)
        await self.client.connect()
        return self.client
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context and disconnect from Temporal."""
        if self.client:
            await self.client.disconnect() 