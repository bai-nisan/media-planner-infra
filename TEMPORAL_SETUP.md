# Temporal Workflow Engine Setup

This document describes the setup and usage of the Temporal workflow engine for the Media Planner infrastructure.

## Overview

The Temporal cluster includes:
- **Temporal Server** (v1.22.0) - Core workflow engine
- **PostgreSQL** (v15) - Persistent storage for workflow history
- **Elasticsearch** (v7.17.9) - Advanced visibility and search
- **Temporal Web UI** (v2.21.3) - Web interface for monitoring
- **Admin Tools & CLI** - Management utilities

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Ports 5433, 7233, 8088, 9200 available

### Start the Cluster

```bash
# Start all services
./scripts/temporal-start.sh start

# Check status
./scripts/temporal-start.sh status

# View Web UI
open http://localhost:8088
```

### Stop the Cluster

```bash
./scripts/temporal-start.sh stop
```

## Architecture

### Services

| Service | Port | Description |
|---------|------|-------------|
| temporal-server | 7233 | gRPC API endpoint |
| temporal-web | 8088 | Web UI interface |
| temporal-postgres | 5433 | PostgreSQL database |
| temporal-elasticsearch | 9200 | Search and visibility |

### Network Configuration

All services run on the `temporal-network` bridge network, enabling secure inter-service communication.

### Data Persistence

- **PostgreSQL Data**: `temporal-postgres-data` volume
- **Elasticsearch Data**: `temporal-elasticsearch-data` volume

## Management Commands

The `./scripts/temporal-start.sh` script provides comprehensive cluster management:

```bash
# Start cluster
./scripts/temporal-start.sh start

# Stop cluster  
./scripts/temporal-start.sh stop

# Restart cluster
./scripts/temporal-start.sh restart

# Show status and health
./scripts/temporal-start.sh status

# View logs (all services)
./scripts/temporal-start.sh logs

# View logs (specific service)
./scripts/temporal-start.sh logs temporal-server

# Create namespace
./scripts/temporal-start.sh namespace media-planner
```

## Configuration

### Environment Variables

Key configuration is managed through `temporal.env`:

```env
# Database
POSTGRES_DB=temporal
POSTGRES_USER=temporal
POSTGRES_PASSWORD=temporal

# Temporal
TEMPORAL_ADDRESS=temporal-server:7233
TEMPORAL_NAMESPACE=default

# CORS (for frontend integration)
TEMPORAL_CORS_ORIGINS=http://localhost:3000,https://lovable.dev
```

### Dynamic Configuration

Runtime settings are configured in `temporal-config/development-sql.yaml`:

- Workflow retention (7 days for development)
- Rate limits (Frontend: 1200 RPS, History: 3000 RPS)
- Advanced visibility features enabled
- Worker versioning support

## Integration with FastAPI

### Client Connection

```python
from temporalio.client import Client

# Connect to Temporal
client = await Client.connect("localhost:7233")
```

### Namespace Setup

Create dedicated namespace for media planning workflows:

```python
# Using the management script
./scripts/temporal-start.sh namespace media-planner

# Or via Python client
await client.operator_service.create_namespace(
    "media-planner",
    namespace_pb2.NamespaceConfig(
        workflow_execution_retention_ttl=Duration(days=7)
    )
)
```

## Development Workflow

### 1. Start Development Environment

```bash
# Start Temporal cluster
./scripts/temporal-start.sh start

# Verify health
./scripts/temporal-start.sh status
```

### 2. Access Web UI

Navigate to http://localhost:8088 to:
- Monitor workflow executions
- View workflow history
- Debug failed workflows
- Manage namespaces

### 3. CLI Access

```bash
# Execute commands in CLI container
docker exec -it temporal-cli temporal workflow list

# Or install Temporal CLI locally
brew install temporal
temporal workflow list --address localhost:7233
```

## Health Monitoring

The startup script includes comprehensive health checks:

- **PostgreSQL**: Connection and readiness
- **Elasticsearch**: Cluster health API
- **Temporal Server**: Workflow list command
- **Web UI**: HTTP endpoint availability

### Health Check Endpoints

- PostgreSQL: `pg_isready -U temporal`
- Elasticsearch: `GET /_cluster/health`
- Temporal: `temporal workflow list`
- Web UI: `GET http://localhost:8088`

## Production Considerations

### Security

1. **Update default passwords** in production
2. **Configure TLS** for gRPC connections
3. **Restrict CORS origins** to production domains
4. **Enable authentication** for Web UI

### Scaling

1. **Horizontal scaling**: Run multiple Temporal server instances
2. **Database optimization**: Use managed PostgreSQL with read replicas
3. **Worker scaling**: Deploy workers across multiple machines
4. **Load balancing**: Use load balancer for Temporal server endpoints

### Monitoring

1. **Metrics**: Prometheus integration available
2. **Logging**: Structured JSON logs with ELK stack
3. **Alerting**: Set up alerts for workflow failures
4. **Dashboards**: Grafana dashboards for visualization

## Troubleshooting

### Common Issues

1. **Port conflicts**: Ensure ports 5433, 7233, 8088, 9200 are available
2. **Memory issues**: Elasticsearch requires adequate memory allocation
3. **Network issues**: Check Docker network configuration
4. **Permission issues**: Ensure script is executable

### Debug Commands

```bash
# View all service logs
./scripts/temporal-start.sh logs

# View specific service logs
./scripts/temporal-start.sh logs temporal-server

# Check container status
docker ps --filter name=temporal

# Test connectivity
docker exec temporal-cli temporal workflow list --address temporal-server:7233
```

### Log Locations

- **Service logs**: `docker logs <container-name>`
- **Temporal server logs**: Available through Web UI
- **Application logs**: Configured per workflow/activity

## Next Steps

1. **Set up Python SDK integration** (Task 2.2)
2. **Define workflow schemas** (Task 2.3)
3. **Implement activity handlers** (Task 2.4)
4. **Configure monitoring** (Task 2.5)

## Resources

- [Temporal Documentation](https://docs.temporal.io/)
- [Python SDK Guide](https://docs.temporal.io/docs/python)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Elasticsearch Guide](https://www.elastic.co/guide/) 