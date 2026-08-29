#!/bin/bash
# FreeDNS (afraid.org) Dynamic DNS Update Script
# Replace YOUR_UPDATE_TOKEN with the token from your FreeDNS account
# You can find the direct update URL in the "Dynamic DNS" section of freedns.afraid.org

TOKEN="YOUR_UPDATE_TOKEN"
UPDATE_URL="https://freedns.afraid.org/dynamic/update.php?${TOKEN}"

echo "Starting FreeDNS update for zacino.mooo.com..."
curl -s "$UPDATE_URL"
echo -e "\nUpdate completed at $(date)"
