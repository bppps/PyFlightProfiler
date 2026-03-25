import pickle
import traceback

from flight_profiler.plugins.server_plugin import Message, ServerPlugin, ServerQueue
from flight_profiler.plugins.vmtool.vmtool_agent import GLOBAL_VMTOOL_AGENT
from flight_profiler.plugins.vmtool.vmtool_parser import (
    VmtoolArgumentParser,
    VmtoolParams,
)
from flight_profiler.utils.render_util import build_error_message


class VmtoolServerPlugin(ServerPlugin):
    def __init__(self, cmd: str, out_q: ServerQueue):
        super().__init__(cmd, out_q)

    async def do_action(self, param):

        try:
            vmtool_param: VmtoolParams = VmtoolArgumentParser().parse_params(param)
            await self.out_q.output_msg(
                Message(True, pickle.dumps(GLOBAL_VMTOOL_AGENT.do_action(vmtool_param)))
            )
        except:
            await self.out_q.output_msg(Message(True, pickle.dumps(build_error_message(traceback.format_exc()))))


def get_instance(cmd: str, out_q: ServerQueue):
    return VmtoolServerPlugin(cmd, out_q)
