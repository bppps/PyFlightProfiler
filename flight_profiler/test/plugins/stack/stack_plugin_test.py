import os
import time
import unittest

from flight_profiler.test.plugins.profile_integration import ProfileIntegration
from flight_profiler.utils.env_util import is_linux


class StackPluginTest(unittest.TestCase):

    def test_stack(self):
        current_directory = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(current_directory, "stack_server_script.py")
        integration = ProfileIntegration()
        integration.start(file, 15)
        try:
            integration.execute_profile_cmd("stack")
            process = integration.client_process
            find = False
            start = time.time()
            target_literal: str = (
                "Current thread" if not is_linux() else "Traceback for thread"
            )
            while time.time() - start < 15:
                output = process.stdout.readline()
                print(output)
                if output:
                    line = str(output)
                    if line.find(target_literal) >= 0:
                        find = True
                        break
                else:
                    break

            self.assertTrue(find)
        except:
            raise
        finally:
            integration.stop()

    def test_stack_filepath(self):
        current_directory = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(current_directory, "stack_server_script.py")
        stack_file = os.path.join(current_directory, "stack.log")
        integration = ProfileIntegration()
        integration.start(file, 15)
        target_literal: str = (
            "Current thread" if not is_linux() else "Traceback for thread"
        )
        try:
            if is_linux():
                integration.execute_profile_cmd(f"stack -f {stack_file}")
            else:
                integration.execute_profile_cmd(f"stack {stack_file}")
            process = integration.client_process
            find = False
            start = time.time()
            while time.time() - start < 15:
                output = process.stdout.readline()
                print(output)
                if output:
                    line = str(output)
                    if line.find(f"Write stack to {stack_file} successfully!") >= 0:
                        find = True
                        break
                else:
                    break

            another_find = False
            with open(stack_file, "r") as f:
                lines = f.readlines()
                for line in lines:
                    if line.find(target_literal) >= 0:
                        another_find = True
                        break
            self.assertTrue(find)
            self.assertTrue(another_find)
        except:
            raise
        finally:
            os.remove(stack_file)
            integration.stop()

    def test_stack_native_frames(self):
        if not is_linux():
            return
        current_directory = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(current_directory, "stack_server_script.py")
        integration = ProfileIntegration()
        integration.start(file, 15)
        try:
            integration.execute_profile_cmd("stack --native")
            process = integration.client_process
            find = False
            start = time.time()
            while time.time() - start < 15:
                output = process.stdout.readline()
                print(output)
                if output:
                    line = str(output)
                    if line.find("(C)") >= 0:
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
    test = StackPluginTest()
    test.test_stack()
    test.test_stack_filepath()
