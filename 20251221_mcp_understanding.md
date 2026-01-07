# MCP Understanding - December 21, 2024

## What MCP Is For

MCP = Claude's window into the user's transformation data.

**The flow:**
1. User uses UI
2. UI calls API
3. API runs flows → creates JSON files + saves to MongoDB
4. User now has THEIR data (specific to their account/app)
5. User wants to ask Claude questions about THEIR data
6. MCP connects Claude to THEIR files and THEIR MongoDB docs
7. Claude answers based on THEIR specific analysis results

The `scout_account_id` + `application_name` pattern ensures Claude only sees that user's data.

---

## Architecture (Keep This Separation)

```
modernizeit-api/
├── api/routes/mcp_config.py    # Config + tool metadata
│   ├── GET /mcp/config         # Returns MCP server connection config
│   └── GET /mcp/tools          # Lists available tools + parameters

modernizeit-mcp/
├── server.py                   # Actual MCP server with tool implementations
```

- **API** provides config so UI knows how to connect to MCP
- **MCP server** runs separately, handles Claude's tool calls
- This separation is intentional - keep it

---

## The 8 MCP Tools

| Tool | Type | What it does |
|------|------|--------------|
| `list_accounts` | File | Shows what accounts/apps exist |
| `list_artifacts` | File | Lists JSON files for an app |
| `read_artifact` | File | Reads a specific JSON file |
| `search_artifacts` | File | Searches content across files |
| `summarize_artifacts` | File | Overview of all artifacts |
| `query_mongodb` | MongoDB | Queries MongoDB directly |
| `list_mongodb_collections` | MongoDB | Lists MongoDB collections |
| `list_mongodb_artifact_types` | MongoDB | Lists artifact types in a collection |

---

## How to Test

### Postman (API only)
```
GET http://localhost:8000/mcp/config
GET http://localhost:8000/mcp/tools
```
These return metadata, not actual tool execution.

### MCP Inspector (test actual tools)
```bash
cd /Users/timhiggins/Desktop/desktop/Source/TransformationCode/code-transformation-modernizeit2/modernizeit-mcp
uv run mcp dev server.py
# Opens http://localhost:6274
```

### Claude Desktop (real integration)
1. Copy config to Claude Desktop:
   ```bash
   cp /Users/timhiggins/Desktop/mcp_test/test/claude_config.json \
      ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```
2. Restart Claude Desktop
3. Look for hammer icon (tools)
4. Ask: "Use the list_accounts tool to show me what data is available"

---

## Key Point

MCP uses stdio, not HTTP. Can't test with Postman directly.
Use MCP Inspector or Claude Desktop for real testing.

---

## Files

| File | Location |
|------|----------|
| MCP Server | `modernizeit-mcp/server.py` |
| API Config Route | `modernizeit-api/api/routes/mcp_config.py` |
| Claude Desktop Config | `/Users/timhiggins/Desktop/mcp_test/test/claude_config.json` |
| MCP Design Doc | `modernizeit-mcp/20251220_mcp_design.md` |

---

## Status

- MCP server: Built, not tested with real data
- API config endpoints: Built
- Claude Desktop config: Created
- Testing: Pending
