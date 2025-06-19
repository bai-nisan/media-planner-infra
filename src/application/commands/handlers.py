"""
Command handlers for write operations in the Media Planning Platform.

Handlers process commands by orchestrating domain logic and infrastructure services
following CQRS pattern principles.
"""

import logging
from typing import Dict, Any
from uuid import UUID

from src.domain.entities import Campaign, Budget, Client, MediaChannel, BudgetAllocation
from src.domain.interfaces.repositories import (
    CampaignRepositoryInterface,
    BudgetRepositoryInterface,
    ClientRepositoryInterface,
    MediaChannelRepositoryInterface,
    UnitOfWorkInterface
)
from src.domain.services import BudgetAllocationService, AllocationStrategy
from src.domain.value_objects import Money, DateRange, CampaignStatus
from src.domain.exceptions import (
    DomainError,
    InvalidCampaignError,
    BudgetExceededError,
    TenantAccessError
)

from .dto import (
    CreateCampaignCommand,
    UpdateCampaignCommand,
    AllocateBudgetCommand,
    ActivateCampaignCommand,
    PauseCampaignCommand,
    CreateClientCommand,
    UpdateClientCommand
)

logger = logging.getLogger(__name__)


class CreateCampaignHandler:
    """Handler for creating new campaigns."""
    
    def __init__(
        self,
        campaign_repository: CampaignRepositoryInterface,
        budget_repository: BudgetRepositoryInterface,
        client_repository: ClientRepositoryInterface,
        uow: UnitOfWorkInterface
    ):
        self.campaign_repository = campaign_repository
        self.budget_repository = budget_repository
        self.client_repository = client_repository
        self.uow = uow

    async def handle(self, command: CreateCampaignCommand) -> Dict[str, Any]:
        """
        Handle campaign creation command.
        
        Creates a new campaign with associated budget and validates
        business rules through domain entities.
        """
        logger.info(f"Creating campaign: {command.name} for tenant: {command.tenant_id}")
        
        try:
            async with self.uow:
                # Validate client exists if provided
                if command.client_id:
                    client = await self.client_repository.get_by_id(
                        command.client_id, command.tenant_id
                    )
                    if not client:
                        raise InvalidCampaignError(
                            f"Client {command.client_id} not found",
                            field="client_id",
                            value=str(command.client_id)
                        )
                
                # Create budget for the campaign
                budget_money = Money(command.budget_amount, command.budget_currency)
                budget = Budget.create(
                    total_amount=budget_money,
                    tenant_id=command.tenant_id,
                    created_by=command.created_by
                )
                
                # Save budget first to get ID
                saved_budget = await self.budget_repository.save(budget)
                
                # Create campaign entity
                campaign = Campaign.create(
                    name=command.name,
                    description=command.description,
                    budget=saved_budget,
                    date_range=DateRange(command.start_date, command.end_date),
                    client_id=command.client_id,
                    tenant_id=command.tenant_id,
                    created_by=command.created_by,
                    metadata=command.metadata or {},
                    tags=command.tags or []
                )
                
                # Save campaign
                saved_campaign = await self.campaign_repository.save(campaign)
                
                # Commit transaction
                await self.uow.commit()
                
                logger.info(f"Campaign created successfully: {saved_campaign.campaign_id}")
                
                return {
                    "campaign_id": saved_campaign.campaign_id,
                    "budget_id": saved_budget.budget_id,
                    "status": saved_campaign.status.value,
                    "message": "Campaign created successfully"
                }
                
        except DomainError:
            await self.uow.rollback()
            raise
        except Exception as e:
            await self.uow.rollback()
            logger.error(f"Failed to create campaign: {str(e)}")
            raise DomainError(f"Campaign creation failed: {str(e)}")


