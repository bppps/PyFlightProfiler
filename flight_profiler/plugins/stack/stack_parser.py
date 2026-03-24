import argparse
from argparse import RawTextHelpFormatter
from typing import Optional

from flight_profiler.common.global_store import get_inject_server_pid
from flight_profiler.help_descriptions import STACK_COMMAND_DESCRIPTION
from flight_profiler.utils.args_util import rewrite_args
from flight_profiler.utils.env_util import is_linux


class StackParams:

    def __init__(self, pid: int, filepath: Optional[str], native: bool, async_stack: bool = False):
        self.pid = pid
        self.native = native
        self.filepath = filepath
        self.async_stack = async_stack  # show async coroutine stack


class StackParser(argparse.ArgumentParser):

    def __init__(self):
        super(StackParser, self).__init__(
            description=STACK_COMMAND_DESCRIPTION.help_hint(),
            add_help=True,
            formatter_class=RawTextHelpFormatter,
        )
        if hasattr(self, "exit_on_error"):
            self.exit_on_error = False
        if is_linux():
            self.add_argument(
                "--pid",
                required=False,
                help="target process pid.",
                default=get_inject_server_pid(),
            )
            self.add_argument(
                "--native",
                required=False,
                action="store_true",
                default=False,
                help="analyze native stack frame or not.",
            )
        self.add_argument(
            "-a",
            "--async",
            dest="async_stack",
            required=False,
            action="store_true",
            default=False,
            help="show async coroutine/task stacks.",
        )
        self.add_argument(
            "-f",
            "--filepath",
            required=False,
            help="dump stack frame to filepath.",
            default=None,
        )

    def error(self, message):
        raise Exception(message)

    def parse_stack_params(self, arg_string: str) -> StackParams:

        if is_linux():
            new_args = rewrite_args(arg_string, unspec_names=["pid"], omit_column=None)
        else:
            new_args = rewrite_args(
                arg_string, unspec_names=["filepath"], omit_column=None
            )
        args = self.parse_args(args=new_args)
        if is_linux():
            return StackParams(
                pid=getattr(args, "pid"),
                native=getattr(args, "native"),
                filepath=getattr(args, "filepath"),
                async_stack=getattr(args, "async_stack"),
            )
        else:
            return StackParams(
                pid=-1,
                native=False,
                filepath=getattr(args, "filepath"),
                async_stack=getattr(args, "async_stack"),
            )


global_stack_parser = StackParser()
