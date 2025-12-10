# HF-Agent Eval

Rubric-based evaluation pipeline implementing [Rubrics as Rewards](https://arxiv.org/abs/2507.17746) paper (RaR-Explicit formula).

## Components

| Component | Purpose | Long Term Goal |
|-----------|---------|----------------|
| **`generate_rubrics.py`** | Generates instance-specific evaluation criteria (7-20 weighted rubrics) from QA pairs using LLM, following the RaR paper methodology | Improve rubric quality with few-shot examples, domain-specific templates, and iterative refinement |
| **`rubric_eval.py`** | Scores responses using RaR-Explicit formula: checks each criterion independently via LLM judge, computes weighted normalized score | Support batch evaluation, caching, and alternative scoring formulas (RaR-Holistic) |
| **`task.py`** | Defines Inspect AI task `hf-benchmark-with-rubrics` that wires dataset, solver, and rubric scorer into a single evaluation pipeline | Add more task variants for different benchmarks (code generation, tool use, multi-turn) |
| **`solvers.py`** | Registry of solver implementations (`hf_agent`, `claude_code`, `claude_code+hf_mcp`) that can be swapped via CLI args | Expand solver library to benchmark more agents (OpenAI Codex, Gemini, open-source agents) |
| **`hf_agent_connector.py`** | Lightweight bridge that spins up the hf-agent stack (tools, MCP, LiteLLM loop) and returns the final assistant response | Enable streaming, intermediate step logging, and cost tracking per evaluation |
| **`leaderboard.py`** | Utilities to build records and append scores to a HuggingFace dataset for tracking performance over time | Add score breakdowns, visualizations, and automatic regression detection |
| **`run_eval_with_leaderboard.py`** | CLI wrapper that runs `inspect eval`, parses scores from logs, and pushes results to the leaderboard dataset | Support scheduled CI runs, PR-gated benchmarks, and multi-dataset aggregation |
| **`hf_io.py`** | Helper utilities for pushing DataFrames to HuggingFace Hub | Extend with dataset versioning and diff tracking |
| **`models.py`** | Shared Pydantic models for evaluation data structures | Centralize all eval schemas for consistency across components |

## Pipeline

```
QA pairs → generate_rubrics.py → run `inspect-ai eval eval/task.py@hf-benchmark-with-rubrics` → scores
```

### 1. Generate Rubrics (if not already generated)

Creates instance-specific evaluation criteria from question + reference answer.

```bash
python eval/generate_rubrics.py \
    --infile qa_pairs.jsonl \
    --outfile qa_rubrics.jsonl \
    --model anthropic/claude-sonnet-4-5-20250929 \
    --push-to-hub akseljoonas/hf-agent-benchmark@rubrics
```

**Input format:**
```json
{"question": "...", "solution": "...", "thread": [...]}
```

**Output:** 7-20 weighted criteria per question (Essential: +5, Important: +3-4, Optional: +1-2, Pitfall: -1 to -2)

### 2. Response evaluation

Files:  
- `eval/hf_agent_connector.py` contains a lightweight bridge that spins up
  the existing hf-agent stack in `agent/` (tools, MCP, LiteLLM loop) and returns the assistant reply.
- `eval/solvers.py` keeps the solver implementations (e.g. `hf_agent`,
  `claude_code`). If additional solvers are needed, register them there and pass
  `-T solver_name=<name>` to swap them in without touching the task.
- `eval/task.py` registers `hf-benchmark-with-rubrics`, which wires
  the dataset, solver, and rubric scorer into a single Inspect task and does the eval.

### Running the hf-agent (implemented in `agent/`) (args are optional)
```bash
uv run inspect eval eval/task.py@hf-benchmark-with-rubrics \
  -T dataset_name=akseljoonas/hf-agent-rubrics \
  -T dataset_split=train \
  -T limit=25 \
  -T solver_name=hf_agent \
  -T solver_kwargs='{"config_path":"agent/config_mcp_example.json","max_iterations":10}' \
  --log-dir logs/inspect
```

Different benchmarks can be used by making/running a new task in `eval/task.py`.

### Running Claude Code headlessly

The `claude_code` solver shell-outs to the `claude` CLI (`claude -p ... --output-format json`)
so you can benchmark Claude Code without any interactive UI. Example:

Claude Code command example (kwargs are optional):
```bash
uv run inspect eval eval/task.py@hf-benchmark-with-rubrics \
  -T solver_name=claude_code \
  -T solver_kwargs='{"allowed_tools":"Bash,Read","output_format":"json"}'
```

### Leaderboard

Scores can be pushed to a Hugging Face dataset automatically by wrapping the run
with `eval/run_eval_with_leaderboard.py` (it executes `inspect eval ...` under the hood
and only appends results when the command succeeds):

```bash
uv run python eval/run_eval_with_leaderboard.py \
  --hf-dataset akseljoonas/hf-agent-leaderboard \
  --hf-token $HF_TOKEN \
  --solver-name hf_agent \
  --solver-kwargs '{"config_path":"agent/config_mcp_example.json","max_iterations":10}' \
  --dataset akseljoonas/hf-agent-rubrics@train \
  --limit 25
```

## Scoring (implemented in `eval/rubric_eval.py`)

The scoring is implemented in `eval/rubric_eval.py` and is based on the RaR-Explicit formula: `score = Σ(weight × satisfied) / Σ(positive_weights)`.

The score is normalized to [0, 1] and clipped if pitfalls make it negative.
