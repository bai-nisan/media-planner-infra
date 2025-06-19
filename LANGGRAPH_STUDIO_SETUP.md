# LangGraph Studio Setup Guide

This guide walks you through setting up LangGraph Studio for visual debugging of the Media Planning multi-agent system.

## Overview

LangGraph Studio provides a visual interface for debugging, prototyping, and monitoring the multi-agent workflow. It enables real-time visualization of agent interactions, state management, and workflow execution.

## Prerequisites

1. **Python 3.11+** with pip and virtual environments
2. **PostgreSQL** (for persistence)
3. **Redis** (for caching)
4. **LangGraph Studio Desktop App** (download from LangChain)

## Installation

### 1. Install Dependencies

The required LangGraph packages are already added to `requirements.txt`. Install them:

```bash
cd media-planner-infra
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Create a `.env` file based on the template:

```bash
# Copy example and edit with your values
cp .env.example .env
```

Required environment variables:
```env
# LangGraph Server Configuration
LANGGRAPH_AUTH_TYPE=noop
LOG_LEVEL=INFO

# Database Configuration
POSTGRES_URI=postgresql://postgres:postgres@localhost:5432/media_planner?sslmode=disable
REDIS_URI=redis://localhost:6379/0

# API Keys
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
LANGSMITH_API_KEY=your_langsmith_key_here

# Development Settings
ENVIRONMENT=development
DEBUG=true
```

### 3. Start Required Services

#### PostgreSQL
```bash
# Using Docker (recommended for development)
docker run --name media-planner-postgres \
  -e POSTGRES_DB=media_planner \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  -d postgres:15

# Or use existing PostgreSQL installation
```

#### Redis
```bash
# Using Docker
docker run --name media-planner-redis \
  -p 6379:6379 \
  -d redis:7-alpine

# Or use existing Redis installation
```

## Configuration

### LangGraph Configuration (`langgraph.json`)

The configuration file defines how LangGraph Server exposes the multi-agent system:

```json
{
  "dependencies": ["."],
  "graphs": {
    "media_planning_graph": "./app/services/langgraph/graph.py:graph"
  },
  "env": ".env",
  "python_version": "3.11",
  "http": {
    "cors": {
      "allow_origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
      "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
      "allow_headers": ["*"]
    }
  }
}
```

### Multi-Agent System Structure

The exposed graph includes:
- **Workspace Agent**: Handles Google Sheets parsing and data extraction
- **Planning Agent**: Develops campaign strategies and budget allocation
- **Insights Agent**: Analyzes performance data and generates insights
- **Supervisor Agent**: Orchestrates workflow and coordinates agents

## Running LangGraph Server

### Option 1: Using the Startup Script (Recommended)

```bash
# Start with default settings
python start_langgraph.py

# Start with custom port and file watching
python start_langgraph.py --port 8123 --watch --debug
```

### Option 2: Using LangGraph CLI Directly

```bash
# Basic startup (ensure venv is activated)
langgraph dev --port 8123 --config langgraph.json

# With file watching for development (ensure venv is activated)
langgraph dev --port 8123 --config langgraph.json --watch
```

### Verify Server is Running

Check server health:
```bash
curl http://localhost:8123/ok
```

Expected response:
```json
{"status": "ok"}
```

## LangGraph Studio Setup

### 1. Install LangGraph Studio

Download and install the desktop application from:
- **Website**: https://studio.langchain.com/
- **GitHub**: https://github.com/langchain-ai/langgraph-studio

### 2. Connect to Server

1. Open LangGraph Studio
2. Click "Connect to Server"
3. Enter server URL: `http://localhost:8123`
4. Studio should automatically detect the available graphs

### 3. Explore the Multi-Agent System

In Studio, you'll see:
- **Graph Visualization**: Visual representation of the agent workflow
- **Node Details**: Information about each agent and their capabilities
- **State Inspection**: Real-time view of workflow state
- **Execution Traces**: Step-by-step execution history

