# Temporal Development Server Setup

This document describes the setup and usage of the Temporal development server using the official Temporal CLI for the Media Planner infrastructure.

## 🎯 **Why Temporal CLI?**

We've migrated from Docker-based setup to the official Temporal CLI for local development:

- ✅ **Native Apple Silicon Support**: No ARM64/AMD64 platform emulation issues
- ✅ **Zero Configuration**: No docker-compose files or complex setup required
- ✅ **Official Recommendation**: This is Temporal's recommended approach for local development
- ✅ **Instant Startup**: Starts in seconds vs minutes with Docker
- ✅ **Built-in Persistence**: Optional SQLite persistence with `--db-filename`
- ✅ **Self-contained**: No external dependencies beyond the CLI

## Quick Start

### Prerequisites

- Temporal CLI installed
- No Docker required!

### Installation

```bash
# macOS
brew install temporal

# Linux/Windows/Other platforms
# See: https://docs.temporal.io/cli#install
```

### Start Development Server

```bash
# Basic development server (in-memory, clean slate each restart)
temporal server start-dev --ui-port 8088

# With persistence (retains data between restarts)
temporal server start-dev --ui-port 8088 --db-filename temporal.db
```

### Access Services

- **Temporal gRPC API**: `localhost:7233`
- **Temporal Web UI**: http://localhost:8088
- **Default Namespace**: `default` (created automatically)

## Development Workflow

### 1. Start Development Environment

```bash
# Terminal 1: Start Temporal development server
temporal server start-dev --ui-port 8088

# Terminal 2: Start FastAPI application
cd media-planner-infra
poetry run uvicorn main:app --reload
```

### 2. Verify Connection

```bash
# Check server status
temporal server status

# List workflows (should be empty initially)
temporal workflow list
```

### 3. Access Web UI

Navigate to http://localhost:8088 to:
- Monitor workflow executions
- View workflow history
- Debug failed workflows
- Explore namespace details

## Configuration

### Default Settings

The development server automatically configures:
- **Database**: In-memory SQLite (or file-based with `--db-filename`)
- **Namespace**: `default` namespace created automatically
- **Ports**: 
  - gRPC: 7233
  - Web UI: 8088 (configurable with `--ui-port`)
- **Persistence**: Optional with `--db-filename temporal.db`

### Integration with FastAPI

Our FastAPI backend connects using these default settings:

```python
# app/core/config.py
TEMPORAL_HOST = "localhost"
TEMPORAL_PORT = 7233
TEMPORAL_NAMESPACE = "default"

# Client connection
from temporalio.client import Client

client = await Client.connect("localhost:7233")
```

### Environment Variables

Update your `.env` file (optional, these are the defaults):

```env
# Temporal Configuration
TEMPORAL_HOST=localhost
TEMPORAL_PORT=7233
TEMPORAL_NAMESPACE=default
```

## Available Commands

### Server Management

```bash
# Start development server
temporal server start-dev --ui-port 8088

# Start with persistence
temporal server start-dev --ui-port 8088 --db-filename temporal.db

# Check server status
temporal server status

# Stop server (Ctrl+C)
```

### Workflow Management

```bash
# List workflows
temporal workflow list

# Describe a workflow
temporal workflow describe --workflow-id=<workflow-id>

# Terminate a workflow
temporal workflow terminate --workflow-id=<workflow-id>

# Show workflow history
temporal workflow show --workflow-id=<workflow-id>
```

### Namespace Management

```bash
# List namespaces
temporal operator namespace list

# Create namespace (optional, default exists)
temporal operator namespace create media-planner

# Describe namespace
temporal operator namespace describe default
```

## Development Features

### Built-in Capabilities

- **Web UI**: Full-featured web interface for monitoring
- **SQLite Database**: Lightweight, file-based persistence option
- **Hot Reloading**: Restart server quickly for development
- **Namespace Isolation**: Multiple namespaces support
- **Worker Versioning**: Built-in support for workflow versioning

### Persistence Options

```bash
# In-memory (default) - Clean slate each restart
temporal server start-dev --ui-port 8088

# File-based persistence - Retains data between restarts
temporal server start-dev --ui-port 8088 --db-filename temporal.db

# Custom database location
temporal server start-dev --ui-port 8088 --db-filename /path/to/temporal.db
```

## Integration Examples

### Basic Workflow Execution

```python
from temporalio import workflow, activity
from temporalio.client import Client

@activity.defn
async def hello_activity(name: str) -> str:
    return f"Hello, {name}!"

@workflow.defn
class HelloWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            hello_activity, name, start_to_close_timeout=timedelta(seconds=10)
        )

# Execute workflow
async def main():
    client = await Client.connect("localhost:7233")
    result = await client.execute_workflow(
        HelloWorkflow.run, "Media Planner", id="hello-workflow"
    )
    print(result)
```

### Health Check Integration

```python
# app/api/v1/health.py
@router.get("/health/temporal")
async def temporal_health():
    try:
        client = await Client.connect("localhost:7233")
        # Simple connectivity test
        await client.list_workflows()
        return {"status": "healthy", "temporal": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "temporal": str(e)}
```

## Troubleshooting

### Common Issues

1. **Port Already in Use**:
   ```bash
   # Check what's using port 7233 or 8088
   lsof -i :7233
   lsof -i :8088
   
   # Use different ports
   temporal server start-dev --port 7234 --ui-port 8089
   ```

2. **Permission Issues**:
   ```bash
   # Make sure temporal CLI is executable
   which temporal
   temporal --version
   ```

3. **Connection Refused**:
   ```bash
   # Verify server is running
   temporal server status
   
   # Check connectivity
   telnet localhost 7233
   ```

### Logging

```bash
# Enable verbose logging
temporal server start-dev --ui-port 8088 --log-level debug

# View server logs (server outputs to console)
```

## Production Considerations

### For Production Environments

**Do NOT use `temporal server start-dev` in production.** Instead:

1. **Temporal Cloud**: Use managed Temporal service
2. **Self-hosted**: Deploy full Temporal cluster with:
   - PostgreSQL or Cassandra
   - Elasticsearch for visibility
   - Load balancers
   - TLS/Authentication

### Migration Path

```bash
# Development
temporal server start-dev --ui-port 8088

# Production
# Use Temporal Cloud or kubernetes deployment
# Update connection in app/core/config.py
```

## Comparison: Docker vs CLI

| Feature | Docker Compose | Temporal CLI |
|---------|----------------|--------------|
| Setup Time | 2-5 minutes | 10 seconds |
| Platform Support | ARM64 issues | Native support |
| Dependencies | Docker, compose files | Single binary |
| Persistence | External volumes | Built-in SQLite |
| Configuration | Multiple files | Single command |
| Resource Usage | High (multiple containers) | Low (single process) |
| Debugging | Complex logs | Direct output |
| Official Support | Community | Official Temporal |

The Temporal CLI approach is simpler, faster, and officially supported for local development! 