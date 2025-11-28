"""
Rubric-based evaluation following the "Rubrics as Rewards" paper.

Implements RaR-Explicit: Weighted sum of individual criterion scores (Equation 1)
"""

from typing import List, Optional

import litellm
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
    rubrics: List[RubricData],
    model: str = "gpt-5-nano",
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
