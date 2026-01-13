"""
Shared pytest fixtures for agent tools testing.
All test data is hardcoded based on real session traces from akseljoonas/hf-agent-sessions.
"""

import os
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_github_token():
    """Set GITHUB_TOKEN for tests"""
    with patch.dict(os.environ, {"GITHUB_TOKEN": "test-github-token-12345"}):
        yield "test-github-token-12345"


@pytest.fixture
def mock_hf_token():
    """Set HF_TOKEN for tests"""
    with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token_12345"}):
        yield "hf_test_token_12345"


@pytest.fixture
def trl_repo_tree():
    """
    Real TRL repository tree structure for mocking GitHub API.
    Based on actual huggingface/trl repo structure.
    """
    return {
        "sha": "main",
        "tree": [
            {
                "path": "examples/scripts/dpo.py",
                "type": "blob",
                "sha": "abc123",
                "size": 5000,
            },
            {
                "path": "examples/scripts/sft.py",
                "type": "blob",
                "sha": "abc124",
                "size": 4500,
            },
            {
                "path": "examples/scripts/grpo.py",
                "type": "blob",
                "sha": "abc125",
                "size": 6000,
            },
            {
                "path": "examples/scripts/ppo.py",
                "type": "blob",
                "sha": "abc126",
                "size": 5500,
            },
            {
                "path": "examples/datasets/hh-rlhf-helpful-base.py",
                "type": "blob",
                "sha": "abc127",
                "size": 2000,
            },
            {
                "path": "trl/scripts/dpo.py",
                "type": "blob",
                "sha": "def456",
                "size": 8000,
            },
            {
                "path": "trl/trainer/dpo_trainer.py",
                "type": "blob",
                "sha": "ghi789",
                "size": 15000,
            },
            {
                "path": "trl/trainer/sft_trainer.py",
                "type": "blob",
                "sha": "ghi790",
                "size": 12000,
            },
            {"path": "trl/__init__.py", "type": "blob", "sha": "init01", "size": 500},
            {"path": "README.md", "type": "blob", "sha": "readme1", "size": 3000},
            {
                "path": "notebooks/dpo_training.ipynb",
                "type": "blob",
                "sha": "nb001",
                "size": 25000,
            },
            {
                "path": "tutorials/getting_started.md",
                "type": "blob",
                "sha": "tut01",
                "size": 5000,
            },
        ],
    }


@pytest.fixture
def trl_repo_info():
    """TRL repository metadata"""
    return {
        "id": 123456,
        "name": "trl",
        "full_name": "huggingface/trl",
        "default_branch": "main",
        "description": "Train transformer language models with reinforcement learning.",
        "stargazers_count": 10000,
        "forks_count": 1500,
    }


@pytest.fixture
def sample_python_file_content():
    """
    Sample Python file content (500+ lines) for testing truncation.
    Based on real DPO training script patterns from session logs.
    """
    header = '''"""
DPO Training Script for Qwen3-1.7B-Base on HH-RLHF
Using TRL DPOTrainer with Trackio monitoring
"""

import os
import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import DPOConfig, DPOTrainer

# Model and dataset configuration
model_id = "Qwen/Qwen3-1.7B-Base"
dataset_name = "trl-lib/hh-rlhf-helpful-base"
output_model_id = "user/qwen3-1.7b-dpo"

print(f"Loading model: {model_id}")
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    trust_remote_code=True,
)

'''
    # Generate 500 lines total
    lines = header.split("\n")
    while len(lines) < 500:
        lines.append(
            f"# Line {len(lines) + 1}: Configuration and training code continues..."
        )
    lines.append("trainer.train()")
    lines.append("trainer.push_to_hub()")
    lines.append("print('Training complete!')")
    return "\n".join(lines)


@pytest.fixture
def sample_jupyter_notebook():
    """
    Sample Jupyter notebook JSON for testing notebook conversion.
    """
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            }
        },
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# DPO Training Tutorial\n",
                    "\n",
                    "This notebook demonstrates DPO training.",
                ],
            },
            {
                "cell_type": "code",
                "metadata": {},
                "source": [
                    "from trl import DPOConfig, DPOTrainer\n",
                    "print('Hello TRL!')",
                ],
                "outputs": [
                    {
                        "output_type": "stream",
                        "name": "stdout",
                        "text": ["Hello TRL!\n"],
                    }
                ],
                "execution_count": 1,
            },
            {
                "cell_type": "code",
                "metadata": {},
                "source": "# Training configuration\nconfig = DPOConfig(output_dir='./output')",
                "outputs": [],
                "execution_count": 2,
            },
        ],
    }


