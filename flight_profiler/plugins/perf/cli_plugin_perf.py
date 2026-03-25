import argparse
import signal
import subprocess

from flight_profiler.help_descriptions import PERF_COMMAND_DESCRIPTION
from flight_profiler.plugins.cli_plugin import BaseCliPlugin
from flight_profiler.plugins.perf.perf_parser import PerfParams, global_perf_parser
from flight_profiler.utils.cli_util import (
    show_error_info,
    show_info_with_icon,
    show_normal_info,
    show_success_info,
)
from flight_profiler.utils.env_util import is_linux


class PerfCliPlugin(BaseCliPlugin):
    def __init__(self, port, server_pid):
        super().__init__(port, server_pid)
        self.local_process = None

    def get_help(self):
        return PERF_COMMAND_DESCRIPTION.help_hint()

    def __dump_to_flamegraph(self, params: PerfParams, cmd: str):
        """
        dump stack trace info to flamegraph based on py-spy from benfred
        see: https://github.com/benfred/py-spy
        """
        command = [
            "py-spy",
            "record",
            "--pid",
            str(params.pid),
            "--output",
            params.filepath,
            "--rate",
            str(params.sample_rate),
        ]
        if params.duration > 0:
            command.extend(["--duration", str(params.duration)])

        if not is_linux():
            # OSX need root privilege to do py-spy
            command.insert(0, "sudo")

        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            show_info_with_icon("Press Control-C to exit.")
            self.__capture_process(process, params)
        except KeyboardInterrupt:
            process.send_signal(signal.SIGINT)
            self.__capture_process(process, params)

    def __capture_process(self, process: subprocess.Popen, params: PerfParams) -> None:
        stdout, stderr = process.communicate()
        if process.returncode == 0:
            show_success_info(
                f"Flamegraph data has been successfully written to {params.filepath}!"
            )
        else:
            show_error_info(stderr.decode())

    def do_action(self, cmd):
        try:
            perf_param: PerfParams = global_perf_parser.parse_perf_params(cmd)
        except argparse.ArgumentError as e:
            show_error_info(f"Perf command parsed failed, {e}")
            return
        except argparse.ArgumentTypeError as e:
            show_error_info(f"Perf command parsed failed, {e}")
            return
        except:
            show_normal_info(self.get_help())
            return
        self.__dump_to_flamegraph(perf_param, cmd)


def get_instance(port: str, server_pid: int):
    return PerfCliPlugin(port, server_pid)
