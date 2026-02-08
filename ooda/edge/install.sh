#!/bin/bash
#
# OODA Edge Installer for Jetson Nano
# This script verifies prerequisites and sets up the OODA edge services
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Minimum version requirements
MIN_DOCKER_VERSION="19.03"
MIN_COMPOSE_VERSION="1.25"

print_status() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo ""
    echo "========================================"
    echo " $1"
    echo "========================================"
    echo ""
}

# Compare version strings (returns 0 if $1 >= $2)
version_gte() {
    [ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

check_jetson() {
    print_header "Checking Jetson Platform"

    if [ -f /etc/nv_tegra_release ]; then
        TEGRA_RELEASE=$(cat /etc/nv_tegra_release)f
        print_status "Jetson platform detected"
        echo "  $TEGRA_RELEASE"
    else
        print_warning "This does not appear to be a Jetson device"
        echo "  /etc/nv_tegra_release not found"
        echo "  Continuing anyway..."
    fi
}

check_docker() {
    print_header "Checking Docker Installation"

    # Check if docker is installed
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        echo ""
        echo "Please install Docker first. For Jetson Nano, run:"
        echo ""
        echo "  # Install Docker"
        echo "  curl -fsSL https://get.docker.com -o get-docker.sh"
        echo "  sudo sh get-docker.sh"
        echo ""
        echo "  # Add user to docker group"
        echo "  sudo usermod -aG docker \$USER"
        echo ""
        echo "  # Log out and back in, then verify with:"
        echo "  docker --version"
        echo ""
        exit 1
    fi

    # Get docker version
    DOCKER_VERSION=$(docker --version | grep -oP '\d+\.\d+' | head -1)

    if version_gte "$DOCKER_VERSION" "$MIN_DOCKER_VERSION"; then
        print_status "Docker version $DOCKER_VERSION installed (minimum: $MIN_DOCKER_VERSION)"
    else
        print_error "Docker version $DOCKER_VERSION is below minimum required ($MIN_DOCKER_VERSION)"
        exit 1
    fi

    # Check if docker daemon is running
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running"
        echo ""
        echo "Start Docker with:"
        echo "  sudo systemctl start docker"
        echo ""
        exit 1
    fi
    print_status "Docker daemon is running"

    # Check if user can run docker without sudo
    if ! docker ps &> /dev/null; then
        print_warning "Current user cannot run Docker without sudo"
        echo "  Run: sudo usermod -aG docker \$USER"
        echo "  Then log out and back in"
    else
        print_status "User has Docker permissions"
    fi
}

check_docker_compose() {
    print_header "Checking Docker Compose Installation"

    # Check for docker-compose (v1) or docker compose (v2)
    COMPOSE_CMD=""
    COMPOSE_VERSION=""

    if docker compose version &> /dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
        COMPOSE_VERSION=$(docker compose version | grep -oP '\d+\.\d+' | head -1)
    elif command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
        COMPOSE_VERSION=$(docker-compose --version | grep -oP '\d+\.\d+' | head -1)
    fi

    if [ -z "$COMPOSE_CMD" ]; then
        print_warning "Docker Compose is not installed. Installing docker-compose v2.24.0..."
        sudo curl -L https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-linux-aarch64 -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose

        if command -v docker-compose &> /dev/null; then
            COMPOSE_CMD="docker-compose"
            COMPOSE_VERSION=$(docker-compose --version | grep -oP '\d+\.\d+' | head -1)
            print_status "docker-compose v2.24.0 installed successfully"
        else
            print_error "Failed to install docker-compose"
            exit 1
        fi
    fi

    if version_gte "$COMPOSE_VERSION" "$MIN_COMPOSE_VERSION"; then
        print_status "Docker Compose version $COMPOSE_VERSION installed (minimum: $MIN_COMPOSE_VERSION)"
        print_status "Using command: $COMPOSE_CMD"
    else
        print_error "Docker Compose version $COMPOSE_VERSION is below minimum required ($MIN_COMPOSE_VERSION)"
        exit 1
    fi
}

check_nvidia_runtime() {
    print_header "Checking NVIDIA Container Runtime"

    # Check if nvidia-container-runtime is available
    if ! command -v nvidia-container-runtime &> /dev/null; then
        print_warning "NVIDIA Container Runtime not found"
        echo "  GPU acceleration may not work without it"
        echo ""
        echo "  Install with:"
        echo "  sudo apt-get install nvidia-container-runtime"
        echo ""
    else
        print_status "NVIDIA Container Runtime is installed"
    fi

    # Check Docker daemon configuration for nvidia runtime
    if docker info 2>/dev/null | grep -q "nvidia"; then
        print_status "NVIDIA runtime is configured in Docker"
    else
        print_warning "NVIDIA runtime may not be configured as default"
        echo "  Check /etc/docker/daemon.json for nvidia runtime configuration"
    fi
}

check_disk_space() {
    print_header "Checking Disk Space"

    # Get available space in GB
    AVAILABLE_GB=$(df -BG "$SCRIPT_DIR" | tail -1 | awk '{print $4}' | tr -d 'G')

    if [ "$AVAILABLE_GB" -lt 10 ]; then
        print_warning "Low disk space: ${AVAILABLE_GB}GB available"
        echo "  Recommend at least 10GB for Docker images and video buffer"
    else
        print_status "Disk space: ${AVAILABLE_GB}GB available"
    fi
}

setup_environment() {
    print_header "Setting Up Environment"

    ENV_FILE="$SCRIPT_DIR/.env"
    ENV_EXAMPLE="$SCRIPT_DIR/.env.example"

    # Create .env.example if it doesn't exist
    if [ ! -f "$ENV_EXAMPLE" ]; then
        cat > "$ENV_EXAMPLE" << 'EOF'
# AWS Credentials (required for upload)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1

# S3 Configuration
OODA_S3_BUCKET=your-bucket-name
OODA_S3_REGION=us-east-1

# Storage Configuration
OODA_MAX_BUFFER_SIZE_GB=20

# Logging
OODA_LOG_LEVEL=INFO

# Upload Schedule (hours)
OODA_UPLOAD_INTERVAL_HOURS=6

# Compression
OODA_COMPRESSION_ENABLED=true
OODA_COMPRESSION_CRF=28

# Batching
OODA_BATCHING_ENABLED=true
OODA_BATCH_WINDOW_HOURS=4
EOF
        print_status "Created .env.example template"
    fi

    if [ ! -f "$ENV_FILE" ]; then
        print_warning ".env file not found"
        echo "  Copy and configure the environment file:"
        echo "  cp $ENV_EXAMPLE $ENV_FILE"
        echo "  nano $ENV_FILE"
    else
        print_status ".env file exists"
    fi
}

print_summary() {
    print_header "Installation Summary"

    echo "All prerequisites are met!"
    echo ""
    echo "Next steps:"
    echo ""
    echo "  1. Configure environment variables:"
    echo "     cp .env.example .env"
    echo "     nano .env"
    echo ""
    echo "  2. (Optional) Configure upload settings:"
    echo "     cp upload/upload_config.example.yaml upload/upload_config.yaml"
    echo "     nano upload/upload_config.yaml"
    echo ""
    echo "  3. Build and start services:"
    echo "     docker-compose build"
    echo "     docker-compose up -d"
    echo ""
    echo "  4. Check service status:"
    echo "     docker-compose ps"
    echo "     docker-compose logs -f"
    echo ""
}

main() {
    echo ""
    echo "========================================"
    echo " OODA Edge Installer for Jetson Nano"
    echo "========================================"

    check_jetson
    check_docker
    check_docker_compose
    check_nvidia_runtime
    check_disk_space
    setup_environment
    print_summary
}

main "$@"
