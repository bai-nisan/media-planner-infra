#!/bin/bash

# Temporal Cluster Management Script
# Usage: ./scripts/temporal-start.sh [start|stop|restart|status|logs]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.temporal.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[TEMPORAL]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker and Docker Compose are available
check_dependencies() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
}

# Function to start Temporal cluster
start_temporal() {
    print_status "Starting Temporal cluster..."
    
    cd "$PROJECT_DIR"
    
    # Use docker compose if available, fallback to docker-compose
    if docker compose version &> /dev/null; then
        docker compose -f docker-compose.temporal.yml up -d
    else
        docker-compose -f docker-compose.temporal.yml up -d
    fi
    
    print_status "Waiting for services to be healthy..."
    sleep 10
    
    # Check service health
    check_health
    
    print_success "Temporal cluster started successfully!"
    print_status "Web UI available at: http://localhost:8088"
    print_status "gRPC endpoint: localhost:7233"
}

# Function to stop Temporal cluster
stop_temporal() {
    print_status "Stopping Temporal cluster..."
    
    cd "$PROJECT_DIR"
    
    if docker compose version &> /dev/null; then
        docker compose -f docker-compose.temporal.yml down
    else
        docker-compose -f docker-compose.temporal.yml down
    fi
    
    print_success "Temporal cluster stopped successfully!"
}

# Function to restart Temporal cluster
restart_temporal() {
    print_status "Restarting Temporal cluster..."
    stop_temporal
    sleep 5
    start_temporal
}

# Function to check service health
check_health() {
    print_status "Checking service health..."
    
    # Check PostgreSQL
    if docker exec temporal-postgres pg_isready -U temporal > /dev/null 2>&1; then
        print_success "PostgreSQL is healthy"
    else
        print_warning "PostgreSQL is not responding"
    fi
    
    # Check Elasticsearch
    if curl -f http://localhost:9200/_cluster/health > /dev/null 2>&1; then
        print_success "Elasticsearch is healthy"
    else
        print_warning "Elasticsearch is not responding"
    fi
    
    # Check Temporal Server
    if docker exec temporal-cli temporal workflow list --address temporal-server:7233 > /dev/null 2>&1; then
        print_success "Temporal Server is healthy"
    else
        print_warning "Temporal Server is not responding"
    fi
    
    # Check Web UI
    if curl -f http://localhost:8088 > /dev/null 2>&1; then
        print_success "Temporal Web UI is healthy"
    else
        print_warning "Temporal Web UI is not responding"
    fi
}

# Function to show service status
show_status() {
    print_status "Temporal cluster status:"
    
    cd "$PROJECT_DIR"
    
    if docker compose version &> /dev/null; then
        docker compose -f docker-compose.temporal.yml ps
    else
        docker-compose -f docker-compose.temporal.yml ps
    fi
    
    echo ""
    check_health
}

# Function to show logs
show_logs() {
    cd "$PROJECT_DIR"
    
    if [ -n "$2" ]; then
        # Show logs for specific service
        if docker compose version &> /dev/null; then
            docker compose -f docker-compose.temporal.yml logs -f "$2"
        else
            docker-compose -f docker-compose.temporal.yml logs -f "$2"
        fi
    else
        # Show logs for all services
        if docker compose version &> /dev/null; then
            docker compose -f docker-compose.temporal.yml logs -f
        else
            docker-compose -f docker-compose.temporal.yml logs -f
        fi
    fi
}

# Function to create namespace
create_namespace() {
    local namespace=${2:-"media-planner"}
    print_status "Creating namespace: $namespace"
    
    docker exec temporal-cli temporal operator namespace create $namespace --address temporal-server:7233
    
    print_success "Namespace '$namespace' created successfully!"
}

# Function to show help
show_help() {
    echo "Temporal Cluster Management Script"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  start              Start the Temporal cluster"
    echo "  stop               Stop the Temporal cluster"
    echo "  restart            Restart the Temporal cluster"
    echo "  status             Show cluster status and health"
    echo "  logs [service]     Show logs (optionally for specific service)"
    echo "  namespace [name]   Create a new namespace (default: media-planner)"
    echo "  help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start                    # Start the cluster"
    echo "  $0 logs temporal-server     # Show server logs"
    echo "  $0 namespace my-namespace   # Create custom namespace"
}

# Main script logic
main() {
    check_dependencies
    
    case "${1:-help}" in
        start)
            start_temporal
            ;;
        stop)
            stop_temporal
            ;;
        restart)
            restart_temporal
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "$@"
            ;;
        namespace)
            create_namespace "$@"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@" 