@pytest.fixture
def trl_docs_sidebar_html():
    """
    Real TRL documentation sidebar HTML structure.
    """
    return """
    <html>
    <body>
    <nav class="flex-auto overflow-y-auto">
        <ul>
            <li><a href="/docs/trl/index">TRL</a></li>
            <li><a href="/docs/trl/installation">Installation</a></li>
            <li><a href="/docs/trl/quickstart">Quickstart</a></li>
            <li><a href="/docs/trl/sft_trainer">SFTTrainer</a></li>
            <li><a href="/docs/trl/dpo_trainer">DPOTrainer</a></li>
            <li><a href="/docs/trl/grpo_trainer">GRPOTrainer</a></li>
            <li><a href="/docs/trl/ppo_trainer">PPOTrainer</a></li>
            <li><a href="/docs/trl/reward_trainer">RewardTrainer</a></li>
            <li><a href="/docs/trl/dataset_formats">Dataset Formats</a></li>
        </ul>
    </nav>
    </body>
    </html>
    """


@pytest.fixture
def dpo_trainer_docs_markdown():
    """
    Sample DPO trainer documentation markdown.
    """
    return """# DPOTrainer

The `DPOTrainer` class implements Direct Preference Optimization for training language models.

## Usage

```python
from trl import DPOConfig, DPOTrainer

config = DPOConfig(
    output_dir="./output",
    beta=0.1,
    learning_rate=5e-7,
)

trainer = DPOTrainer(
    model=model,
    ref_model=ref_model,
    args=config,
    train_dataset=dataset,
    processing_class=tokenizer,
)

trainer.train()
```

## Parameters

- `beta`: The beta parameter for DPO loss (default: 0.1)
- `learning_rate`: Learning rate for training (default: 5e-7)
"""


@pytest.fixture
def sample_openapi_spec():
    """
    Minimal HuggingFace OpenAPI spec for testing.
    """
    return {
        "openapi": "3.0.0",
        "info": {"title": "Hugging Face Hub API", "version": "1.0.0"},
        "servers": [{"url": "https://huggingface.co"}],
        "tags": [
            {"name": "repos", "description": "Repository operations"},
            {"name": "models", "description": "Model operations"},
        ],
        "paths": {
            "/api/repos/{repo_id}": {
                "get": {
                    "tags": ["repos"],
                    "operationId": "get_repo",
                    "summary": "Get repository information",
                    "parameters": [
                        {
                            "name": "repo_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                            "example": "bert-base-uncased",
                        }
                    ],
                    "responses": {"200": {"description": "Repository information"}},
                }
            },
            "/api/repos": {
                "post": {
                    "tags": ["repos"],
                    "operationId": "create_repo",
                    "summary": "Create a new repository",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "example": {"name": "my-model", "private": True},
                                }
                            }
                        }
                    },
                    "responses": {"201": {"description": "Repository created"}},
                }
            },
        },
    }


@pytest.fixture
def sample_uv_install_logs():
    """
    Sample UV package installation logs for testing filtering.
    """
    return [
        "Resolved 42 packages in 1.23s",
        "Prepared 42 packages in 2.34s",
        "   + torch==2.0.0",
        "   + transformers==4.35.0",
        "   + trl==0.7.0",
        "   + datasets==2.14.0",
        "   + accelerate==0.24.0",
        "   + peft==0.6.0",
        "   + bitsandbytes==0.41.0",
        "   + safetensors==0.4.0",
        "   + tokenizers==0.14.0",
        "   + huggingface-hub==0.19.0",
        "   + numpy==1.24.0",
        "   + pandas==2.0.0",
        "Installed 42 packages in 3.2s",
        "Loading model: Qwen/Qwen3-1.7B-Base",
        "Model loaded successfully",
        "Starting training...",
        "Epoch 1/3: loss=0.5",
        "Training complete!",
    ]


@pytest.fixture
def sample_plan_todos():
    """
    Sample plan todos from real session traces.
    """
    return [
        {
            "id": "1",
            "content": "Inspect Anthropic/hh-rlhf dataset structure",
            "status": "completed",
        },
        {
            "id": "2",
            "content": "Research TRL documentation for DPO training",
            "status": "completed",
        },
        {"id": "3", "content": "Create DPO training script", "status": "in_progress"},
        {"id": "4", "content": "Submit training job to HF Jobs", "status": "pending"},
        {"id": "5", "content": "Verify model upload to Hub", "status": "pending"},
    ]
