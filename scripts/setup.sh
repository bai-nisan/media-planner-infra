#!/bin/bash
set -e

echo "Setting up development environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

echo "Development environment setup complete!" 