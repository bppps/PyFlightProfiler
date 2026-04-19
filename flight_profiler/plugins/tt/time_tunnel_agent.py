import asyncio
import functools
import importlib
import inspect
import pickle
import time
import traceback
import types
from typing import Dict

from flight_profiler.common import aop_decorator
from flight_profiler.common.code_wrapper_entity import CodeWrapperResult
from flight_profiler.common.system_logger import logger
from flight_profiler.plugins.server_plugin import Message
from flight_profiler.plugins.tt.time_tunnel_recorder import (
    TimeTunnelCmd,
    global_time_tunnel_recorder,
)
from flight_profiler.utils.render_util import (
    COLOR_END,
    COLOR_GREEN,
    COLOR_ORANGE,
    COLOR_RED,
    build_long_spy_command_hint,
)


def generate_time_tunnel_wrapper(tt_cmd: TimeTunnelCmd):
    def time_tunnel_decorator(func):
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                if tt_cmd.enter():
                    s = time.time()
                    try:
                        if tt_cmd.need_wrap_nested_inplace:
                            current_frame = inspect.currentframe().f_back
                            func_name = tt_cmd.nested_method
                            target_func = current_frame.f_locals[func_name]
                            new_func = types.FunctionType(
                                tt_cmd.nested_code_obj, target_func.__globals__, func_name,
                                target_func.__defaults__, target_func.__closure__
                            )
                            return_obj = await new_func(*args, **kwargs)
                        else:
                            return_obj = await func(*args, **kwargs)

                        e = time.time()
                        try:
                            tt_cmd.dump_invocation(
                                int(s * 1000),
                                (e - s) * 1000,
                                return_obj,
                                *args,
                                **kwargs,
                            )
                        except:
                            msg = traceback.format_exc()
                            logger.error(msg)
                        return return_obj
                    except Exception as ex:
                        try:
                            e = time.time()
                            msg = traceback.format_exc()
                            tt_cmd.dump_error(
                                int(s * 1000), (e - s) * 1000, msg, *args, **kwargs
                            )
                        except:
                            msg = traceback.format_exc()
                            logger.error(msg)
                        raise ex
                    finally:
                        tt_cmd.exit()
                else:
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if tt_cmd.enter():
                    s = time.time()
                    try:
                        if tt_cmd.need_wrap_nested_inplace:
                            current_frame = inspect.currentframe().f_back
                            func_name = tt_cmd.nested_method
                            target_func = current_frame.f_locals[func_name]
                            new_func = types.FunctionType(
                                tt_cmd.nested_code_obj, target_func.__globals__, func_name,
                                target_func.__defaults__, target_func.__closure__
                            )
                            return_obj = new_func(*args, **kwargs)
                        else:
                            return_obj = func(*args, **kwargs)
                        e = time.time()
                        try:
                            tt_cmd.dump_invocation(
                                int(s * 1000),
                                (e - s) * 1000,
                                return_obj,
                                *args,
                                **kwargs,
                            )
                        except:
                            msg = traceback.format_exc()
                            logger.error(msg)
                        return return_obj
                    except Exception as ex:
                        try:
                            e = time.time()
                            msg = traceback.format_exc()
                            tt_cmd.dump_error(
                                int(s * 1000), (e - s) * 1000, msg, *args, **kwargs
                            )
                        except:
                            msg = traceback.format_exc()
                            logger.error(msg)
                        raise ex
                    finally:
                        tt_cmd.exit()
                else:
                    return func(*args, **kwargs)

            return wrapper

    return time_tunnel_decorator


