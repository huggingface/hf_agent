# HF-Agent Eval

Rubric-based evaluation pipeline implementing [Rubrics as Rewards](https://arxiv.org/abs/2410.13254) (RaR-Explicit).

## Pipeline

```
QA pairs → generate_rubrics.py → `eval/task.py@hf-benchmark-with-rubrics` → scores
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

### 2. Evaluate Responses (Inspect)

Load your rubric dataset, run a solver, and score with `rubric_scorer` using `inspect-ai`.

Files:  
- `eval/hf_agent_connector.py` contains a lightweight bridge that spins up
  the existing hf-agent stack in `agent/` (tools, MCP, LiteLLM loop) and returns the assistant reply.
- `eval/solvers.py` keeps the solver implementations (e.g. `hf_agent_solver`,
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
  -T solver_name=hf_agent_solver \
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


## Scoring (implemented in `eval/rubric_eval.py`)

The scoring is implemented in `eval/rubric_eval.py` and is based on the RaR-Explicit formula: `score = Σ(weight × satisfied) / Σ(positive_weights)`.

The score is normalized to [0, 1] and clipped if pitfalls make it negative.
