#!/bin/bash

# Install Python dependencies
if [ -f "backend/requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip install -r backend/requirements.txt
else
    echo "Python requirements file not found. Skipping Python dependencies installation."
fi

# Install Node.js dependencies
if [ -f "frontend/package.json" ]; then
    echo "Installing Node.js dependencies..."
    cd frontend
    npm install
    cd ..
else
    echo "Node.js package.json file not found. Skipping Node.js dependencies installation."
fi

# Print completion message
echo "All dependencies have been installed successfully."