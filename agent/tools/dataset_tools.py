"""
Hugging Face Dataset Tool - Query datasets via the Datasets Server API

Allows downloading rows and listing splits from Hugging Face datasets.
"""

from typing import Any, Dict

import httpx

from agent.tools.types import ToolResult


def list_splits(dataset: str) -> ToolResult:
    """
    List all available splits for a dataset.
    
    Args:
        dataset: Dataset identifier (e.g., "facebook/research-plan-gen")
    
    Returns:
        ToolResult with split information
    """
    base_url = "https://datasets-server.huggingface.co"
    url = f"{base_url}/splits"
    
    params = {"dataset": dataset}
    
    try:
        response = httpx.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        
        splits = data.get("splits", [])
        if not splits:
            return {
                "formatted": f"No splits found for dataset '{dataset}'",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": False,
            }
        
        # Format splits information
        split_info = []
        for split in splits:
            split_name = split.get("split", "unknown")
            num_rows = split.get("num_examples", "unknown")
            split_info.append(f"- **{split_name}**: {num_rows} rows")
        
        formatted = f"Available splits for dataset '{dataset}':\n\n" + "\n".join(split_info)
        
        return {
            "formatted": formatted,
            "totalResults": len(splits),
            "resultsShared": len(splits),
            "isError": False,
        }
    
    except httpx.HTTPStatusError as e:
        return {
            "formatted": f"HTTP error {e.response.status_code}: {str(e)}",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }
    except Exception as e:
        return {
            "formatted": f"Failed to list splits: {str(e)}",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }


def download_rows(
    dataset: str,
    split: str,
    config: str | None = None,
    offset: int = 0,
    length: int = 5,
) -> ToolResult:
    """
    Download rows from a dataset split.
    
    Args:
        dataset: Dataset identifier (e.g., "facebook/research-plan-gen")
        split: Split name (e.g., "train", "test", "validation")
        config: Optional config name (for datasets with multiple configs)
        offset: Starting row index (default: 0)
        length: Number of rows to fetch (default: 5, max recommended: 1000)
    
    Returns:
        ToolResult with row data
    """
    base_url = "https://datasets-server.huggingface.co"
    url = f"{base_url}/rows"
    
    params = {
        "dataset": dataset,
        "split": split,
        "offset": offset,
        "length": length,
    }
    
    if config:
        params["config"] = config
    
    try:
        response = httpx.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        
        rows = data.get("rows", [])
        features = data.get("features", [])
        
        if not rows:
            return {
                "formatted": f"No rows found for dataset '{dataset}', split '{split}' at offset {offset}",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": False,
            }
        
        # Format a summary of the rows
        formatted_parts = [
            f"Downloaded {len(rows)} rows from dataset '{dataset}'",
            f"Split: {split}",
            f"Offset: {offset}",
        ]
        
        if config:
            formatted_parts.append(f"Config: {config}")
        
        formatted_parts.append(f"\nFeatures: {', '.join([f.get('name', 'unknown') for f in features])}")
        formatted_parts.append(f"\nTotal rows in response: {len(rows)}")
        
        # Show first row as example
        if rows:
            first_row = rows[0].get("row", {})
            formatted_parts.append(f"\nExample row (first row):")
            for key, value in list(first_row.items())[:20]:  # Show up to 20 fields
                value_str = str(value)
                if len(value_str) > 200:
                    value_str = value_str[:200] + "..."
                formatted_parts.append(f"  - {key}: {value_str}")
        
        formatted = "\n".join(formatted_parts)
        
        return {
            "formatted": formatted,
            "totalResults": len(rows),
            "resultsShared": len(rows),
            "isError": False,
        }
    
    except httpx.HTTPStatusError as e:
        return {
            "formatted": f"HTTP error {e.response.status_code}: {str(e)}",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }
    except Exception as e:
        return {
            "formatted": f"Failed to download rows: {str(e)}",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }


