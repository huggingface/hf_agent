"""
Context management for conversation history
"""

from litellm import Message


class ContextManager:
    """Manages conversation context and message history for the agent"""

    def __init__(self):
        self.system_prompt = self._load_system_prompt()
        self.items: list[Message] = [
            Message(role="system", content=self.system_prompt)
        ]

    def _load_system_prompt(self):
        """Load the system prompt"""

        # TODO: get system prompt from jinja template
        return "You are a helpful assistant."

    def add_message(self, message: Message) -> None:
        """Add a message to the history"""
        self.items.append(message)

    def get_messages(self) -> list[Message]:
        """Get all messages for sending to LLM"""
        return self.items

    def compact(self, target_size: int) -> None:
        """Remove old messages to keep history under target size"""
        # Keep system prompt (first message) and remove oldest user/assistant messages
        if len(self.items) <= target_size:
            return

        # Always keep system prompt
        system_msg = self.items[0] if self.items and self.items[0].role == "system" else None
        messages_to_keep = self.items[-(target_size - 1):]

        if system_msg:
            self.items = [system_msg] + messages_to_keep
        else:
            self.items = messages_to_keep
