import json

from teacher_distill.data_sources import (
    dedupe_tasks,
    load_apps_tasks,
    load_taco_tasks,
    load_training_tasks,
    normalize_apps_row,
    normalize_taco_row,
)


class FakeDataset:
    def __init__(self, rows):
        self.rows = list(rows)

    def __len__(self):
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def select(self, indices):
        return FakeDataset([self.rows[i] for i in indices])


def test_normalize_taco_row_keeps_train_metadata():
    row = {
        "question": "Read n and print n.",
        "starter_code": "",
        "input_output": json.dumps({"inputs": ["3\n"], "outputs": ["3\n"]}),
        "difficulty": "EASY",
        "name": "identity",
    }

    task = normalize_taco_row(row, index=7)

    assert task.task_id == "taco:7"
    assert task.source == "BAAI/TACO"
    assert task.split == "train"
    assert task.prompt == "Read n and print n."
    assert task.difficulty == "EASY"


def test_normalize_apps_row_uses_question_and_tests():
    row = {
        "question": "Return the input.",
        "starter_code": "",
        "input_output": json.dumps({"inputs": ["x\n"], "outputs": ["x\n"]}),
        "difficulty": "introductory",
    }

    task = normalize_apps_row(row, index=3)

    assert task.task_id == "apps:3"
    assert task.source == "codeparrot/apps"
    assert task.split == "train"
    assert "Return the input" in task.prompt


def test_dedupe_tasks_keeps_first_matching_prompt_and_starter():
    first = normalize_apps_row(
        {
            "question": "Return the input.",
            "starter_code": "",
            "input_output": "{}",
            "difficulty": "introductory",
        },
        index=1,
    )
    duplicate = normalize_apps_row(
        {
            "question": "Return the input.",
            "starter_code": "",
            "input_output": "{}",
            "difficulty": "introductory",
        },
        index=2,
    )

    assert [task.task_id for task in dedupe_tasks([first, duplicate])] == ["apps:1"]


def test_load_taco_tasks_applies_limit(monkeypatch):
    rows = [
        {
            "question": "Print 1.",
            "starter_code": "",
            "input_output": "{}",
            "difficulty": "easy",
        },
        {
            "question": "Print 2.",
            "starter_code": "",
            "input_output": "{}",
            "difficulty": "easy",
        },
    ]

    def fake_load_dataset(path, config, split):
        assert (path, config, split) == ("BAAI/TACO", "ALL", "train")
        return FakeDataset(rows)

    monkeypatch.setattr("teacher_distill.data_sources.load_dataset", fake_load_dataset)

    tasks = load_taco_tasks(limit=1)

    assert [task.task_id for task in tasks] == ["taco:0"]
    assert tasks[0].prompt == "Print 1."


def test_load_training_tasks_combines_sources_and_dedupes(monkeypatch):
    taco_rows = [
        {
            "question": "Print from taco.",
            "starter_code": "",
            "input_output": "{}",
            "difficulty": "easy",
        }
    ]
    apps_rows = [
        {
            "question": "Print from apps.",
            "starter_code": "",
            "input_output": "{}",
            "difficulty": "introductory",
        }
    ]

    def fake_load_dataset(path, *args, **kwargs):
        if path == "BAAI/TACO":
            return FakeDataset(taco_rows)
        if path == "codeparrot/apps":
            return FakeDataset(apps_rows)
        raise AssertionError(path)

    monkeypatch.setattr("teacher_distill.data_sources.load_dataset", fake_load_dataset)

    tasks = load_training_tasks(taco_limit=1, apps_limit=1)

    assert [task.task_id for task in tasks] == ["taco:0", "apps:0"]


def test_load_apps_tasks_applies_limit(monkeypatch):
    rows = [
        {
            "question": "Return A.",
            "starter_code": "",
            "input_output": "{}",
            "difficulty": "introductory",
        },
        {
            "question": "Return B.",
            "starter_code": "",
            "input_output": "{}",
            "difficulty": "introductory",
        },
    ]

    def fake_load_dataset(path, split):
        assert (path, split) == ("codeparrot/apps", "train")
        return FakeDataset(rows)

    monkeypatch.setattr("teacher_distill.data_sources.load_dataset", fake_load_dataset)

    tasks = load_apps_tasks(limit=1)

    assert [task.task_id for task in tasks] == ["apps:0"]
    assert tasks[0].prompt == "Return A."
