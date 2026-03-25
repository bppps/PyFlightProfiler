import os
import time
import unittest

from flight_profiler.test.plugins.profile_integration import ProfileIntegration


class TracePluginTest(unittest.TestCase):

    def test_trace(self):
        current_directory = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(current_directory, "trace_server_script.py")
        integration = ProfileIntegration()
        integration.start(file, 15)
        try:
            integration.execute_profile_cmd("trace __main__ test_func -i 0")
            process = integration.client_process
            find = False
            start = time.time()
            while time.time() - start < 15:
                output = process.stdout.readline()
                print(output)
                if output:
                    line = str(output)
                    if (
                        line.find("thread=") >= 0
                        and line.find("tid=") >= 0
                        and line.find("daemon=") >= 0
                        and line.find("cost=") >= 0
                    ):
                        find = True
                        break
                else:
                    break

            self.assertTrue(find)
        except:
            raise
        finally:
            integration.stop()

    def test_trace_class_method(self):
        current_directory = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(current_directory, "trace_server_script.py")
        integration = ProfileIntegration()
        integration.start(file, 15)
        try:
            integration.execute_profile_cmd("trace __main__ A hello")
            process = integration.client_process
            find = False
            start = time.time()
            while time.time() - start < 15:
                output = process.stdout.readline()
                print(output)
                if output:
                    line = str(output)
                    if (
                        line.find("thread=") >= 0
                        and line.find("tid=") >= 0
                        and line.find("daemon=") >= 0
                        and line.find("cost=") >= 0
                    ):
                        find = True
                        break
                else:
                    break

            self.assertTrue(find)
        except:
            raise
        finally:
            integration.stop()

    def test_trace_class_nested_method(self):
        current_directory = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(current_directory, "trace_server_script.py")
        integration = ProfileIntegration()
        integration.start(file, 15)
        try:
            integration.execute_profile_cmd("trace __main__ A nested_hello -nm nested_inner")
            process = integration.client_process
            find = False
            start = time.time()
            while time.time() - start < 15:
                output = process.stdout.readline()
                print(output)
                if output:
                    line = str(output)
                    if (
                        line.find("thread=") >= 0
                        and line.find("tid=") >= 0
                        and line.find("daemon=") >= 0
                        and line.find("cost=") >= 0
                    ):
                        find = True
                        break
                else:
                    break

            self.assertTrue(find)
        except:
            raise
        finally:
            integration.stop()

    def test_trace_class_depth_method(self):
        current_directory = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(current_directory, "trace_server_script.py")
        integration = ProfileIntegration()
        integration.start(file, 15)
        try:
            integration.execute_profile_cmd("trace __main__ A depth_call -d 3 -i 0")
            process = integration.client_process
            find = False
            start = time.time()
            while time.time() - start < 15:
                output = process.stdout.readline()
                print(output)
                if output:
                    line = str(output)
                    if (
                        line.find("thread=") >= 0
                        and line.find("tid=") >= 0
                        and line.find("daemon=") >= 0
                        and line.find("cost=") >= 0
                    ):
                        find = True
                        break
                else:
                    break

            self.assertTrue(find)
        except:
            raise
        finally:
            integration.stop()


if __name__ == "__main__":
    test = TracePluginTest()
    test.test_trace()
    test.test_trace_class_method()
