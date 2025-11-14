from itertools import product

from datasets import Dataset

# Task templates (excluding Very hard difficulty)
tasks = [
    {
        "task": "Evaluate models {M} on benchmarks {B}",
        "difficulty": "Easy",
        "category": "Evaluation",
        "params": ["M", "B"],
    },
    {
        "task": "Train models {M} on datasets {D} evaluating them on benchmarks {B}",
        "difficulty": "Medium",
        "category": "Training",
        "params": ["M", "D", "B"],
    },
    {
        "task": "Run an ablation for hyperparameter {P} for model {M} on dataset {D}",
        "difficulty": "Hard",
        "category": "Ablation",
        "params": ["P", "M", "D"],
    },
    {
        "task": "Generate completions with model {M} on benchmarks {B} using engine {E}",
        "difficulty": "Medium",
        "category": "Generation",
        "params": ["M", "B", "E"],
    },
    # {
    #     "task": "Merge models {M} using linear averaging to find the best result on benchmarks {B}",
    #     "difficulty": "Hard",
    #     "category": "Model Merging",
    #     "params": ["M", "B"],
    # },
    {
        "task": "Decontaminate dataset {D} against benchmarks {B}",
        "difficulty": "Hard",
        "category": "Data Processing",
        "params": ["D", "B"],
    },
    {
        "task": "Format dataset {D} for compatibility with framework {F} on task {T}",
        "difficulty": "Easy",
        "category": "Data Formatting",
        "params": ["D", "F", "T"],
    },
]

# Parameter values
values = {
    "M": [
        "Qwen/Qwen3-4B-Instruct-2507",
        "openai/gpt-oss-20b",
        "gpt-4o-mini",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        "anthropic's latest model",
    ],
    "B": [
        "Idavidrein/gpqa",
        "HuggingFaceH4/MATH-500",
        "lighteval/SimpleQA",
        "TIGER-Lab/MMLU-Pro",
    ],
    "D": [
        "HuggingFaceH4/multi_turn_if",
        "HuggingFaceH4/ultrachat_200k",
        "HuggingFaceH4/AceReason-1.1-SFT config: math_no_think",
    ],
    "E": [
        "vllm",
        "sglang",
    ],
    "F": [
        "trl",
        "axolotl",
        "verl",
    ],
    "P": [
        "learning_rate",
        "batch_size",
        "num_epochs",
    ],
    "T": [
        "SFT",
        "GRPO",
    ],
}

# Task-specific instance limits
# For each task, specify which parameter(s) to pivot on and how many instances per pivot combination
# pivot can be a single parameter string or a list of parameters
task_limits = [
    {"pivot": "B", "instances_per_pivot": 1},  # Task 0: 1 instance per
    {"pivot": ["M", "B"], "instances_per_pivot": 3},  # Task 1: 3 instances per model
    {"pivot": ["P", "D"], "instances_per_pivot": 3},  # Task 2:
    {"pivot": "E", "instances_per_pivot": 2},  # Task 3: 2 instances per benchmark
    # {"pivot": "M", "instances_per_pivot": 2},  # Task 4
    {"pivot": "D", "instances_per_pivot": 2},  # Task 5: 2 instances per dataset
    {"pivot": ["D", "F", "T"], "instances_per_pivot": 2},  # Task 6:
]


def main():
    eval_data = []

    for task_idx, task_dict in enumerate(tasks):
        template = task_dict["task"]
        params = task_dict["params"]
        limit_config = task_limits[task_idx]

        pivot_params = limit_config["pivot"]
        instances_per_pivot = limit_config["instances_per_pivot"]

        # Normalize pivot to list
        if isinstance(pivot_params, str):
            pivot_params = [pivot_params]

        # Get all combinations of pivot values
        pivot_param_values = [values[p] for p in pivot_params]
        pivot_combinations = product(*pivot_param_values)

        # For each pivot combination, generate limited instances
        for pivot_combo in pivot_combinations:
            # Get combinations of other (non-pivot) parameters
            other_params = [p for p in params if p not in pivot_params]
            other_param_values = [values[p] for p in other_params]
            other_combinations = list(product(*other_param_values))

            # Limit to specified number of instances per pivot combination
            limited_combinations = other_combinations[:instances_per_pivot]

            # Generate instances
            for combo in limited_combinations:
                # Build kwargs with pivot values and other values
                kwargs = dict(zip(pivot_params, pivot_combo))
                kwargs.update(dict(zip(other_params, combo)))

                concrete_task = template.format(**kwargs)
                eval_data.append(
                    {
                        "task": concrete_task,
                        "difficulty": task_dict["difficulty"],
                        "category": task_dict["category"],
                    }
                )

    print(f"Generated {len(eval_data)} instances from {len(tasks)} templates")

    dataset = Dataset.from_list(eval_data)
    print(f"\nDataset: {len(dataset)} rows")
    print(f"Sample: {dataset[0]['task']}")

    dataset.push_to_hub("akseljoonas/qyestions", private=False)
    print("\n✓ Pushed to akseljoonas/qyestions")


if __name__ == "__main__":
    main()
