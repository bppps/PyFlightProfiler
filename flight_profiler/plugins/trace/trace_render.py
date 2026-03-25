import traceback
from typing import List, Optional

from flight_profiler.plugins.trace.trace_frame import (
    FlattenTreeTraceFrame,
    WrapTraceFrame,
    build_frame_stack,
)
from flight_profiler.utils.frame_util import global_filepath_operator
from flight_profiler.utils.render_util import (
    BOX_HORIZONTAL,
    CMD_ICON_TRACE,
    COLOR_AWAIT,
    COLOR_BRIGHT_GREEN,
    COLOR_END,
    COLOR_FAINT,
    COLOR_FUNCTION,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_WHITE_255,
    COLOR_YELLOW,
)
from flight_profiler.utils.time_util import time_ns_to_formatted_string

INDENT = ["├─ ", "│  ", "└─ ", "   "]


class SkipStrategy:

    def should_skip(self, frame: FlattenTreeTraceFrame) -> bool:
        raise NotImplementedError


class ImportLibSkipStrategy(SkipStrategy):
    """
    remove importlib._bootstrap frame
    """

    def should_skip(self, frame: FlattenTreeTraceFrame) -> bool:

        if frame.filename and "<frozen importlib._bootstrap" in frame.filename:
            return True
        return False


class TraceRender(SkipStrategy):

    def __init__(self, total_cost_ns: int):
        self.total_cost_ns = total_cost_ns
        self.strategy_list: List[SkipStrategy] = [ImportLibSkipStrategy()]

    def preprocess_frame(
        self, flatten_frame: FlattenTreeTraceFrame
    ) -> Optional[FlattenTreeTraceFrame]:
        """
        filter frame that not qualified and shorten filepath for output
        """
        idx = 0
        flatten_frame.filename = global_filepath_operator.shorten_filepath(
            flatten_frame.filename
        )
        while idx < len(flatten_frame.sub_frames):
            if self.should_skip(flatten_frame.sub_frames[idx]):
                flatten_frame.sub_frames.pop(idx)
            else:
                self.preprocess_frame(flatten_frame.sub_frames[idx])
                idx += 1
        return flatten_frame

    def should_skip(self, frame: FlattenTreeTraceFrame) -> bool:
        for strategy in self.strategy_list:
            if strategy.should_skip(frame):
                return True
        return False

    def display(self, wrap: WrapTraceFrame) -> str:
        """
        concat full frame stack
        """
        try:
            cost_ms = wrap.frames[0].cost_ns / 1000000
            title: str = (
                f"{COLOR_FAINT}{BOX_HORIZONTAL * 60}{COLOR_END}\n"
                f"{CMD_ICON_TRACE} {COLOR_WHITE_255}{time_ns_to_formatted_string(wrap.frames[0].start_ns)}{COLOR_END} "
                f"{COLOR_FAINT}thread={COLOR_END}{wrap.thread_name} "
                f"{COLOR_FAINT}tid={COLOR_END}{wrap.thread_id} "
                f"{COLOR_FAINT}daemon={COLOR_END}{wrap.is_daemon} "
                f"{COLOR_FAINT}cost={COLOR_END}{COLOR_WHITE_255}{cost_ms:.3f}ms{COLOR_END}\n"
            )
            frame: FlattenTreeTraceFrame = self.preprocess_frame(
                build_frame_stack(wrap.frames)
            )
            return title + self.render_frame(frame)
        except:
            return traceback.format_exc()

    def get_color_by_time(self, time: float) -> str:
        """
        output different color based on frame cost weight
        """
        if self.total_cost_ns <= 0:
            return ""

        weight = time / self.total_cost_ns

        if weight > 0.5:
            return COLOR_RED
        elif weight > 0.2:
            return COLOR_YELLOW
        elif weight > 0.05:
            return COLOR_GREEN
        else:
            return COLOR_BRIGHT_GREEN + COLOR_FAINT

    def render_frame(
        self, frame: FlattenTreeTraceFrame, indent: str = "", child_indent: str = ""
    ) -> str:
        """
        do depth first search from root frame recursively
        """

        show_msg = indent
        time_color: str = self.get_color_by_time(frame.cost_ns)
        if frame.await_frame:
            show_msg = show_msg + (
                f"[{time_color}{frame.cost_ns / 1000000}ms{COLOR_END}]  "
                f"{COLOR_AWAIT}{frame.method_name}{COLOR_END}    "
                f"{COLOR_FAINT}{frame.filename}{COLOR_END}\n"
            )
        elif frame.c_frame:
            show_msg = show_msg + (
                f"[{time_color}{frame.cost_ns / 1000000}ms{COLOR_END}]  "
                f"{COLOR_FUNCTION}{frame.method_name}{COLOR_END}    "
                f"{COLOR_FAINT}{frame.filename}{COLOR_END}\n"
            )
        else:
            show_msg = show_msg + (
                f"[{time_color}{frame.cost_ns / 1000000}ms{COLOR_END}] "
                f"{COLOR_FUNCTION}{frame.method_name}{COLOR_END}    "
                f"{COLOR_FAINT}{frame.filename}:{frame.line_no}{COLOR_END}\n"
            )
        for i, sub_frame in enumerate(frame.sub_frames):
            if i < len(frame.sub_frames) - 1:
                c_indent = child_indent + INDENT[0]
                cc_indent = child_indent + INDENT[1]
            else:
                c_indent = child_indent + INDENT[2]
                cc_indent = child_indent + INDENT[3]
            show_msg = show_msg + self.render_frame(sub_frame, c_indent, cc_indent)
        return show_msg
