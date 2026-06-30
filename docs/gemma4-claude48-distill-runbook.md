# Gemma 4 12B Claude 4.8 Coding Distillation Runbook

## Phase 1: Smoke

1. Build 10 verified trajectories:

```powershell
uv run python scripts/build_gemma4_distill_dataset.py --output .\data\gemma4-smoke.jsonl --taco-limit 10 --apps-limit 10 --max-verified 10 --concurrency 1
```

2. Train one short LoRA smoke job on AML:

```powershell
uv run python scripts/submit_gemma4_distill_aml.py train-smoke --dataset azureml://datastores/waxamlstore_private/paths/agent_train/datasets/gemma4-smoke.jsonl
```

3. Run HumanEval+ and MBPP+ for base and smoke finetune:

```powershell
uv run python scripts/eval_gemma4_public_benchmarks.py --model google/gemma-4-12B-it --output .\eval-results\base --tp 4
uv run python scripts/eval_gemma4_public_benchmarks.py --model C:\mnt\agent_train\models\gemma4-smoke-merged --output .\eval-results\smoke --tp 4
```

## Phase 2: v1

1. Build 5,000 verified trajectories from TACO/APPS train.
2. Train Gemma 4 12B LoRA for one epoch on `a100x4`.
3. Evaluate base and finetune on HumanEval+, MBPP+, and BigCodeBench Hard.
4. Accept v1 only if P0 metrics improve or stay within the regression threshold.

## Guardrails

- Do not train on `evalplus/humanevalplus`, `evalplus/mbppplus`, or `bigcode/bigcodebench`.
- Do not request hidden chain-of-thought from the teacher; request a public solution rationale.
- Do not publish benchmark claims unless base and finetune use the same harness, same decoding, and same tensor-parallel settings.

## Known setup dependency

`scripts/submit_gemma4_distill_aml.py` requires `agent.tools.azure_aml_tool`. If that tool is not present in the current checkout, merge or install the Azure ML tool before submitting AML jobs.
