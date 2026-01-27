"""
Unit tests for plan_tool.
Based on real usage:
{"todos": [{"id": "1", "content": "Research dataset format", "status": "completed"},
           {"id": "2", "content": "Create processing script", "status": "in_progress"}]}
"""

from agent.tools.plan_tool import PlanTool, get_current_plan


class TestValidatesTodoStructure:
    """Test todo structure validation."""

    async def test_validates_missing_id(self):
        """Test error when todo missing id field."""
        tool = PlanTool()

        result = await tool.execute(
            {"todos": [{"content": "Task without id", "status": "pending"}]}
        )

        assert result.get("isError", True)
        assert "id" in result["formatted"]

    async def test_validates_missing_content(self):
        """Test error when todo missing content field."""
        tool = PlanTool()

        result = await tool.execute({"todos": [{"id": "1", "status": "pending"}]})

        assert result.get("isError", True)
        assert "content" in result["formatted"]

    async def test_validates_missing_status(self):
        """Test error when todo missing status field."""
        tool = PlanTool()

        result = await tool.execute({"todos": [{"id": "1", "content": "Task"}]})

        assert result.get("isError", True)
        assert "status" in result["formatted"]

    async def test_validates_invalid_status(self):
        """Test error when status is invalid value."""
        tool = PlanTool()

        result = await tool.execute(
            {"todos": [{"id": "1", "content": "Task", "status": "invalid_status"}]}
        )

        assert result.get("isError", True)
        assert (
            "invalid_status" in result["formatted"] or "status" in result["formatted"]
        )

    async def test_validates_non_dict_todo(self):
        """Test error when todo is not a dict."""
        tool = PlanTool()

        result = await tool.execute({"todos": ["not a dict", "another string"]})

        assert result.get("isError", True)
        assert "object" in result["formatted"]


class TestFormatsProgressOutput:
    """Test progress formatting."""

    async def test_formats_progress_output(self, sample_plan_todos):
        """
        Test formatting of 5 todos: 2 completed, 1 in_progress, 2 pending.
        Should show clear progress indication.
        """
        tool = PlanTool()

        result = await tool.execute({"todos": sample_plan_todos})

        assert not result.get("isError", False)
        assert result["totalResults"] == 5

        formatted = result["formatted"]

        # Should show all tasks
        assert "Inspect Anthropic" in formatted
        assert "Research TRL" in formatted
        assert "Create DPO training script" in formatted
        assert "Submit training job" in formatted
        assert "Verify model upload" in formatted

    async def test_updates_current_plan(self, sample_plan_todos):
        """Test that _current_plan is updated after execution."""
        tool = PlanTool()

        await tool.execute({"todos": sample_plan_todos})

        current = get_current_plan()
        assert len(current) == 5
        assert current[0]["id"] == "1"
        assert current[2]["status"] == "in_progress"

    async def test_valid_status_values_accepted(self):
        """Test that all valid status values work."""
        tool = PlanTool()

        todos = [
            {"id": "1", "content": "Pending task", "status": "pending"},
            {"id": "2", "content": "In progress task", "status": "in_progress"},
            {"id": "3", "content": "Completed task", "status": "completed"},
        ]

        result = await tool.execute({"todos": todos})

        assert not result.get("isError", False)
        assert result["totalResults"] == 3

    async def test_empty_todos_list(self):
        """Test empty todos list is valid."""
        tool = PlanTool()

        result = await tool.execute({"todos": []})

        assert not result.get("isError", False)
        assert result["totalResults"] == 0


class TestPlanPersistence:
    """Test plan state persistence."""

    async def test_new_plan_replaces_old(self):
        """Test that each execution replaces the entire plan."""
        tool = PlanTool()

        # First plan
        await tool.execute(
            {"todos": [{"id": "1", "content": "First task", "status": "pending"}]}
        )

        assert len(get_current_plan()) == 1
        assert get_current_plan()[0]["content"] == "First task"

        # Second plan replaces first
        await tool.execute(
            {
                "todos": [
                    {"id": "a", "content": "New task A", "status": "in_progress"},
                    {"id": "b", "content": "New task B", "status": "pending"},
                ]
            }
        )

        assert len(get_current_plan()) == 2
        assert get_current_plan()[0]["content"] == "New task A"
        assert get_current_plan()[1]["content"] == "New task B"
