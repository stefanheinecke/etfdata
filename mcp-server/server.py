"""MCP server for GoETF — lists available ETFs via the public API."""
import os
import contextvars
import httpx
import uvicorn
from mcp.server import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware

API_BASE_URL = os.getenv("GOETF_API_URL", "http://localhost:8000")
PORT = int(os.getenv("PORT", 8080))

# Holds the caller API key for the duration of each request
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
        params = {"limit": limit}
        if provider:
            params["provider"] = provider
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/etfs", params=params, headers={"x-api-key": api_key})
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
            lines.append(f"  * {isin} - {name} ({provider_name}){f' | TER: {ter}%' if ter else ''}")
        return "\n".join(lines)
    except httpx.HTTPStatusError as e:
        return "Error: Invalid API key." if e.response.status_code == 401 else f"API error: {e.response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    mcp = MCPServer(name="goetf-mcp", title="GoETF", description="List ETFs in GoETF database. Requires a GoETF API key.", version="1.0.0")

    @mcp.tool()
    async def list_etfs(provider: str = None, limit: int = 50) -> str:
        """
        List available ETFs in GoETF database.

        Args:
            provider: Filter by provider (e.g. UBS, iShares)
            limit: Maximum number of ETFs to return (default 50)
        """
        return await list_etfs_impl(provider, limit)

    app = mcp.streamable_http_app(host="0.0.0.0")
    app.add_middleware(APIKeyMiddleware)
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()