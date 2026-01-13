"""
Unit tests for github_list_repos tool.
"""

from unittest.mock import MagicMock, patch

from agent.tools.github_list_repos import list_repos


class TestListReposSorting:
    """Test repository listing and sorting."""

    def test_list_huggingface_repos_sorted_by_stars(self, mock_github_token):
        """
        Test listing repos with sorting by stars.
        Should handle client-side sorting for unsupported sort fields.
        """
        # Unsorted response from API
        repos_data = [
            {
                "name": "datasets",
                "full_name": "huggingface/datasets",
                "description": "Datasets library",
                "stargazers_count": 18000,
                "forks_count": 2500,
                "html_url": "https://github.com/huggingface/datasets",
            },
            {
                "name": "transformers",
                "full_name": "huggingface/transformers",
                "description": "Transformers library",
                "stargazers_count": 120000,
                "forks_count": 25000,
                "html_url": "https://github.com/huggingface/transformers",
            },
            {
                "name": "trl",
                "full_name": "huggingface/trl",
                "description": "TRL library",
                "stargazers_count": 10000,
                "forks_count": 1500,
                "html_url": "https://github.com/huggingface/trl",
            },
        ]

        with patch("agent.tools.github_list_repos.requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = repos_data
            mock_get.return_value = response

            result = list_repos(owner="huggingface", sort="stars")

            # Verify no error
            assert not result.get("isError", False)
            assert result["totalResults"] == 3

            # Verify transformers (highest stars) appears first
            formatted = result["formatted"]
            transformers_pos = formatted.find("transformers")
            datasets_pos = formatted.find("datasets")
            trl_pos = formatted.find("trl")

            assert transformers_pos < datasets_pos < trl_pos

    def test_list_repos_sorted_by_forks(self, mock_github_token):
        """Test sorting by forks."""
        repos_data = [
            {
                "name": "small-repo",
                "full_name": "org/small-repo",
                "stargazers_count": 100,
                "forks_count": 10,
                "html_url": "https://github.com/org/small-repo",
            },
            {
                "name": "big-repo",
                "full_name": "org/big-repo",
                "stargazers_count": 50,
                "forks_count": 500,
                "html_url": "https://github.com/org/big-repo",
            },
        ]

        with patch("agent.tools.github_list_repos.requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = repos_data
            mock_get.return_value = response

            result = list_repos(owner="org", sort="forks")

            assert not result.get("isError", False)
            formatted = result["formatted"]

            # big-repo has more forks, should appear first
            big_pos = formatted.find("big-repo")
            small_pos = formatted.find("small-repo")
            assert big_pos < small_pos


class TestErrorHandling:
    """Test error handling."""

    def test_missing_github_token_returns_error(self):
        """Test missing GITHUB_TOKEN."""
        with patch.dict("os.environ", {}, clear=True):
            result = list_repos(owner="huggingface")

            assert result.get("isError", True)
            assert "GITHUB_TOKEN" in result["formatted"]

    def test_api_error_handled_gracefully(self, mock_github_token):
        """Test API error handling."""
        with patch("agent.tools.github_list_repos.requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 403
            response.json.return_value = {"message": "Rate limit exceeded"}
            mock_get.return_value = response

            result = list_repos(owner="huggingface")

            assert result.get("isError", True)
            assert (
                "rate limit" in result["formatted"].lower()
                or "403" in result["formatted"]
            )
