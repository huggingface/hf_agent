"""
Terminal display utilities with colors and formatting
"""


# ANSI color codes
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


def truncate_to_lines(text: str, max_lines: int = 6) -> str:
    """Truncate text to max_lines, adding '...' if truncated"""
    lines = text.split("\n")
    if len(lines) <= max_lines:
        return text
    return (
        "\n".join(lines[:max_lines])
        + f"\n{Colors.CYAN}... ({len(lines) - max_lines} more lines){Colors.RESET}"
    )


def format_header(text: str, emoji: str = "") -> str:
    """Format a header with bold"""
    full_text = f"{emoji} {text}" if emoji else text
    return f"{Colors.BOLD}{full_text}{Colors.RESET}"


def format_plan_display() -> str:
    """Format the current plan for display (no colors, full visibility)"""
    from agent.tools.plan_tool import get_current_plan

    plan = get_current_plan()
    if not plan:
        return ""

    lines = ["\n" + "=" * 60]
    lines.append("CURRENT PLAN")
    lines.append("=" * 60 + "\n")

    # Group by status
    completed = [t for t in plan if t["status"] == "completed"]
    in_progress = [t for t in plan if t["status"] == "in_progress"]
    pending = [t for t in plan if t["status"] == "pending"]

    if completed:
        lines.append("Completed:")
        for todo in completed:
            lines.append(f"  [x] {todo['id']}. {todo['content']}")
        lines.append("")

    if in_progress:
        lines.append("In Progress:")
        for todo in in_progress:
            lines.append(f"  [~] {todo['id']}. {todo['content']}")
        lines.append("")

    if pending:
        lines.append("Pending:")
        for todo in pending:
            lines.append(f"  [ ] {todo['id']}. {todo['content']}")
        lines.append("")

    lines.append(
        f"Total: {len(plan)} todos ({len(completed)} completed, {len(in_progress)} in progress, {len(pending)} pending)"
    )
    lines.append("=" * 60 + "\n")

    return "\n".join(lines)


def format_error(message: str) -> str:
    """Format an error message in red"""
    return f"{Colors.RED}ERROR: {message}{Colors.RESET}"


def format_success(message: str, emoji: str = "") -> str:
    """Format a success message in green"""
    prefix = f"{emoji} " if emoji else ""
    return f"{Colors.GREEN}{prefix}{message}{Colors.RESET}"


def format_tool_call(tool_name: str, arguments: str) -> str:
    """Format a tool call message"""
    return f"{Colors.YELLOW}Calling tool: {Colors.BOLD}{tool_name}{Colors.RESET}{Colors.YELLOW} with arguments: {arguments}{Colors.RESET}"


def format_tool_output(output: str, success: bool, truncate: bool = True) -> str:
    """Format tool output with color and optional truncation"""
    original_length = len(output)
    if truncate:
        output = truncate_to_lines(output, max_lines=6)

    if success:
        return (
            f"{Colors.YELLOW}Tool output ({original_length} tkns): {Colors.RESET}\n{output}"
        )
    else:
        return (
            f"{Colors.RED}Tool output ({original_length} tokens): {Colors.RESET}\n{output}"
        )


def format_turn_complete() -> str:
    """Format turn complete message in green with hugging face emoji"""
    return f"{Colors.GREEN}{Colors.BOLD}\U0001f917 Turn complete{Colors.RESET}\n"


def format_separator(char: str = "=", length: int = 60) -> str:
    """Format a separator line"""
    return char * length


def format_plan_tool_output(todos: list) -> str:
    """Format the plan tool output (no colors, full visibility)"""
    if not todos:
        return "Plan is empty."

    lines = ["Plan updated successfully", ""]

    # Group by status
    completed = [t for t in todos if t["status"] == "completed"]
    in_progress = [t for t in todos if t["status"] == "in_progress"]
    pending = [t for t in todos if t["status"] == "pending"]

    if completed:
        lines.append("Completed:")
        for todo in completed:
            lines.append(f"  [x] {todo['id']}. {todo['content']}")
        lines.append("")

    if in_progress:
        lines.append("In Progress:")
        for todo in in_progress:
            lines.append(f"  [~] {todo['id']}. {todo['content']}")
        lines.append("")

    if pending:
        lines.append("Pending:")
        for todo in pending:
            lines.append(f"  [ ] {todo['id']}. {todo['content']}")
        lines.append("")

    lines.append(
        f"Total: {len(todos)} todos ({len(completed)} completed, {len(in_progress)} in progress, {len(pending)} pending)"
    )

    return "\n".join(lines)