class UpdateCampaignHandler:
    """Handler for updating existing campaigns."""
    
    def __init__(
        self,
        campaign_repository: CampaignRepositoryInterface,
        uow: UnitOfWorkInterface
    ):
        self.campaign_repository = campaign_repository
        self.uow = uow

    async def handle(self, command: UpdateCampaignCommand) -> Dict[str, Any]:
        """Handle campaign update command."""
        logger.info(f"Updating campaign: {command.campaign_id}")
        
        try:
            async with self.uow:
                # Get existing campaign
                campaign = await self.campaign_repository.get_by_id(
                    command.campaign_id, command.tenant_id
                )
                if not campaign:
                    raise InvalidCampaignError(
                        f"Campaign {command.campaign_id} not found",
                        field="campaign_id",
                        value=str(command.campaign_id)
                    )
                
                # Update campaign fields
                if command.name is not None:
                    campaign.update_name(command.name)
                
                if command.description is not None:
                    campaign.update_description(command.description)
                
                if command.budget_amount is not None:
                    new_budget = Money(command.budget_amount, campaign.budget.total_amount.currency)
                    campaign.update_budget(new_budget)
                
                if command.start_date is not None or command.end_date is not None:
                    start_date = command.start_date or campaign.date_range.start_date
                    end_date = command.end_date or campaign.date_range.end_date
                    campaign.update_date_range(DateRange(start_date, end_date))
                
                if command.metadata is not None:
                    campaign.update_metadata(command.metadata)
                
                if command.tags is not None:
                    campaign.update_tags(command.tags)
                
                # Record who updated
                campaign.record_update(command.updated_by)
                
                # Save updated campaign
                await self.campaign_repository.save(campaign)
                await self.uow.commit()
                
                logger.info(f"Campaign updated successfully: {command.campaign_id}")
                
                return {
                    "campaign_id": campaign.campaign_id,
                    "status": campaign.status.value,
                    "message": "Campaign updated successfully"
                }
                
        except DomainError:
            await self.uow.rollback()
            raise
        except Exception as e:
            await self.uow.rollback()
            logger.error(f"Failed to update campaign: {str(e)}")
            raise DomainError(f"Campaign update failed: {str(e)}")


class AllocateBudgetHandler:
    """Handler for budget allocation operations."""
    
    def __init__(
        self,
        campaign_repository: CampaignRepositoryInterface,
        budget_repository: BudgetRepositoryInterface,
        media_channel_repository: MediaChannelRepositoryInterface,
        budget_allocation_service: BudgetAllocationService,
        uow: UnitOfWorkInterface
    ):
        self.campaign_repository = campaign_repository
        self.budget_repository = budget_repository
        self.media_channel_repository = media_channel_repository
        self.budget_allocation_service = budget_allocation_service
        self.uow = uow

    async def handle(self, command: AllocateBudgetCommand) -> Dict[str, Any]:
        """Handle budget allocation command."""
        logger.info(f"Allocating budget for campaign: {command.campaign_id}")
        
        try:
            async with self.uow:
                # Get campaign and budget
                campaign = await self.campaign_repository.get_by_id(
                    command.campaign_id, command.tenant_id
                )
                if not campaign:
                    raise InvalidCampaignError(
                        f"Campaign {command.campaign_id} not found",
                        field="campaign_id",
                        value=str(command.campaign_id)
                    )
                
                budget = await self.budget_repository.get_by_id(
                    command.budget_id, command.tenant_id
                )
                if not budget:
                    raise BudgetExceededError(
                        f"Budget {command.budget_id} not found",
                        budget_id=command.budget_id,
                        requested_amount=0,
                        available_amount=0
                    )
                
                # Get media channels
                channels = []
                for allocation_dict in command.allocations:
                    for channel_name in allocation_dict.keys():
                        channel = await self.media_channel_repository.get_by_name(
                            channel_name, command.tenant_id
                        )
                        if not channel:
                            raise InvalidCampaignError(
                                f"Media channel '{channel_name}' not found",
                                field="media_channel",
                                value=channel_name
                            )
                        if not channel.is_active:
                            raise InvalidCampaignError(
                                f"Media channel '{channel_name}' is not active",
                                field="media_channel",
                                value=channel_name
                            )
                        channels.append(channel)
                
                # Perform allocation using domain service
                if command.strategy == "manual":
                    # Manual allocation - create allocations directly
                    allocations = []
                    for allocation_dict in command.allocations:
                        for channel_name, amount in allocation_dict.items():
                            channel = next(c for c in channels if c.name == channel_name)
                            allocation_money = Money(amount, budget.total_amount.currency)
                            allocation = budget.add_allocation(channel, allocation_money)
                            allocations.append(allocation)
                else:
                    # Use domain service for strategy-based allocation
                    strategy = AllocationStrategy(command.strategy)
                    allocations = self.budget_allocation_service.allocate_budget(
                        budget=budget,
                        channels=channels,
                        strategy=strategy
                    )
                
                # Save updated budget
                await self.budget_repository.save(budget)
                
                # Update campaign with allocation record
                campaign.record_budget_allocation(
                    len(allocations),
                    sum(a.allocated_amount.amount for a in allocations),
                    command.allocated_by
                )
                await self.campaign_repository.save(campaign)
                
                await self.uow.commit()
                
                logger.info(f"Budget allocated successfully: {len(allocations)} channels")
                
                return {
                    "campaign_id": command.campaign_id,
                    "budget_id": command.budget_id,
                    "allocations_count": len(allocations),
                    "total_allocated": sum(a.allocated_amount.amount for a in allocations),
                    "strategy_used": command.strategy,
                    "message": "Budget allocated successfully"
                }
                
        except DomainError:
            await self.uow.rollback()
            raise
        except Exception as e:
            await self.uow.rollback()
            logger.error(f"Failed to allocate budget: {str(e)}")
            raise DomainError(f"Budget allocation failed: {str(e)}")


