#!/usr/bin/env env python3
"""
Rubric Generation Script for HF-Agent Benchmark

Generates instance-specific evaluation rubrics following the "Rubrics as Rewards" paper.
Uses LiteLLM to call LLM models for rubric synthesis with expert grounding via reference answers.
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

import litellm
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel


class Rubric(BaseModel):
    title: str
    description: str
    weight: int


class RubricList(BaseModel):
    rubrics: List[Rubric]


# Load environment variables
load_dotenv()

# Rubric generation prompt template based on RaR paper


PROMPT_TEMPLATE = """You are an expert rubric writer. Your job is to generate a self-contained set of evaluation criteria (“rubrics”) for judging
how good, helpful and complete an agent's trajectory is to a given user question/request. 

Rubrics can cover aspects of a response such as, but not limited to, factual correctness, helpfulness, completeness, harmlessness, correctness of using Hugging Face best practices (based on HF documentation), depth of
reasoning, contextual relevance and usefulness. Each item must be self-contained – non expert readers should not need to
infer anything or consult external information. Begin each description with its category: “Essential Criteria: . . . ”, “Important
Criteria: . . . ”, “Optional Criteria: . . . ”, or “Pitfall Criteria: Does not mention . . . ”.


Inputs: !!!
- question: <<<{question}>>>
- reference_answer (ideal solution): <<<{reference_answer}>>>
- thread: <<<{thread}>>>

Total items:
• Choose 7–20 rubric items based on the complexity of the question.

Each rubric item:
• title (2–4 words).
• description: One sentence starting with its category prefix that explicitly states exactly what to look for. For example:
– Essential Criteria: Writes a up-to-date, correct, complete and working training loop using the latest Hugging Face best practices. Launches the training with hf-jobs. 
– Pitfall Criteria: Deprecated launcher usage. Uses python -m torch.distributed.launch instead of torchrun / accelerate.
– Important Criteria: Explains common DDP knobs. Mentions ddp_find_unused_parameters=False for models with conditional branches; optional ddp_timeout; brief note on when they matter and why.
– Optional Criteria: Briefly notes --deepspeed ds_config.json as an alternative scaler when models get big (but stays on DDP for this Q).
• weight: For Essential/Important/Optional, use 1–5 (5 = most important); for Pitfall, use –1 or –2.

Category guidance:
• Essential: Critical actions to answer/complete the user's question/request; if missing, the response is invalid and useless (weight 5).
• Important: Key reasoning, completeness, or clarity; strongly affects quality and usefulness (weight 3–4).
• Optional: Helpfulness in educating the user or providing extra depth; nice to have but not deal-breaking (weight 1–2).
• Pitfall: Common mistakes or omissions specific to this prompt—identify things a respondent often forgets or misstates.
Each Pitfall description must begin with “Pitfall Criteria: Does not mention . . . ” or “Pitfall Criteria: Recommends . . . ”
and use weight –1 or –2.

To ensure self-contained guidance:
• When referring to answer choices, explicitly say “Identifies (A)”, “Identifies (B)”, etc., rather than vague phrasing.
• If the format requires an action like calling a tool or launching a training run, include a rubric item such as:
– Essential Criteria: Includes a clear statement "Launches the training with hf-jobs.".
• If reasoning should precede the answer, include a rubric like:
– Important Criteria: Presents the explanation and reasoning before stating the final answer.
• If brevity is valued, include a rubric like:
– Optional Criteria: Remains concise and avoids unnecessary detail.
• If the question context demands mention of specific findings/best practices, include that explicitly (e.g., “Essential Criteria: Mentions
that training data must be in "messages" column for LLM training”).

