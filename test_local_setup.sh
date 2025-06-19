#!/bin/bash

echo "🧪 Testing Media Planning Platform Local Setup..."

BASE_URL="http://localhost:8000"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to test endpoint
test_endpoint() {
    local endpoint=$1
    local description=$2
    
    echo -n "Testing $description... "
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$endpoint")
    
    if [ "$response" -eq 200 ]; then
        echo -e "${GREEN}✅ PASS${NC}"
        return 0
    else
        echo -e "${RED}❌ FAIL (HTTP $response)${NC}"
        return 1
    fi
}

# Test basic endpoints
echo -e "${YELLOW}🔍 Testing Core API Endpoints...${NC}"
test_endpoint "/" "Root endpoint"
test_endpoint "/health" "Health check"
test_endpoint "/api/docs" "API documentation"

# Test agent endpoints
echo -e "${YELLOW}🤖 Testing Agent System...${NC}"
test_endpoint "/api/v1/agents/" "Agent listing"
test_endpoint "/api/v1/agents/health" "Agent health check"

# Test other endpoints
echo -e "${YELLOW}🏢 Testing Business Endpoints...${NC}"
test_endpoint "/api/v1/tenants/" "Tenants endpoint"
test_endpoint "/api/v1/database/health" "Database health"
test_endpoint "/api/v1/workflows/health" "Workflows health"

echo -e "${YELLOW}📊 Detailed Agent Status:${NC}"
curl -s "$BASE_URL/api/v1/agents/health" | python -m json.tool 2>/dev/null | head -20

echo -e "${GREEN}🎉 Local setup test completed!${NC}"
echo -e "${YELLOW}📖 Access API docs at: http://localhost:8000/api/docs${NC}" 