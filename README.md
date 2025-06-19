# Media Planner Infrastructure

A comprehensive FastAPI backend service for media planning platform with multi-tenant architecture, real-time analytics, and workflow orchestration using Temporal.

## 🏗️ Architecture Overview

This infrastructure provides a robust backend for media planning operations with the following key components:

- **FastAPI Application**: Modern Python web framework with automatic API documentation
- **Temporal Workflows**: Durable workflow orchestration for complex media planning processes
- **Multi-tenant Architecture**: Support for multiple organizations with data isolation
- **Google API Integration**: Native integration with Google Ads, Drive, and Sheets
- **AI-Powered Planning**: LangGraph integration for intelligent campaign optimization
- **Real-time Communication**: WebSocket support for live updates

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Architecture Components](#architecture-components)
- [Development Setup](#development-setup)
- [API Documentation](#api-documentation)
- [Temporal Workflows](#temporal-workflows)
- [Configuration](#configuration)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- Poetry (dependency management)
- Temporal CLI (replaces Docker setup)
- PostgreSQL (optional, for production)
- Redis (for caching)

### Installation

1. **Install Temporal CLI** (one-time setup):
```bash
# macOS
brew install temporal

# Other platforms: https://docs.temporal.io/cli#install
```

2. **Clone and setup environment**:
```bash
git clone <repository-url>
cd media-planner-infra
poetry install
```

3. **Start Temporal development server**:
```bash
# Basic development server (in-memory, clean slate each restart)
temporal server start-dev --ui-port 8088

# With persistence (retains data between restarts)
temporal server start-dev --ui-port 8088 --db-filename temporal.db
```

4. **Configure environment**:
```bash
cp temporal.env .env
# Edit .env with your configuration
```

5. **Run the application** (in a new terminal):
```bash
poetry run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

6. **Access the application**:
- API Documentation: http://localhost:8000/api/docs
- Health Check: http://localhost:8000/health
- Temporal Web UI: http://localhost:8088
- Temporal gRPC: localhost:7233

## 🏛️ Architecture Components

### Core Application (`app/`)

```
app/
├── api/v1/               # API endpoints and routing
├── core/                 # Core configuration and exceptions
├── services/             # Business logic services
├── temporal/             # Workflow definitions and activities
├── models/               # Data models and schemas
├── middleware/           # Custom middleware
├── crud/                 # Database operations
└── schemas/              # Pydantic schemas
```

### Key Services

#### 1. Temporal Service (`app/services/temporal_service.py`)
- **MediaPlanningWorkflowService**: Campaign analysis and budget optimization
- **IntegrationWorkflowService**: Platform synchronization and data import
- **SyncWorkflowService**: Scheduled data synchronization
- **WorkflowManagementService**: Workflow monitoring and control

#### 2. Authentication Service (`app/services/auth.py`)
- JWT token management
- Multi-tenant authentication
- Google OAuth integration
- Role-based access control

#### 3. WebSocket Service (`app/services/websocket.py`)
- Real-time campaign updates
- Live analytics streaming
- User notification system

#### 4. Google API Services (`app/services/google/`)
- Google Ads API integration
- Google Drive file management
- Google Sheets data import/export

## 🛠️ Development Setup

### Local Development

1. **Install dependencies**:
```bash
poetry install --with dev,test
```

2. **Setup pre-commit hooks**:
```bash
poetry run pre-commit install
```

3. **Start development services**:
```bash
# Start Temporal development server
temporal server start-dev --ui-port 8088

# Start Redis (if not using Docker)
redis-server

# Start the FastAPI application (in a new terminal)
poetry run uvicorn main:app --reload
```

### Temporal CLI Advantages

The new Temporal CLI approach provides significant benefits over Docker:

- ✅ **Native Apple Silicon Support**: No ARM64/AMD64 platform issues
- ✅ **Zero Configuration**: No docker-compose complexity
- ✅ **Official Recommendation**: Temporal's preferred local development setup
- ✅ **Instant Startup**: Starts in seconds vs minutes with Docker
- ✅ **Built-in Persistence**: Optional SQLite persistence with `--db-filename`
- ✅ **Self-contained**: No external dependencies beyond the CLI

### Code Quality Tools

The project uses several tools for code quality:

- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **pytest**: Testing

Run all checks:
```bash
poetry run black .
poetry run isort .
poetry run flake8 .
poetry run mypy .
poetry run pytest
```

## 📚 API Documentation

### Available Endpoints

The API is versioned and follows RESTful conventions:

- **Base URL**: `/api/v1`
- **Authentication**: JWT Bearer tokens
- **Content-Type**: `application/json`

### Key Endpoint Categories

1. **Authentication** (`/auth`):
   - User registration and login
   - Token refresh
   - Google OAuth flow

2. **Campaigns** (`/campaigns`):
   - Campaign CRUD operations
   - Budget management
   - Performance analytics

3. **Workflows** (`/workflows`):
   - Workflow execution management
   - Status monitoring
   - Result retrieval

4. **Integrations** (`/integrations`):
   - Platform connections
   - Data synchronization
   - Import/export operations

### Interactive Documentation

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI Spec**: http://localhost:8000/api/v1/openapi.json

## 🔄 Temporal Workflows

### Overview

Temporal provides durable workflow execution for complex media planning processes that may run for hours or days. We now use the official Temporal CLI for local development, which provides a much simpler setup compared to the previous Docker-based approach.

### Development Setup

```bash
# Start Temporal development server
temporal server start-dev --ui-port 8088

# With persistence (optional)
temporal server start-dev --ui-port 8088 --db-filename temporal.db
```

See [TEMPORAL_SETUP.md](TEMPORAL_SETUP.md) for detailed setup instructions.

### Workflow Categories

#### 1. Media Planning Workflows
- **Campaign Analysis**: Deep analysis of campaign performance
- **Budget Optimization**: AI-driven budget allocation
- **A/B Testing**: Automated test management

#### 2. Integration Workflows
- **Platform Sync**: Synchronize data with external platforms
- **Data Import**: Import campaigns and performance data
- **Export Operations**: Generate reports and export data

#### 3. Scheduled Workflows
- **Daily Sync**: Regular data synchronization
- **Performance Monitoring**: Continuous campaign monitoring
- **Alert Processing**: Automated alert generation

### Temporal Setup

The Temporal cluster includes:
- **Temporal Server** (v1.22.0): Core workflow engine
- **PostgreSQL** (v15): Persistent storage
- **Elasticsearch** (v7.17.9): Advanced visibility
- **Web UI** (v2.21.3): Monitoring interface

See [TEMPORAL_SETUP.md](TEMPORAL_SETUP.md) for detailed setup instructions.

## ⚙️ Configuration

### Environment Variables

Key configuration is managed through environment variables:

```env
# Application
PROJECT_NAME=Media Planning Platform API
VERSION=0.1.0
ENVIRONMENT=development
DEBUG=true

# Database
DATABASE_URL=postgresql://user:pass@localhost/db
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Temporal
TEMPORAL_HOST=localhost
TEMPORAL_PORT=7233
TEMPORAL_NAMESPACE=default

# Google APIs
GOOGLE_OAUTH_CLIENT_ID=your-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
GOOGLE_ADS_DEVELOPER_TOKEN=your-developer-token
```

### Configuration Management

- **Settings Class**: Centralized configuration in `app/core/config.py`
- **Environment-based**: Different settings for dev/staging/production
- **Validation**: Pydantic validation for all configuration values
- **Type Safety**: Full type hints for all settings

## 🧪 Testing

### Test Structure

```
tests/
├── api/                  # API endpoint tests
├── core/                 # Core functionality tests
├── models/               # Model validation tests
├── test_auth.py          # Authentication tests
├── test_database.py      # Database operation tests
└── test_main.py          # Application startup tests
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app

# Run specific test file
poetry run pytest tests/test_auth.py

# Run tests with verbose output
poetry run pytest -v
```

### Test Categories

1. **Unit Tests**: Individual component testing
2. **Integration Tests**: Service interaction testing
3. **API Tests**: Endpoint testing with test client
4. **Workflow Tests**: Temporal workflow testing

## 🚀 Deployment

### Production Checklist

1. **Environment Configuration**:
   - Set `ENVIRONMENT=production`
   - Configure production database URLs
   - Set secure secret keys
   - Configure CORS origins

2. **Security Hardening**:
   - Enable HTTPS
   - Configure proper CORS settings
   - Set up rate limiting
   - Enable authentication

3. **Infrastructure**:
   - Deploy Temporal cluster
   - Set up monitoring
   - Configure logging
   - Set up backup systems

### Docker Deployment

```bash
# Build the application image
docker build -t media-planner-api .

# Run with Docker Compose
docker-compose up -d
```

### Health Monitoring

The application provides comprehensive health checks:

- **Basic Health**: `/health`
- **Temporal Health**: `/health/temporal`
- **Component Status**: Individual service health checks

## 🔧 Key Features

### Multi-tenant Architecture
- Tenant isolation at the data level
- Tenant-specific configurations
- Scalable tenant management

### Workflow Orchestration
- Durable workflow execution
- Complex business process automation
- Fault tolerance and recovery

### Google API Integration
- Native Google Ads API support
- Google Drive file management
- Google Sheets data processing

### Real-time Updates
- WebSocket-based live updates
- Campaign performance streaming
- User notification system

### AI-Powered Features
- LangGraph workflow integration
- Intelligent campaign optimization
- Automated decision making

## 📊 Performance Considerations

### Scalability Features

1. **Async Operations**: Full async/await support
2. **Connection Pooling**: Optimized database connections
3. **Caching**: Redis-based caching layer
4. **Worker Scaling**: Temporal worker auto-scaling

### Monitoring and Observability

1. **Structured Logging**: JSON-based logging
2. **Health Checks**: Comprehensive health monitoring
3. **Metrics**: Application performance metrics
4. **Tracing**: Request tracing capabilities

## 🤝 Contributing

### Development Workflow

1. **Fork and Clone**: Fork the repository and clone locally
2. **Branch**: Create a feature branch from `main`
3. **Develop**: Write code following the style guide
4. **Test**: Ensure all tests pass
5. **Submit**: Create a pull request

### Code Style

- Follow PEP 8 style guidelines
- Use type hints for all functions
- Write comprehensive docstrings
- Maintain test coverage above 80%

### Pull Request Process

1. Update documentation for new features
2. Add tests for new functionality
3. Ensure all CI checks pass
4. Request review from maintainers

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:

- **Documentation**: Check the `/api/docs` endpoint
- **Issues**: Create GitHub issues for bugs
- **Discussions**: Use GitHub discussions for questions

## 🔗 Related Projects

- **Frontend**: [Media Planner Frontend](../frontend)
- **Shared Components**: [Shared Libraries](../shared)
- **Documentation**: [Project Documentation](../docs)
