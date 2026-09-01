"""MCP server for GoETF — lists available ETFs via the public API."""
import os
import json
import httpx
from mcp.server import Server
from mcp.types import Tool, TextContent, ToolResult

# Configuration
API_BASE_URL = os.getenv("GOETF_API_URL", "http://localhost:8000")
API_KEY = os.getenv("GOETF_API_KEY", "")

server = Server("goetf-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="list_etfs",
            description="List available ETFs in GoETF database",
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "description": "Filter by provider (e.g., 'UBS', 'iShares')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of ETFs to return (default 50)",
                        "default": 50,
                    },
                },
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> ToolResult:
    """Handle tool calls."""
    if name == "list_etfs":
        return await handle_list_etfs(arguments)
    return ToolResult(
        content=[TextContent(type="text", text=f"Unknown tool: {name}")],
        isError=True,
    )


async def handle_list_etfs(arguments: dict) -> ToolResult:
    """Fetch and return ETFs from GoETF API."""
    try:
        provider = arguments.get("provider")
        limit = arguments.get("limit", 50)

        headers = {}
        if API_KEY:
            headers["x-api-key"] = API_KEY

        url = f"{API_BASE_URL}/etfs"
        params = {"limit": limit}
        if provider:
            params["provider"] = provider

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            etfs = response.json()

        # Format output
        if not etfs:
            text = "No ETFs found."
        else:
            lines = [f"Found {len(etfs)} ETF(s):\n"]
            for etf in etfs:
                isin = etf.get("isin", "N/A")
                name = etf.get("name", "N/A")
                provider = etf.get("provider", "N/A")
                ter = etf.get("ter")
                ter_str = f" | TER: {ter}%" if ter else ""
                lines.append(f"  • {isin} — {name} ({provider}){ter_str}")
            text = "\n".join(lines)

        return ToolResult(content=[TextContent(type="text", text=text)])

    except httpx.HTTPError as e:
        return ToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"API error: {e.response.status_code if hasattr(e, 'response') else 'unknown'}\nURL: {API_BASE_URL}/etfs\nMake sure GOETF_API_URL and GOETF_API_KEY are set correctly.",
                )
            ],
            isError=True,
        )
    except Exception as e:
        return ToolResult(
            content=[TextContent(type="text", text=f"Error: {str(e)}")],
            isError=True,
        )


if __name__ == "__main__":
    import asyncio
    server.run_stdio()
