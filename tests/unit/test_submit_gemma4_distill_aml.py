import pytest

from scripts import submit_gemma4_distill_aml as submit_aml


def test_build_job_config_for_build_uses_data_builder_script():
    args = submit_aml.parse_args(
        [
            "build",
            "--output",
            "${outputs.output_path}/out.jsonl",
            "--taco-limit",
            "2",
            "--apps-limit",
            "3",
            "--max-verified",
            "4",
            "--concurrency",
            "1",
        ]
    )

    config = submit_aml.build_job_config(args, hf_token="hf-test")

    assert config["display_name"] == "gemma4-claude48-build-data"
    assert config["timeout_hours"] == 12
    assert config["env_vars"]["HF_TOKEN"] == "hf-test"
    assert "scripts/build_gemma4_distill_dataset.py" in config["script"]
    assert "--max-verified" in config["script"]
    assert "4" in config["script"]


def test_build_job_config_for_eval_uses_public_benchmark_script():
    args = submit_aml.parse_args(["eval", "--model", "merged-model"])

    config = submit_aml.build_job_config(args, hf_token="")

    assert config["display_name"] == "gemma4-claude48-eval"
    assert config["timeout_hours"] == 8
    assert "scripts/eval_gemma4_public_benchmarks.py" in config["script"]
    assert "merged-model" in config["script"]


def test_resolve_azure_aml_handler_reports_missing_tool(monkeypatch):
    monkeypatch.setattr(
        submit_aml,
        "import_module",
        lambda _name: (_ for _ in ()).throw(ModuleNotFoundError("missing")),
    )

    with pytest.raises(RuntimeError, match="agent.tools.azure_aml_tool"):
        submit_aml.resolve_azure_aml_handler()
