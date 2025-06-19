#!/bin/bash
source venv/bin/activate
pytest --cov=src --cov-report=html --cov-report=term-missing 