"""
Unit tests for server_plugin_stack.py async coroutine stack functionality.
"""

import asyncio
import unittest
from unittest.mock import MagicMock

from flight_profiler.plugins.stack.server_plugin_stack import StackServerPlugin
from flight_profiler.utils.render_util import (
    COLOR_FAINT,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_WHITE_255,
    COLOR_YELLOW,
)


class MockServerQueue:
    """Mock ServerQueue for testing."""

    def __init__(self):
        self.messages = []

    async def output_msg(self, msg):
        self.messages.append(msg)


class TestStackServerPluginFiltering(unittest.TestCase):
    """Test cases for flight_profiler filtering logic."""

    def setUp(self):
        self.out_q = MockServerQueue()
        self.plugin = StackServerPlugin("stack", self.out_q)

    def test_is_flight_profiler_thread_with_hyphen(self):
        """Test thread name filtering with 'flight-profiler' pattern."""
        self.assertTrue(self.plugin._is_flight_profiler_thread("flight-profiler-worker-0"))
        self.assertTrue(self.plugin._is_flight_profiler_thread("flight-profiler-injector"))
        self.assertTrue(self.plugin._is_flight_profiler_thread("Flight-Profiler-Worker"))

    def test_is_flight_profiler_thread_with_underscore(self):
        """Test thread name filtering with 'flight_profiler' pattern."""
        self.assertTrue(self.plugin._is_flight_profiler_thread("flight_profiler_worker"))
        self.assertTrue(self.plugin._is_flight_profiler_thread("Flight_Profiler_Task"))

    def test_is_flight_profiler_thread_negative(self):
        """Test that non-flight_profiler threads are not filtered."""
        self.assertFalse(self.plugin._is_flight_profiler_thread("MainThread"))
        self.assertFalse(self.plugin._is_flight_profiler_thread("AsyncEventLoop"))
        self.assertFalse(self.plugin._is_flight_profiler_thread("Worker-1"))
        self.assertFalse(self.plugin._is_flight_profiler_thread("Thread-2"))

    def test_is_flight_profiler_thread_empty_or_none(self):
        """Test handling of empty or None thread names."""
        self.assertFalse(self.plugin._is_flight_profiler_thread(""))
        self.assertFalse(self.plugin._is_flight_profiler_thread(None))


class TestStackServerPluginStateColor(unittest.TestCase):
    """Test cases for state color mapping."""

    def setUp(self):
        self.out_q = MockServerQueue()
        self.plugin = StackServerPlugin("stack", self.out_q)

    def test_state_color_pending(self):
        """Test PENDING state returns yellow color."""
        self.assertEqual(self.plugin._get_state_color("PENDING"), COLOR_YELLOW)

    def test_state_color_waiting(self):
        """Test WAITING state returns green color."""
        self.assertEqual(self.plugin._get_state_color("WAITING"), COLOR_GREEN)

    def test_state_color_finished(self):
        """Test FINISHED state returns green color."""
        self.assertEqual(self.plugin._get_state_color("FINISHED"), COLOR_GREEN)

    def test_state_color_cancelled(self):
        """Test CANCELLED state returns faint color."""
        self.assertEqual(self.plugin._get_state_color("CANCELLED"), COLOR_FAINT)

    def test_state_color_failed(self):
        """Test FAILED state returns red color."""
        self.assertEqual(self.plugin._get_state_color("FAILED"), COLOR_RED)

    def test_state_color_unknown(self):
        """Test UNKNOWN state returns faint color."""
        self.assertEqual(self.plugin._get_state_color("UNKNOWN"), COLOR_FAINT)

    def test_state_color_unrecognized(self):
        """Test unrecognized state returns default white color."""
        self.assertEqual(self.plugin._get_state_color("SOME_OTHER_STATE"), COLOR_WHITE_255)


