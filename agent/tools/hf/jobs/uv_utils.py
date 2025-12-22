"""
UV command utilities

Ported from: hf-mcp-server/packages/mcp/src/jobs/commands/uv-utils.ts
"""
import base64
from typing import List, Dict, Optional, Any


UV_DEFAULT_IMAGE = 'ghcr.io/astral-sh/uv:python3.12-bookworm'


def build_uv_command(script: str, args: Dict[str, Any]) -> List[str]:
    """Build UV run command"""
    parts = ['uv', 'run']

    # Add dependencies
    with_deps = args.get('with_deps', [])
    if with_deps:
        for dep in with_deps:
            parts.extend(['--with', dep])

    # Add python version
    python = args.get('python')
    if python:
        parts.extend(['-p', python])

    parts.append(script)

    # Add script arguments
    script_args = args.get('script_args', [])
    if script_args:
        parts.extend(script_args)

    return parts


def wrap_inline_script(script: str, args: Dict[str, Any]) -> str:
    """Wrap inline script with base64 encoding for UV"""
    encoded = base64.b64encode(script.encode('utf-8')).decode('utf-8')
    base_command = build_uv_command('-', args)
    # Shell quote the command parts
    quoted_command = ' '.join(base_command)
    return f'echo "{encoded}" | base64 -d | {quoted_command}'


def resolve_uv_command(args: Dict[str, Any]) -> List[str]:
    """Resolve UV command based on script source"""
    script_source = args.get('script', '')

    options = {
        'with_deps': args.get('with_deps'),
        'python': args.get('python'),
        'script_args': args.get('script_args'),
    }

    # URL script
    if script_source.startswith('http://') or script_source.startswith('https://'):
        return build_uv_command(script_source, options)

    # Inline multi-line script
    if '\n' in script_source:
        return ['/bin/sh', '-lc', wrap_inline_script(script_source, options)]

    # File path or single-line script
    return build_uv_command(script_source, options)
