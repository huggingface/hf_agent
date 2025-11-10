# HF Agent

AI Agent for working with Hugging Face models, datasets, and tools.

## Structure

```
agent/
├── core/                 # Core agent logic
│   ├── agent.py         # Main agent implementation
│   ├── base.py          # Base classes and interfaces
│   ├── planner.py       # Task planning and decomposition
│   └── executor.py      # Task execution engine
│
├── tools/               # Agent tools and actions
│   ├── base.py         # Tool base class and registry
│   ├── search/         # Search tools (models, datasets, papers)
│   ├── generation/     # Generation tools (content, code, data)
│   ├── analysis/       # Analysis and evaluation tools
│   └── dataset_ops/    # Dataset operations
│
├── prompts/            # Prompt templates
│   ├── system/         # System prompts
│   ├── task/           # Task-specific prompts
│   └── few_shot/       # Few-shot examples
│
├── memory/             # Memory systems
│   ├── short_term/     # Conversational memory
│   └── long_term/      # Persistent knowledge
│
├── config/             # Configuration
│   ├── settings.py     # Settings management
│   └── default_config.json
│
├── utils/              # Utilities
│   ├── logging.py      # Logging setup
│   └── retry.py        # Retry logic
│
└── tests/              # Test suite
    ├── unit/           # Unit tests
    └── integration/    # Integration tests
```

## Key Components

### Core
- **Agent**: Main orchestrator that coordinates planning, execution, and reflection
- **Planner**: Breaks down complex tasks into actionable steps
- **Executor**: Executes individual steps using available tools

### Tools
- Modular tool system with base class and registry
- Tools organized by category (search, generation, analysis, dataset ops)
- Each tool can be registered and used by the agent

### Memory
- **Short-term**: Manages conversation context and current task state
- **Long-term**: Persistent storage for learned knowledge and past interactions

### Prompts
- Template-based prompt management
- System prompts for agent behavior
- Task-specific prompts for different operations
- Few-shot examples for learning

## Usage

```python
from agent import Agent
from agent.config import load_config

# Load configuration
config = load_config()

# Create agent
agent = Agent(config=config.model_dump())

# Run a task
result = await agent.run("Find the top 5 text generation models")
```

## Development

### Adding a New Tool

1. Create a new file in the appropriate `tools/` subdirectory
2. Inherit from `BaseTool`
3. Implement `execute()` and `_get_parameters()`
4. Register the tool with the agent

```python
from agent.tools.base import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"

    async def execute(self, **kwargs):
        # Implementation
        pass

    def _get_parameters(self):
        return {
            "type": "object",
            "properties": {...}
        }
```

### Running Tests

```bash
pytest agent/tests/
```

## Configuration

Configure the agent via `config/default_config.json` or by passing a config dict:

```python
config = {
    "model_name": "gpt-4",
    "temperature": 0.7,
    "max_iterations": 10,
    "reflection_enabled": True
}
agent = Agent(config=config)
```
