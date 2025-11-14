from litellm import Tool
from pydantic import BaseModel


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server"""

    name: str
    command: str
    args: list[str]
    env: dict[str, str] | None = None


class Config(BaseModel):
    """Configuration manager"""

    model_name: str
    tools: list[Tool]
    system_prompt_path: str
    mcp_servers: list[MCPServerConfig] = []


def load_config(config_path: str = "config.json") -> Config:
    """Load configuration from file"""
    with open(config_path, "r") as f:
        return Config.model_validate_json(f.read())
