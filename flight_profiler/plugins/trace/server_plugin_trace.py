import pickle
import traceback

from flight_profiler.plugins.server_plugin import Message, ServerPlugin, ServerQueue
from flight_profiler.plugins.trace.trace_agent import TracePoint, global_trace_agent
from flight_profiler.plugins.trace.trace_parser import TraceArgumentParser
from flight_profiler.utils.args_util import split_regex
from flight_profiler.utils.render_util import build_error_message


class TraceServerPlugin(ServerPlugin):
    def __init__(self, cmd: str, out_q: ServerQueue):
        super().__init__(cmd, out_q)

    async def do_action(self, param):
        if param is None:
            await self.out_q.output_msg(Message(True, "trace param is None"))
            return
        splits = split_regex(param)
        if splits[0] == "on":
            new_param = param[len(splits[0]) :]
            try:
                point: TracePoint = TraceArgumentParser().parse_trace_point(new_param)
                point.out_q = self.out_q
                global_trace_agent.set_point(point)
                # will not return end message, server request will block
            except:
                await self.out_q.output_msg(Message(True, pickle.dumps(build_error_message(traceback.format_exc()))))
        elif splits[0] == "off":
            new_param = param[len(splits[0]) :]
            try:
                point: TracePoint = TraceArgumentParser().parse_trace_point(new_param)
                point.out_q = self.out_q
                global_trace_agent.clear_point(point)
                await self.out_q.output_msg(Message(True, None))
            except:
                await self.out_q.output_msg(Message(True, pickle.dumps(build_error_message(traceback.format_exc()))))
        else:
            await self.out_q.output_msg(Message(True, pickle.dumps(build_error_message("trace param is illegal."))))


def get_instance(cmd: str, out_q: ServerQueue):
    return TraceServerPlugin(cmd, out_q)
