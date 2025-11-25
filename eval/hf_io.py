"""
HuggingFace Dataset I/O Utilities

Reusable functions for uploading and downloading JSONL data to/from HuggingFace Hub.
Supports the dataset_name@config_name notation for managing multiple configurations.
"""

from typing import List, Optional

import pandas as pd
from datasets import Dataset, load_dataset


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
