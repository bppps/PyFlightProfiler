---
name: flight-profiler-reload
description: Hot-reload a Python function implementation from the latest file content without restarting the process. Use this to apply code fixes live after identifying a bug with watch/trace.
---

# flight-profiler-reload

Reload function implementation based on the latest file content without restarting the process. Enables live patching — edit the source file, then reload to apply the change immediately.

> **Prerequisites:** Read the **flight-profiler-attach** skill first for platform requirements, installation, permissions, and connection details.

## When to Use

- You've identified a bug via watch/trace and want to apply a fix without restarting
- You're iterating on a fix in a long-running process where restart is expensive
- You want to verify a code change takes effect before deploying
- You want to add `print()` or `logging` statements into a function for auxiliary diagnostics — the output will appear in the target process's stdout/log. This is useful when you know where the process log is directed (e.g., a log file, container stdout, or a terminal). Note: reload is not limited to adding prints — it can change the actual execution logic of the method as well

## Usage

```
flight_profiler <pid> --cmd "reload module [class] method [-v]" --no-color
```

## Positional Arguments

- `module` — the module name as it would be imported in the target process. For example, if the target code does `from myapp.utils import helper`, then module is `myapp.utils`. PyFlightProfiler locates the module via `importlib.import_module`. If you're unsure of the module name, run a separate command to resolve it first: `flight_profiler <pid> --cmd "module /absolute/path/to/file.py" --no-color`, then use the returned module name here.
- `class` (optional) — class name if method belongs to a class
- `method` — target method name

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-v, --verbose` | Display the full method source after reload. Without `-v`, methods longer than 20 lines are truncated (first 10 + last 10 lines). | off |

## Output Format

**Success** — function was reloaded with new code:

```
Reload is done successfully.
Located file path: /path/to/file.py
Extracted method source:
def compute(x, y):
    result = x + y
    print(f"compute({x}, {y}) = {result}")
    return result
```

**No change** — the source file has not been modified since the function was last loaded:

```
Error: Method source has not changed.
Located file path: /path/to/file.py
Extracted method source:
def compute(x, y):
    return x + y
```

**Error** — module/method not found or other failure:

```
Error: Cannot locate method nonexistent in module __main__.
```

### Output Fields

| Field | Description |
|-------|-------------|
| Status line | "Reload is done successfully." or "Error: \<reason\>." |
| `Located file path` | The source file path resolved from the module (shown when module is found) |
| `Extracted method source` | The method source code read from the file (shown when method is located) |

## Examples

### 1. Reload unchanged function — source not modified

If the file hasn't been edited since the function was loaded, reload reports no change:

```bash
flight_profiler <pid> --cmd "reload __main__ compute" --no-color
```

```
Error: Method source has not changed.
Located file path: /Users/zy/workspace/app/main.py
Extracted method source:
def compute(x, y):
    return x + y
```

This is expected — edit the source file first, then reload.

### 2. Reload module-level function after edit

After editing `compute` in the source file:

```bash
flight_profiler <pid> --cmd "reload __main__ compute -v" --no-color
```

```
Reload is done successfully.
Located file path: /Users/zy/workspace/app/main.py
Extracted method source:
def compute(x, y):
    result = x + y
    print(f"compute({x}, {y}) = {result}")
    return result
```

### 3. Reload class method after edit

After editing `Calculator.add` in the source file:

```bash
flight_profiler <pid> --cmd "reload __main__ Calculator add -v" --no-color
```

```
Reload is done successfully.
Located file path: /Users/zy/workspace/app/main.py
Extracted method source:
    def add(self, a, b):
        print(f"Calculator.add({a}, {b})")
        return a + b
```

### 4. Nonexistent method

```bash
flight_profiler <pid> --cmd "reload __main__ nonexistent" --no-color
```

```
Error: Cannot locate method nonexistent in module __main__.
```

### 5. Nonexistent module

```bash
flight_profiler <pid> --cmd "reload nonexistent_module func" --no-color
```

```
Error: Unexpected error during reload: No module named 'nonexistent_module'.
```

## Typical Debug-Fix Workflow

The simplest cycle is: **edit source → reload → observe the effect**. If the method is on a regularly triggered call path (e.g., handling HTTP requests), you'll see the change take effect immediately after reload.

For deeper investigation — such as observing internal method arguments, return values, or call trees — use watch/trace before and after reload:

```bash
# Optional: use watch/trace to inspect internal behavior before the fix
flight_profiler <pid> --cmd "watch __main__ compute -n 3" --no-color

# Step 1: Edit the source file to fix the issue
# (use Edit tool to modify the function)

# Step 2: Apply the fix live and verify the new source
flight_profiler <pid> --cmd "reload __main__ compute -v" --no-color

# Optional: use watch/trace to verify internal behavior after the fix
flight_profiler <pid> --cmd "watch __main__ compute -n 3" --no-color
```

If you edited multiple methods in one fix, reload each method separately:

```bash
# Reload each modified method individually
flight_profiler <pid> --cmd "reload __main__ Calculator validate -v" --no-color
flight_profiler <pid> --cmd "reload __main__ Calculator process -v" --no-color
flight_profiler <pid> --cmd "reload __main__ helper_func -v" --no-color
```

## Limitations

- **Method-level only** — reload operates at the function/method level. It cannot reload module-level statements, class definitions, global variable assignments, or import changes. Only the function body is replaced.
- **One method per reload** — each reload command updates exactly one method. If a fix spans multiple methods, run reload once for each modified method.
- **All changes must be inside the function body** — reload only replaces the function body. Any new code — including `import` statements — must be placed inside the function. Python supports function-level imports, so move them into the body:

```python
# WRONG — module-level import is outside the function body, reload ignores it
import json

def process(data):
    return json.dumps(data)

# CORRECT — import inside the function body, reload picks it up
def process(data):
    import json
    return json.dumps(data)
```
- **No class restructuring** — adding/removing methods, changing inheritance, or modifying class-level attributes requires a process restart.

## Tips

- Always use `-v` to verify the reloaded source matches what you expect
- The reload reads the current file on disk — make sure your edits are saved before reloading
- Reload replaces the function object's code — existing references to the function will use the new implementation
- For methods longer than 20 lines, the source is truncated by default (first 10 + last 10 lines). Use `-v` to see the full source.
- "Method source has not changed" means the bytecode compiled from the file matches the running code — the file hasn't been modified

## Related Commands

- **watch** / **trace** — diagnose the issue before reloading, and verify the fix after reloading
- **console** — for one-off fixes that don't warrant editing the source file, or to execute new imports before reload

## Source Files

- CLI plugin: `flight_profiler/plugins/reload/cli_plugin_reload.py`
- Parser: `flight_profiler/plugins/reload/reload_parser.py`
- Server plugin: `flight_profiler/plugins/reload/server_plugin_reload.py`
