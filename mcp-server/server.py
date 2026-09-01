"""MCP server for GoETF — lists available ETFs via the public API."""
import os
import contextvars
import asyncio
import httpx
import uvicorn
from mcp.server import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware

API_BASE_URL = os.getenv("GOETF_API_URL", "http://localhost:8000")
PORT = int(os.getenv("PORT", 8080))

# Holds the caller's API key for the duration of each request
request_api_key: contextvars.ContextVar[str] = contextvars.ContextVar("request_api_key", default="")


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Extracts API key from x-api-key header, Authorization: Bearer, or ?api_key= query param."""
    async def dispatch(self, request, call_next):
        api_key = (
            request.headers.get("x-api-key")
            or request.headers.get("authorization", "").removeprefix("Bearer ")
            or request.query_params.get("api_key", "")
        )
        token = request_api_key.set(api_key)
        try:
            return await call_next(request)
        finally:
            request_api_key.reset(token)


async def list_etfs_impl(provider: str = None, limit: int = 50) -> str:
    api_key = request_api_key.get()
    if not api_key:
        return "Error: No API key provided. Append ?api_key=YOUR_KEY to the connector URL."

    try:
        url = f"{API_BASE_URL}/etfs"
        params = {"limit": limit}
        if provider:
            params["provider"] = provider

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers={"x-api-key": api_key})
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

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return "Error: Invalid API key."
        return f"API error: {e.response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    mcp = MCPServer(
        name="goetf-mcp",
        title="GoETF",
        description="List ETFs available in GoETF database. Requires a GoETF API key.",
        version="1.0.0"
    )

    @mcp.tool()
    async def list_etfs(provider: str = None, limit: int = 50) -> str:
        """
        List available ETFs in GoETF database.

        Args:
            provider: Filter by provider (e.g., 'UBS', 'iShares')
            limit: Maximum number of ETFs to return (default 50)
        """
        return await list_etfs_impl(provider, limit)

    app = mcp.streamable_http_app(host="0.0.0.0")
    app.add_middleware(APIKeyMiddleware)
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()


API_BASE_URL = os.getenv("GOETF_API_URL", "http://localhost:8000")
PORT = int(os.getenv("PORT", 8080))

# Holds the caller's API key for the duration of each request
request_api_key: contextvars.ContextVar[str] = contextvars.ContextVar("request_api_key", default="")


class APIKeyMiddleware:
    """Extracts API key from x-api-key header, Authorization header, or ?api_key= query param."""
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            # Try x-api-key header first, then Authorization: Bearer, then ?api_key= query param
            api_key = headers.get(b"x-api-key", b"").decode()
            if not api_key:
                auth = headers.get(b"authorization", b"").decode()
                if auth.startswith("Bearer "):
                    api_key = auth[7:]
            if not api_key:
                query = scope.get("query_string", b"").decode()
                for part in query.split("&"):
                    if part.startswith("api_key="):
                        api_key = part[8:]
            token = request_api_key.set(api_key)
            try:
                await self.app(scope, receive, send)
            finally:
                request_api_key.reset(token)
        else:
            await self.app(scope, receive, send)


async def list_etfs_impl(provider: str = None, limit: int = 50) -> str:
    api_key = request_api_key.get()
    if not api_key:
        return "Error: No API key provided. In your connector settings, add the header x-api-key with your GoETF API key."

    try:
        url = f"{API_BASE_URL}/etfs"
        params = {"limit": limit}
        if provider:
            params["provider"] = provider

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers={"x-api-key": api_key})
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

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return "Error: Invalid API key. Please check your GoETF API key."
        return f"API error: {e.response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    server = MCPServer(
        name="goetf-mcp",
        title="GoETF",
        description="List ETFs available in GoETF database. Requires a GoETF API key set as x-api-key header.",
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

    app = APIKeyMiddleware(server.streamable_http_app)
    uvicorn.run(app, host="0.0.0.0", port=PORT)


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
