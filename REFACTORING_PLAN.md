# Media Planner Infrastructure Refactoring Plan

## Overview

This document outlines a comprehensive refactoring plan to transform the current media-planner-infra project into a Clean Architecture, Domain-Driven Design (DDD) based application following the FastAPI best practices.

## Current State Analysis

### Issues with Current Structure

1. **Mixed Concerns**: Business logic is mixed with infrastructure code in services
2. **No Clear Domain Layer**: Missing domain entities and value objects
3. **Direct Database Access**: No repository pattern implementation
4. **Flat Structure**: All services in one directory without clear boundaries
5. **Missing Application Layer**: No command/query separation or use cases
6. **Limited Testing Structure**: Tests not mirroring source structure
7. **Inconsistent Error Handling**: No domain-specific exceptions
8. **No Infrastructure Abstraction**: Direct coupling to external services

## Target Architecture

```
media-planner-infra/
├── src/
│   ├── main.py                      # FastAPI app entry point
│   ├── core/                        # Core application concerns
│   │   ├── config.py               # Settings management
│   │   ├── database.py             # Database configuration
│   │   ├── security.py             # Auth & security utilities
│   │   ├── exceptions.py           # Global exception definitions
│   │   └── dependencies.py         # Global dependencies
│   │
│   ├── domain/                      # Domain layer (business entities)
│   │   ├── interfaces/             # Abstract interfaces (ports)
│   │   │   ├── repositories.py     # Repository interfaces
│   │   │   └── services.py         # Service interfaces
│   │   ├── entities/               # Domain entities
│   │   │   ├── campaign.py
│   │   │   ├── user.py
│   │   │   ├── tenant.py
│   │   │   └── media_plan.py
│   │   ├── value_objects/          # Value objects
│   │   │   ├── money.py
│   │   │   ├── email.py
│   │   │   └── campaign_status.py
│   │   └── exceptions.py           # Domain-specific exceptions
│   │
│   ├── application/                 # Application layer (use cases)
│   │   ├── commands/               # Command handlers (write operations)
│   │   │   ├── create_campaign.py
│   │   │   ├── update_media_plan.py
│   │   │   └── process_workflow.py
│   │   ├── queries/                # Query handlers (read operations)
│   │   │   ├── get_campaign.py
│   │   │   └── list_campaigns.py
│   │   └── services/               # Application services
│   │       ├── campaign_service.py
│   │       ├── auth_service.py
│   │       └── workflow_service.py
│   │
│   ├── infrastructure/              # Infrastructure layer
│   │   ├── database/
│   │   │   ├── models/             # SQLAlchemy/Supabase models
│   │   │   ├── repositories/       # Repository implementations
│   │   │   └── mappers/            # Entity-Model mappers
│   │   ├── external/               # External API clients
│   │   │   ├── google/
│   │   │   ├── temporal/
│   │   │   └── langgraph/
│   │   └── cache/
│   │       └── redis_client.py
│   │
│   ├── presentation/                # Presentation layer (API)
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── dependencies.py
│   │   │       └── routers/
│   │   │           ├── campaigns.py
│   │   │           ├── auth.py
│   │   │           └── workflows.py
│   │   ├── middleware/
│   │   └── schemas/                # Pydantic models
│   │       ├── base.py
│   │       ├── campaign.py
│   │       └── auth.py
│   │
│   └── shared/                      # Shared utilities
│       ├── utils.py
│       └── constants.py
│
└── tests/                           # Test directory mirrors src
    ├── unit/
    ├── integration/
    └── e2e/
```

## Refactoring Steps

### Phase 1: Project Structure Reorganization (Week 1)

#### 1.1 Create New Directory Structure
```bash
# Create the new source structure
mkdir -p src/{core,domain,application,infrastructure,presentation,shared}
mkdir -p src/domain/{interfaces,entities,value_objects}
mkdir -p src/application/{commands,queries,services}
mkdir -p src/infrastructure/{database,external,cache}
mkdir -p src/presentation/api/v1/{routers,dependencies}
mkdir -p tests/{unit,integration,e2e,fixtures}
```

#### 1.2 Move Core Components
- Move `app/core/*` to `src/core/`
- Update imports across the project
- Ensure configuration management follows Pydantic Settings pattern

