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

    UPLOAD_ENV="$SCRIPT_DIR/upload/.env"
    GENERATED_ENV="$SCRIPT_DIR/upload/.env.generated"

    # Install the Terraform-generated .env if available
    if [ -f "$GENERATED_ENV" ]; then
        cp "$GENERATED_ENV" "$UPLOAD_ENV"
        print_status "Copied .env.generated to upload/.env"
    elif [ -f "$UPLOAD_ENV" ]; then
        print_status "upload/.env already exists"
    else
        print_error "No upload/.env or .env.generated found"
        echo "  Run 'terraform apply' in cloud/aws first, then re-copy the edge directory"
        exit 1
    fi

    # Inject AWS credentials from environment, then ~/.aws/credentials, then skip
    if [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
        sed -i '/^AWS_ACCESS_KEY_ID=/d; /^AWS_SECRET_ACCESS_KEY=/d' "$UPLOAD_ENV"
        echo "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID" >> "$UPLOAD_ENV"
        echo "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY" >> "$UPLOAD_ENV"
        print_status "Injected AWS credentials from environment"
    elif [ -f "$HOME/.aws/credentials" ]; then
        AWS_KEY=$(awk -F= '/aws_access_key_id/{print $2}' "$HOME/.aws/credentials" | tr -d ' ' | head -1)
        AWS_SECRET=$(awk -F= '/aws_secret_access_key/{print $2}' "$HOME/.aws/credentials" | tr -d ' ' | head -1)
        if [ -n "$AWS_KEY" ] && [ -n "$AWS_SECRET" ]; then
            sed -i '/^AWS_ACCESS_KEY_ID=/d; /^AWS_SECRET_ACCESS_KEY=/d' "$UPLOAD_ENV"
            echo "AWS_ACCESS_KEY_ID=$AWS_KEY" >> "$UPLOAD_ENV"
            echo "AWS_SECRET_ACCESS_KEY=$AWS_SECRET" >> "$UPLOAD_ENV"
            print_status "Injected AWS credentials from ~/.aws/credentials"
        fi
    else
        if grep -q 'AWS_ACCESS_KEY_ID=.' "$UPLOAD_ENV" 2>/dev/null; then
            print_status "AWS credentials already in upload/.env"
        else
            print_warning "AWS credentials not found"
            echo "  Run 'aws configure' or export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
        fi
    fi
}

setup_iot_certs() {
    print_header "Installing IoT Certificates"

    CERTS_SRC="$SCRIPT_DIR/certs"
    CERTS_DEST="/etc/ooda/iot"

    if [ ! -d "$CERTS_SRC" ]; then
        print_warning "No certs/ directory found, skipping IoT setup"
        return
    fi

    if [ ! -f "$CERTS_SRC/iot_certificate.pem" ] || [ ! -f "$CERTS_SRC/iot_private_key.pem" ]; then
        print_warning "IoT certificate files not found in certs/, skipping"
        return
    fi

    sudo mkdir -p "$CERTS_DEST"
    sudo cp "$CERTS_SRC/iot_certificate.pem" "$CERTS_DEST/cert.pem"
    sudo cp "$CERTS_SRC/iot_private_key.pem" "$CERTS_DEST/key.pem"
    print_status "Installed IoT certificate and private key to $CERTS_DEST"

    # Download Amazon Root CA if not already present
    if [ ! -f "$CERTS_DEST/root-ca.pem" ]; then
        sudo curl -s https://www.amazontrust.com/repository/AmazonRootCA1.pem -o "$CERTS_DEST/root-ca.pem"
        print_status "Downloaded Amazon Root CA"
    else
        print_status "Amazon Root CA already present"
    fi

    sudo chown -R root:root "$CERTS_DEST"
    sudo chmod 600 "$CERTS_DEST"/*
    print_status "Set certificate file permissions"
}

print_summary() {
    print_header "Installation Complete"

    echo "Next steps:"
    echo ""
    echo "  1. Build and start services:"
    echo "     ./run.sh build"
    echo "     ./run.sh up"
    echo ""
    echo "  2. Check service status:"
    echo "     ./run.sh status"
    echo "     ./run.sh logs"
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
    setup_iot_certs
    print_summary
}

main "$@"
