import sys
from typing import List

from flight_profiler.communication.flight_client import FlightClient
from flight_profiler.help_descriptions import STACK_COMMAND_DESCRIPTION
from flight_profiler.plugins.cli_plugin import BaseCliPlugin
from flight_profiler.plugins.stack.stack_parser import StackParams, global_stack_parser
from flight_profiler.utils.cli_util import show_error_info
from flight_profiler.utils.env_util import is_linux
from flight_profiler.utils.render_util import COLOR_END, COLOR_GREEN


class StackCliPlugin(BaseCliPlugin):
    def __init__(self, port, server_pid):
        super().__init__(port, server_pid)

    def get_help(self):
        return STACK_COMMAND_DESCRIPTION.help_hint()

    def __analyze_under_linux(self, params: StackParams):
        """
        analyze process stack under linux based on pystack from Bloomberg
        see: https://github.com/bloomberg/pystack
        """
        from pystack.engine import NativeReportingMode, StackMethod, get_process_threads
        from pystack.traceback_formatter import format_thread

        if params.native:
            native_mode = NativeReportingMode.PYTHON
            stop_process = True
        else:
            native_mode = NativeReportingMode.OFF
            stop_process = False

        thread_lines: List[str] = []
        for thread in get_process_threads(
            int(params.pid),
            stop_process=stop_process,
            native_mode=native_mode,
            locals=False,
            method=StackMethod.AUTO,
        ):
            if params.filepath is not None:
                for line in format_thread(thread, params.native):
                    thread_lines.append(line)
            else:
                for line in format_thread(thread, params.native):
                    print(line, file=sys.stdout, flush=True)

        if params.filepath is not None:
            with open(params.filepath, "w") as f:
                for line in thread_lines:
                    print(line, file=f, flush=True)
            stack_literal = "native stack" if params.native else "stack"
            print(
                f"{COLOR_GREEN}write {stack_literal} to {params.filepath} successfully!{COLOR_END}"
            )

    def __show_coroutine_stacks(self, params: StackParams):
        """
        Show async coroutine stacks via server communication.
        Coroutines must be fetched from the target process's event loop.
        """
        body = {"target": "stack", "param": "async"}
        try:
            client = FlightClient(host="localhost", port=self.port)
        except:
            show_error_info("Target process exited!")
            return
        try:
            coro_lines: List[str] = []
            for line in client.request_stream(body):
                if line:
                    line = line.decode("utf-8")
                    if params.filepath is not None:
                        coro_lines.append(line)
                    else:
                        print(line)
            if params.filepath is not None:
                with open(params.filepath, "w") as f:
                    for line in coro_lines:
                        print(line, file=f, flush=True)
                print(
                    f"{COLOR_GREEN}write coroutine stacks to {params.filepath} successfully!{COLOR_END}"
                )
        finally:
            client.close()

    def do_action(self, cmd):
        try:
            stack_param: StackParams = global_stack_parser.parse_stack_params(cmd)
        except:
            print(self.get_help())
            return

        # Handle async coroutine stack display
        if stack_param.async_stack:
            self.__show_coroutine_stacks(stack_param)
            return

        if is_linux():
            try:
                self.__analyze_under_linux(stack_param)
            except Exception as e:
                if str(e).__contains__("No such process id"):
                    show_error_info("Target process exited!")
                    return
                else:
                    raise e
        else:
            body = {"target": "stack", "param": ""}
            try:
                client = FlightClient(host="localhost", port=self.port)
            except:
                show_error_info("Target process exited!")
                return
            try:
                if stack_param.filepath is not None:
                    file_name = stack_param.filepath
                    with open(file_name, "w") as f:
                        for line in client.request_stream(body):
                            if line:
                                line = line.decode("utf-8")
                                f.write(line + "\n")
                    print(
                        f"{COLOR_GREEN}write stack to {file_name} successfully!{COLOR_END}"
                    )
                else:
                    for line in client.request_stream(body):
                        if line:
                            line = line.decode("utf-8")
                            print(line)
            finally:
                client.close()


def get_instance(port: str, server_pid: int):
    return StackCliPlugin(port, server_pid)
