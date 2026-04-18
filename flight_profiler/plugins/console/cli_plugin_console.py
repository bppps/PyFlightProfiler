import json

from flight_profiler.communication.base import TargetProcessExitError
from flight_profiler.communication.flight_client import FlightClient
from flight_profiler.help_descriptions import CONSOLE_COMMAND_DESCRIPTION
from flight_profiler.plugins.cli_plugin import BaseCliPlugin
from flight_profiler.utils.cli_util import show_error_info, show_normal_info


class ConsoleCliPlugin(BaseCliPlugin):
    def __init__(self, port, server_pid):
        super().__init__(port, server_pid)

    @property
    def handles_own_input(self):
        return True

    def get_help(self):
        return CONSOLE_COMMAND_DESCRIPTION.help_hint()

    def do_action(self, no_op):
        body = {
            "target": "console",
        }
        try:
            client = FlightClient(host="localhost", port=self.port)
        except:
            show_error_info("Target process exited!")
            return

        try:
            client.send(json.dumps(body).encode("utf-8"))
        except TargetProcessExitError:
            show_error_info("Target process exit!")
            return
        except:
            raise

        try:
            while True:
                response_bytes: bytes = client.recv()
                if not response_bytes:
                    break
                response: str = response_bytes.decode("utf-8")
                try:
                    prompt, response = response.split("\n", 1)
                except:
                    break
                if response != "":
                    show_normal_info(response)
                try:
                    cmd = input(prompt)
                except EOFError:
                    cmd = "exit()"
                    print("")
                except KeyboardInterrupt:
                    cmd = "None"
                    print("")
                client.send(cmd.encode("utf-8"))
        except TargetProcessExitError:
            show_error_info("Target process exit!")
            return
        finally:
            client.close()

    def on_interrupted(self):
        pass


def get_instance(port: str, server_pid: int):
    return ConsoleCliPlugin(port, server_pid)
