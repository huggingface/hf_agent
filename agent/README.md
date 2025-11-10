# Agent

Async agent loop with LiteLLM.

## Architecture

**Queue-based async system:**
- Submissions in (user input) → Agent Loop → Events output for possible UI updates
- Session maintains state (context + tools) for possible future Context Engineering
- Handlers operations like (USER_INPUT, INTERRUPT, COMPACT, UNDO, SHUTDOWN) for possible UI control

```
core/
├── agent_loop.py      # submission_loop + Handlers
├── session.py         # Session, Event, OpType
└── executor.py        # ToolExecutor

context_manager/
└── manager.py         # Message history management

config.py              # Config with model_name + tools
tools/                 # Tool implementations (todo)
utils/                 # Logging, etc
```
