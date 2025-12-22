"""
Job utility functions

Ported from: hf-mcp-server/packages/mcp/src/jobs/commands/utils.ts
"""
import re
import shlex
from typing import Dict, Optional, Any, List, Union


def parse_timeout(timeout: str) -> int:
    """Parse timeout string (e.g., "5m", "2h", "30s") to seconds"""
    time_units = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
    }

    match = re.match(r'^(\d+(?:\.\d+)?)(s|m|h|d)$', timeout)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        return int(value * time_units[unit])

    # Try to parse as plain number (seconds)
    try:
        return int(timeout)
    except ValueError:
        raise ValueError(
            f'Invalid timeout format: "{timeout}". Use format like "5m", "2h", "30s", or plain seconds.'
        )


def parse_image_source(image: str) -> Dict[str, Optional[str]]:
    """
    Detect if image is a Space URL and extract spaceId
    Returns {'dockerImage': ...} or {'spaceId': ...}
    """
    space_prefixes = [
        'https://huggingface.co/spaces/',
        'https://hf.co/spaces/',
        'huggingface.co/spaces/',
        'hf.co/spaces/',
    ]

    for prefix in space_prefixes:
        if image.startswith(prefix):
            return {'dockerImage': None, 'spaceId': image[len(prefix):]}

    # Not a space, treat as docker image
    return {'dockerImage': image, 'spaceId': None}


def parse_command(command: Union[str, List[str]]) -> Dict[str, Any]:
    """
    Parse command string or array into command array
    Uses shlex for POSIX-compliant parsing
    """
    # If already an array, return as-is
    if isinstance(command, list):
        return {'command': command, 'arguments': []}

    # Parse the command string using shlex for POSIX-compliant parsing
    try:
        string_args = shlex.split(command)
    except ValueError as e:
        raise ValueError(
            f'Unsupported shell syntax in command: "{command}". '
            f'Please use an array format for commands with complex shell operators. Error: {e}'
        )

    if len(string_args) == 0:
        raise ValueError(f'Invalid command: "{command}". Command cannot be empty.')

    return {'command': string_args, 'arguments': []}


def replace_token_placeholder(value: str, hf_token: Optional[str]) -> str:
    """Replace HF token placeholder with actual token if available"""
    if not hf_token:
        return value

    if value in ('$HF_TOKEN', '${HF_TOKEN}'):
        return hf_token

    return value


def transform_env_map(
    env_map: Optional[Dict[str, str]],
    hf_token: Optional[str]
) -> Optional[Dict[str, str]]:
    """Transform environment map, replacing token placeholders"""
    if not env_map:
        return None

    return {
        key: replace_token_placeholder(value, hf_token)
        for key, value in env_map.items()
    }


def create_job_spec(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a JobSpec from run command arguments"""
    # Validate required fields
    if not args.get('image'):
        raise ValueError('image parameter is required. Provide a Docker image (e.g., "python:3.12") or Space URL.')
    if not args.get('command'):
        raise ValueError('command parameter is required. Provide a command as string or array.')

    image_source = parse_image_source(args['image'])
    command_parsed = parse_command(args['command'])
    timeout_seconds = parse_timeout(args['timeout']) if args.get('timeout') else None
    environment = transform_env_map(args.get('env'), args.get('hfToken')) or {}
    secrets = transform_env_map(args.get('secrets'), args.get('hfToken')) or {}

    spec = {
        **{k: v for k, v in image_source.items() if v is not None},
        'command': command_parsed['command'],
        'arguments': command_parsed['arguments'],
        'flavor': args.get('flavor', 'cpu-basic'),
        'environment': environment,
        'secrets': secrets,
    }

    if timeout_seconds is not None:
        spec['timeoutSeconds'] = timeout_seconds

    return spec
