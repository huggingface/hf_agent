"""GLUE SST-2 dataset loading and evaluation helpers."""

from datasets import load_dataset
from huggingface_hub import InferenceClient

from agent.eval.compare import ModelResult
from agent.eval.registry import EvalTask


def normalize_label(label: str) -> int:
    mapping = {
        "NEGATIVE": 0,
        "POSITIVE": 1,
        "LABEL_0": 0,
        "LABEL_1": 1,
    }
    try:
        return mapping[label.upper()]
    except KeyError as exc:
        raise ValueError(f"Unsupported label from inference API: {label}") from exc


def load_examples(
    task: EvalTask,
    split: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    selected_split = split or task.default_split
    dataset = load_dataset(task.dataset_name, task.dataset_config, split=selected_split)
    records = list(dataset)
    if limit is not None:
        records = records[:limit]
    return records


def evaluate_model(
    task: EvalTask,
    model_id: str,
    examples: list[dict],
    client: InferenceClient | None = None,
) -> ModelResult:
    client = client or InferenceClient()
    correct = 0

    for example in examples:
        response = client.text_classification(example[task.text_column], model=model_id)
        predicted = normalize_label(response[0]["label"])
        if predicted == example[task.label_column]:
            correct += 1

    accuracy = correct / len(examples) if examples else 0.0
    return ModelResult(model_id=model_id, metrics={"accuracy": accuracy})
