"""
Rubric-based evaluation following the "Rubrics as Rewards" paper.

Implements RaR-Explicit: Weighted sum of individual criterion scores (Equation 1)
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import litellm
import pandas as pd
from hf_dataset_io import df_to_hub
from pydantic import BaseModel


class CriterionCheck(BaseModel):
    """Result of checking a single rubric criterion."""

    title: str
    description: str
    weight: int
    satisfied: bool
    reasoning: Optional[str] = None


class RubricEvaluation(BaseModel):
    """Complete rubric-based evaluation result."""

    criterion_checks: List[CriterionCheck]
    raw_score: float  # Unnormalized score
    normalized_score: float  # Score normalized to [0, 1]


class EvaluatedResponse(BaseModel):
    """Complete evaluated response with rubric scores."""

    discussion_title: str
    discussion_url: str
    question: str
    response: str
    reference_answer: str
    evaluation: RubricEvaluation


CRITERION_PROMPT = """You are evaluating whether a response satisfies a specific evaluation criterion.

Question: {question}

Response to evaluate: {response}

Evaluation Criterion:
{criterion_description}

Your task: Determine if the response satisfies this criterion.

Output a JSON object with:
- "satisfied": true or false
- "reasoning": Brief explanation (1-2 sentences) of why it does or doesn't satisfy the criterion