# Tool specifications
DATASETS_SERVER_LIST_SPLITS_TOOL_SPEC = {
    "name": "hf_datasets_list_splits",
    "description": (
        "List all available splits for a Hugging Face dataset.\n\n"
        "Use this to discover what splits (train, test, validation, etc.) are available "
        "for a dataset before downloading rows.\n\n"
        "## When to use\n"
        "- When you need to know what splits are available for a dataset\n"
        "- Before downloading rows to identify the correct split name\n"
        "- To check dataset structure and organization\n"
        "- **CRITICAL: Always use this tool BEFORE training/fine-tuning models via hf_jobs** "
        "to understand the dataset structure and ensure you're using the correct splits\n\n"
        "## Example\n"
        "{\n"
        '  "dataset": "facebook/research-plan-gen"\n'
        "}"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "dataset": {
                "type": "string",
                "description": "Dataset identifier in format 'org/dataset-name' (e.g., 'facebook/research-plan-gen'). Required.",
            },
        },
        "required": ["dataset"],
    },
}

DATASETS_SERVER_DOWNLOAD_ROWS_TOOL_SPEC = {
    "name": "hf_datasets_download_rows",
    "description": (
        "Download rows from a Hugging Face dataset split via the Datasets Server API.\n\n"
        "Fetches a specified number of rows starting from a given offset. Useful for "
        "sampling data, inspecting dataset contents, or processing datasets in batches.\n\n"
        "## When to use\n"
        "- **CRITICAL: Always use this tool BEFORE training/fine-tuning models via hf_jobs** "
        "to inspect and understand the dataset structure, data format, column names, and data types. "
        "This helps avoid costly mistakes and ensures proper data preprocessing.\n"
        "- When you need to inspect or sample data from a dataset\n"
        "- To understand the data format and structure before writing training scripts\n"
        "- To verify column names and data types match your expectations\n"
        "- To download specific rows for analysis or processing\n"
        "- To fetch data in batches (use offset and length parameters)\n\n"
        "## When NOT to use\n"
        "- For downloading entire large datasets (use huggingface_hub or datasets library instead)\n"
        "- When you need to process all data (use streaming or local download)\n\n"
        "## Examples\n"
        "// Inspect first 5 rows to understand dataset structure (recommended before training)\n"
        "{\n"
        '  "dataset": "facebook/research-plan-gen",\n'
        '  "split": "train",\n'
        '  "config": "arxiv",\n'
        '  "offset": 0,\n'
        '  "length": 5\n'
        "}\n\n"
        "// Get next batch (rows 5-10)\n"
        "{\n"
        '  "dataset": "facebook/research-plan-gen",\n'
        '  "split": "train",\n'
        '  "offset": 5,\n'
        '  "length": 5\n'
        "}"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "dataset": {
                "type": "string",
                "description": "Dataset identifier in format 'org/dataset-name' (e.g., 'facebook/research-plan-gen'). Required.",
            },
            "split": {
                "type": "string",
                "description": "Split name (e.g., 'train', 'test', 'validation'). Required.",
            },
            "config": {
                "type": "string",
                "description": "Config name (only needed for datasets with multiple configs). Optional.",
            },
            "offset": {
                "type": "integer",
                "description": "Starting row index (default: 0).",
                "default": 0,
            },
            "length": {
                "type": "integer",
                "description": "Number of rows to fetch (default: 5, max recommended: 1000). Use small values (1-5) for quick inspection before training.",
                "default": 5,
            },
        },
        "required": ["dataset", "split"],
    },
}


async def hf_datasets_list_splits_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    """Handler for listing dataset splits"""
    try:
        result = list_splits(dataset=arguments["dataset"])
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error: {str(e)}", False


async def hf_datasets_download_rows_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    """Handler for downloading dataset rows"""
    try:
        result = download_rows(
            dataset=arguments["dataset"],
            split=arguments["split"],
            config=arguments.get("config"),
            offset=arguments.get("offset", 0),
            length=arguments.get("length", 5),
        )
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error: {str(e)}", False

