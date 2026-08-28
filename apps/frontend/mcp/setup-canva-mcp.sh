#!/usr/bin/env bash
# setup-canva-mcp.sh — Install and configure Canva Dev MCP Server for z-platform

set -euo pipefail

echo "Setting up Canva Dev MCP Server..."

# Install the MCP server
npm install -g @canva/dev-mcp-server

# Verify installation
if command -v canva-dev-mcp-server &> /dev/null; then
    echo "✓ Canva Dev MCP Server installed successfully"
else
    echo "✗ Installation failed"
    exit 1
fi

# Create MCP config if it doesn't exist
CONFIG_DIR="$HOME/.config/claude"
CONFIG_FILE="$CONFIG_DIR/settings.json"

mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_FILE" ]; then
    echo '{}' > "$CONFIG_FILE"
fi

# Add Canva Dev MCP to config
echo "Configuring MCP server in $CONFIG_FILE"
echo "Add the following to your MCP configuration:"
echo ""
echo '  "canva-dev": {'
echo '    "command": "npx",'
echo '    "args": ["@canva/dev-mcp-server"]'
echo '  }'
echo ""
echo "Setup complete!"