#### 1.3 Extract and Create Domain Layer
Create domain entities from existing code:

```python
# src/domain/entities/campaign.py
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.domain.value_objects.money import Money
from src.domain.value_objects.campaign_status import CampaignStatus
from src.domain.exceptions import DomainError

@dataclass
class Campaign:
    """Campaign domain entity."""
    id: Optional[str]
    name: str
    budget: Money
    start_date: datetime
    end_date: datetime
    tenant_id: str
    status: CampaignStatus
    
    def __post_init__(self):
        self._validate()
    
    def _validate(self):
        if self.start_date >= self.end_date:
            raise DomainError("Start date must be before end date")
        if self.budget.amount <= 0:
            raise DomainError("Budget must be positive")
```

### Phase 2: Repository Pattern Implementation (Week 2)

#### 2.1 Define Repository Interfaces
```python
# src/domain/interfaces/repositories.py
from abc import ABC, abstractmethod
from typing import List, Optional

from src.domain.entities.campaign import Campaign

class CampaignRepositoryInterface(ABC):
    """Campaign repository interface."""
    
    @abstractmethod
    async def save(self, campaign: Campaign) -> Campaign:
        pass
    
    @abstractmethod
    async def get_by_id(self, campaign_id: str, tenant_id: str) -> Optional[Campaign]:
        pass
    
    @abstractmethod
    async def list_by_tenant(self, tenant_id: str, skip: int = 0, limit: int = 100) -> List[Campaign]:
        pass
```

#### 2.2 Implement Repository Pattern
- Create SQLAlchemy/Supabase models in `src/infrastructure/database/models/`
- Implement repositories in `src/infrastructure/database/repositories/`
- Create mappers for entity-model conversion

### Phase 3: Application Layer Development (Week 3)

#### 3.1 Create Command Handlers
```python
# src/application/commands/create_campaign.py
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime

@dataclass
class CreateCampaignCommand:
    """Command for creating a campaign."""
    name: str
    budget_amount: Decimal
    currency: str
    start_date: datetime
    end_date: datetime
    tenant_id: str
    created_by: str
```

#### 3.2 Implement Application Services
- Extract business logic from current services
- Create clean service interfaces
- Implement command/query separation

### Phase 4: Infrastructure Layer Refactoring (Week 4)

#### 4.1 External Service Abstraction
- Move Google API clients to `src/infrastructure/external/google/`
- Move Temporal client to `src/infrastructure/external/temporal/`
- Move LangGraph agents to `src/infrastructure/external/langgraph/`

#### 4.2 Database Layer
- Implement Unit of Work pattern
- Add proper transaction management
- Create database migration scripts

### Phase 5: Presentation Layer Update (Week 5)

#### 5.1 Router Reorganization
- Move endpoints to `src/presentation/api/v1/routers/`
- Update dependency injection patterns
- Implement proper error handling

#### 5.2 Schema Updates
- Create comprehensive Pydantic schemas
- Implement request/response models
- Add proper validation

### Phase 6: Testing Structure (Week 6)

#### 6.1 Unit Tests
- Create unit tests for domain entities
- Test application services in isolation
- Mock external dependencies

#### 6.2 Integration Tests
- Test repository implementations
- Test API endpoints with test database
- Test external service integrations

## Migration Strategy

### Step-by-Step Migration Process

1. **Parallel Development**
   - Keep existing `app/` directory functional
   - Build new structure in `src/` directory
   - Gradually migrate components

2. **Component Migration Order**
   - Core configuration and dependencies
   - Domain entities and value objects
   - Repository interfaces and implementations
   - Application services
   - API routers
   - External service integrations

3. **Testing During Migration**
   - Maintain existing tests
   - Add new tests for refactored components
   - Ensure feature parity

## Code Quality Standards

### Required for All Code

1. **Type Hints**: All functions must have type hints
2. **Async/Await**: Use async patterns for all I/O operations
3. **Documentation**: Docstrings for all classes and public methods
4. **Error Handling**: Proper exception handling with custom exceptions
5. **Testing**: Minimum 80% code coverage

### Tools Configuration

```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
```