class ActivateCampaignHandler:
    """Handler for activating campaigns."""
    
    def __init__(
        self,
        campaign_repository: CampaignRepositoryInterface,
        uow: UnitOfWorkInterface
    ):
        self.campaign_repository = campaign_repository
        self.uow = uow

    async def handle(self, command: ActivateCampaignCommand) -> Dict[str, Any]:
        """Handle campaign activation command."""
        logger.info(f"Activating campaign: {command.campaign_id}")
        
        try:
            async with self.uow:
                campaign = await self.campaign_repository.get_by_id(
                    command.campaign_id, command.tenant_id
                )
                if not campaign:
                    raise InvalidCampaignError(
                        f"Campaign {command.campaign_id} not found",
                        field="campaign_id",
                        value=str(command.campaign_id)
                    )
                
                # Activate campaign through domain logic
                campaign.activate(command.activated_by)
                
                # Save updated campaign
                await self.campaign_repository.save(campaign)
                await self.uow.commit()
                
                logger.info(f"Campaign activated successfully: {command.campaign_id}")
                
                return {
                    "campaign_id": command.campaign_id,
                    "status": campaign.status.value,
                    "message": "Campaign activated successfully"
                }
                
        except DomainError:
            await self.uow.rollback()
            raise
        except Exception as e:
            await self.uow.rollback()
            logger.error(f"Failed to activate campaign: {str(e)}")
            raise DomainError(f"Campaign activation failed: {str(e)}")


class PauseCampaignHandler:
    """Handler for pausing campaigns."""
    
    def __init__(
        self,
        campaign_repository: CampaignRepositoryInterface,
        uow: UnitOfWorkInterface
    ):
        self.campaign_repository = campaign_repository
        self.uow = uow

    async def handle(self, command: PauseCampaignCommand) -> Dict[str, Any]:
        """Handle campaign pause command."""
        logger.info(f"Pausing campaign: {command.campaign_id}")
        
        try:
            async with self.uow:
                campaign = await self.campaign_repository.get_by_id(
                    command.campaign_id, command.tenant_id
                )
                if not campaign:
                    raise InvalidCampaignError(
                        f"Campaign {command.campaign_id} not found",
                        field="campaign_id",
                        value=str(command.campaign_id)
                    )
                
                # Pause campaign through domain logic
                campaign.pause(command.paused_by, command.reason)
                
                # Save updated campaign
                await self.campaign_repository.save(campaign)
                await self.uow.commit()
                
                logger.info(f"Campaign paused successfully: {command.campaign_id}")
                
                return {
                    "campaign_id": command.campaign_id,
                    "status": campaign.status.value,
                    "message": "Campaign paused successfully"
                }
                
        except DomainError:
            await self.uow.rollback()
            raise
        except Exception as e:
            await self.uow.rollback()
            logger.error(f"Failed to pause campaign: {str(e)}")
            raise DomainError(f"Campaign pause failed: {str(e)}")