class TestStackServerPluginTaskInfo(unittest.TestCase):
    """Test cases for task information extraction."""

    def setUp(self):
        self.out_q = MockServerQueue()
        self.plugin = StackServerPlugin("stack", self.out_q)

    def test_get_task_name_with_get_name(self):
        """Test getting task name using get_name() method."""
        mock_task = MagicMock()
        mock_task.get_name.return_value = "TestTask"
        self.assertEqual(self.plugin._get_task_name(mock_task), "TestTask")

    def test_get_task_name_without_get_name(self):
        """Test getting task name when get_name() is not available."""
        mock_task = MagicMock(spec=[])  # No get_name method
        result = self.plugin._get_task_name(mock_task)
        self.assertIn("MagicMock", result)

    def test_get_task_name_with_exception(self):
        """Test handling exception when getting task name."""
        mock_task = MagicMock()
        mock_task.get_name.side_effect = Exception("Test error")
        self.assertEqual(self.plugin._get_task_name(mock_task), "<unknown>")

    def test_get_task_state_done_cancelled(self):
        """Test getting state for cancelled task."""
        mock_task = MagicMock()
        mock_task.done.return_value = True
        mock_task.cancelled.return_value = True
        self.assertEqual(self.plugin._get_task_state(mock_task), "CANCELLED")

    def test_get_task_state_done_failed(self):
        """Test getting state for failed task."""
        mock_task = MagicMock()
        mock_task.done.return_value = True
        mock_task.cancelled.return_value = False
        mock_task.exception.return_value = Exception("Test")
        self.assertEqual(self.plugin._get_task_state(mock_task), "FAILED")

    def test_get_task_state_done_finished(self):
        """Test getting state for finished task."""
        mock_task = MagicMock()
        mock_task.done.return_value = True
        mock_task.cancelled.return_value = False
        mock_task.exception.return_value = None
        self.assertEqual(self.plugin._get_task_state(mock_task), "FINISHED")

    def test_get_task_state_waiting(self):
        """Test getting state for waiting task."""
        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_task._fut_waiter = MagicMock()  # Has a waiter
        self.assertEqual(self.plugin._get_task_state(mock_task), "WAITING")

    def test_get_task_state_pending(self):
        """Test getting state for pending task."""
        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_task._fut_waiter = None  # No waiter
        self.assertEqual(self.plugin._get_task_state(mock_task), "PENDING")


class TestStackServerPluginCoroRepr(unittest.TestCase):
    """Test cases for coroutine representation."""

    def setUp(self):
        self.out_q = MockServerQueue()
        self.plugin = StackServerPlugin("stack", self.out_q)

    def test_get_coro_repr_with_qualname(self):
        """Test getting coroutine repr with __qualname__."""
        mock_coro = MagicMock()
        mock_coro.__qualname__ = "MyClass.my_coroutine"
        mock_task = MagicMock()
        mock_task.get_coro.return_value = mock_coro
        self.assertEqual(self.plugin._get_coro_repr(mock_task), "MyClass.my_coroutine")

    def test_get_coro_repr_with_name(self):
        """Test getting coroutine repr with __name__ when __qualname__ is None."""
        mock_coro = MagicMock(spec=["__name__"])
        mock_coro.__name__ = "my_coroutine"
        mock_task = MagicMock()
        mock_task.get_coro.return_value = mock_coro
        result = self.plugin._get_coro_repr(mock_task)
        self.assertEqual(result, "my_coroutine")

    def test_get_coro_repr_no_coro(self):
        """Test getting coroutine repr when task has no coroutine."""
        mock_task = MagicMock()
        mock_task.get_coro.return_value = None
        self.assertEqual(self.plugin._get_coro_repr(mock_task), "<no coroutine>")


