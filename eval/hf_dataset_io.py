"""
HuggingFace Dataset I/O Utilities

Reusable functions for uploading and downloading JSONL data to/from HuggingFace Hub.
Supports the dataset_name@config_name notation for managing multiple configurations.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd
from datasets import Dataset, load_dataset


def upload_jsonl_to_hf(
    jsonl_file: Union[str, Path],
    dataset_spec: str,
    split: str = "train",
    private: bool = False,
) -> bool:
    """
    Upload a JSONL file to HuggingFace Hub as a dataset.

    This function reads a JSONL file where each line is a complete JSON object,
    converts it to a HuggingFace Dataset, and uploads it to the Hub.

    Args:
        jsonl_file: Path to the JSONL file to upload. Each line should be a valid
            JSON object. Example format:
            ```
            {"question": "How to...", "solution": "...", "rubric": "[...]"}
            {"question": "What is...", "solution": "...", "rubric": "[...]"}
            ```

        dataset_spec: Dataset specification in the format "dataset_name" or
            "dataset_name@config_name". Examples:
            - "username/my-dataset" (uses "default" config)
            - "username/my-dataset@rubrics" (uses "rubrics" config)
            - "username/my-dataset@evaluations" (uses "evaluations" config)

            Multiple configs allow you to store different data types in the same
            dataset repository (e.g., raw data, rubrics, evaluation results).

        split: The dataset split name. Defaults to "train". Common values:
            - "train": Training or main data
            - "validation": Validation data
            - "test": Test data

        private: Whether to create a private dataset. Defaults to False (public).

    Returns:
        bool: True if upload succeeded, False otherwise

    Raises:
        FileNotFoundError: If the JSONL file doesn't exist
        ValueError: If the JSONL file is empty or contains invalid JSON
        Exception: For HuggingFace Hub upload errors

    Example:
        >>> # Upload rubrics with custom config
        >>> upload_jsonl_to_hf(
        ...     "qa_rubrics.jsonl",
        ...     "username/hf-agent-benchmark@rubrics",
        ...     split="train"
        ... )

        >>> # Upload evaluation results with different config
        >>> upload_jsonl_to_hf(
        ...     "evaluation_results.jsonl",
        ...     "username/hf-agent-benchmark@evaluations",
        ...     split="test"
        ... )

    Notes:
        - Requires authentication via `huggingface-cli login` or HF_TOKEN env var
        - If the dataset doesn't exist, it will be created automatically
        - If it exists, the specified config/split will be updated
        - Empty files will raise ValueError to prevent uploading invalid data
    """
    jsonl_path = Path(jsonl_file)

    # Validate file exists
    if not jsonl_path.exists():
        raise FileNotFoundError(f"JSONL file not found: {jsonl_file}")

    # Parse dataset specification
    if "@" in dataset_spec:
        dataset_name, config_name = dataset_spec.split("@", 1)
    else:
        dataset_name = dataset_spec
        config_name = "default"

    try:
        print(f"\nUploading {jsonl_path.name} to HuggingFace Hub...")
        print(f"  Dataset: {dataset_name}")
        print(f"  Config: {config_name}")
        print(f"  Split: {split}")

        # Load JSONL file
        records = []
        with open(jsonl_path, "r") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if line:  # Skip empty lines
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Invalid JSON on line {line_num}: {e}") from e

        if not records:
            raise ValueError("JSONL file is empty or contains no valid records")

        print(f"  Loaded {len(records)} records from JSONL")

        # Create HuggingFace Dataset
        dataset = Dataset.from_list(records)

        # Upload to HuggingFace Hub
        dataset.push_to_hub(
            dataset_name,
            config_name=config_name,
            split=split,
            private=private,
        )

        print(
            f"✓ Successfully uploaded to {dataset_name}@{config_name} (split: {split})"
        )
        return True

    except Exception as e:
        print(f"✗ Failed to upload to HuggingFace: {type(e).__name__}: {str(e)}")
        print(f"  JSONL file preserved at: {jsonl_path}")
        return False


def download_hf_to_jsonl(
    dataset_spec: str,
    output_file: Union[str, Path],
    split: str = "train",
    overwrite: bool = False,
) -> bool:
    """
    Download a dataset from HuggingFace Hub and save as JSONL.

    This function downloads a dataset from the HuggingFace Hub and saves it as a
    JSONL file where each line is a complete JSON object.

    Args:
        dataset_spec: Dataset specification in the format "dataset_name" or
            "dataset_name@config_name". Examples:
            - "username/my-dataset" (uses "default" config)
            - "username/my-dataset@rubrics" (uses "rubrics" config)
            - "username/my-dataset@evaluations" (uses "evaluations" config)

        output_file: Path where the JSONL file will be saved. Will create parent
            directories if they don't exist. Example: "data/downloaded_rubrics.jsonl"

        split: The dataset split to download. Defaults to "train". Common values:
            - "train": Training or main data
            - "validation": Validation data
            - "test": Test data
            - "all": Download all splits (creates one JSONL with all data)

        overwrite: Whether to overwrite existing file. Defaults to False.

    Returns:
        bool: True if download succeeded, False otherwise

    Raises:
        FileExistsError: If output file exists and overwrite=False
        ValueError: If the dataset/config/split doesn't exist
        Exception: For HuggingFace Hub download errors

    Example:
        >>> # Download rubrics from specific config
        >>> download_hf_to_jsonl(
        ...     "username/hf-agent-benchmark@rubrics",
        ...     "local_rubrics.jsonl",
        ...     split="train"
        ... )

        >>> # Download evaluation results
        >>> download_hf_to_jsonl(
        ...     "username/hf-agent-benchmark@evaluations",
        ...     "local_evaluations.jsonl",
        ...     split="test",
        ...     overwrite=True
        ... )

    Notes:
        - Requires authentication for private datasets via `huggingface-cli login`
        - Downloaded data will be in the same format as uploaded (preserves structure)
        - Each line in the output JSONL is a complete, valid JSON object
        - Large datasets may take time to download
    """
    output_path = Path(output_file)

    # Check if file exists
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Output file already exists: {output_file}. "
            "Use overwrite=True to replace it."
        )

    # Parse dataset specification
    if "@" in dataset_spec:
        dataset_name, config_name = dataset_spec.split("@", 1)
    else:
        dataset_name = dataset_spec
        config_name = "default"

    try:
        print("\nDownloading from HuggingFace Hub...")
        print(f"  Dataset: {dataset_name}")
        print(f"  Config: {config_name}")
        print(f"  Split: {split}")

        # Download dataset from HuggingFace Hub
        dataset = load_dataset(
            dataset_name,
            name=config_name,
            split=split,
        )

        print(f"  Downloaded {len(dataset)} records")

        # Create parent directories if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to JSONL
        with open(output_path, "w") as f:
            for record in dataset:
                # Convert record to JSON and write as line
                f.write(json.dumps(record) + "\n")

        print(f"✓ Successfully saved to {output_path}")
        print(f"  Total records: {len(dataset)}")
        return True

    except Exception as e:
        print(f"✗ Failed to download from HuggingFace: {type(e).__name__}: {str(e)}")
        return False


def list_dataset_configs(dataset_name: str) -> Optional[List[str]]:
    """
    List all available configs for a dataset on HuggingFace Hub.

    Args:
        dataset_name: Name of the dataset (e.g., "username/my-dataset")

    Returns:
        List of config names, or None if unable to retrieve

    Example:
        >>> configs = list_dataset_configs("username/hf-agent-benchmark")
        >>> print(configs)
        ['default', 'rubrics', 'evaluations']
    """
    try:
        from datasets import get_dataset_config_names

        configs = get_dataset_config_names(dataset_name)
        return configs
    except Exception as e:
        print(f"✗ Failed to list configs: {type(e).__name__}: {str(e)}")
        return None


def get_dataset_info(dataset_spec: str, split: str = "train") -> Optional[Dict]:
    """
    Get information about a dataset on HuggingFace Hub.

    Args:
        dataset_spec: Dataset specification ("dataset_name" or "dataset_name@config")
        split: The split to get info for (default: "train")

    Returns:
        Dictionary with dataset info, or None if unable to retrieve

    Example:
        >>> info = get_dataset_info("username/hf-agent-benchmark@rubrics")
        >>> print(f"Records: {info['num_rows']}")
        >>> print(f"Columns: {info['column_names']}")
    """
    # Parse dataset specification
    if "@" in dataset_spec:
        dataset_name, config_name = dataset_spec.split("@", 1)
    else:
        dataset_name = dataset_spec
        config_name = "default"

    try:
        # Load just to get info (streaming mode for efficiency)
        dataset = load_dataset(
            dataset_name,
            name=config_name,
            split=split,
            streaming=True,
        )

        # Get basic info
        info = {
            "dataset_name": dataset_name,
            "config_name": config_name,
            "split": split,
            "features": str(dataset.features),
            "column_names": dataset.column_names
            if hasattr(dataset, "column_names")
            else None,
        }

        # Try to get row count (only works for non-streaming)
        dataset_full = load_dataset(dataset_name, name=config_name, split=split)
        info["num_rows"] = len(dataset_full)

        return info

    except Exception as e:
        print(f"✗ Failed to get dataset info: {type(e).__name__}: {str(e)}")
        return None


def df_to_hub(
    df: pd.DataFrame,
    dataset_spec: str,
    split: str = "train",
    private: bool = False,
) -> bool:
    """
    Upload a pandas DataFrame directly to HuggingFace Hub as a dataset.

    This function converts a pandas DataFrame to a HuggingFace Dataset and uploads
    it to the Hub. This is useful for uploading data directly without creating an
    intermediate JSONL file.

    Args:
        df: pandas DataFrame to upload. All column types should be serializable.
            Example DataFrame:
            ```
            | question | solution | rubric |
            |----------|----------|--------|
            | "How..." | "You..." | {...}  |
            ```

        dataset_spec: Dataset specification in the format "dataset_name" or
            "dataset_name@config_name". Examples:
            - "username/my-dataset" (uses "default" config)
            - "username/my-dataset@rubrics" (uses "rubrics" config)
            - "username/my-dataset@evaluations" (uses "evaluations" config)

        split: The dataset split name. Defaults to "train". Common values:
            - "train": Training or main data
            - "validation": Validation data
            - "test": Test data

        private: Whether to create a private dataset. Defaults to False (public).

    Returns:
        bool: True if upload succeeded, False otherwise

    Raises:
        ValueError: If DataFrame is empty
        Exception: For HuggingFace Hub upload errors

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     "question": ["How to train?", "What is fine-tuning?"],
        ...     "solution": ["Use trainer...", "Fine-tuning is..."],
        ...     "rubric": ['[{"title": "...", ...}]', '[{"title": "...", ...}]']
        ... })
        >>> upload_dataframe_to_hf(df, "username/dataset@rubrics")

    Notes:
        - Requires authentication via `huggingface-cli login` or HF_TOKEN env var
        - DataFrame columns with complex objects should be serialized first (e.g., to JSON strings)
        - If the dataset doesn't exist, it will be created automatically
        - Empty DataFrames will raise ValueError to prevent uploading invalid data
    """
    # Validate DataFrame
    if df.empty:
        raise ValueError("DataFrame is empty")

    # Parse dataset specification
    if "@" in dataset_spec:
        dataset_name, config_name = dataset_spec.split("@", 1)
    else:
        dataset_name = dataset_spec
        config_name = "default"

    try:
        print("\nUploading DataFrame to HuggingFace Hub...")
        print(f"  Dataset: {dataset_name}")
        print(f"  Config: {config_name}")
        print(f"  Split: {split}")
        print(f"  Rows: {len(df)}")
        print(f"  Columns: {list(df.columns)}")

        # Convert DataFrame to HuggingFace Dataset
        dataset = Dataset.from_pandas(df)

        # Upload to HuggingFace Hub
        dataset.push_to_hub(
            dataset_name,
            config_name=config_name,
            split=split,
            private=private,
        )

        print(
            f"✓ Successfully uploaded to {dataset_name}@{config_name} (split: {split})"
        )
        return True

    except Exception as e:
        print(f"✗ Failed to upload to HuggingFace: {type(e).__name__}: {str(e)}")
        return False


def hub_to_df(
    dataset_spec: str,
    split: str = "train",
) -> Optional[pd.DataFrame]:
    """
    Download a dataset from HuggingFace Hub as a pandas DataFrame.

    This function downloads a dataset from the HuggingFace Hub and returns it as a
    pandas DataFrame for immediate use in Python.

    Args:
        dataset_spec: Dataset specification in the format "dataset_name" or
            "dataset_name@config_name". Examples:
            - "username/my-dataset" (uses "default" config)
            - "username/my-dataset@rubrics" (uses "rubrics" config)
            - "username/my-dataset@evaluations" (uses "evaluations" config)

        split: The dataset split to download. Defaults to "train". Common values:
            - "train": Training or main data
            - "validation": Validation data
            - "test": Test data

    Returns:
        pd.DataFrame: Downloaded data as pandas DataFrame, or None if failed

    Raises:
        ValueError: If the dataset/config/split doesn't exist
        Exception: For HuggingFace Hub download errors

    Example:
        >>> # Download rubrics from specific config
        >>> df = hub_to_df("username/hf-agent-benchmark@rubrics")
        >>> print(df.head())
        >>> print(f"Shape: {df.shape}")

        >>> # Download evaluation results
        >>> results_df = download_hf_to_dataframe(
        ...     "username/hf-agent-benchmark@evaluations",
        ...     split="test"
        ... )

    Notes:
        - Requires authentication for private datasets via `huggingface-cli login`
        - Downloaded data will be in the same format as uploaded (preserves structure)
        - Large datasets may take time to download and consume significant memory
        - For very large datasets, consider using streaming or download_hf_to_jsonl
    """
    # Parse dataset specification
    if "@" in dataset_spec:
        dataset_name, config_name = dataset_spec.split("@", 1)
    else:
        dataset_name = dataset_spec
        config_name = "default"

    try:
        print("\nDownloading from HuggingFace Hub...")
        print(f"  Dataset: {dataset_name}")
        print(f"  Config: {config_name}")
        print(f"  Split: {split}")

        # Download dataset from HuggingFace Hub
        dataset = load_dataset(
            dataset_name,
            name=config_name,
            split=split,
        )

        print(f"  Downloaded {len(dataset)} records")

        # Convert to pandas DataFrame
        df = dataset.to_pandas()

        print("✓ Successfully loaded as DataFrame")
        print(f"  Shape: {df.shape}")
        print(f"  Columns: {list(df.columns)}")
        return df

    except Exception as e:
        print(f"✗ Failed to download from HuggingFace: {type(e).__name__}: {str(e)}")
        return None


if __name__ == "__main__":
    # Example usage
    print("HuggingFace Dataset I/O Utilities")
    print("=" * 60)
    print("\nExample: Upload rubrics")
    print('  upload_jsonl_to_hf("qa_rubrics.jsonl", "username/dataset@rubrics")')
    print("\nExample: Download evaluations")
    print('  download_hf_to_jsonl("username/dataset@evaluations", "local.jsonl")')
    print("\nExample: List configs")
    print('  list_dataset_configs("username/dataset")')
    print("\nExample: Get dataset info")
    print('  get_dataset_info("username/dataset@rubrics")')
    print("=" * 60)
