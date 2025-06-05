# test/test_leaderboard_manager.py

import pytest
import json
import os
import datetime
from core.leaderboard_manager import LeaderboardManager
import settings # To get LEADERBOARD_FILE and LEADERBOARD_MAX_ENTRIES

# --- Pytest Fixture for LeaderboardManager ---
@pytest.fixture
def leaderboard_env(tmp_path, mocker):
    """
    Sets up a temporary environment for LeaderboardManager tests.
    - Creates a temporary directory for the leaderboard file.
    - Allows mocking of settings for LEADERBOARD_FILE and LEADERBOARD_MAX_ENTRIES.
    """
    # Create a temporary leaderboard file path
    temp_leaderboard_file = tmp_path / "test_leaderboard.json"
    
    # Mock settings to use this temporary file and a specific max_entries for testing
    mocker.patch('settings.LEADERBOARD_FILE', str(temp_leaderboard_file))
    mocker.patch('settings.LEADERBOARD_MAX_ENTRIES', 3) # Use a small number for easier testing

    # Ensure the 'data' subdirectory (or equivalent based on mocked path) exists if needed by os.makedirs
    # If LEADERBOARD_FILE is just a filename in tmp_path, its dirname is tmp_path itself.
    # If it's tmp_path / "data" / "file.json", then tmp_path / "data" needs to exist.
    # For simplicity with tmp_path, the file will be directly in tmp_path.
    # os.makedirs(os.path.dirname(str(temp_leaderboard_file)), exist_ok=True) # tmp_path handles this

    yield str(temp_leaderboard_file), settings.LEADERBOARD_MAX_ENTRIES

    # Clean up: os.remove(temp_leaderboard_file) is usually handled by tmp_path if the file exists.


class TestLeaderboardManager:
    """Test suite for the LeaderboardManager class."""

    def test_load_scores_valid_file(self, leaderboard_env, mocker):
        """Test loading scores from a valid, existing JSON file."""
        file_path, max_entries = leaderboard_env
        
        sample_scores = [
            {"name": "Alice", "score": 100, "ai_defeated": "original", "date": "2023-01-01 10:00"},
            {"name": "Bob", "score": 200, "ai_defeated": "aggressive", "date": "2023-01-02 11:00"}
        ]
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(sample_scores, f)

        lb_manager = LeaderboardManager()
        
        # Scores should be sorted by score descending after loading
        expected_sorted_scores = sorted(sample_scores, key=lambda x: x.get('score', 0), reverse=True)
        assert lb_manager.scores == expected_sorted_scores, "Scores not loaded or sorted correctly."

    def test_load_scores_empty_or_invalid_json_file(self, leaderboard_env, mocker):
        """Test loading scores from an empty or malformed JSON file."""
        file_path, max_entries = leaderboard_env

        # Test with an empty file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("") 
        lb_manager_empty = LeaderboardManager()
        assert lb_manager_empty.scores == [], "Scores should be empty for an empty file."
        os.remove(file_path) # Clean up

        # Test with a malformed JSON file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("{,") # Invalid JSON
        lb_manager_invalid = LeaderboardManager()
        assert lb_manager_invalid.scores == [], "Scores should be empty for a malformed JSON file."
    
    def test_add_score_new_high_score(self, leaderboard_env, mocker):
        """Test adding a new score that makes it onto the leaderboard."""
        file_path, max_entries = leaderboard_env # max_entries is 3
        
        lb_manager = LeaderboardManager() # Starts with empty scores
        
        # Mock datetime to control the timestamp
        mock_now = datetime.datetime(2024, 6, 1, 12, 0, 0)
        mocker.patch('datetime.datetime', mocker.Mock(now=mocker.Mock(return_value=mock_now)))

        lb_manager.add_score("Charlie", 150, "conservative")
        assert len(lb_manager.scores) == 1
        assert lb_manager.scores[0]["name"] == "Charlie"
        assert lb_manager.scores[0]["score"] == 150
        assert lb_manager.scores[0]["date"] == "2024-06-01 12:00"

        # Add another score, higher
        lb_manager.add_score("David", 250, "item_focused")
        assert len(lb_manager.scores) == 2
        assert lb_manager.scores[0]["name"] == "David" # David should be first
        assert lb_manager.scores[1]["name"] == "Charlie"

        # Add a third score, should also fit
        lb_manager.add_score("Eve", 50, "original")
        assert len(lb_manager.scores) == 3
        assert lb_manager.scores[0]["name"] == "David"
        assert lb_manager.scores[1]["name"] == "Charlie"
        assert lb_manager.scores[2]["name"] == "Eve"

        # Add a score that pushes out the lowest (Eve)
        lb_manager.add_score("Frank", 100, "aggressive")
        assert len(lb_manager.scores) == 3 # Still max_entries
        assert lb_manager.scores[0]["name"] == "David"    # 250
        assert lb_manager.scores[1]["name"] == "Charlie"  # 150
        assert lb_manager.scores[2]["name"] == "Frank"    # 100 (Eve 50 is pushed out)
        assert not any(s["name"] == "Eve" for s in lb_manager.scores)

    def test_add_score_not_high_enough(self, leaderboard_env, mocker):
        """Test adding a score that is too low to make it onto a full leaderboard."""
        file_path, max_entries = leaderboard_env # max_entries is 3
        
        initial_scores = [
            {"name": "PlayerA", "score": 300, "ai_defeated": "original", "date": "2023-01-01 10:00"},
            {"name": "PlayerB", "score": 200, "ai_defeated": "original", "date": "2023-01-01 11:00"},
            {"name": "PlayerC", "score": 100, "ai_defeated": "original", "date": "2023-01-01 12:00"}
        ]
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(initial_scores, f)
        
        lb_manager = LeaderboardManager() # Loads the initial_scores
        assert len(lb_manager.scores) == 3

        lb_manager.add_score("LowScorer", 50, "item_focused")
        
        assert len(lb_manager.scores) == 3 # Length should not change
        assert lb_manager.scores[0]["name"] == "PlayerA"
        assert lb_manager.scores[1]["name"] == "PlayerB"
        assert lb_manager.scores[2]["name"] == "PlayerC" # LowScorer (50) should not be on the list
        assert not any(s["name"] == "LowScorer" for s in lb_manager.scores)

    def test_is_score_high_enough(self, leaderboard_env, mocker):
        """Test the is_score_high_enough method."""
        file_path, max_entries = leaderboard_env # max_entries is 3
        lb_manager = LeaderboardManager()

        # Leaderboard is empty
        assert lb_manager.is_score_high_enough(10) is True

        # Add some scores
        lb_manager.add_score("A", 100, "original")
        lb_manager.add_score("B", 200, "original")
        # Leaderboard: [B:200, A:100], still space
        assert lb_manager.is_score_high_enough(50) is True # Can fit
        assert lb_manager.is_score_high_enough(150) is True
        assert lb_manager.is_score_high_enough(250) is True

        lb_manager.add_score("C", 300, "original")
        # Leaderboard: [C:300, B:200, A:100], full
        assert lb_manager.is_score_high_enough(50) is False # Lower than lowest (A:100)
        assert lb_manager.is_score_high_enough(100) is False # Equal to lowest
        assert lb_manager.is_score_high_enough(101) is True # Higher than lowest
        assert lb_manager.is_score_high_enough(350) is True

   