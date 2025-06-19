#!/bin/bash
source venv/bin/activate
echo "Running Black..."
black .
echo "Running isort..."
isort .
echo "Running mypy..."
mypy . 