class TestStackServerPluginCoroFrames(unittest.TestCase):
    """Test cases for coroutine frame collection (cr_await chain)."""

    def setUp(self):
        self.out_q = MockServerQueue()
        self.plugin = StackServerPlugin("stack", self.out_q)

    def test_collect_coro_frames_single_frame(self):
        """Test collecting frames from a single coroutine."""
        # Create mock frame
        mock_code = MagicMock()
        mock_code.co_filename = "/path/to/test.py"
        mock_code.co_name = "test_func"

        mock_frame = MagicMock()
        mock_frame.f_code = mock_code
        mock_frame.f_lineno = 42

        # Create mock coroutine
        mock_coro = MagicMock()
        mock_coro.cr_frame = mock_frame
        mock_coro.cr_await = None

        stack_info = []
        self.plugin._collect_coro_frames(mock_coro, stack_info)

        self.assertEqual(len(stack_info), 1)
        self.assertEqual(stack_info[0]["filename"], "/path/to/test.py")
        self.assertEqual(stack_info[0]["lineno"], 42)
        self.assertEqual(stack_info[0]["name"], "test_func")

    def test_collect_coro_frames_chain(self):
        """Test collecting frames from a chain of coroutines (cr_await)."""
        # Create mock frames
        mock_code1 = MagicMock()
        mock_code1.co_filename = "/path/to/level1.py"
        mock_code1.co_name = "level1_func"
        mock_frame1 = MagicMock()
        mock_frame1.f_code = mock_code1
        mock_frame1.f_lineno = 10

        mock_code2 = MagicMock()
        mock_code2.co_filename = "/path/to/level2.py"
        mock_code2.co_name = "level2_func"
        mock_frame2 = MagicMock()
        mock_frame2.f_code = mock_code2
        mock_frame2.f_lineno = 20

        # Create nested coroutines
        mock_coro2 = MagicMock()
        mock_coro2.cr_frame = mock_frame2
        mock_coro2.cr_await = None

        mock_coro1 = MagicMock()
        mock_coro1.cr_frame = mock_frame1
        mock_coro1.cr_await = mock_coro2

        stack_info = []
        self.plugin._collect_coro_frames(mock_coro1, stack_info)

        self.assertEqual(len(stack_info), 2)
        self.assertEqual(stack_info[0]["name"], "level1_func")
        self.assertEqual(stack_info[1]["name"], "level2_func")

    def test_collect_coro_frames_max_depth(self):
        """Test that recursion is limited by max depth."""
        # Create a chain longer than max depth
        stack_info = []

        # Create deep chain (depth > 100)
        def create_chain(depth):
            if depth > 105:
                return None
            mock_code = MagicMock()
            mock_code.co_filename = f"/path/to/level{depth}.py"
            mock_code.co_name = f"level{depth}"
            mock_frame = MagicMock()
            mock_frame.f_code = mock_code
            mock_frame.f_lineno = depth

            mock_coro = MagicMock()
            mock_coro.cr_frame = mock_frame
            mock_coro.cr_await = create_chain(depth + 1)
            return mock_coro

        root_coro = create_chain(0)
        self.plugin._collect_coro_frames(root_coro, stack_info)

        # Should stop at max depth (100)
        self.assertLessEqual(len(stack_info), 101)

    def test_collect_coro_frames_none_coro(self):
        """Test handling of None coroutine."""
        stack_info = []
        self.plugin._collect_coro_frames(None, stack_info)
        self.assertEqual(len(stack_info), 0)


