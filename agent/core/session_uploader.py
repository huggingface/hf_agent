#!/usr/bin/env python3
"""
Standalone script for uploading session trajectories to HuggingFace.
This runs as a separate process to avoid blocking the main agent.
"""

import json
import os
import sys
from pathlib import Path


def upload_session_to_dataset(session_file: str, repo_id: str, max_retries: int = 3):
    """Upload a single session file to HuggingFace dataset"""
    try:
        from datasets import Dataset, load_dataset
    except ImportError:
        print("Error: datasets library not available", file=sys.stderr)
        return False

    try:
        # Load session data
        with open(session_file, "r") as f:
            data = json.load(f)

        # Check if already uploaded
        upload_status = data.get("upload_status")
        if upload_status == "success":
            return True

        # Prepare row for upload
        row = {
            "session_id": data["session_id"],
            "session_start_time": data["session_start_time"],
            "session_end_time": data["session_end_time"],
            "model_name": data["model_name"],
            "messages": json.dumps(data["messages"]),
            "events": json.dumps(data["events"]),
        }

        hf_token = os.getenv("HF_TOKEN")
        if not hf_token:
            # Update status to failed
            data["upload_status"] = "failed"
            with open(session_file, "w") as f:
                json.dump(data, f, indent=2)
            return False

        # Try to load existing dataset and append
        for attempt in range(max_retries):
            try:
                try:
                    existing_dataset = load_dataset(repo_id, split="train")
                    new_dataset = Dataset.from_dict(
                        {k: list(existing_dataset[k]) + [v] for k, v in row.items()}
                    )
                except Exception:
                    # Dataset doesn't exist yet, create new one
                    new_dataset = Dataset.from_dict({k: [v] for k, v in row.items()})

                # Push to hub
                new_dataset.push_to_hub(repo_id, private=True, token=hf_token)

                # Update status to success
                data["upload_status"] = "success"
                data["upload_url"] = f"https://huggingface.co/datasets/{repo_id}"
                with open(session_file, "w") as f:
                    json.dump(data, f, indent=2)

                return True

            except Exception:
                if attempt < max_retries - 1:
                    import time

                    wait_time = 2**attempt
                    time.sleep(wait_time)
                else:
                    # Final attempt failed
                    data["upload_status"] = "failed"
                    with open(session_file, "w") as f:
                        json.dump(data, f, indent=2)
                    return False

    except Exception as e:
        print(f"Error uploading session: {e}", file=sys.stderr)
        return False


def retry_failed_uploads(directory: str, repo_id: str):
    """Retry all failed/pending uploads in a directory"""
    log_dir = Path(directory)
    if not log_dir.exists():
        return

    session_files = list(log_dir.glob("session_*.json"))

    for filepath in session_files:
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            upload_status = data.get("upload_status", "unknown")

            # Only retry pending or failed uploads
            if upload_status in ["pending", "failed"]:
                upload_session_to_dataset(str(filepath), repo_id)

        except Exception:
            pass


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: session_uploader.py <command> <args...>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "upload":
        # python session_uploader.py upload <session_file> <repo_id>
        if len(sys.argv) < 4:
            print("Usage: session_uploader.py upload <session_file> <repo_id>")
            sys.exit(1)
        session_file = sys.argv[2]
        repo_id = sys.argv[3]
        success = upload_session_to_dataset(session_file, repo_id)
        sys.exit(0 if success else 1)

    elif command == "retry":
        # python session_uploader.py retry <directory> <repo_id>
        if len(sys.argv) < 4:
            print("Usage: session_uploader.py retry <directory> <repo_id>")
            sys.exit(1)
        directory = sys.argv[2]
        repo_id = sys.argv[3]
        retry_failed_uploads(directory, repo_id)
        sys.exit(0)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
