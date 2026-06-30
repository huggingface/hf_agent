import json
from pathlib import Path

from scripts import eval_gemma4_public_benchmarks as bench


def test_build_commands_defaults_to_evalplus_only():
    commands = bench.build_commands(
        model="google/gemma-4-12B-it",
        tensor_parallel_size=4,
        run_bigcodebench=False,
    )

    assert commands == [
        [
            "evalplus.evaluate",
            "--model",
            "google/gemma-4-12B-it",
            "--dataset",
            "humaneval",
            "--backend",
            "vllm",
            "--tp",
            "4",
            "--greedy",
        ],
        [
            "evalplus.evaluate",
            "--model",
            "google/gemma-4-12B-it",
            "--dataset",
            "mbpp",
            "--backend",
            "vllm",
            "--tp",
            "4",
            "--greedy",
        ],
    ]


def test_build_commands_includes_bigcodebench_hard_when_requested():
    commands = bench.build_commands(
        model="merged-model",
        tensor_parallel_size=2,
        run_bigcodebench=True,
    )

    assert commands[-2:] == [
        [
            "bigcodebench.evaluate",
            "--model",
            "merged-model",
            "--execution",
            "gradio",
            "--split",
            "instruct",
            "--subset",
            "hard",
            "--backend",
            "vllm",
        ],
        [
            "bigcodebench.evaluate",
            "--model",
            "merged-model",
            "--execution",
            "gradio",
            "--split",
            "complete",
            "--subset",
            "hard",
            "--backend",
            "vllm",
        ],
    ]


def test_write_manifest_records_selected_benchmarks(tmp_path):
    output = tmp_path / "results"

    bench.write_manifest(
        output=output,
        model="merged-model",
        run_bigcodebench=True,
    )

    payload = json.loads(Path(output / "manifest.json").read_text(encoding="utf-8"))
    assert payload == {
        "model": "merged-model",
        "evalplus": ["humaneval", "mbpp"],
        "bigcodebench": ["instruct-hard", "complete-hard"],
    }