Output: Provide a JSON array of rubric objects. Each object must contain exactly three keys—title, description, and weight.
Do not copy large blocks of the question or reference_answer into the text. Each description must begin with its category
prefix, and no extra keys are allowed.
Now, given the question, thread and reference_answer, generate the rubric as described. The reference answer is an good and helpful response
but not necessarily exhaustive; use it only as guidance."""


def build_prompt(
    question: str, reference_answer: str, thread: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    """
    Build the messages list for LiteLLM completion.

    Args:
        question: The question/task to evaluate
        reference_answer: The reference/accepted solution

    Returns:
        List of message dicts for LiteLLM
    """
    prompt = PROMPT_TEMPLATE.format(
        question=question, reference_answer=reference_answer, thread=thread
    )

    return [{"role": "user", "content": prompt}]


def validate_rubric(rubric_list: List[Dict[str, Any]]) -> bool:
    """
    Validate that rubric meets basic requirements.

    Args:
        rubric_list: List of rubric items to validate

    Returns:
        True if valid, False otherwise
    """
    # Check count
    if not (7 <= len(rubric_list) <= 20):
        return False

    # Check each item
    category_prefixes = [
        "Essential Criteria:",
        "Important Criteria:",
        "Optional Criteria:",
        "Pitfall Criteria:",
    ]

    for item in rubric_list:
        # Check keys
        if set(item.keys()) != {"title", "description", "weight"}:
            return False

        # Check description starts with category prefix
        if not any(
            item["description"].startswith(prefix) for prefix in category_prefixes
        ):
            return False

    return True


def generate_rubric(row: pd.Series, model: str, timeout: int = 120) -> Dict[str, Any]:
    """
    Generate rubric for a single question using LiteLLM.

    Args:
        question: The question text
        reference_answer: The reference solution
        model: Model name for LiteLLM
        timeout: Request timeout in seconds

    Returns:
        Dict with rubric_list and rubric_count, or None on failure
    """

    messages = build_prompt(row["question"], row["solution"], row["thread"])

    try:
        response = litellm.completion(
            model=model,
            messages=messages,
            timeout=timeout,
            response_format=RubricList,
        )

        # Parse structured output
        rubric_list: RubricList = RubricList.model_validate_json(
            response.choices[0].message.content
        )

        return rubric_list.model_dump_json()
    except Exception as e:
        print(f"Error generating rubric: {e}", file=sys.stderr)
        return None


def load_input_data(infile: str) -> pd.DataFrame:
    """
    Load input data from CSV or JSONL file.

    Args:
        infile: Path to input file

    Returns:
        DataFrame with loaded data
    """
    path = Path(infile)

    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {infile}")

    if path.suffix == ".csv":
        # Try to auto-detect delimiter (comma or semicolon)
        df = pd.read_csv(infile, sep=None, engine="python")
    elif path.suffix == ".jsonl":
        df = pd.read_json(infile, lines=True)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}. Use .csv or .jsonl")

    # Validate required columns
    required_cols = [
        "discussion_title",
        "discussion_url",
        "question",
        "thread",
        "solution",
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Generate rubrics for HF-agent benchmark evaluation"
    )
    parser.add_argument(
        "--infile", type=str, required=True, help="Input file path (.csv or .jsonl)"
    )
    parser.add_argument(
        "--outfile", type=str, required=True, help="Output JSONL file path"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="anthropic/claude-sonnet-4-5-20250929",
        help="LiteLLM model name (default: from LITELLM_MODEL env or gpt-4o-mini)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Request timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=30,
        help="Maximum number of concurrent workers (default: 30)",
    )

    args = parser.parse_args()

    # Determine model
    model = args.model or os.getenv("LITELLM_MODEL", "gpt-4o-mini")
    print(f"Using model: {model}")

    # Load input data
    print(f"Loading data from {args.infile}...")
    df = load_input_data(args.infile)
    print(f"Loaded {len(df)} examples")

    # Run rubric generation in parallel using ThreadPoolExecutor
    print(f"Running generation with {args.max_concurrent} parallel workers...")

    with ThreadPoolExecutor(max_workers=args.max_concurrent) as executor:
        # Submit all tasks
        future_to_idx = {}
        for idx, row in df.iterrows():
            future = executor.submit(
                generate_rubric,
                row=row,
                model=model,
                timeout=args.timeout,
            )
            future_to_idx[future] = idx

        # Collect results in order
        results = [None] * len(df)
        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()
            completed += 1
            print(f"Completed: {completed}/{len(df)}", end="\r")

    print()  # New line after progress

    # Write results to file
    print(f"Writing results to {args.outfile}...")
    success_count = 0
    failure_count = 0

    with open(args.outfile, "w") as outf:
        for idx, (_, row) in enumerate(df.iterrows()):
            rubric_result = results[idx]

            if rubric_result is None:
                failure_count += 1
                continue

            # Merge with original data
            output_row = row.to_dict()
            output_row["rubric"] = rubric_result

            # Write JSONL line
            outf.write(json.dumps(output_row, default=str) + "\n")
            success_count += 1

    print("\nComplete!")
    print(f"Success: {success_count}/{len(df)}")
    print(f"Failures: {failure_count}/{len(df)}")
    print(f"Output written to: {args.outfile}")


if __name__ == "__main__":
    main()