## Specific Refactoring Tasks

### 1. Authentication Service Refactoring

Current: `app/services/auth.py`
Target: Split into:
- `src/domain/entities/user.py` - User entity
- `src/application/services/auth_service.py` - Business logic
- `src/infrastructure/external/google/oauth_client.py` - Google OAuth
- `src/presentation/api/v1/routers/auth.py` - API endpoints

### 2. Campaign Management

Create new components:
- `src/domain/entities/campaign.py`
- `src/domain/value_objects/money.py`
- `src/application/commands/create_campaign.py`
- `src/infrastructure/database/repositories/campaign_repository.py`

### 3. Temporal Workflow Integration

Current: `app/services/temporal_service.py`
Target:
- `src/infrastructure/external/temporal/client.py`
- `src/application/services/workflow_service.py`
- `src/domain/interfaces/workflow_interface.py`

### 4. Multi-tenant Architecture

Implement proper tenant isolation:
- `src/domain/entities/tenant.py`
- `src/core/dependencies.py` - Tenant extraction
- `src/infrastructure/database/repositories/base_repository.py` - Tenant filtering

## Performance Optimizations

1. **Database Queries**
   - Implement eager loading
   - Use proper indexes
   - Optimize N+1 queries

2. **Caching Strategy**
   - Redis caching for frequently accessed data
   - Cache invalidation patterns
   - Response caching middleware

3. **Async Patterns**
   - Concurrent operations with `asyncio.gather()`
   - Background task processing
   - Connection pooling

## Security Enhancements

1. **Authentication**
   - JWT token management
   - Refresh token implementation
   - Session management

2. **Authorization**
   - Role-based access control
   - Permission-based authorization
   - Resource-level permissions

3. **Multi-tenancy**
   - Tenant isolation at all layers
   - Cross-tenant access prevention
   - Audit logging

## Monitoring and Observability

1. **Structured Logging**
   - JSON formatted logs
   - Request correlation IDs
   - Performance metrics

2. **Health Checks**
   - Database connectivity
   - External service availability
   - Resource utilization

3. **Metrics Collection**
   - API response times
   - Error rates
   - Business metrics

## Timeline and Milestones

### Week 1-2: Foundation
- Set up new project structure
- Create domain entities
- Implement repository interfaces

### Week 3-4: Core Features
- Migrate authentication
- Implement campaign management
- Set up testing framework

### Week 5-6: Integration
- External service integration
- API migration
- Performance optimization

### Week 7-8: Polish
- Comprehensive testing
- Documentation
- Performance tuning

## Success Criteria

1. **Clean Architecture Compliance**
   - Clear separation of concerns
   - Dependency direction compliance
   - Testable components

2. **Feature Parity**
   - All existing features work
   - No performance regression
   - Improved error handling

3. **Code Quality**
   - 80%+ test coverage
   - All linting checks pass
   - Type checking with mypy

4. **Documentation**
   - Updated API documentation
   - Architecture documentation
   - Developer guide

## Risk Mitigation

1. **Parallel Development**
   - Keep old code functional
   - Feature flags for new code
   - Gradual rollout

2. **Testing Strategy**
   - Comprehensive test suite
   - Integration testing
   - Load testing

3. **Rollback Plan**
   - Version control branches
   - Database migration rollback
   - Feature toggles

## Conclusion

This refactoring plan will transform the media-planner-infra project into a maintainable, scalable, and testable application following Clean Architecture and Domain-Driven Design principles. The phased approach ensures minimal disruption while achieving significant architectural improvements.

## Detailed Component Refactoring Examples

### Example 1: Refactoring Temporal Service

#### Current Implementation
```python
# app/services/temporal_service.py
class TemporalService:
    def __init__(self, client, settings):
        self.client = client
        self.settings = settings
    
    async def start_media_planning_workflow(self, workflow_input):
        # Mixed concerns: business logic + infrastructure
        # Direct temporal client usage
        pass
```

#### Refactored Implementation

**Domain Layer:**
```python
# src/domain/interfaces/workflow_interface.py
from abc import ABC, abstractmethod
from typing import Any

class WorkflowInterface(ABC):
    """Workflow orchestration interface."""
    
    @abstractmethod
    async def start_workflow(self, workflow_id: str, input_data: Any) -> str:
        pass
    
    @abstractmethod
    async def get_workflow_status(self, workflow_id: str) -> str:
        pass
```

