import argparse
import pickle
import sys
from typing import Union

from flight_profiler.communication.flight_client import FlightClient
from flight_profiler.help_descriptions import TRACE_COMMAND_DESCRIPTION
from flight_profiler.plugins.cli_plugin import BaseCliPlugin
from flight_profiler.plugins.trace.trace_agent import TracePoint
from flight_profiler.plugins.trace.trace_frame import (
    WrapTraceFrame,
    deserialize_string_frames,
)
from flight_profiler.plugins.trace.trace_parser import TraceArgumentParser
from flight_profiler.plugins.trace.trace_render import TraceRender
from flight_profiler.utils.cli_util import (
    common_plugin_execute_routine,
    show_error_info,
    show_normal_info,
)
from flight_profiler.utils.frame_util import global_filepath_operator


class TraceCliPlugin(BaseCliPlugin):
    def __init__(self, port, server_pid):
        super().__init__(port, server_pid)

    def get_help(self):
        return TRACE_COMMAND_DESCRIPTION.help_hint()

    def do_action(self, cmd):
        try:
            trace_point: TracePoint = TraceArgumentParser().parse_trace_point(cmd)
        except argparse.ArgumentError as e:
            show_error_info(f" Trace command parsed failed, {e}")
            return
        except:
            show_normal_info(self.get_help())
            return

        self.last_cmd = cmd
        body = {"target": "trace", "param": "on " + cmd}
        try:
            client = FlightClient(host="localhost", port=self.port)
        except:
            show_error_info("Target process exited!")
            raise
        try:
            first_chunk = True
            for content in client.request_stream(body):
                sys.stdout.flush()
                if first_chunk:
                    global_filepath_operator.set_sys_path(pickle.loads(content))
                    first_chunk = False
                else:
                    wrap: Union[WrapTraceFrame, str] = pickle.loads(content)
                    if type(wrap) == str:
                        # String message (e.g., spy command hint)
                        print(wrap)
                        continue
                    if (
                        len(wrap.frames) > 0
                        and wrap.frames[0] is None
                        or len(wrap.frames) == 0
                    ):
                        # frames[0] is root frame
                        show_normal_info(
                            f"Trace method cost is below {trace_point.interval}ms, skip display."
                        )
                        continue
                    wrap = deserialize_string_frames(wrap)
                    if (
                        wrap.frames[0].cost_ns
                        < trace_point.entrance_time * 1_000_000
                    ):
                        continue
                    show_msg: str = TraceRender(wrap.frames[0].cost_ns).display(
                        wrap
                    )
                    show_normal_info(show_msg)
        finally:
            client.close()

    def on_interrupted(self):
        common_plugin_execute_routine(
            cmd="trace",
            param="off " + self.last_cmd,
            port=self.port,
        )


def get_instance(port: str, server_pid: int):
    return TraceCliPlugin(port, server_pid)
