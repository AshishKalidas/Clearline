"""A real stdio MCP client: initialize, list tools and execute an invoice search."""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "search_invoices",
    "get_invoice",
    "find_customers",
    "get_customer",
    "get_payment_history",
    "find_similar_cases",
    "get_pop_verification",
    "list_pending_proposals",
}


async def main() -> None:
    """Verify protocol compatibility against the configured local database."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        env=dict(os.environ),
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
        await client.initialize()
        tools = (await client.list_tools()).tools
        assert {tool.name for tool in tools} == EXPECTED_TOOLS
        assert all(tool.annotations and tool.annotations.readOnlyHint for tool in tools)
        result = await client.call_tool("search_invoices", {"tolerance_cents": 0})
        assert not result.isError and result.content
        print("MCP stdio: initialized; 8 read-only tools; search_invoices succeeded.")


if __name__ == "__main__":
    asyncio.run(main())