**Application Layer:**
```python
# src/application/services/workflow_service.py
from src.domain.interfaces.workflow_interface import WorkflowInterface
from src.application.commands.start_workflow import StartWorkflowCommand

class WorkflowService:
    """Application service for workflow orchestration."""
    
    def __init__(self, workflow_interface: WorkflowInterface):
        self._workflow = workflow_interface
    
    async def start_media_planning_workflow(
        self, 
        command: StartWorkflowCommand
    ) -> str:
        """Start media planning workflow with business validation."""
        # Business logic here
        workflow_id = f"mp-{command.tenant_id}-{command.campaign_id}"
        
        # Delegate to infrastructure
        return await self._workflow.start_workflow(
            workflow_id, 
            command.to_dict()
        )
```

**Infrastructure Layer:**
```python
# src/infrastructure/external/temporal/temporal_workflow_adapter.py
from temporalio.client import Client
from src.domain.interfaces.workflow_interface import WorkflowInterface

class TemporalWorkflowAdapter(WorkflowInterface):
    """Temporal implementation of workflow interface."""
    
    def __init__(self, client: Client):
        self._client = client
    
    async def start_workflow(self, workflow_id: str, input_data: Any) -> str:
        """Start workflow using Temporal."""
        handle = await self._client.start_workflow(
            "MediaPlanningWorkflow",
            input_data,
            id=workflow_id,
            task_queue="media-planning-queue"
        )
        return handle.id
```

### Example 2: Refactoring LangGraph Agent Service

#### Current Implementation
```python
# app/services/langgraph/agent_service.py
class AgentService:
    def __init__(self):
        # Direct LangGraph dependencies
        self.workspace_agent = WorkspaceAgent()
        self.planning_agent = PlanningAgent()
```

#### Refactored Implementation

**Domain Layer:**
```python
# src/domain/entities/agent_session.py
from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime

@dataclass
class AgentSession:
    """Agent session domain entity."""
    id: str
    tenant_id: str
    session_type: str
    state: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    def update_state(self, new_state: Dict[str, Any]):
        """Update session state with validation."""
        self.state.update(new_state)
        self.updated_at = datetime.utcnow()
```

**Application Layer:**
```python
# src/application/services/agent_orchestration_service.py
from typing import Dict, Any
from src.domain.entities.agent_session import AgentSession
from src.domain.interfaces.agent_interface import AgentInterface

class AgentOrchestrationService:
    """Orchestrate multi-agent workflows."""
    
    def __init__(
        self,
        workspace_agent: AgentInterface,
        planning_agent: AgentInterface,
        insights_agent: AgentInterface
    ):
        self._agents = {
            "workspace": workspace_agent,
            "planning": planning_agent,
            "insights": insights_agent
        }
    
    async def process_request(
        self,
        session: AgentSession,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process request through appropriate agent."""
        agent_type = self._determine_agent_type(request)
        agent = self._agents[agent_type]
        
        result = await agent.process(session.state, request)
        session.update_state(result.state_updates)
        
        return result.response
```

### Example 3: Multi-tenant Repository Pattern

#### Current Pattern
```python
# Direct database queries with tenant filtering
async def get_campaigns(tenant_id: str):
    # Manual tenant filtering in each query
    pass
```

#### Refactored Pattern

**Domain Layer:**
```python
# src/domain/entities/base.py
from abc import ABC
from dataclasses import dataclass

@dataclass
class TenantEntity(ABC):
    """Base class for tenant-scoped entities."""
    tenant_id: str
    
    def ensure_same_tenant(self, other: "TenantEntity") -> None:
        """Ensure entities belong to same tenant."""
        if self.tenant_id != other.tenant_id:
            raise ValueError("Cross-tenant operation not allowed")
```

