
import sys
import os
import re
import subprocess

if __name__ == "__main__": # if running as a script for individual testing
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sources.tools.tools import Tools

class PyInterpreter(Tools):
    """
    This class is a tool to allow agent for python code execution.
    """
    def __init__(self):
        super().__init__()
        self.tag = "python"
        self.name = "Python Interpreter"
        self.description = "This tool allows the agent to execute python code."

    def execute(self, codes:str, safety = False, timeout=300) -> str:
        """
        Execute python code in an isolated subprocess.
        The code runs in the work directory and is killed after `timeout`
        seconds, so runaway code cannot freeze the backend.
        """
        if safety and input("Execute code ? y/n") != "y":
            return "Code rejected by user."
        code = '\n\n'.join(codes)
        self.logger.info(f"Executing code:\n{code}")
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )
        except subprocess.TimeoutExpired:
            self.logger.error(f"Code execution timed out after {timeout} seconds.")
            return f"code execution failed: timed out after {timeout} seconds."
        except Exception as e:
            self.logger.error(f"Code execution failed: {str(e)}")
            return "code execution failed:" + str(e)
        if result.returncode != 0:
            self.logger.error(f"Code execution failed:\n{result.stderr}")
            return "code execution failed:" + (result.stderr or result.stdout)
        self.logger.info("Code execution finished.")
        return result.stdout

    def interpreter_feedback(self, output:str) -> str:
        """
        Provide feedback based on the output of the code execution
        """
        if self.execution_failure_check(output):
            feedback = f"[failure] Error in execution:\n{output}"
        else:
            feedback = "[success] Execution success, code output:\n" + output
        return feedback

    def execution_failure_check(self, feedback:str) -> bool:
        """
        Check if the code execution failed.
        """
        error_patterns = [
            r"expected", 
            r"errno", 
            r"failed", 
            r"traceback", 
            r"invalid", 
            r"unrecognized", 
            r"exception", 
            r"syntax", 
            r"crash", 
            r"segmentation fault", 
            r"core dumped"
        ]
        combined_pattern = "|".join(error_patterns)
        if re.search(combined_pattern, feedback, re.IGNORECASE):
            self.logger.error(f"Execution failure detected: {feedback}")
            return True
        self.logger.info("No execution success detected.")
        return False

if __name__ == "__main__":
    text = """
For Python, let's also do a quick check:

```python
print("Hello from Python!")
```

If these work, you'll see the outputs in the next message. Let me know if you'd like me to test anything specific! 

here is a save test
```python:tmp.py

def print_hello():
    hello = "Hello World"
    print(hello)

if __name__ == "__main__":
    print_hello()
```
"""
    py = PyInterpreter()
    codes, save_path = py.load_exec_block(text)
    py.save_block(codes, save_path)
    print(py.execute(codes))