class TimeTunnelAgent:

    def __init__(self):
        self.aop_points: Dict[str, TimeTunnelCmd] = dict()

    def on_action(self, tt_cmd: TimeTunnelCmd):
        """
        supports time_tunnel/show_list/index three kinds actions
        """
        if tt_cmd.time_tunnel is not None:
            # records method invocation within time fragments
            if tt_cmd.unique_key() in self.aop_points:
                self.clear_tt_point(tt_cmd)

            tt_cmd.global_instance = global_tt_agent
            try:
                module = importlib.import_module(tt_cmd.module_name)
            except Exception as e:
                tt_cmd.out_q.output_msg_nowait(
                    Message(
                        True,
                        pickle.dumps(
                            f"{COLOR_RED}Error in locating module named "
                            f"{COLOR_ORANGE}{tt_cmd.module_name}{COLOR_END}{COLOR_RED}. Type: {type(e)}, details: {str(e)}!{COLOR_END}"
                        ),
                    )
                )
                return

            wrapper_result: CodeWrapperResult = aop_decorator.add_func_wrapper(
                module,
                tt_cmd.class_name,
                tt_cmd.method_name,
                generate_time_tunnel_wrapper,
                tt_cmd,
                ["sys", "time", "traceback", "inspect", "types"],
            {
                    "flight_profiler.common.system_logger": ["logger"]
                },
                module_name=tt_cmd.module_name,
                nested_method=tt_cmd.nested_method,
            )
            if wrapper_result.failed:
                tt_cmd.out_q.output_msg_nowait(
                    Message(
                        True,
                        pickle.dumps(f"{COLOR_RED}{wrapper_result.failed_reason}{COLOR_END}"),
                    )
                )
                return
            else:
                if tt_cmd.nested_method is not None and wrapper_result.value.need_wrap_nested_inplace:
                    # used to construct new code at runtime
                    tt_cmd.need_wrap_nested_inplace = True
                    tt_cmd.nested_code_obj = wrapper_result.value.nested_code_obj
                tt_cmd.origin_code = wrapper_result.value
                tt_cmd.out_q.output_msg_nowait(
                    Message(
                        False,
                        pickle.dumps(
                            build_long_spy_command_hint(
                                tt_cmd.module_name,
                                tt_cmd.class_name,
                                tt_cmd.method_name,
                                tt_cmd.nested_method
                            )
                        ),
                    )
                )
                self.aop_points[tt_cmd.unique_key()] = tt_cmd
        elif tt_cmd.show_list:
            global_time_tunnel_recorder.show_list_records(tt_cmd)
        elif tt_cmd.index is not None:
            if not tt_cmd.play:
                global_time_tunnel_recorder.show_indexed_record(tt_cmd)
            else:
                global_time_tunnel_recorder.replay_time_fragment(tt_cmd)
        elif tt_cmd.delete_id is not None:
            ret: bool = global_time_tunnel_recorder.delete_specified_record(
                tt_cmd.delete_id
            )
            if ret:
                tt_cmd.out_q.output_msg_nowait(
                    Message(
                        True,
                        msg=f"{COLOR_GREEN}Index {tt_cmd.delete_id} is deleted successfully.{COLOR_END}",
                    )
                )
            else:
                tt_cmd.out_q.output_msg_nowait(
                    Message(
                        True,
                        msg=f"{COLOR_RED}Index {tt_cmd.delete_id} is not recorded.{COLOR_END}",
                    )
                )
        elif tt_cmd.delete_all:
            global_time_tunnel_recorder.delete_all_records()
            tt_cmd.out_q.output_msg_nowait(
                Message(
                    True, msg=f"{COLOR_GREEN}All time fragments are deleted.{COLOR_END}"
                )
            )

    def clear_tt_point(self, cmd: TimeTunnelCmd):
        if cmd.time_tunnel is None:
            raise ValueError("Trying to remove not existing tt point!")

        origin_tt_cmd = self.aop_points.pop(cmd.unique_key())
        if origin_tt_cmd is not None:
            if origin_tt_cmd.origin_code is not None:
                module = importlib.import_module(origin_tt_cmd.module_name)
                aop_decorator.clear_func_wrapper(
                    module,
                    origin_tt_cmd.class_name,
                    origin_tt_cmd.method_name,
                    origin_tt_cmd.origin_code,
                )
            origin_tt_cmd.out_q.output_msg_nowait(Message(is_end=True, msg=""))

    def off_action(self, tt_cmd: TimeTunnelCmd):
        """
        current only stop recording tt
        """
        self.clear_tt_point(tt_cmd)

    def clear_auto_close(self, unique_key):
        self.aop_points.pop(unique_key)


global_tt_agent: TimeTunnelAgent = TimeTunnelAgent()
