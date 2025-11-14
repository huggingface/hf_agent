# MCP Integration for HF Agent

This agent now supports the Model Context Protocol (MCP), allowing it to connect to and use tools from MCP servers.

## Overview

The MCP integration allows the agent to:
- Connect to multiple MCP servers simultaneously
- Automatically discover and use tools from connected servers
- Execute tool calls through the MCP protocol
- Seamlessly integrate MCP tools with the agent's existing tool system

## Architecture

The integration consists of several components:

1. **MCPClient** (`agent/core/mcp_client.py`): Manages connections to MCP servers
2. **ToolExecutor** (`agent/core/executor.py`): Executes both MCP and local tools
3. **Config** (`agent/config.py`): Stores MCP server configurations
4. **Session** (`agent/core/session.py`): Initializes MCP connections and manages lifecycle

## Configuration

To use MCP servers with your agent, add them to your configuration file:

```json
{
  "model_name": "anthropic/claude-sonnet-4-5-20250929",
  "tools": [],
  "system_prompt_path": "",
  "mcp_servers": [
    {
      "name": "weather",
      "command": "python",
      "args": ["path/to/weather_server.py"],
      "env": null
    },
    {
      "name": "filesystem",
      "command": "node",
      "args": ["path/to/filesystem_server.js"],
      "env": {
        "ALLOWED_PATHS": "/home/user/documents"
      }
    }
  ]
}
```

### Configuration Fields

- `name`: Unique identifier for the MCP server
- `command`: Command to execute the server (`python`, `node`, etc.)
- `args`: Arguments to pass to the command (path to server script)
- `env`: (Optional) Environment variables for the server process

## Usage

### Basic Usage

```python
import asyncio
from agent.config import Config, load_config
from agent.core.agent_loop import submission_loop

async def main():
    # Load config with MCP servers
    config = load_config("config.json")

    # Create queues
    submission_queue = asyncio.Queue()
    event_queue = asyncio.Queue()

    # Start agent loop (MCP connections initialized automatically)
    await submission_loop(submission_queue, event_queue, config)

if __name__ == "__main__":
    asyncio.run(main())
```

### Programmatic Configuration

```python
from agent.config import Config, MCPServerConfig

config = Config(
    model_name="anthropic/claude-sonnet-4-5-20250929",
    tools=[],
    system_prompt_path="",
    mcp_servers=[
        MCPServerConfig(
            name="weather",
            command="python",
            args=["weather_server.py"],
            env=None
        )
    ]
)
```

## How It Works

1. **Initialization**: When the agent loop starts, it calls `session.initialize_mcp()`
2. **Connection**: The session connects to all configured MCP servers
3. **Tool Discovery**: Tools from all servers are discovered and added to the agent's tool list
4. **Tool Naming**: MCP tools are prefixed with their server name (e.g., `weather__get_forecast`)
5. **Execution**: When the LLM calls a tool, the ToolExecutor routes it to the appropriate MCP server
6. **Cleanup**: When the agent shuts down, all MCP connections are cleaned up properly

## Tool Naming Convention

MCP tools are automatically prefixed with their server name to avoid conflicts:

- Original tool: `get_forecast`
- MCP tool name: `weather__get_forecast`

This ensures that tools from different servers don't conflict, even if they have the same name.

## Example: Creating a Simple MCP Server

Here's a minimal example of an MCP server (save as `calculator_server.py`):

```python
import asyncio
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent

app = Server("calculator")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="add",
            description="Add two numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                },
                "required": ["a", "b"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "add":
        result = arguments["a"] + arguments["b"]
        return [TextContent(type="text", text=str(result))]

    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

## Troubleshooting

### Server Connection Issues

If you see errors connecting to an MCP server:

1. Check that the server script path is correct
2. Ensure the command (`python`, `node`) is in your PATH
3. Verify the server script is executable
4. Check server logs for initialization errors

### Tool Not Found

If the agent can't find an MCP tool:

1. Verify the server is connected (check startup logs)
2. Check tool naming (should be `servername__toolname`)
3. Ensure the server properly implements `list_tools()`

### Performance Considerations

- MCP server initialization happens once at startup
- Tool calls are asynchronous and don't block the agent
- Multiple servers can be used simultaneously
- Consider using local tools for high-frequency operations

## Best Practices

1. **Unique Server Names**: Give each MCP server a unique, descriptive name
2. **Error Handling**: MCP connection failures are logged but don't crash the agent
3. **Resource Cleanup**: Always let the agent shut down gracefully to cleanup connections
4. **Testing**: Test MCP servers independently before integrating them
5. **Security**: Be cautious with file system and network access in MCP servers

## Future Enhancements

Potential improvements to consider:

- Dynamic server addition/removal during runtime
- Server health monitoring and auto-reconnection
- Tool caching and performance optimization
- Support for MCP resources and prompts
- Rate limiting and timeout configuration
