import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict

import litellm
from models import (
    Correctness,
    EvaluatedQuestionAndSolution,
    JudgementResult,
    QuestionAndSolution,
)

# from: https://github.com/centerforaisafety/hle/blob/7b6be5aad6f9b43af3857de7867f3b52f6e4acb3/hle_eval/run_judge_results.py#L16-L33
GRADER_TEMPLATE = """
Judge whether the following [response] to [question] is correct or not based on if the [response] includes the precise and unambiguous [correct_answer] below.

[question]: {question}

[response]: {response}

Your judgement must be in the format and criteria specified below:

extracted_final_answer: The final exact answer extracted from the [response]. Put the extracted answer as 'None' if there is no exact, final answer to extract from the response.

[correct_answer]: {correct_answer}

reasoning: Explain why the [correct_answer] is included or not included in the extracted_final_answer, focusing only on if there are meaningful differences between [correct_answer] and the extracted_final_answer. Do not comment on any background to the problem, do not attempt to solve the problem, do not argue for any answer different than [correct_answer], focus only on whether the answers match.

correct: Answer 'yes' if [correct_answer] is included in the extracted_final_answer given above, or is within a small margin of error for numerical problems. Answer 'no' otherwise, i.e. if there if there is any inconsistency, ambiguity, non-equivalency, or if the extracted answer is incorrect.


confidence: The extracted confidence score between 0|%| and 100|%| from [response]. Put 100 if there is no confidence score available.
""".strip()

CHOICE_STRINGS = ["yes", "no"]


def evaluate_single_response(
    question: str,
    response: str,
    correct_answer: str,
    model: str = "gpt-4o-mini",
) -> Dict[str, Any]:
    """
    Evaluate a single response against the ground truth using LLM as judge.

    Args:
        question: The question being answered
        response: The response to evaluate
        correct_answer: The ground truth answer
        model: The LLM model to use for judging

    Returns:
        Dictionary containing the judgement result and metadata
    """
    prompt = GRADER_TEMPLATE.format(
        question=question, response=response, correct_answer=correct_answer
    )

    # Use litellm with structured output
    llm_response = litellm.completion(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are an expert judge evaluating answers for accuracy and equivalence.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format=JudgementResult,
        temperature=0.0,
    )

    # Parse structured output
    result: JudgementResult = JudgementResult.model_validate_json(
        llm_response.choices[0].message.content
    )
    return result


def evaluate_dataset(
    input_file: str,
    eval_file: str,
    output_file: str = "evaluation_results.jsonl",
    model: str = "gpt-4o-mini",
    max_concurrent: int = 30,
    limit: int = None,
) -> None:
    """
    Evaluate all QA pairs in the input file using LLM as judge.

    Args:
        input_file: Path to input JSONL file with QA pairs
        output_file: Path to output JSONL file for results
        model: The LLM model to use for judging
        max_concurrent: Maximum number of concurrent threads
        limit: Optional limit on number of examples to evaluate
    """
    # Load input data as proper models
    to_evaluate = [
        QuestionAndSolution.model_validate_json(line) for line in open(input_file, "r")
    ]
    if limit:
        to_evaluate = to_evaluate[:limit]

    print(f"Loaded {len(to_evaluate)} QA pairs to evaluate")

    # Load ground truth dataset
    print(f"Loading ground truth from {eval_file}...")
    with open(eval_file, "r") as f:
        ground_truths = [QuestionAndSolution.model_validate_json(line) for line in f]

    print(f"Loaded {len(ground_truths)} ground truths")

    # Run evaluations in parallel using ThreadPoolExecutor
    print(f"Running evaluations with {max_concurrent} parallel workers...")
    results = []

    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        # Submit all tasks
        future_to_idx = {}
        for idx, (qa_pair, ground_truth) in enumerate(zip(to_evaluate, ground_truths)):
            question = ground_truth.question
            ground_truth_answer = ground_truth.solution
            response = qa_pair.solution

            future = executor.submit(
                evaluate_single_response,
                response=response,
                question=question,
                correct_answer=ground_truth_answer,
                model=model,
            )
            future_to_idx[future] = idx

        # Collect results in order
        results = [None] * len(to_evaluate)
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()

    # Combine results with original data using proper models
    output_data: list[EvaluatedQuestionAndSolution] = []
    correct_count = 0
    error_count = 0

    for qa_pair, result in zip(to_evaluate, results):
        print(result.model_dump_json())

        # Create proper evaluated model
        output_entry = EvaluatedQuestionAndSolution(
            **qa_pair.model_dump(),
            evaluation=result
        )
        output_data.append(output_entry)

        if result.correct == Correctness.yes:
            correct_count += 1
        else:
            error_count += 1

    # Write results using proper model serialization
    print(f"Writing results to {output_file}...")
    with open(output_file, "w") as f:
        for entry in output_data:
            f.write(entry.model_dump_json() + "\n")

    # Print summary
    total = len(to_evaluate)
    success_rate = (total - error_count) / total * 100 if total > 0 else 0
    accuracy = correct_count / total * 100 if total > 0 else 0

    print("\n" + "=" * 50)
    print("EVALUATION SUMMARY")
    print("=" * 50)
    print(f"Total examples: {total}")
    print(f"Successful evaluations: {total - error_count}")
    print(f"Errors: {error_count}")
    print(f"Success rate: {success_rate:.2f}%")
    print(f"Correct answers: {correct_count}")
    print(f"Accuracy: {accuracy:.2f}%")
    print("=" * 50)


#


def main():
    """Main entry point for the evaluation script"""
    evaluate_dataset(
        input_file="eval/qa_pairs.jsonl",
        eval_file="eval/qa_pairs.jsonl",
        output_file="evaluation_results.jsonl",
        model="gpt-4o-mini",
        max_concurrent=30,
        limit=10,  # Set to None to evaluate all, or a number to limit
    )


if __name__ == "__main__":
    main()
