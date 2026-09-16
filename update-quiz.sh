#!/bin/bash

# Cotton Flat Bar Quiz Auto-Update Script
# This script pulls the latest Quiz.py from the GitHub repo and restarts the service

REPO_DIR="/home/pi/CottonFlatBarQuiz"
REPO_URL="https://github.com/DamianRoberts432/CottonFlatBarQuiz.git"

cd "$REPO_DIR"

# Pull latest changes
git pull origin main

# Restart the service
sudo systemctl restart cotton-flat-quiz.service

echo "Quiz.py updated and service restarted at $(date)"
