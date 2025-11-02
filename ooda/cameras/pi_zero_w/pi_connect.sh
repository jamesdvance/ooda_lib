#!/bin/bash
# Script to connect to a Raspberry Pi

# Load configuration from YAML file using yq
# Check if yq is installed
if ! command -v yq &> /dev/null; then
    echo "Error: yq is not installed. Please install it using:"
    echo "  pip install yq"
    exit 1
fi

# Default to Pi Zero if no argument is provided
PI_TYPE="zero"
if [ "$1" == "pi4" ]; then
    PI_TYPE="pi4"
fi

# Load configuration values
PI_USER=$(yq -r .pi.$PI_TYPE.user config.yaml)
PI_HOST=$(yq -r .pi.$PI_TYPE.host config.yaml)

echo "Connecting to $PI_TYPE at $PI_HOST..."
ssh ${PI_USER}@${PI_HOST}