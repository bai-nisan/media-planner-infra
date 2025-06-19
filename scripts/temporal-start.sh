#!/bin/bash

# Temporal CLI Management Script
# Usage: ./scripts/temporal-start.sh [start|stop|restart|status|logs|help]
# 
# This script provides a convenient wrapper around the Temporal CLI
# for local development. It replaces the old Docker-based approach.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Default configuration
DEFAULT_UI_PORT=8088
DEFAULT_GRPC_PORT=7233
DEFAULT_DB_FILE="temporal.db"
TEMPORAL_PID_FILE="$PROJECT_DIR/.temporal.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[TEMPORAL CLI]${NC} $1"
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

# Check if Temporal CLI is available
check_temporal_cli() {
    if ! command -v temporal &> /dev/null; then
        print_error "Temporal CLI is not installed or not in PATH"
        print_status "Install with: brew install temporal"
        print_status "Or see: https://docs.temporal.io/cli#install"
        exit 1
    fi
}

# Check if Temporal server is running
is_temporal_running() {
    if [ -f "$TEMPORAL_PID_FILE" ]; then
        local pid=$(cat "$TEMPORAL_PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$TEMPORAL_PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Function to start Temporal development server
start_temporal() {
    if is_temporal_running; then
        print_warning "Temporal server is already running"
        show_status
        return 0
    fi

    print_status "Starting Temporal development server..."
    
    cd "$PROJECT_DIR"
    
    # Determine if we should use persistence
    local cmd="temporal server start-dev --ui-port $DEFAULT_UI_PORT"
    
    if [ -f "$DEFAULT_DB_FILE" ] || [ "$1" = "--persist" ]; then
        cmd="$cmd --db-filename $DEFAULT_DB_FILE"
        print_status "Using persistent database: $DEFAULT_DB_FILE"
    else
        print_status "Using in-memory database (clean slate each restart)"
        print_status "Use '$0 start --persist' for persistent storage"
    fi
    
    # Start in background and save PID
    print_status "Starting server with command: $cmd"
    nohup $cmd > temporal.log 2>&1 &
    local pid=$!
    echo $pid > "$TEMPORAL_PID_FILE"
    
    # Wait a moment for startup
    sleep 3
    
    # Check if it's still running
    if ps -p "$pid" > /dev/null 2>&1; then
        print_success "Temporal development server started successfully!"
        print_status "PID: $pid"
        print_status "gRPC endpoint: localhost:$DEFAULT_GRPC_PORT"
        print_status "Web UI: http://localhost:$DEFAULT_UI_PORT"
        print_status "Logs: $PROJECT_DIR/temporal.log"
        print_status ""
        print_status "To view logs: tail -f temporal.log"
        print_status "To stop: $0 stop"
    else
        print_error "Failed to start Temporal server"
        rm -f "$TEMPORAL_PID_FILE"
        print_status "Check logs: cat temporal.log"
        exit 1
    fi
}

# Function to stop Temporal server
stop_temporal() {
    if ! is_temporal_running; then
        print_warning "Temporal server is not running"
        return 0
    fi
    
    print_status "Stopping Temporal development server..."
    
    local pid=$(cat "$TEMPORAL_PID_FILE")
    kill "$pid" 2>/dev/null || true
    
    # Wait for graceful shutdown
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        ((count++))
    done
    
    # Force kill if still running
    if ps -p "$pid" > /dev/null 2>&1; then
        print_warning "Graceful shutdown failed, force killing..."
        kill -9 "$pid" 2>/dev/null || true
    fi
    
    rm -f "$TEMPORAL_PID_FILE"
    print_success "Temporal server stopped successfully!"
}

# Function to restart Temporal server
restart_temporal() {
    print_status "Restarting Temporal development server..."
    stop_temporal
    sleep 2
    start_temporal "$1"
}

# Function to check server health and show status
check_health() {
    print_status "Checking Temporal server health..."
    
    # Check if process is running
    if is_temporal_running; then
        local pid=$(cat "$TEMPORAL_PID_FILE")
        print_success "Temporal server process is running (PID: $pid)"
    else
        print_error "Temporal server process is not running"
        return 1
    fi
    
    # Check gRPC connectivity
    if temporal server status > /dev/null 2>&1; then
        print_success "Temporal gRPC endpoint is healthy"
    else
        print_warning "Temporal gRPC endpoint is not responding"
    fi
    
    # Check Web UI
    if curl -f http://localhost:$DEFAULT_UI_PORT > /dev/null 2>&1; then
        print_success "Temporal Web UI is healthy"
    else
        print_warning "Temporal Web UI is not responding"
    fi
}

# Function to show service status
show_status() {
    print_status "Temporal development server status:"
    echo ""
    
    if is_temporal_running; then
        local pid=$(cat "$TEMPORAL_PID_FILE")
        print_success "Status: RUNNING (PID: $pid)"
        
        # Show server info
        echo "  gRPC Endpoint: localhost:$DEFAULT_GRPC_PORT"
        echo "  Web UI: http://localhost:$DEFAULT_UI_PORT"
        echo "  Log File: $PROJECT_DIR/temporal.log"
        
        # Check if using persistent storage
        if [ -f "$PROJECT_DIR/$DEFAULT_DB_FILE" ]; then
            echo "  Database: Persistent ($DEFAULT_DB_FILE)"
        else
            echo "  Database: In-memory"
        fi
        
        echo ""
        check_health
    else
        print_warning "Status: NOT RUNNING"
        echo ""
        print_status "Start with: $0 start"
    fi
}

# Function to show logs
show_logs() {
    if [ -f "$PROJECT_DIR/temporal.log" ]; then
        if [ "$1" = "-f" ] || [ "$1" = "--follow" ]; then
            print_status "Following Temporal server logs (Ctrl+C to stop)..."
            tail -f "$PROJECT_DIR/temporal.log"
        else
            print_status "Showing last 50 lines of Temporal server logs..."
            tail -50 "$PROJECT_DIR/temporal.log"
        fi
    else
        print_warning "No log file found at $PROJECT_DIR/temporal.log"
        print_status "Start the server first with: $0 start"
    fi
}

# Function to create namespace
create_namespace() {
    local namespace=${1:-"media-planner"}
    print_status "Creating namespace: $namespace"
    
    if ! is_temporal_running; then
        print_error "Temporal server is not running. Start it first with: $0 start"
        exit 1
    fi
    
    if temporal operator namespace create "$namespace"; then
        print_success "Namespace '$namespace' created successfully!"
    else
        print_warning "Failed to create namespace '$namespace' (it may already exist)"
    fi
}

# Function to show help
show_help() {
    echo "Temporal CLI Management Script (Updated for Temporal CLI)"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  start [--persist]      Start the Temporal development server"
    echo "  stop                   Stop the Temporal development server"
    echo "  restart [--persist]    Restart the Temporal development server"
    echo "  status                 Show server status and health"
    echo "  logs [-f|--follow]     Show server logs"
    echo "  namespace [name]       Create a new namespace (default: media-planner)"
    echo "  help                   Show this help message"
    echo ""
    echo "Options:"
    echo "  --persist             Use persistent SQLite database (retains data between restarts)"
    echo ""
    echo "Examples:"
    echo "  $0 start              # Start with in-memory database"
    echo "  $0 start --persist    # Start with persistent database"
    echo "  $0 logs -f           # Follow logs in real-time"
    echo "  $0 namespace my-ns   # Create custom namespace"
    echo ""
    echo "New Temporal CLI Benefits:"
    echo "  ✅ Native Apple Silicon support (no Docker needed)"
    echo "  ✅ Instant startup (seconds vs minutes)"
    echo "  ✅ Zero configuration required"
    echo "  ✅ Built-in SQLite persistence"
    echo "  ✅ Official Temporal recommendation"
    echo ""
    echo "Endpoints:"
    echo "  gRPC API: localhost:$DEFAULT_GRPC_PORT"
    echo "  Web UI:   http://localhost:$DEFAULT_UI_PORT"
}

# Main script logic
main() {
    check_temporal_cli
    
    case "${1:-help}" in
        start)
            start_temporal "$2"
            ;;
        stop)
            stop_temporal
            ;;
        restart)
            restart_temporal "$2"
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "$2"
            ;;
        namespace)
            create_namespace "$2"
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