#!/bin/bash
# Copies AWS credentials from environment variables into the upload .env file
# Usage: AWS_ACCESS_KEY_ID=xxx AWS_SECRET_ACCESS_KEY=yyy ./configure.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/upload/.env"
GENERATED="$SCRIPT_DIR/upload/.env.generated"

if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
  echo "Error: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set"
  exit 1
fi

if [ ! -f "$GENERATED" ]; then
  echo "Error: $GENERATED not found. Run 'terraform apply' first."
  exit 1
fi

cp "$GENERATED" "$ENV_FILE"

# Prepend AWS credentials
sed -i "1a\\
AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID\\
AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY" "$ENV_FILE"

echo "Wrote credentials to $ENV_FILE"
