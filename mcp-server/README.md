# GoETF MCP Server

Simple MCP (Model Context Protocol) server that exposes GoETF ETF data via the public API.

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set environment variables
```bash
export GOETF_API_URL=https://etfdata-production.up.railway.app
export GOETF_API_KEY=your_api_key_here
```

### 3. Run the server
```bash
python server.py
```

## Configuration

- `GOETF_API_URL` (default: `http://localhost:8000`): Base URL of GoETF API
- `GOETF_API_KEY` (optional): API key for authentication

## Tools

### `list_etfs`
List available ETFs in the GoETF database.

**Parameters:**
- `provider` (string, optional): Filter by provider (e.g., "UBS", "iShares")
- `limit` (integer, default: 50): Maximum number of ETFs to return

**Example:**
```json
{
  "provider": "UBS",
  "limit": 20
}
```

## Integration

### Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "goetf": {
      "command": "python",
      "args": ["/path/to/mcp-server/server.py"],
      "env": {
        "GOETF_API_URL": "https://etfdata-production.up.railway.app",
        "GOETF_API_KEY": "your_key_here"
      }
    }
  }
}
```
