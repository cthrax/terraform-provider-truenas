#!/bin/bash
# Local acceptance testing script for TrueNAS Terraform Provider
# This script sets up environment variables and runs acceptance tests

set -e

# Check if TrueNAS credentials are provided
if [ -z "$TRUENAS_HOST" ]; then
    echo "Error: TRUENAS_HOST environment variable is not set"
    echo "Usage: TRUENAS_HOST=192.168.1.100 TRUENAS_TOKEN=your-token ./test-local.sh"
    exit 1
fi

if [ -z "$TRUENAS_TOKEN" ]; then
    echo "Error: TRUENAS_TOKEN environment variable is not set"
    echo "Usage: TRUENAS_HOST=192.168.1.100 TRUENAS_TOKEN=your-token ./test-local.sh"
    exit 1
fi

# Enable acceptance tests
export TF_ACC=1

echo "Running acceptance tests against TrueNAS at $TRUENAS_HOST"
echo "=================================================="

# Run all acceptance tests
go test ./internal/provider -v -run TestAcc

echo ""
echo "=================================================="
echo "Acceptance tests completed"