class CreateClientHandler:
    """Handler for creating new clients."""
    
    def __init__(
        self,
        client_repository: ClientRepositoryInterface,
        uow: UnitOfWorkInterface
    ):
        self.client_repository = client_repository
        self.uow = uow

    async def handle(self, command: CreateClientCommand) -> Dict[str, Any]:
        """Handle client creation command."""
        logger.info(f"Creating client: {command.name} for tenant: {command.tenant_id}")
        
        try:
            async with self.uow:
                # Check if client email already exists for tenant
                existing_client = await self.client_repository.get_by_email(
                    command.email, command.tenant_id
                )
                if existing_client:
                    raise InvalidCampaignError(  # Could create ClientError but using existing
                        f"Client with email {command.email} already exists",
                        field="email",
                        value=command.email
                    )
                
                # Create client entity
                client = Client.create(
                    name=command.name,
                    email=command.email,
                    industry=command.industry,
                    company_size=command.company_size,
                    phone=command.phone,
                    website=command.website,
                    address=command.address,
                    description=command.description,
                    additional_info=command.additional_info or {},
                    interests=command.interests or [],
                    tenant_id=command.tenant_id,
                    created_by=command.created_by
                )
                
                # Save client
                saved_client = await self.client_repository.save(client)
                await self.uow.commit()
                
                logger.info(f"Client created successfully: {saved_client.client_id}")
                
                return {
                    "client_id": saved_client.client_id,
                    "name": saved_client.name,
                    "email": saved_client.email,
                    "is_active": saved_client.is_active,
                    "message": "Client created successfully"
                }
                
        except DomainError:
            await self.uow.rollback()
            raise
        except Exception as e:
            await self.uow.rollback()
            logger.error(f"Failed to create client: {str(e)}")
            raise DomainError(f"Client creation failed: {str(e)}")


class UpdateClientHandler:
    """Handler for updating existing clients."""
    
    def __init__(
        self,
        client_repository: ClientRepositoryInterface,
        uow: UnitOfWorkInterface
    ):
        self.client_repository = client_repository
        self.uow = uow

    async def handle(self, command: UpdateClientCommand) -> Dict[str, Any]:
        """Handle client update command."""
        logger.info(f"Updating client: {command.client_id}")
        
        try:
            async with self.uow:
                # Get existing client
                client = await self.client_repository.get_by_id(
                    command.client_id, command.tenant_id
                )
                if not client:
                    raise InvalidCampaignError(
                        f"Client {command.client_id} not found",
                        field="client_id",
                        value=str(command.client_id)
                    )
                
                # Check email uniqueness if email is being updated
                if command.email and command.email != client.email:
                    existing_client = await self.client_repository.get_by_email(
                        command.email, command.tenant_id
                    )
                    if existing_client and existing_client.client_id != command.client_id:
                        raise InvalidCampaignError(
                            f"Client with email {command.email} already exists",
                            field="email",
                            value=command.email
                        )
                
                # Update client fields
                if command.name is not None:
                    client.update_name(command.name)
                
                if command.email is not None:
                    client.update_email(command.email)
                
                if command.industry is not None:
                    client.update_industry(command.industry)
                
                if command.company_size is not None:
                    client.update_company_size(command.company_size)
                
                if command.phone is not None:
                    client.update_phone(command.phone)
                
                if command.website is not None:
                    client.update_website(command.website)
                
                if command.address is not None:
                    client.update_address(command.address)
                
                if command.description is not None:
                    client.update_description(command.description)
                
                if command.additional_info is not None:
                    client.update_additional_info(command.additional_info)
                
                if command.interests is not None:
                    client.update_interests(command.interests)
                
                if command.is_active is not None:
                    if command.is_active:
                        client.activate()
                    else:
                        client.deactivate()
                
                # Record who updated
                client.record_update(command.updated_by)
                
                # Save updated client
                await self.client_repository.save(client)
                await self.uow.commit()
                
                logger.info(f"Client updated successfully: {command.client_id}")
                
                return {
                    "client_id": client.client_id,
                    "name": client.name,
                    "email": client.email,
                    "is_active": client.is_active,
                    "message": "Client updated successfully"
                }
                
        except DomainError:
            await self.uow.rollback()
            raise
        except Exception as e:
            await self.uow.rollback()
            logger.error(f"Failed to update client: {str(e)}")
            raise DomainError(f"Client update failed: {str(e)}") 