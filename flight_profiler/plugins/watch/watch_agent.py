import asyncio
import functools
import importlib
import inspect
import json
import pickle
import time
import traceback
import types
from types import CodeType

from flight_profiler.common import aop_decorator
from flight_profiler.common.code_wrapper_entity import CodeWrapperResult
from flight_profiler.common.enter_exit_command import EnterExitCommand
from flight_profiler.common.expression_resolver import FilterExprResolver
from flight_profiler.common.system_logger import logger
from flight_profiler.plugins.server_plugin import Message, ServerQueue
from flight_profiler.plugins.watch.watch_displayer import WatchDisplayer, WatchResult
from flight_profiler.utils.render_util import (
    COLOR_END,
    COLOR_ORANGE,
    COLOR_RED,
    build_long_spy_command_hint,
)


class WatchSetting(EnterExitCommand):
    def __init__(
        self,
        method_name: str,
        watch_expr: str,
        module_name: str = None,
        nested_method: str = None,
        class_name: str = None,
        filter_expr: str = None,
        record_on_exception: bool = False,
        raw_output: bool = False,
        expand_level: int = 2,
        verbose: bool = False,
        # max count to display
        max_count: int = 10,
        out_q: ServerQueue = None,
        need_wrap_nested_inplace: bool = False,
        nested_code_obj: CodeType = None
    ):
        super().__init__(limit=max_count)
        self.module_name = module_name
        self.class_name = class_name
        self.method_name = method_name
        self.raw_output = raw_output
        self.watch_expr = watch_expr
        self.nested_method = nested_method
        self.origin_code = None
        if self.class_name is not None:
            if self.nested_method:
                self.method_identifier = (
                    f"{self.module_name}.{self.class_name}.{self.method_name}.{self.nested_method}"
                )
            else:
                self.method_identifier = (
                    f"{self.module_name}.{self.class_name}.{self.method_name}"
                )
        else:
            self.method_identifier = f"{self.module_name}.{self.method_name}"
        self.verbose = verbose
        self.watch_displayer = WatchDisplayer(
            watch_expr, expand_level, self.method_identifier, self.raw_output, verbose
        )
        self.filter_expr = filter_expr
        self.watch_filter: FilterExprResolver = FilterExprResolver(self.filter_expr)
        self.record_on_exception = record_on_exception
        self.module_name = module_name
        self.max_count = max_count
        self.expand_level = expand_level
        self.need_wrap_nested_inplace = need_wrap_nested_inplace
        self.nested_code_obj = nested_code_obj
        if expand_level == -1:
            self.expand_level = None  # infinite
        self.out_q = out_q
        self.enable = True

    def import_module(self):
        if self.module_name is not None:
            return importlib.import_module(self.module_name)
        else:
            raise Exception("module_name not specified")

    def valid(self):
        if self.method_name is None:
            raise Exception(f"watch setting needs method_name")
        return True

    def child_clear_action(self):
        global_watch_agent.clear_auto_close(self.unique_key())

    def __str__(self):
        state = self.__dict__.copy()
        del state["watch_displayer"]
        del state["watch_filter"]
        del state["out_q"]
        del state["origin_code"]
        return str(json.dumps(state))

    def dump_result(self, start_ms, target_obj, time_cost, return_obj, *args, **kwargs):
        # filter params or return obj
        try:
            if self.watch_filter.eval_filter(
                target_obj, return_obj, time_cost, *args, **kwargs
            ):
                # dump watch params/return obj to json
                json_str = self.watch_displayer.dump(
                    start_ms, target_obj, time_cost, return_obj, *args, **kwargs
                )
                if self.out_q is not None:
                    self.out_q.output_msg_nowait(
                        Message(False, json_str)
                    )
        except:
            if self.out_q is not None:
                watch_result = WatchResult(
                    method_identifier=self.method_identifier,
                    cost_ms=time_cost,
                    is_exp=False,
                    start_ms=start_ms,
                    filter_expr=self.filter_expr,
                    filter_fail_info=traceback.format_exc(),
                )
                self.out_q.output_msg_nowait(
                    Message(
                        False,
                        pickle.dumps(watch_result),
                    )
                )

    def dump_error(self, start_ms, target_obj, time_cost, err_text, *args, **kwargs):
        # filter params or return obj
        try:
            if self.watch_filter.eval_filter(
                target_obj, None, time_cost, *args, **kwargs
            ):
                # dump watch params/return obj to json
                json_str = self.watch_displayer.dump_error(
                    start_ms, target_obj, time_cost, err_text, *args, **kwargs
                )
                if self.out_q is not None:
                    self.out_q.output_msg_nowait(
                        Message(False, json_str)
                    )
        except:
            if self.out_q is not None:
                watch_result = WatchResult(
                    method_identifier=self.method_identifier,
                    cost_ms=time_cost,
                    is_exp=True,
                    start_ms=start_ms,
                    filter_expr=self.filter_expr,
                    filter_fail_info=traceback.format_exc(),
                )
                self.out_q.output_msg_nowait(
                    Message(
                        False,
                        pickle.dumps(watch_result),
                    )
                )


