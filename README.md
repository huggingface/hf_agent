# HF Agent

An MLE agent CLI with MCP (Model Context Protocol) integration and built-in tool support.


## Quick Start

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd hf-agent

# Install dependencies (using uv)
uv sync
```

### Interactive CLI

```bash
uv run python -m agent.main
```

This starts an interactive chat session with the agent. Type your messages and the agent will respond, using tools as needed.

The agent will automatically discover and register all tools from configured MCP servers.

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         User/CLI                             │
└────────────┬─────────────────────────────────────┬───────────┘
             │ User request                                │ Events
             ↓                                             ↑
      submission_queue                                   event_queue
             │                                                 │
             ↓                                                 │
┌────────────────────────────────────────────────────┐         │
│            submission_loop (agent_loop.py)         │         │
│  ┌──────────────────────────────────────────────┐  │         │
│  │  1. Receive Operation from queue             │  │         │
│  │  2. Route to Handler (run_agent/compact/...) │  │         │
│  └──────────────────────────────────────────────┘  │         │
│                      ↓                             │         │
│  ┌──────────────────────────────────────────────┐  │         │
│  │         Handlers.run_agent()                 │  ├─────────┤
│  │                                              │  │ Emit    │
│  │  ┌────────────────────────────────────────┐  │  │ Events  │
│  │  │  Agentic Loop (max 10 iterations)      │  │  │         │
│  │  │                                        │  │  │         │
│  │  │  ┌──────────────────────────────────┐  │  │  │         │
│  │  │  │ Session                          │  │  │  │         │
│  │  │  │  ┌────────────────────────────┐  │  │  │  │         │
│  │  │  │  │ ContextManager             │  │  │  │  │         │
│  │  │  │  │ • Message history          │  │  │  │  │         │
│  │  │  │  │   (litellm.Message[])      │  │  │  │  │         │
│  │  │  │  └────────────────────────────┘  │  │  │  │         │
│  │  │  │                                  │  │  │  │         │
│  │  │  │  ┌────────────────────────────┐  │  │  │  │         │
│  │  │  │  │ ToolRouter                 │  │  │  │  │         │
│  │  │  │  │  ├─ bash                   │  │  │  │  │         │
│  │  │  │  │  ├─ read_file              │  │  │  │  │         │
│  │  │  │  │  ├─ write_file             │  │  │  │  │         │
│  │  │  │  │  └─ McpConnectionManager   │  │  │  │  │         │
│  │  │  │  │      ├─ mcp__server1__*    │  │  │  │  │         │
│  │  │  │  │      └─ mcp__server2__*    │  │  │  │  │         │
│  │  │  │  └────────────────────────────┘  │  │  │  │         │
│  │  │  └──────────────────────────────────┘  │  │  │         │
│  │  │                                        │  │  │         │
│  │  │  Loop:                                 │  │  │         │
│  │  │    1. LLM call (litellm.acompletion)   │  │  │         │
│  │  │       ↓                                │  │  │         │
│  │  │    2. Parse tool_calls[]               │  │  │         │
│  │  │       ↓                                │  │  │         │
│  │  │    3. Execute via ToolRouter           │  │  │         │
│  │  │       ↓                                │  │  │         │
│  │  │    4. Add results to ContextManager    │  │  │         │
│  │  │       ↓                                │  │  │         │
│  │  │    5. Repeat if tool_calls exist       │  │  │         │
│  │  └────────────────────────────────────────┘  │  │         │
│  └──────────────────────────────────────────────┘  │         │
└────────────────────────────────────────────────────┴─────────┘
```

### Agentic Loop Flow

```
User Message
     ↓
[Add to ContextManager]
     ↓
     ╔═══════════════════════════════════════╗
     ║      Iteration Loop (max 10)          ║
     ║                                       ║
     ║  Get messages + tool specs            ║
     ║         ↓                             ║
     ║  litellm.acompletion()                ║
     ║         ↓                             ║
     ║  Has tool_calls? ──No──> Done         ║
     ║         │                             ║
     ║        Yes                            ║
     ║         ↓                             ║
     ║  Add assistant msg (with tool_calls)  ║
     ║         ↓                             ║
     ║  For each tool_call:                  ║
     ║    • ToolRouter.execute_tool()        ║
     ║    • Add result to ContextManager     ║
     ║         ↓                             ║
     ║  Continue loop ─────────────────┐     ║
     ║         ↑                       │     ║
     ╚═════════╧═══════════════════════╧═════╝
```

## Project Structure

```
agent/
├── config.py                 # Configuration models
├── main.py                   # Interactive CLI entry point
├── context_manager/
│   └── manager.py           # Message history management
└── core/
    ├── agent_loop.py        # Main agent loop and handlers
    ├── session.py           # Session management
    ├── mcp_client.py        # MCP SDK integration
    └── tools.py             # ToolRouter and built-in tools

test_integration.py          # Basic integration tests
test_tools.py                # Tool execution tests
eval/                        # Evaluation suite (see eval/README.md)
```


## Events

The agent emits the following events via `event_queue`:

- `processing` - Starting to process user input
- `assistant_message` - LLM response text
- `tool_call` - Tool being called with arguments
- `tool_output` - Tool execution result
- `turn_complete` - Agent finished processing
- `error` - Error occurred during processing
- `interrupted` - Agent was interrupted
- `compacted` - Context was compacted
- `undo_complete` - Undo operation completed
- `shutdown` - Agent shutting down

## Development

### Adding Built-in Tools

Edit `agent/core/tools.py`:

```python
def create_builtin_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="your_tool",
            description="What your tool does",
            parameters={
                "type": "object",
                "properties": {
                    "param": {"type": "string", "description": "Parameter description"}
                },
                "required": ["param"]
            },
            handler=your_async_handler
        ),
        # ... existing tools
    ]
```

### Adding MCP Servers

Add to your config:

```python
config = Config(
    model_name="anthropic/claude-sonnet-4-5-20250929",
    mcp_servers=[
        MCPServerConfig(
            name="your_server",
            command="command",
            args=["arg1", "arg2"],
            env={"KEY": "value"}
        )
    ]
)
```