**Infrastructure Layer:**
```python
# src/infrastructure/database/repositories/base_repository.py
from typing import TypeVar, Generic, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

T = TypeVar('T')

class TenantAwareRepository(Generic[T]):
    """Base repository with automatic tenant filtering."""
    
    def __init__(self, session: AsyncSession, model_class: type[T]):
        self._session = session
        self._model_class = model_class
    
    async def get_by_id(self, id: str, tenant_id: str) -> Optional[T]:
        """Get entity by ID with tenant filtering."""
        stmt = select(self._model_class).where(
            self._model_class.id == id,
            self._model_class.tenant_id == tenant_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_by_tenant(
        self, 
        tenant_id: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[T]:
        """List entities for tenant."""
        stmt = (
            select(self._model_class)
            .where(self._model_class.tenant_id == tenant_id)
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
```

### Example 4: Dependency Injection Refactoring

#### Current Pattern
```python
# app/dependencies.py
async def get_current_tenant(tenant_id: str = Path(...)):
    # Simple extraction
    return tenant_id
```

#### Refactored Pattern

```python
# src/presentation/api/v1/dependencies.py
from typing import Annotated
from fastapi import Depends, Path, HTTPException
from src.application.services.tenant_service import TenantService

async def get_tenant_service(
    db: DatabaseDep
) -> TenantService:
    """Get tenant service instance."""
    repo = TenantRepository(db)
    return TenantService(repo)

async def get_validated_tenant(
    tenant_id: str = Path(..., description="Tenant identifier"),
    tenant_service: TenantService = Depends(get_tenant_service)
) -> Tenant:
    """Extract and validate tenant."""
    tenant = await tenant_service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    if not tenant.is_active:
        raise HTTPException(403, "Tenant is not active")
    return tenant

# Type alias for clean usage
TenantDep = Annotated[Tenant, Depends(get_validated_tenant)]
```

### Example 5: Error Handling Refactoring

#### Current Pattern
```python
# Generic exception handling
raise Exception("Something went wrong")
```

#### Refactored Pattern

```python
# src/domain/exceptions.py
class DomainError(Exception):
    """Base domain exception."""
    pass

class InvalidCampaignError(DomainError):
    """Campaign validation error."""
    pass

class TenantAccessError(DomainError):
    """Cross-tenant access attempt."""
    pass

# src/presentation/middleware/error_handling.py
from fastapi import Request
from fastapi.responses import JSONResponse
from src.domain.exceptions import DomainError

async def domain_error_handler(
    request: Request, 
    exc: DomainError
) -> JSONResponse:
    """Handle domain errors with proper status codes."""
    error_mapping = {
        InvalidCampaignError: 400,
        TenantAccessError: 403,
    }
    
    status_code = error_mapping.get(type(exc), 400)
    
    return JSONResponse(
        status_code=status_code,
        content={
            "error": type(exc).__name__,
            "message": str(exc),
            "request_id": request.state.request_id
        }
    )
```

## Migration Checklist

### Pre-Migration
- [ ] Set up parallel directory structure (`src/`)
- [ ] Configure testing framework
- [ ] Set up CI/CD for new structure
- [ ] Create feature flags for gradual migration

### Phase 1: Core Components
- [ ] Migrate configuration to Pydantic Settings
- [ ] Create base domain entities
- [ ] Set up dependency injection framework
- [ ] Implement base repository interfaces

### Phase 2: Domain Layer
- [ ] Extract Campaign entity
- [ ] Extract User entity  
- [ ] Create value objects (Money, Email, etc.)
- [ ] Define domain exceptions

### Phase 3: Application Layer
- [ ] Create command handlers
- [ ] Implement application services
- [ ] Set up query handlers
- [ ] Add business validation

### Phase 4: Infrastructure
- [ ] Implement repository pattern
- [ ] Migrate Temporal integration
- [ ] Migrate LangGraph agents
- [ ] Set up Redis caching

### Phase 5: Presentation
- [ ] Reorganize API routers
- [ ] Update Pydantic schemas
- [ ] Implement new middleware
- [ ] Update OpenAPI documentation

### Phase 6: Testing
- [ ] Unit tests for domain layer
- [ ] Integration tests for repositories
- [ ] API endpoint tests
- [ ] End-to-end workflow tests

### Post-Migration
- [ ] Remove old `app/` directory
- [ ] Update documentation
- [ ] Performance benchmarking
- [ ] Production deployment 