## Using Studio for Debugging

### Visual Debugging Features

1. **Real-time Execution**: Watch agents execute in real-time
2. **State Inspection**: Examine agent states at any point
3. **Breakpoints**: Pause execution at specific nodes
4. **Step-through**: Execute workflow step-by-step
5. **Message Tracing**: Track messages between agents

### Workflow Testing

1. **Input Simulation**: Send test inputs to the workflow
2. **Agent Isolation**: Test individual agents
3. **State Manipulation**: Modify state during execution
4. **Performance Monitoring**: Monitor execution times and resource usage

### Common Debug Scenarios

#### Testing Agent Interactions
```javascript
// Example input for testing
{
  "campaign_data": {
    "name": "Q4 Campaign",
    "budget": 50000,
    "channels": ["google_ads", "facebook_ads"]
  },
  "goals": {
    "target_audience": "B2B SaaS",
    "kpis": ["conversions", "cpa", "roas"]
  }
}
```

#### Monitoring State Changes
- Watch how data flows between agents
- Verify state persistence across nodes
- Check error handling and recovery

## Development Workflow

### 1. Code Changes

When modifying agent code:
1. Save your changes
2. LangGraph server will auto-reload (if `--watch` is enabled)
3. Refresh Studio to see updates

### 2. Testing New Features

1. **Modify Agent Logic**: Update agent implementations
2. **Test in Studio**: Use Studio to test changes interactively
3. **Debug Issues**: Use breakpoints and state inspection
4. **Iterate**: Refine based on visual feedback

### 3. Performance Optimization

1. **Monitor Execution**: Use Studio's performance metrics
2. **Identify Bottlenecks**: Find slow agents or operations
3. **Optimize Code**: Improve based on insights
4. **Validate**: Confirm improvements in Studio

## Troubleshooting

### Common Issues

#### Server Won't Start
```bash
# Check dependencies (ensure venv is activated)
pip install -r requirements.txt

# Verify configuration
cat langgraph.json

# Check logs
python start_langgraph.py --debug
```

#### Studio Can't Connect
```bash
# Verify server is running
curl http://localhost:8123/ok

# Check firewall/network settings
# Ensure port 8123 is accessible
```

#### Graph Not Loading
```bash
# Test graph compilation
python -c "from app.services.langgraph.graph import graph; print('Graph compiled successfully')"

# Check for import errors
python app/services/langgraph/graph.py
```

### Error Messages

#### "Module not found"
- Ensure all dependencies are installed: `pip install -r requirements.txt` (with venv activated)
- Check Python path and imports

#### "Database connection failed"
- Verify PostgreSQL is running
- Check connection string in `.env`

#### "Graph compilation failed"
- Check agent implementations
- Verify state model definitions

## Advanced Configuration

### Custom Authentication

To enable authentication:
```json
{
  "http": {
    "disable_studio_auth": false
  },
  "auth": {
    "path": "src/auth.py:auth_handler"
  }
}
```

### Production Deployment

For production use:
1. Use PostgreSQL for persistence
2. Configure proper authentication
3. Set up monitoring and logging
4. Use environment-specific configuration

### Scaling

For high-throughput scenarios:
1. Use PostgreSQL connection pooling
2. Configure Redis clustering
3. Deploy multiple server instances
4. Use load balancing

## Next Steps

1. **Explore Agents**: Familiarize yourself with each agent's functionality
2. **Test Scenarios**: Create test campaigns to understand the workflow
3. **Customize**: Modify agents based on your specific requirements
4. **Monitor**: Use Studio to monitor production workflows
5. **Optimize**: Continuously improve based on insights

## Resources

- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [LangGraph Studio Guide](https://python.langchain.com/docs/langgraph/how-tos/studio)
- [Multi-Agent Patterns](https://python.langchain.com/docs/langgraph/tutorials/multi_agent)
- [Media Planning Architecture](./docs/LANGGRAPH_ARCHITECTURE.md) 