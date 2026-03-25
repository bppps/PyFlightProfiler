import pickle
import sys
from typing import Union

from flight_profiler.common.expression_result import ExpressionResult
from flight_profiler.communication.flight_client import FlightClient
from flight_profiler.utils.render_util import (
    COLOR_BRIGHT_GREEN,
    COLOR_END,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_WHITE_255,
    COLOR_YELLOW,
    EXIT_CODE_HINTS,
    ICON_FAILED,
    ICON_INFO,
    ICON_SUCCESS,
    ICON_WARNING,
    build_command_header,
    get_command_icon,
    render_expression_result,
)


def show_error_info(msg: str) -> None:
    """
    Display error information with red color and error icon.

    Args:
        msg (str): Error message to display
    """
    print(f"{COLOR_RED}{ICON_FAILED} {msg}{COLOR_END}")


def show_success_info(msg: str) -> None:
    """
    Display success information with green color and success icon.

    Args:
        msg (str): Success message to display
    """
    print(f"{COLOR_GREEN}{ICON_SUCCESS} {msg}{COLOR_END}")


def show_warning_info(msg: str) -> None:
    """
    Display warning information with yellow color and warning icon.

    Args:
        msg (str): Warning message to display
    """
    print(f"{COLOR_YELLOW}{ICON_WARNING} {msg}{COLOR_END}")


def show_normal_info(msg: str) -> None:
    """
    Display normal information with white color.

    Args:
        msg (str): Message to display
    """
    print(f"{COLOR_WHITE_255}{msg}{COLOR_END}")


def show_info_with_icon(msg: str) -> None:
    """
    Display information with info icon.

    Args:
        msg (str): Message to display
    """
    print(f"{COLOR_WHITE_255}{ICON_INFO} {msg}{COLOR_END}")


def show_command_header(cmd_name: str) -> None:
    """
    Display a command header with icon.

    Args:
        cmd_name (str): Name of the command
    """
    icon = get_command_icon(cmd_name)
    print(build_command_header(cmd_name, icon))

def verify_exit_code(exit_code: int, pid: Union[int, str]) -> None:
    """
    Verify the exit code and display appropriate error messages.

    Args:
        exit_code (int): Exit code from the process
        pid (Union[int, str]): Process ID for error context
    """
    if exit_code == 0:
        return

    print(f"{COLOR_RED}{ICON_FAILED} PyFlightProfiler attach failed, reason: {EXIT_CODE_HINTS[exit_code]}{COLOR_END}!")
    if exit_code == 10 or exit_code == 16:
        print(f"\n{ICON_INFO} Hint: This error is likely due to target process holds global interpreter lock and never releases it. We highly recommend you to use \n  `{COLOR_BRIGHT_GREEN}pystack remote "
              f"{pid}{COLOR_END}` or \n  `{COLOR_BRIGHT_GREEN}pystack remote {pid} --native{COLOR_END}` to find out which thread is stuck in gil scope.\n")
    exit(1)

def common_plugin_execute_routine(
    cmd: str,
    param: str,
    port: int,
    raw_text: bool = False,
    expression_result: bool = False,
) -> None:
    """
    Performs normal cli plugin request and render routines, should be called at the end of plugin action.

    Args:
        cmd (str): Command to execute
        param (str): Parameters for the command
        port (int): Port number for the flight client
        raw_text (bool): Whether to treat response as raw text
        expression_result (bool): Whether to process as expression result
    """
    body = {
        "target": cmd,
        "param": param
    }
    try:
        client = FlightClient(host="localhost", port=port)
    except:
        show_error_info("Target process exited!")
        return
    try:
        for line in client.request_stream(body):
            if not expression_result:
                if line:
                    if raw_text:
                        line = line.decode("utf-8")
                    else:
                        line = pickle.loads(line)
                    # Handle newline messages
                    show_normal_info(line)
            else:
                result: Union[ExpressionResult, str] = pickle.loads(
                    line
                )
                if type(result) is str:
                    print(result)
                else:
                    print(
                        render_expression_result(
                            result
                        )
                    )
            sys.stdout.flush()
    finally:
        client.close()
