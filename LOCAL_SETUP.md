# 🚀 Media Planning Platform - Local Setup Guide

A comprehensive guide to run the **Media Planning Platform** with **LangGraph Multi-Agent System** locally.

## 📋 Prerequisites

- **Python 3.11+**
- **Poetry** (`curl -sSL https://install.python-poetry.org | python3 -`)
- **Git**
- **OpenAI API Key** (required for AI agents)
- **Supabase Account** (for database)

## 🛠️ Quick Setup (5 minutes)

### 1. Install Dependencies
```bash
cd media-planner-infra
poetry install
```

### 2. Configure Environment
```bash
# Copy and edit environment file
cp .env.example .env
# Edit .env with your API keys (see configuration section below)
```

### 3. Start the Server
```bash
poetry run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Test Your Setup
```bash
# Run our automated test script
./test_local_setup.sh

# Or manually visit:
# http://localhost:8000/api/docs
```

## ⚙️ Detailed Configuration

### Required Environment Variables

Edit your `.env` file with these **required** variables:

```bash
# 🔑 API Keys (REQUIRED)
OPENAI_API_KEY=sk-your_openai_api_key_here

# 🗄️ Database (REQUIRED)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_JWT_SECRET=your_jwt_secret

# 🔧 Application Settings
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=your_secret_key_at_least_32_characters_long
```

### Optional Services

```bash
# 📦 Redis (for caching)
REDIS_URL=redis://localhost:6379

# ⏱️ Temporal (for workflow orchestration)
TEMPORAL_HOST=localhost
TEMPORAL_PORT=7233
```

## 🔑 Getting API Keys

### OpenAI API Key (Required)
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create a new API key
3. Add to `.env`: `OPENAI_API_KEY=sk-...`

### Supabase Setup (Required)
1. Go to [Supabase](https://supabase.com)
2. Create a new project
3. Get credentials from Settings > API:
   - **Project URL** → `SUPABASE_URL`
   - **anon public key** → `SUPABASE_KEY`
   - **JWT Secret** → `SUPABASE_JWT_SECRET`

## 🏗️ Architecture Overview

The system includes:

- **FastAPI Backend** (Port 8000)
- **LangGraph Multi-Agent System**:
  - 🔄 **Workspace Agent** - Data ingestion and management
  - 📊 **Planning Agent** - Campaign strategy and optimization  
  - 💡 **Insights Agent** - Performance analysis and recommendations
  - 👨‍💼 **Supervisor Agent** - Workflow orchestration
- **Supabase Database** (Multi-tenant)
- **Optional: Redis Cache**
- **Optional: Temporal Workflows**

## 🚀 Running Different Configurations

### Basic Setup (Minimal)
```bash
# Just the FastAPI server with agents
poetry run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### With Redis Caching
```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start FastAPI
poetry run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Full Stack with Temporal
```bash
# Terminal 1: Start Temporal
docker-compose -f docker-compose.temporal-minimal.yml up

# Terminal 2: Start FastAPI
poetry run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## ✅ Testing Your Setup

### Automated Testing
```bash
# Run comprehensive test suite
./test_local_setup.sh
```

### Manual Testing

1. **API Documentation**: http://localhost:8000/api/docs
2. **Health Check**: http://localhost:8000/health
3. **Agent Status**: http://localhost:8000/api/v1/agents/health

### Key Endpoints to Test

```bash
# Core API
curl http://localhost:8000/
curl http://localhost:8000/health

# Agent System
curl http://localhost:8000/api/v1/agents/
curl http://localhost:8000/api/v1/agents/health

# Business Logic
curl http://localhost:8000/api/v1/tenants/
curl http://localhost:8000/api/v1/workflows/health
```

## 🤖 Testing the Agent System

The LangGraph multi-agent system includes:

```bash
# Test agent initialization
curl http://localhost:8000/api/v1/agents/health

# Expected response:
{
  "status": "healthy",
  "agents": {
    "workspace": "initialized",
    "planning": "initialized", 
    "insights": "initialized",
    "supervisor": "initialized"
  },
  "dependencies": {
    "supabase": "connected",
    "openai": "configured"
  }
}
```

## 🐛 Troubleshooting

### Common Issues

**1. Import Errors**
```bash
# Reinstall dependencies
poetry install --no-cache
```

**2. Agent Initialization Failures**
```bash
# Check OpenAI API key
echo $OPENAI_API_KEY

# Check agent logs
tail -f server.log
```

**3. Database Connection Issues**
```bash
# Test Supabase connection
curl http://localhost:8000/api/v1/database/health
```

**4. Port Already in Use**
```bash
# Use different port
poetry run uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Debug Mode

```bash
# Run with detailed logging
export DEBUG=true
poetry run uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level debug
```

## 📝 Development Workflow

1. **Start Development Server**:
   ```bash
   poetry run uvicorn main:app --reload
   ```

2. **View Logs**:
   ```bash
   tail -f server.log
   ```

3. **Test Changes**:
   ```bash
   ./test_local_setup.sh
   ```

4. **Run Tests**:
   ```bash
   poetry run pytest
   ```

## 🔧 Optional Enhancements

### Install Redis (for caching)
```bash
# macOS
brew install redis
redis-server

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis
```

### Install Temporal (for workflows)
```bash
# Use Docker
docker-compose -f docker-compose.temporal-minimal.yml up
```

## 📖 Next Steps

- Visit **API Docs**: http://localhost:8000/api/docs
- Test **Agent Endpoints**: http://localhost:8000/api/v1/agents/
- Check **System Health**: http://localhost:8000/health
- Review **Agent Logs**: `tail -f server.log`

## 🆘 Support

If you encounter issues:

1. Run `./test_local_setup.sh` to diagnose problems
2. Check `server.log` for detailed error messages
3. Verify all required environment variables are set
4. Ensure OpenAI API key has sufficient credits

---

**🎉 You're ready to start developing with the Media Planning Platform!** 