Be strict but fair. The criterion must be clearly satisfied for you to answer true."""


class RubricData(BaseModel):
    """Rubric data loaded from file."""

    title: str
    description: str
    weight: int


def load_rubrics_from_file(rubric_file: str) -> Dict[str, List[RubricData]]:
    """
    Load rubrics from JSONL file and index by question.

    Args:
        rubric_file: Path to rubric JSONL file

    Returns:
        Dictionary mapping questions to their rubrics
    """
    rubrics_by_question = {}

    with open(rubric_file, "r") as f:
        for line in f:
            entry = json.loads(line)
            question = entry["question"]

            # Parse rubric JSON string
            rubric_data = json.loads(entry["rubric"])
            rubrics = [RubricData(**r) for r in rubric_data["rubrics"]]

            rubrics_by_question[question] = rubrics

    return rubrics_by_question


def check_criterion(
    question: str, response: str, criterion: RubricData, model: str = "gpt-4o-mini"
) -> CriterionCheck:
    """
    Check if response satisfies a single criterion.

    Args:
        question: The question being answered
        response: The response to evaluate
        criterion: The rubric criterion to check
        model: LLM model for judging

    Returns:
        CriterionCheck with satisfaction result
    """
    prompt = CRITERION_PROMPT.format(
        question=question,
        response=response,
        criterion_description=criterion.description,
    )

    llm_response = litellm.completion(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are an expert evaluator for rubric-based assessment.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        response_format=CriterionCheck,
    )

    result = CriterionCheck.model_validate_json(llm_response.choices[0].message.content)

    return result


def evaluate_with_rubrics(
    question: str,
    response: str,
    reference_answer: str,
    rubrics: List[RubricData],
    model: str = "gpt-4o-mini",
) -> RubricEvaluation:
    """
    Evaluate response using RaR-Explicit method (weighted sum).

    Implements Equation 1 from paper:
    r(x, ŷ) = Σ(w_j * c_j(x, ŷ)) / Σ(w_j)

    Args:
        question: The question
        response: Response to evaluate
        reference_answer: Reference answer (not directly used, but available)
        rubrics: List of rubric criteria
        model: LLM model for judging

    Returns:
        RubricEvaluation with normalized score
    """
    # Check each criterion independently
    checks = []
    for rubric in rubrics:
        check = check_criterion(question, response, rubric, model)
        checks.append(check)

    # Calculate weighted score (Equation 1)
    # Only positive weights contribute to denominator
    positive_weights = sum(abs(r.weight) for r in rubrics if r.weight > 0)

    raw_score = 0.0
    for check in checks:
        if check.satisfied:
            raw_score += check.weight

    # Normalize to [0, 1]
    normalized_score = raw_score / positive_weights if positive_weights > 0 else 0.0
    # Clip to [0, 1] in case pitfalls make it negative
    normalized_score = max(0.0, min(1.0, normalized_score))

    return RubricEvaluation(
        raw_score=raw_score,
        normalized_score=normalized_score,
        criterion_checks=checks,
    )


def evaluate_dataset_with_rubrics(
    input_file: str,
    rubric_file: str,
    ground_truth_file: str,
    output_file: str = "rubric_evaluation_results.jsonl",
    model: str = "gpt-4o-mini",
    max_concurrent: int = 10,
    limit: Optional[int] = None,
    push_to_hub: Optional[str] = None,
) -> None:
    """
    Evaluate all responses using rubric-based assessment.

    Args:
        input_file: Path to JSONL with responses to evaluate
        rubric_file: Path to JSONL with rubrics (output from generate_rubrics.py)
        ground_truth_file: Path to JSONL with ground truth answers
        output_file: Path to output JSONL file
        model: LLM model for judging
        max_concurrent: Maximum concurrent evaluations
        limit: Optional limit on number of examples
        push_to_hub: Optional HuggingFace dataset spec (e.g., username/dataset@evaluations)
    """
    # Load data
    print(f"Loading responses from {input_file}...")
    with open(input_file, "r") as f:
        responses = [json.loads(line) for line in f]

    print(f"Loading rubrics from {rubric_file}...")
    rubrics_by_question = load_rubrics_from_file(rubric_file)

    print(f"Loading ground truth from {ground_truth_file}...")
    with open(ground_truth_file, "r") as f:
        ground_truths = [json.loads(line) for line in f]

    if limit:
        responses = responses[:limit]
        ground_truths = ground_truths[:limit]

    print(f"Loaded {len(responses)} responses to evaluate")
    print(f"Judge model: {model}")

    # Match responses with rubrics and ground truth
    evaluation_tasks = []
    for response_data, gt_data in zip(responses, ground_truths):
        question = gt_data["question"]

        # Find rubrics for this question
        rubrics = rubrics_by_question.get(question)
        if not rubrics:
            print(f"Warning: No rubrics found for question: {question[:50]}...")
            continue

        evaluation_tasks.append(
            {
                "question": question,
                "response": response_data["solution"],
                "reference_answer": gt_data["solution"],
                "rubrics": rubrics,
                "metadata": {
                    "discussion_title": response_data.get("discussion_title", ""),
                    "discussion_url": response_data.get("discussion_url", ""),
                },
            }
        )

    print(
        f"Running {len(evaluation_tasks)} evaluations with {max_concurrent} parallel workers..."
    )

    # Run evaluations in parallel
    results = []
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        # Submit all tasks
        future_to_idx = {}
        for idx, task in enumerate(evaluation_tasks):
            future = executor.submit(
                evaluate_with_rubrics,
                question=task["question"],
                response=task["response"],
                reference_answer=task["reference_answer"],
                rubrics=task["rubrics"],
                model=model,
            )
            future_to_idx[future] = idx

        # Collect results in order
        results = [None] * len(evaluation_tasks)
        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()
            completed += 1
            print(f"Completed: {completed}/{len(evaluation_tasks)}", end="\r")

    print()  # New line after progress

    # Combine results with metadata
    output_data = []
    total_score = 0.0

    for task, evaluation in zip(evaluation_tasks, results):
        evaluated_response = EvaluatedResponse(
            discussion_title=task["metadata"]["discussion_title"],
            discussion_url=task["metadata"]["discussion_url"],
            question=task["question"],
            response=task["response"],
            reference_answer=task["reference_answer"],
            evaluation=evaluation,
        )
        output_data.append(evaluated_response)
        total_score += evaluation.normalized_score

    # Convert to DataFrame for HuggingFace upload
    results_df = pd.DataFrame([entry.model_dump() for entry in output_data])

    # Upload to HuggingFace if specified (before saving JSONL)
    if push_to_hub:
        print(f"\nUploading to HuggingFace: {push_to_hub}")
        upload_success = df_to_hub(
            df=results_df,
            dataset_spec=push_to_hub,
            split="test",
            private=False,
        )
        if not upload_success:
            print("Warning: HuggingFace upload failed, but continuing to save JSONL...")

    # Write results to JSONL file
    print(f"\nWriting results to {output_file}...")
    with open(output_file, "w") as f:
        for entry in output_data:
            f.write(entry.model_dump_json() + "\n")

    # Print summary
    avg_score = total_score / len(output_data) if output_data else 0.0

    print("\n" + "=" * 60)
    print("RUBRIC-BASED EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total examples: {len(output_data)}")
    print(f"Judge model: {model}")
    print(f"Average normalized score: {avg_score:.3f}")
    print(f"Average percentage: {avg_score * 100:.1f}%")

    # Per-criterion statistics
    total_satisfied = sum(
        sum(1 for check in eval.evaluation.criterion_checks if check.satisfied)
        for eval in output_data
    )
    total_criteria = sum(len(eval.evaluation.criterion_checks) for eval in output_data)
    satisfaction_rate = total_satisfied / total_criteria if total_criteria > 0 else 0.0
    print(f"Criteria satisfaction rate: {satisfaction_rate * 100:.1f}%")

    if push_to_hub and upload_success:
        print(f"Pushed to: {push_to_hub}")

    print("=" * 60)


if __name__ == "__main__":
    evaluate_dataset_with_rubrics(
        input_file="eval/qa_pairs_accepted.jsonl",
        rubric_file="eval/qa_rubrics.jsonl",
        ground_truth_file="eval/qa_pairs_accepted.jsonl",
        output_file="rubric_evaluation.jsonl",
        model="gpt-4o-mini",
        max_concurrent=10,
        limit=30,  # Set to None to evaluate all
        push_to_hub="akseljoonas/hf-agent-benchmark@ground-truth",  # Set to "username/dataset@evaluations" to upload
    )
