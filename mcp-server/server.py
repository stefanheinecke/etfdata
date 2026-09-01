"""MCP server for GoETF — lists available ETFs via the public API."""
import os
import sys
import httpx
import asyncio
from mcp.server import MCPServer

# Configuration
API_BASE_URL = os.getenv("GOETF_API_URL", "http://localhost:8000")
API_KEY = os.getenv("GOETF_API_KEY", "")
PORT = int(os.getenv("PORT", 8080))


async def list_etfs_impl(provider: str = None, limit: int = 50) -> str:
    """Fetch and return ETFs from GoETF API."""
    try:
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

        if not etfs:
            return "No ETFs found."

        lines = [f"Found {len(etfs)} ETF(s):\n"]
        for etf in etfs:
            isin = etf.get("isin", "N/A")
            name = etf.get("name", "N/A")
            provider_name = etf.get("provider", "N/A")
            ter = etf.get("ter")
            ter_str = f" | TER: {ter}%" if ter else ""
            lines.append(f"  • {isin} — {name} ({provider_name}){ter_str}")

        return "\n".join(lines)

    except httpx.HTTPError as e:
        return f"API error: {e.response.status_code if hasattr(e, 'response') else 'unknown'}"
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    server = MCPServer(
        name="goetf-mcp",
        title="GoETF",
        description="List ETFs available in GoETF database",
        version="1.0.0"
    )

    @server.tool()
    async def list_etfs(provider: str = None, limit: int = 50) -> str:
        """
        List available ETFs in GoETF database.

        Args:
            provider: Filter by provider (e.g., 'UBS', 'iShares')
            limit: Maximum number of ETFs to return (default 50)
        """
        return await list_etfs_impl(provider, limit)

    asyncio.run(server.run_streamable_http_async(host="0.0.0.0", port=PORT))


if __name__ == "__main__":
    main()



async def list_etfs_impl(provider: str = None, limit: int = 50) -> str:
    """Fetch and return ETFs from GoETF API."""
    try:
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
            return "No ETFs found."
        
        lines = [f"Found {len(etfs)} ETF(s):\n"]
        for etf in etfs:
            isin = etf.get("isin", "N/A")
            name = etf.get("name", "N/A")
            provider_name = etf.get("provider", "N/A")
            ter = etf.get("ter")
            ter_str = f" | TER: {ter}%" if ter else ""
            lines.append(f"  • {isin} — {name} ({provider_name}){ter_str}")
        
        return "\n".join(lines)

    except httpx.HTTPError as e:
        return f"API error: {e.response.status_code if hasattr(e, 'response') else 'unknown'}\nURL: {API_BASE_URL}/etfs\nMake sure GOETF_API_URL and GOETF_API_KEY are set correctly."
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    sys.stderr.write("[GOETF MCP] main() called\n")
    sys.stderr.flush()
    
    server = MCPServer(
        name="goetf-mcp",
        title="GoETF API",
        description="MCP server for GoETF — lists available ETFs via the public API",
        version="1.0.0"
    )
    
    sys.stderr.write("[GOETF MCP] MCPServer created, registering tool\n")
    sys.stderr.flush()

    @server.tool()
    async def list_etfs(provider: str = None, limit: int = 50) -> str:
        """
        List available ETFs in GoETF database.
        
        Args:
            provider: Filter by provider (e.g., 'UBS', 'iShares')
            limit: Maximum number of ETFs to return (default 50)
        """
        return await list_etfs_impl(provider, limit)

    sys.stderr.write("[GOETF MCP] Running server via stdio...\n")
    sys.stderr.flush()
    
    import asyncio
    try:
        asyncio.run(server.run_stdio_async())
    except KeyboardInterrupt:
        sys.stderr.write("[GOETF MCP] Server stopped.\n")


if __name__ == "__main__":
    main()
