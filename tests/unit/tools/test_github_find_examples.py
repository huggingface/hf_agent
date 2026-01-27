"""
Unit tests for github_find_examples tool.
Based on real usage: {"repo": "trl", "keyword": "dpo", "org": "huggingface"}
"""

from unittest.mock import MagicMock, patch

from agent.tools.github_find_examples import (
    _get_pattern_priority,
    _score_against_example_patterns,
    _score_against_keyword,
    find_examples,
)


class TestFindDpoExamplesInTrl:
    """Test finding DPO examples in TRL repo - real workflow pattern."""

    def test_find_dpo_examples_in_trl(
        self, mock_github_token, trl_repo_tree, trl_repo_info
    ):
        """
        Real workflow: find DPO training examples in huggingface/trl.
        Should find examples/scripts/dpo.py and trl/scripts/dpo.py.
        """
        with patch("agent.tools.github_find_examples.requests.get") as mock_get:
            # Mock repo info response
            repo_response = MagicMock()
            repo_response.status_code = 200
            repo_response.json.return_value = trl_repo_info

            # Mock tree response
            tree_response = MagicMock()
            tree_response.status_code = 200
            tree_response.json.return_value = trl_repo_tree

            mock_get.side_effect = [repo_response, tree_response]

            result = find_examples(keyword="dpo", repo="trl", org="huggingface")

            # Verify no error
            assert not result.get("isError", False)
            assert result["totalResults"] > 0

            # Verify DPO files found
            formatted = result["formatted"]
            assert "examples/scripts/dpo.py" in formatted
            assert "trl/scripts/dpo.py" in formatted

    def test_fuzzy_scoring_prioritizes_scripts_directory(self):
        """Verify fuzzy scoring gives higher priority to scripts/ directory."""
        # scripts/ should score higher than random directories
        scripts_score = _score_against_example_patterns("examples/scripts/train.py")
        random_score = _score_against_example_patterns("src/utils/helper.py")

        assert scripts_score > random_score
        assert scripts_score >= 60  # Should meet minimum threshold

    def test_keyword_scoring_finds_partial_matches(self):
        """Test that keyword scoring finds partial matches correctly."""
        # "dpo" should match "dpo_trainer.py" with high score
        score = _score_against_keyword("trl/trainer/dpo_trainer.py", "dpo")
        assert score >= 80  # Should be a strong match

        # "grpo" should not match "dpo" well
        score_mismatch = _score_against_keyword("trl/trainer/dpo_trainer.py", "grpo")
        assert score_mismatch < 80


class TestRepoNotFoundSuggestsAlternatives:
    """Test error handling when repo not found."""

    def test_repo_not_found_suggests_alternatives(self, mock_github_token):
        """
        When repo 'trll' (typo) not found, suggest similar repos.
        """
        similar_repos = [
            {
                "name": "trl",
                "full_name": "huggingface/trl",
                "description": "Train transformer language models with RL",
                "stargazers_count": 10000,
                "html_url": "https://github.com/huggingface/trl",
            },
            {
                "name": "transformers",
                "full_name": "huggingface/transformers",
                "description": "Transformers library",
                "stargazers_count": 120000,
                "html_url": "https://github.com/huggingface/transformers",
            },
        ]

        with patch("agent.tools.github_find_examples.requests.get") as mock_get:
            # First call: repo info returns 404
            repo_response = MagicMock()
            repo_response.status_code = 404

            # Second call: search for similar repos
            search_response = MagicMock()
            search_response.status_code = 200
            search_response.json.return_value = {"items": similar_repos}

            mock_get.side_effect = [repo_response, search_response]

            result = find_examples(repo="trll", org="huggingface", keyword="dpo")

            # Should return error with suggestions
            assert result.get("isError", False)
            assert "not found" in result["formatted"].lower()
            assert "trl" in result["formatted"]
            assert (
                "Similar" in result["formatted"]
                or "similar" in result["formatted"].lower()
            )


class TestPatternPriority:
    """Test pattern priority scoring."""

    def test_examples_directory_has_highest_priority(self):
        """Files in examples/ directory should have highest priority."""
        examples_priority = _get_pattern_priority("examples/scripts/train.py")
        other_priority = _get_pattern_priority("src/scripts/train.py")

        # Lower tuple values = higher priority
        # examples_priority[0] should be 0 (in examples dir)
        assert examples_priority[0] == 0
        assert other_priority[0] == 1  # Not in examples dir

    def test_scripts_has_higher_priority_than_demos(self):
        """scripts/ should have higher priority than demos/."""
        scripts_priority = _get_pattern_priority("examples/scripts/train.py")
        demos_priority = _get_pattern_priority("examples/demos/demo.py")

        # scripts is index 0 in EXAMPLE_PATTERNS, demos is later
        assert scripts_priority[1] < demos_priority[1]
