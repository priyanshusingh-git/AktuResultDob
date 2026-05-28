#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"
export AKTU_RESULT_HOME="$DIR/.aktubot_http_home"

echo "==========================================="
echo " Starting AKTU Result                      "
echo "==========================================="
echo "Checking dependencies..."
echo "Using local app home: $AKTU_RESULT_HOME"

if ! command -v python3 &> /dev/null; then
    echo ""
    echo "ERROR: Python 3 was not found on this Mac."
    echo "Please download and install Python from: https://www.python.org/downloads/"
    echo ""
    read -p "Press [Enter] to close this window..."
    exit 1
fi

python3 -m pip install -r requirements.txt --quiet --disable-pip-version-check --user

echo "Starting application window..."
python3 main.py

echo ""
echo "AKTU Result has closed."
read -p "Press [Enter] to close this terminal window..."
