#!/bin/bash
#
# OODA Edge Runner
# Starts the OODA edge services using Docker Compose
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect compose command (v1 or v2)
if command -v docker compose &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif docker compose-version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo "Error: Docker Compose is not installed"
    echo "Run ./install.sh to check prerequisites"
    exit 1
fi

# Default action
ACTION="${1:-up}"

case "$ACTION" in
    up)
        echo "Starting OODA edge services..."
        $COMPOSE_CMD up -d
        echo ""
        echo "Services started. View logs with:"
        echo "  ./run.sh logs"
        ;;
    down)
        echo "Stopping OODA edge services..."
        $COMPOSE_CMD down
        ;;
    restart)
        echo "Restarting OODA edge services..."
        $COMPOSE_CMD restart
        ;;
    logs)
        $COMPOSE_CMD logs -f "${@:2}"
        ;;
    status|ps)
        $COMPOSE_CMD ps
        ;;
    build)
        echo "Building OODA edge images..."
        $COMPOSE_CMD build "${@:2}"
        ;;
    *)
        echo "Usage: $0 {up|down|restart|logs|status|build}"
        echo ""
        echo "Commands:"
        echo "  up       Start services in detached mode (default)"
        echo "  down     Stop and remove services"
        echo "  restart  Restart services"
        echo "  logs     Follow service logs (optionally specify service name)"
        echo "  status   Show service status"
        echo "  build    Build or rebuild services"
        exit 1
        ;;
esac