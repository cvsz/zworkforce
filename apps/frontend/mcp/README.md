# Canva Dev MCP Server

Canva Dev MCP Server setup for z-platform frontend development.

## What is it?

The Canva Dev MCP Server is a local developer tool that connects coding agents to Canva's developer docs, examples, and helper tooling.

## Setup

### Prerequisites

- Node.js >= 18
- Claude Code, Cursor, or other MCP-compatible agent

### Installation

```bash
# Install the Canva Dev MCP Server globally
npm install -g @canva/dev-mcp-server

# Or run via npx
npx @canva/dev-mcp-server
```

### Configuration

Add to your agent config (e.g., `.claude.json` or MCP config):

```json
{
  "mcpServers": {
    "canva-dev": {
      "command": "npx",
      "args": ["@canva/dev-mcp-server"]
    }
  }
}
```

## Usage

Once connected, your coding agent can:
- Answer Canva API questions with direct documentation access
- Generate Canva app SDK code
- Validate API requests against Canva specs
- Scaffold Canva integration projects

## References

- Docs: https://www.canva.dev/docs/connect/mcp-server
- Canva Connect API: https://www.canva.dev/docs/connect
- Canva Apps SDK: https://www.canva.dev/docs/apps
- Dev Blog: https://www.canva.dev/blog/developers/canva-and-coding-agents-platforms/
