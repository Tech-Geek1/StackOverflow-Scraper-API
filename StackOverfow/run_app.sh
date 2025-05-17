#!/usr/bin/env bash
SCRIPT="stackoverflow_scraper.py"
TIMEOUT=30
PORT=23468
export STACKOVERFLOW_API_PORT=$PORT

# Use python3 to create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Run the script in the background
python3 $SCRIPT &

# Wait for the server to start
while ! $(curl -s localhost:$PORT > /dev/null) && [ $TIMEOUT -gt 0 ]; do
    sleep 1
    ((TIMEOUT--))
done

# Kill the script process
pkill -f $SCRIPT

# Deactivate the virtual environment
deactivate

# Check if the server started successfully
if [ $TIMEOUT -gt 0 ]; then
    echo "Verified"
else
    echo "Failed"
fi

