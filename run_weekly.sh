#!/bin/bash
# Weekly meal plan generator — runs every Saturday morning via cron
# Generates next week's plan and sends grocery list to Slack (and WhatsApp if configured)
export PATH="$HOME/.toolbox/bin:$HOME/.local/bin:/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$(dirname "$0")"

python3 planner.py generate >> /tmp/meal_planner.log 2>&1

echo "$(date): Weekly meal plan generated" >> /tmp/meal_planner.log
