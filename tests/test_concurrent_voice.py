"""
Test concurrent voice calls to verify DB session threading is safe.

This test verifies that the MCP server properly handles concurrent
voice requests without DB session conflicts.
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConcurrentVoiceCalls:
    """Test concurrent voice call handling."""

    @pytest.mark.asyncio
    async def test_concurrent_list_courses_calls(self):
        """Test that multiple concurrent list_courses calls work without DB errors."""
        from mcp_server.server import _invoke_tool_handler_in_thread
        from mcp_server.tools import courses

        # Run multiple concurrent calls
        tasks = []
        for _ in range(5):
            task = asyncio.to_thread(
                _invoke_tool_handler_in_thread,
                courses.list_courses,
                {"skip": 0, "limit": 10}
            )
            tasks.append(task)

        # All should complete without errors
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check no exceptions occurred
        for result in results:
            assert not isinstance(result, Exception), f"Concurrent call failed: {result}"

    @pytest.mark.asyncio
    async def test_concurrent_mixed_read_calls(self):
        """Test concurrent calls to different read tools."""
        from mcp_server.server import _invoke_tool_handler_in_thread, TOOL_REGISTRY, build_tool_registry

        # Ensure registry is built
        if not TOOL_REGISTRY:
            build_tool_registry()

        # Define test calls
        read_calls = [
            ('list_courses', {"skip": 0, "limit": 5}),
            ('get_users', {}),
            ('get_available_pages', {}),
        ]

        tasks = []
        for tool_name, args in read_calls:
            tool_info = TOOL_REGISTRY.get(tool_name)
            if tool_info:
                task = asyncio.to_thread(
                    _invoke_tool_handler_in_thread,
                    tool_info['handler'],
                    args
                )
                tasks.append(task)

        # All should complete without errors
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check no DB session errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Allow "not found" errors, but not session errors
                error_msg = str(result).lower()
                assert 'session' not in error_msg or 'not found' in error_msg, \
                    f"Possible DB session error in call {i}: {result}"

    @pytest.mark.asyncio
    async def test_context_store_concurrent_access(self):
        """Test concurrent access to context store."""
        from api.services.context_store import ContextStore

        # Skip if Redis not available
        try:
            store = ContextStore()
        except Exception:
            pytest.skip("Redis not available")
            return

        user_ids = [1, 2, 3, 4, 5]

        # Concurrent writes
        async def update_context(user_id):
            store.update_context(user_id, active_course_id=user_id * 10)
            return store.get_context(user_id)

        tasks = [asyncio.to_thread(update_context, uid) for uid in user_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        for i, result in enumerate(results):
            assert not isinstance(result, Exception), f"Context store failed for user {user_ids[i]}: {result}"

    @pytest.mark.asyncio
    async def test_action_history_concurrent(self):
        """Test concurrent action recording."""
        from api.services.context_store import ContextStore

        # Skip if Redis not available
        try:
            store = ContextStore()
        except Exception:
            pytest.skip("Redis not available")
            return

        user_id = 999  # Test user

        # Clear any existing history
        store.clear_context(user_id)

        # Concurrent action recording
        async def record_action(action_num):
            return store.record_action(
                user_id,
                action_type=f"test_action_{action_num}",
                action_data={"num": action_num},
                undo_data={"revert_num": action_num},
            )

        tasks = [asyncio.to_thread(record_action, i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        for result in results:
            assert not isinstance(result, Exception), f"Action recording failed: {result}"

        # Verify history is intact
        history = store.get_action_history(user_id, limit=10)
        assert len(history) == 5, f"Expected 5 actions, got {len(history)}"

        # Cleanup
        store.clear_context(user_id)


class TestVoiceConverseEndpoint:
    """Test the voice converse endpoint."""

    @pytest.mark.asyncio
    async def test_navigation_intent_detection(self):
        """Test that navigation intents are detected quickly."""
        from api.api.voice_converse_router import detect_navigation_intent

        test_cases = [
            ("go to courses", "/courses"),
            ("show me the forum", "/forum"),
            ("open sessions", "/sessions"),
            ("navigate to reports", "/reports"),
            ("open the console", "/console"),
        ]

        for transcript, expected_path in test_cases:
            result = detect_navigation_intent(transcript)
            assert result == expected_path, f"Failed for '{transcript}': expected {expected_path}, got {result}"

    @pytest.mark.asyncio
    async def test_action_intent_detection(self):
        """Test that action intents are detected correctly."""
        from api.api.voice_converse_router import detect_action_intent

        test_cases = [
            ("show my courses", "list_courses"),
            ("create a new course", "create_course"),
            ("start the copilot", "start_copilot"),
            ("create a poll", "create_poll"),
            ("go live", "go_live"),
            ("undo that", "undo_action"),
            ("what's my context", "get_context"),
            ("clear my context", "clear_context"),
        ]

        for transcript, expected_action in test_cases:
            result = detect_action_intent(transcript)
            assert result == expected_action, f"Failed for '{transcript}': expected {expected_action}, got {result}"

    @pytest.mark.asyncio
    async def test_ui_target_extraction(self):
        """Test UI target extraction from voice commands."""
        from api.api.voice_converse_router import extract_ui_target

        test_cases = [
            ("select course Machine Learning", "ui_select_course", "select-course"),
            ("choose the first session", "ui_select_session", "select-session"),
            ("go to summary tab", "ui_switch_tab", "tab-summary"),
            ("click generate report", "ui_click_button", "generate-report"),
        ]

        for transcript, action, expected_target in test_cases:
            result = extract_ui_target(transcript, action)
            assert result.get("target") == expected_target, \
                f"Failed for '{transcript}': expected target {expected_target}, got {result.get('target')}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
