"""
Prompt template management
"""

from litellm import Message


class ContextManager:
    """Manages context templates for the agent"""

    def __init__(self):
        self.system_prompt = self._load_system_prompt()
        self.messages: list[Message] = [
            Message(role="system", content=self.system_prompt)
        ]

    def _load_system_prompt(self):
        """Load the system prompt"""

        # TODO: get system prompt from jinja template
        return "You are a helpful assistant."

    def add_message(self, message: Message) -> None:
        self.messages.append(message)

    def get_messages(self) -> list[Message]:
        return self.messages
