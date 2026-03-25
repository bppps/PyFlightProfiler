import asyncio
import functools
import inspect
import types
import unittest

from flight_profiler.common import aop_decorator
from flight_profiler.plugins.watch.watch_agent import WatchSetting


class AopDecoratorTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_wrap_module_func(self):
        from flight_profiler.test.util.test_aop import test_aop_module

        def watch_func(watch_setting):
            def wrapper(func):
                def wrapped_func(*args, **kwargs):
                    ret = func(*args, **kwargs)
                    return ret + 1

                return wrapped_func

            return wrapper

        self.assertEqual(test_aop_module.func_to_wrap(5), 5)
        wrapper_result = aop_decorator.add_func_wrapper(
            test_aop_module, None, "func_to_wrap", watch_func, None, ["time"]
        )
        self.assertEqual(test_aop_module.func_to_wrap(5), 6)

        aop_decorator.clear_func_wrapper(
            test_aop_module, None, "func_to_wrap", wrapper_result.value
        )
        self.assertEqual(test_aop_module.func_to_wrap(5), 5)

    def test_nested_module_func(self):
        from flight_profiler.test.util.test_aop import test_aop_module

        def watch_func(watch_setting):
            def wrapper(func):
                def wrapped_func(*args, **kwargs):
                    ret = func(*args, **kwargs)
                    return ret + 1

                return wrapped_func

            return wrapper

        self.assertEqual(test_aop_module.nested_func_to_wrap(), 5)
        wrapper_result = aop_decorator.add_func_wrapper(
            test_aop_module, None, "nested_func_to_wrap", watch_func, None, ["time"], nested_method="nested_func",
            module_name="flight_profiler.test.util.test_aop.test_aop_module"
        )
        self.assertEqual(test_aop_module.nested_func_to_wrap(), 6)

        aop_decorator.clear_func_wrapper(
            test_aop_module, None, "nested_func_to_wrap", wrapper_result.value
        )
        self.assertEqual(test_aop_module.nested_func_to_wrap(), 5)

    def test_nested_module_func_deref(self):
        from flight_profiler.test.util.test_aop import test_aop_module

        def watch_func(watch_setting):
            def wrapper(func):
                def wrapped_func(*args, **kwargs):
                    current_frame = inspect.currentframe().f_back
                    func_name = watch_setting.nested_method
                    target_func = current_frame.f_locals[func_name]
                    new_func = types.FunctionType(
                        watch_setting.nested_code_obj, target_func.__globals__, func_name,
                        target_func.__defaults__, target_func.__closure__
                    )
                    z1 = func
                    ret= new_func(*args, **kwargs)
                    return ret + 1

                return wrapped_func

            return wrapper

        self.assertEqual(test_aop_module.nested_func_to_wrap_deref(5), 5)
        watch_setting = WatchSetting(
            method_name="nested_func_to_wrap_deref",
            watch_expr="args,kwargs",
            module_name="flight_profiler.test.util.test_aop.test_aop_module",
            nested_method="nested_func"
        )
        wrapper_result = aop_decorator.add_func_wrapper(
            test_aop_module, None, "nested_func_to_wrap_deref", watch_func, watch_setting, ["time", "inspect", "types"], nested_method="nested_func",
            module_name="flight_profiler.test.util.test_aop.test_aop_module"
        )
        watch_setting.nested_code_obj = wrapper_result.value.nested_code_obj
        self.assertEqual(test_aop_module.nested_func_to_wrap_deref(5), 6)

        aop_decorator.clear_func_wrapper(
            test_aop_module, None, "nested_func_to_wrap_deref", wrapper_result.value
        )
        self.assertEqual(test_aop_module.nested_func_to_wrap_deref(5), 5)

    def test_wrap_async_module_func(self):
        from flight_profiler.test.util.test_aop import test_aop_module

        def watch_func(watch_setting):
            def wrapper(func):
                @functools.wraps(func)
                async def wrapped_func(*args, **kwargs):
                    ret = await func(*args, **kwargs)
                    return ret + 1

                return wrapped_func

            return wrapper

        self.assertEqual(asyncio.run(test_aop_module.async_func_to_wrap(5)), 5)
        wrapper_result = aop_decorator.add_func_wrapper(
            test_aop_module, None, "async_func_to_wrap", watch_func, None, ["time"]
        )
        self.assertEqual(asyncio.run(test_aop_module.async_func_to_wrap(5)), 6)

        aop_decorator.clear_func_wrapper(
            test_aop_module, None, "async_func_to_wrap", wrapper_result.value
        )
        self.assertEqual(asyncio.run(test_aop_module.async_func_to_wrap(5)), 5)

    def test_wrap_class_func(self):
        from flight_profiler.test.util.test_aop import test_aop_class_module
        from flight_profiler.test.util.test_aop.test_aop_class_module import (
            TestAopClass,
        )

        def watch_func(watch_setting):
            def wrapper(func):
                def wrap_func(*args, **kwargs):
                    ret = func(*args, **kwargs)
                    return ret + 1

                return wrap_func

            return wrapper

        test_aop = TestAopClass(5)
        self.assertEqual(test_aop.cls_func_to_wrap(), 5)
        wrapper_result = aop_decorator.add_func_wrapper(
            test_aop_class_module,
            "TestAopClass",
            "cls_func_to_wrap",
            watch_func,
            None,
            ["time"],
        )
        self.assertFalse(wrapper_result.failed)
        self.assertEqual(test_aop.cls_func_to_wrap(), 6)

        aop_decorator.clear_func_wrapper(
            test_aop_class_module,
            "TestAopClass",
            "cls_func_to_wrap",
            wrapper_result.value,
        )
        self.assertEqual(test_aop.cls_func_to_wrap(), 5)


if __name__ == "__main__":
    unittest.main()
