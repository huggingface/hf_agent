#!/usr/bin/env python3
"""
Minimal script to check if tasks in solved_tasks.jsonl were fully completed and verified.
Uses an LLM to assess completion status and adds the result to each row.
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import litellm
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class CompletionCheck(BaseModel):
    reasoning: str
    completed: bool
    verified: bool


PROMPT = """You are evaluating whether an AI agent fully completed a task AND verified its completion.

Task: {question}

Agent's final answer: {solution}

Agent's trace (tool calls and responses):
{trace}

Evaluate:
1. **completed**: Did the agent actually complete the task? (not just explain what could be done, but actually do it)
2. **verified**: Did the agent verify/confirm that the task was completed correctly? (e.g., checked output, validated results, confirmed success)

Be strict:
- If the agent asked for more information or said "please provide...", it's NOT completed.
- If the agent only explained how to do something but didn't do it, it's NOT completed.
- If the agent just made a plan of how to complete it but didn't do it, it's NOT completed.
- If there's an error in the trace and no recovery, it's NOT completed.
- If the agent didn't check/confirm the code/command completed succesfully or the result is correct somehow, it's NOT verified.

Return JSON with: completed (bool), verified (bool), reasoning (brief explanation)."""


def format_trace(messages: list) -> str:
    """Format messages trace for the prompt."""
    if not messages:
        return "(No trace)"

    parts = []
    for msg in messages:
        role = msg.get("role", "unknown")
        if role == "system":
            continue

        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])

        if tool_calls:
            for tc in tool_calls:
                if isinstance(tc, dict) and "function" in tc:
                    name = tc["function"].get("name", "?")
                    parts.append(f"[TOOL CALL] {name}")

        if content:
            # Truncate long content
            if len(content) > 5000:
                content = content[:4000] + "..." + content[-1000:]
            parts.append(f"[{role.upper()}] {content}")

    return "\n".join(parts) if parts else "(Empty trace)"


def check_row(row: dict, model: str) -> CompletionCheck | None:
    """Check if a single task was completed and verified."""
    prompt = PROMPT.format(
        question=row["question"],
        solution=row.get("solution", "(No solution)"),
        trace=format_trace(row.get("messages", [])),
    )

    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format=CompletionCheck,
            timeout=60,
        )
        return CompletionCheck.model_validate_json(response.choices[0].message.content)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Check task completion status")
    parser.add_argument("--infile", type=str, default="eval/solved_tasks.jsonl")
    parser.add_argument(
        "--outfile", type=str, default="eval/solved_tasks_checked.jsonl"
    )
    parser.add_argument(
        "--model", type=str, default="anthropic/claude-sonnet-4-5-20250929"
    )
    parser.add_argument("--max-concurrent", type=int, default=30)
    args = parser.parse_args()

    # Load data
    print(f"Loading {args.infile}...")
    rows = []
    with open(args.infile) as f:
        for line in f:
            rows.append(json.loads(line))
    print(f"Loaded {len(rows)} rows")

    # Process in parallel
    print(f"Checking completion with {args.model}...")
    with ThreadPoolExecutor(max_workers=args.max_concurrent) as executor:
        futures = {
            executor.submit(check_row, row, args.model): i for i, row in enumerate(rows)
        }
        results = [None] * len(rows)

        for future in as_completed(futures):
            idx = futures[future]
            results[idx] = future.result()
            print(
                f"Done: {sum(1 for r in results if r is not None)}/{len(rows)}",
                end="\r",
            )

    print()

    # Merge results
    output_rows = []
    for row, result in zip(rows, results):
        if result:
            row["task_completed"] = result.completed
            row["task_verified"] = result.verified
            row["completion_reasoning"] = result.reasoning
        else:
            row["task_completed"] = None
            row["task_verified"] = None
            row["completion_reasoning"] = "Error during check"
        output_rows.append(row)

    # Write output
    print(f"Writing to {args.outfile}...")
    with open(args.outfile, "w") as f:
        for row in output_rows:
            f.write(json.dumps(row, default=str) + "\n")

    # Summary
    completed = sum(1 for r in results if r and r.completed)
    verified = sum(1 for r in results if r and r.verified)
    print("\nSummary:")
    print(f"  Completed: {completed}/{len(rows)}")
    print(f"  Verified: {verified}/{len(rows)}")


if __name__ == "__main__":
    main()
