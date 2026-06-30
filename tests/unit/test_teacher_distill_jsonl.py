from teacher_distill.jsonl import append_jsonl, read_seen_task_ids


def test_read_seen_task_ids_from_existing_jsonl(tmp_path):
    path = tmp_path / "data.jsonl"
    append_jsonl(path, {"task": {"task_id": "taco:1"}})
    append_jsonl(path, {"task": {"task_id": "apps:2"}})

    assert read_seen_task_ids(path) == {"taco:1", "apps:2"}


def test_read_seen_task_ids_missing_file(tmp_path):
    assert read_seen_task_ids(tmp_path / "missing.jsonl") == set()
