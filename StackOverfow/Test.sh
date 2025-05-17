#!/bin/bash

# Activate virtual environment
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Run Flask app in the background
python stackoverflow_scraper.py &

# Wait for the server to start
TIMEOUT=20
while ! nc -z localhost 23467; do
    sleep 1
    ((TIMEOUT--))
    if [ $TIMEOUT -le 0 ]; then
        echo "Server did not start in time"
        exit 1
    fi
done

echo "Server is up and running"

