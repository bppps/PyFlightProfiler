import unittest
from typing import List

from flight_profiler.plugins.trace.trace_frame import (
    FlattenTreeTraceFrame,
    WrapTraceFrame,
    build_frame_stack,
    deserialize_string_frames,
)
from flight_profiler.plugins.trace.trace_render import (
    ImportLibSkipStrategy,
    TraceRender,
)
from flight_profiler.test.plugins.trace import SENDING_FRAMES


def build_wrap_trace_frame() -> WrapTraceFrame:
    return deserialize_string_frames(WrapTraceFrame(SENDING_FRAMES))


def build_tree_trace_frame() -> FlattenTreeTraceFrame:
    return build_frame_stack(build_wrap_trace_frame().frames)


class TraceRenderTest(unittest.TestCase):

    def test_importlib_frame_strategy(self):
        frame = build_tree_trace_frame()
        frame.filename = "<frozen importlib._bootstrap>"

        strategy = ImportLibSkipStrategy()
        self.assertTrue(strategy.should_skip(frame))

    def test_display_frame(self):

        render = TraceRender(0)
        show_msg = render.display(build_wrap_trace_frame())
        lines = show_msg.split("\n")
        # First line is separator, second line is title
        title = lines[1]
        self.assertTrue("thread=" in title)
        self.assertTrue("daemon=" in title)
        self.assertTrue("False" in title)  # daemon value

        self.assertTrue("hello" in lines[2])
        self.assertTrue("test_func" in lines[3])
        self.assertTrue("print" in lines[4])

        self.assertEqual(6, len(lines))

    def test_render_frame_skip(self):
        wrap_frame = build_wrap_trace_frame()
        infos: List[str] = wrap_frame.frames[1].description.split("\x00")
        wrap_frame.frames[1].description = (
            infos[0] + "\x00" + "<frozen importlib._bootstrap>" + "\x00" + infos[2]
        )

        render = TraceRender(500)
        show_msg = render.display(wrap_frame)

        lines = show_msg.split("\n")
        # First line is separator, second line is title
        title = lines[1]
        self.assertTrue("thread=" in title)
        self.assertTrue("daemon=" in title)
        self.assertTrue("False" in title)  # daemon value

        self.assertTrue("hello" in lines[2])
        self.assertEqual(4, len(lines))