def wrapper_generator(watch_setting: WatchSetting):
    # wrap function, do some aop watch action
    def watch_func(func):
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def wrapped(*args, **kwargs):
                if watch_setting.enter():
                    new_args = args
                    # filter class method self
                    target_obj = None
                    if watch_setting.class_name is not None and watch_setting.nested_method is None:
                        target_obj = args[0]
                        new_args = args[1:]
                    s = time.time()
                    try:
                        if watch_setting.need_wrap_nested_inplace:
                            current_frame = inspect.currentframe().f_back
                            func_name = watch_setting.nested_method
                            target_func = current_frame.f_locals[func_name]
                            new_func = types.FunctionType(
                                watch_setting.nested_code_obj, target_func.__globals__, func_name,
                                target_func.__defaults__, target_func.__closure__
                            )
                            return_obj = await new_func(*args, **kwargs)
                        else:
                            return_obj = await func(*args, **kwargs)
                        e = time.time()
                        try:
                            if not watch_setting.record_on_exception:
                                watch_setting.dump_result(
                                    int(s * 1000),
                                    target_obj,
                                    (e - s) * 1000,
                                    return_obj,
                                    *new_args,
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
                            watch_setting.dump_error(
                                int(s * 1000),
                                target_obj,
                                (e - s) * 1000,
                                msg,
                                *new_args,
                                **kwargs,
                            )
                        except:
                            msg = traceback.format_exc()
                            logger.error(msg)
                        raise ex
                    finally:
                        watch_setting.exit()
                else:
                    return await func(*args, **kwargs)

        else:

            @functools.wraps(func)
            def wrapped(*args, **kwargs):
                if watch_setting.enter():
                    new_args = args
                    # filter class method self
                    target_obj = None
                    if watch_setting.class_name is not None and watch_setting.nested_method is None:
                        target_obj = args[0]
                        new_args = args[1:]
                    s = time.time()
                    try:
                        if watch_setting.need_wrap_nested_inplace:
                            current_frame = inspect.currentframe().f_back
                            func_name = watch_setting.nested_method
                            target_func = current_frame.f_locals[func_name]
                            new_func = types.FunctionType(
                                watch_setting.nested_code_obj, target_func.__globals__, func_name,
                                target_func.__defaults__, target_func.__closure__
                            )
                            return_obj = new_func(*args, **kwargs)
                        else:
                            return_obj = func(*args, **kwargs)
                        e = time.time()
                        try:
                            if not watch_setting.record_on_exception:
                                watch_setting.dump_result(
                                    int(s * 1000),
                                    target_obj,
                                    (e - s) * 1000,
                                    return_obj,
                                    *new_args,
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
                            watch_setting.dump_error(
                                int(s * 1000),
                                target_obj,
                                (e - s) * 1000,
                                msg,
                                *new_args,
                                **kwargs,
                            )
                        except:
                            msg = traceback.format_exc()
                            logger.error(msg)
                        raise ex
                    finally:
                        watch_setting.exit()
                else:
                    return func(*args, **kwargs)

        return wrapped

    return watch_func


class WatchAgent(object):

    def __init__(self):
        self.aop_points = dict()

    def add_watch(self, watch_setting: WatchSetting):
        watch_setting.valid()
        key = watch_setting.unique_key()
        old_setting: WatchSetting = self.aop_points.get(key, None)
        if old_setting is not None:
            self.clear_watch(old_setting)

        try:
            module = watch_setting.import_module()
        except Exception as e:
            watch_setting.out_q.output_msg_nowait(
                Message(
                    True,
                    pickle.dumps(
                        f"{COLOR_RED}Error in locating module named "
                        f"{COLOR_ORANGE}{watch_setting.module_name}{COLOR_END}{COLOR_RED}. Type: {type(e)}, details: {str(e)}!{COLOR_END}"
                    ),
                )
            )
            return

        wrapper_result: CodeWrapperResult = aop_decorator.add_func_wrapper(
            module,
            watch_setting.class_name,
            watch_setting.method_name,
            wrapper_generator,
            watch_setting,
            ["time", "traceback", "inspect", "types"],
            {
                "flight_profiler.common.system_logger": ["logger"]
            },
            nested_method=watch_setting.nested_method,
            module_name=watch_setting.module_name
        )

        if wrapper_result.failed:
            watch_setting.out_q.output_msg_nowait(
                Message(
                    True,
                    pickle.dumps(f"{COLOR_RED}{wrapper_result.failed_reason}{COLOR_END}"),
                )
            )
        else:
            if watch_setting.nested_method is not None and wrapper_result.value.need_wrap_nested_inplace:
                # used to construct new code at runtime
                watch_setting.need_wrap_nested_inplace = True
                watch_setting.nested_code_obj = wrapper_result.value.nested_code_obj

            watch_setting.origin_code = wrapper_result.value
            watch_setting.out_q.output_msg_nowait(
                Message(
                    False,
                    pickle.dumps(
                        build_long_spy_command_hint(
                            watch_setting.module_name,
                            watch_setting.class_name,
                            watch_setting.method_name,
                            watch_setting.nested_method
                        )
                    ),
                )
            )
            self.aop_points[key] = watch_setting

    def clear_watch(self, watch_setting: WatchSetting):
        watch_setting.valid()
        old_setting: WatchSetting = self.aop_points.get(watch_setting.unique_key(), None)
        if old_setting is None:
            logger.warning(
                f"class function {watch_setting.unique_key()} "
                f"not watched, will skip clear"
            )
            return None
        self.aop_points.pop(old_setting.unique_key())
        if old_setting.origin_code is not None:
            module = old_setting.import_module()
            aop_decorator.clear_func_wrapper(
                module,
                watch_setting.class_name,
                watch_setting.method_name,
                old_setting.origin_code,
            )
            old_setting.out_q.output_msg_nowait(Message(True, None))
        else:
            logger.warning(
                f"old watch setting {old_setting.unique_key()} exists, but no origin function is stored"
            )


    def clear_auto_close(self, unique_key: str):
        """
        execute times exceed limit, auto clear points
        """
        old_setting: WatchSetting = self.aop_points.get(unique_key)
        if old_setting is None:
            logger.warning(
                f"class function {unique_key} " f"not watched, will skip clear"
            )
            return None
        self.aop_points.pop(old_setting.unique_key())


global_watch_agent = WatchAgent()
