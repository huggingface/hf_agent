# HF-Agent Eval

Rubric-based evaluation pipeline implementing [Rubrics as Rewards](https://arxiv.org/abs/2410.13254) (RaR-Explicit).

## Pipeline

```
QA pairs → generate_rubrics.py → evaluate.py → scores
```

### 1. Generate Rubrics

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

### 2. Evaluate Responses

Scores responses using generated rubrics via LLM-as-judge.

```python
from evaluate import evaluate_dataset_with_rubrics

evaluate_dataset_with_rubrics(
    input_file="responses.jsonl",
    rubric_file="qa_rubrics.jsonl",
    ground_truth_file="qa_pairs.jsonl",
    output_file="results.jsonl",
    model="gpt-4o-mini",
    push_to_hub="akseljoonas/hf-agent-benchmark@evaluations"
)
```

**Output:** Normalized score [0, 1] + per-criterion satisfaction + reasoning

## HuggingFace Integration

Both scripts upload DataFrames before saving JSONL:

```python
from hf_dataset_io import df_to_hub, hub_to_df

# Upload
df_to_hub(df, "username/dataset@config", split="train")

# Download
df = hub_to_df("username/dataset@config", split="train")
```

Use `@config` notation to organize: `@rubrics`, `@evaluations`, `@ground-truth`

## Key Parameters

- **--max-concurrent**: Parallel workers (default: 30 for rubrics, 10 for eval)
- **--push-to-hub**: Auto-upload to HF Hub (e.g., `user/dataset@rubrics`)
- **--model**: LiteLLM model string
- **split**: `train` for rubrics, `test` for evaluations

## Scoring

RaR-Explicit: `score = Σ(weight × satisfied) / Σ(positive_weights)`

Normalized to [0, 1], clipped if pitfalls make it negative.
