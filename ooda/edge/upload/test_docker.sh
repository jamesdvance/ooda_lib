#!/bin/bash
# Quick test script for the upload Docker container

set -e

echo "=== OODA Upload Docker Test ==="
echo

# Create .env from example if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

# Create test directories
mkdir -p test_data/video_buffer test_logs

echo "1. Building container..."
docker-compose -f docker-compose.local.yml build

echo
echo "2. Testing imports..."
docker-compose -f docker-compose.local.yml up upload
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo
    echo "SUCCESS: Container builds and imports work correctly"
    echo
    echo "Next steps:"
    echo "  - Test daemon mode: docker-compose -f docker-compose.local.yml --profile daemon up upload-daemon"
    echo "  - Test status:      docker-compose -f docker-compose.local.yml run upload python -m upload status"
    echo "  - Run once:         docker-compose -f docker-compose.local.yml run upload python -m upload once"
else
    echo
    echo "FAILED: Container test failed with exit code $EXIT_CODE"
    exit 1
fi
