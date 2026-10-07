# Read-only MCP integration

Clearline uses the [official Python MCP SDK, v1 API](https://py.sdk.modelcontextprotocol.io/v1/) over stdio. The dependency is capped below v2 so its protocol/runtime API matches the tested implementation. The host launches a local process; there is no separate public MCP listener.

Start the seeded workspace with `make demo`, then run a real client check:

```bash
make mcp-check
```

The client initializes a session, lists exactly eight read-only tools and executes `search_invoices`. Tests also call every tool, verify masking, reject fractional cents and unknown write tools, and attempt an actual database write in the read-only transaction.

## Client configuration

For an MCP host accepting the common `mcpServers` JSON shape, replace the path below with your absolute checkout directory:

```json
{
  "mcpServers": {
    "clearline": {
      "command": "docker",
      "args": ["compose", "--project-directory", "/absolute/path/to/Clearline", "exec", "-T", "api", "python", "-m", "mcp_server.server"]
    }
  }
}
```

If your installation supplies the standalone Compose CLI instead, use `"command": "docker-compose"`, remove `"compose"` from the arguments, and set the client's `env` to `{"DOCKER_CONTEXT": "your-context"}` when needed. `make` detects either Compose form automatically.

The Docker executable must be on the host's PATH and its Docker engine/context must have the Clearline services running. If using a dedicated context, add `"--context", "your-context"` before `"compose"`. `-T` disables the TTY so stdout remains MCP protocol data. Logs use stderr. The process inherits the container's agent database URL and never receives the API mutation key through tool arguments.

Native Python alternative: install `.[dev]`, set `AGENT_DATABASE_URL` to the `clearline_agent` PostgreSQL connection, `EMBEDDER=hash`, and launch `.venv/bin/python -m mcp_server.server` from the repository root. PostgreSQL MCP access refuses an absent agent URL or a different database role. SQLite is only an isolated development/test fallback and uses `PRAGMA query_only`.

## Tools

| Tool | Parameters | Returned evidence |
|---|---|---|
| `search_invoices` | Optional customer, amount/tolerance cents, reference substring, issue-date range | At most 100 open invoices |
| `get_invoice` | `invoice_number` | Invoice and existing allocation facts |
| `find_customers` | `name_query` | Up to five fuzzy customer candidates |
| `get_customer` | `customer_id` | Masked notes and open balance |
| `get_payment_history` | `customer_id`, `limit` (1–50) | Historical allocations |
| `find_similar_cases` | `bank_line_id`, `k` (1–20), optional customer | Local case search; empty when retrieval disabled |
| `get_pop_verification` | `bank_line_id` | Linked verdicts and checks |
| `list_pending_proposals` | `limit` (1–100, default 20) | Largest pending recommendations first |

Bank-scoped tools require an explicit line ID; obtain it from a pending proposal or the local review API. Amounts are strict integer cents. Validation bounds are reused from the agent tools. A missing line yields a structured `bank_line_not_found` result; invalid arguments produce a protocol tool error.

Example `search_invoices` arguments: `{"amount_cents": 370000, "tolerance_cents": 0}`. With no filters it lists the first open invoices ordered by issue date and number. A fully settled workspace can legitimately return an empty list.

No `submit_proposal`, approve, reject, ingestion, upload, allocation or arbitrary SQL tool exists. PostgreSQL reads have a five-second statement timeout, and results use the same targeted masking as the agent. Returned references, notes and past-case text are untrusted data; they must not become host instructions. Use the browser workflow for financial decisions.
