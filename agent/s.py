import json

from datasets import load_dataset
from dotenv import load_dotenv
from huggingface_hub import hf_hub_download

load_dotenv()

# Download only this specific parquet file
path = hf_hub_download(
    repo_id="smolagents/hf-agent-sessions-2",
    filename="sessions/2026-01/batch_20260130_121208_c1c0c1e7.parquet",
    repo_type="dataset",
)
ds = load_dataset("parquet", data_files=path, split="train")

# Sort by updated_at descending, get the latest row
sorted_ds = ds.sort("updated_at", reverse=True)
latest = sorted_ds[0]

print(type(latest["messages_json"]))
print(json.dumps(json.loads(latest["messages_json"]), indent=2))