class TestStackServerPluginTaskFiltering(unittest.TestCase):
    """Test cases for flight_profiler task filtering."""

    def setUp(self):
        self.out_q = MockServerQueue()
        self.plugin = StackServerPlugin("stack", self.out_q)

    def test_is_flight_profiler_task_by_coro_name(self):
        """Test filtering task by coroutine name."""
        mock_coro = MagicMock()
        mock_coro.__qualname__ = "flight_profiler.server.run"
        mock_coro.__module__ = "some_module"

        mock_task = MagicMock()
        mock_task.get_coro.return_value = mock_coro
        mock_task.get_stack.return_value = []

        self.assertTrue(self.plugin._is_flight_profiler_task(mock_task))

    def test_is_flight_profiler_task_by_module(self):
        """Test filtering task by module name."""
        mock_coro = MagicMock()
        mock_coro.__qualname__ = "some_func"
        mock_coro.__module__ = "flight_profiler.plugins.stack"

        mock_task = MagicMock()
        mock_task.get_coro.return_value = mock_coro
        mock_task.get_stack.return_value = []

        self.assertTrue(self.plugin._is_flight_profiler_task(mock_task))

    def test_is_flight_profiler_task_by_filename(self):
        """Test filtering task by file path."""
        mock_code = MagicMock()
        mock_code.co_filename = "/path/to/flight_profiler/server.py"

        mock_coro = MagicMock()
        mock_coro.__qualname__ = "some_func"
        mock_coro.__module__ = "some_module"
        mock_coro.cr_code = mock_code

        mock_task = MagicMock()
        mock_task.get_coro.return_value = mock_coro
        mock_task.get_stack.return_value = []

        self.assertTrue(self.plugin._is_flight_profiler_task(mock_task))

    def test_is_flight_profiler_task_by_stack_frame(self):
        """Test filtering task by stack frame file path."""
        mock_coro = MagicMock()
        mock_coro.__qualname__ = "user_func"
        mock_coro.__module__ = "user_module"
        mock_coro.cr_code = None

        mock_code = MagicMock()
        mock_code.co_filename = "/path/to/flight_profiler/plugin.py"
        mock_frame = MagicMock()
        mock_frame.f_code = mock_code

        mock_task = MagicMock()
        mock_task.get_coro.return_value = mock_coro
        mock_task.get_stack.return_value = [mock_frame]

        self.assertTrue(self.plugin._is_flight_profiler_task(mock_task))

    def test_is_flight_profiler_task_negative(self):
        """Test that user tasks are not filtered."""
        mock_coro = MagicMock()
        mock_coro.__qualname__ = "user_coroutine"
        mock_coro.__module__ = "my_app.handlers"
        mock_coro.cr_code = None

        mock_code = MagicMock()
        mock_code.co_filename = "/path/to/my_app/handlers.py"
        mock_frame = MagicMock()
        mock_frame.f_code = mock_code

        mock_task = MagicMock()
        mock_task.get_coro.return_value = mock_coro
        mock_task.get_stack.return_value = [mock_frame]

        self.assertFalse(self.plugin._is_flight_profiler_task(mock_task))


class TestStackServerPluginIntegration(unittest.TestCase):
    """Integration tests using real asyncio tasks."""

    def _run_async_test(self, coro):
        """
        Run async test in an isolated event loop without affecting global state.
        """
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            # Cancel all pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            # Run loop to process cancellations
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    def test_get_task_info_with_real_task(self):
        """Test extracting info from a real asyncio task."""
        out_q = MockServerQueue()
        plugin = StackServerPlugin("stack", out_q)
        test_case = self

        async def sample_coroutine():
            await asyncio.sleep(100)

        async def run_test():
            task = asyncio.create_task(sample_coroutine(), name="TestSampleTask")
            await asyncio.sleep(0.01)  # Let task start

            # Test task name
            name = plugin._get_task_name(task)
            test_case.assertEqual(name, "TestSampleTask")

            # Test task state
            state = plugin._get_task_state(task)
            test_case.assertEqual(state, "WAITING")

            # Test coroutine repr
            coro_repr = plugin._get_coro_repr(task)
            test_case.assertEqual(
                coro_repr,
                "TestStackServerPluginIntegration.test_get_task_info_with_real_task.<locals>.sample_coroutine"
            )

            # Cleanup
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._run_async_test(run_test())

    def test_collect_frames_with_real_coroutine_chain(self):
        """Test frame collection with real nested coroutines."""
        out_q = MockServerQueue()
        plugin = StackServerPlugin("stack", out_q)
        test_case = self

        async def inner_coro():
            await asyncio.sleep(100)

        async def outer_coro():
            await inner_coro()

        async def run_test():
            task = asyncio.create_task(outer_coro(), name="ChainTest")
            await asyncio.sleep(0.01)  # Let task start

            # Get task stack
            stack = plugin._get_task_stack(task)

            # Should have frames from the coroutine chain
            test_case.assertGreater(len(stack), 0)

            # Verify frame structure
            for frame in stack:
                test_case.assertIn("filename", frame)
                test_case.assertIn("lineno", frame)
                test_case.assertIn("name", frame)

            # Cleanup
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._run_async_test(run_test())


if __name__ == "__main__":
    unittest.main()
