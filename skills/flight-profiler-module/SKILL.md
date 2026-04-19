---
name: flight-profiler-module
description: Translate a file path to its Python module name in a running Python process. Use this when you know a file path but need the module name for commands like watch, trace, or reload.
---

# flight-profiler-module

Translate a file path to its corresponding Python module name. Most diagnostic commands (watch, trace, reload, getglobal) require a module name — use this to find it from a file path.

> **Prerequisites:** Read the **flight-profiler-attach** skill first for platform requirements, installation, permissions, and connection details.

## When to Use

- You know the file path but not the module name needed by watch/trace/reload/getglobal
- The module name isn't obvious from the file structure (e.g., namespace packages, src layouts)
- You want to confirm the exact module name as seen by the target process's `sys.modules`

## Usage

```
flight_profiler <pid> --cmd "module <filepath>" --no-color
```

## Arguments

- `filepath` — Absolute or relative path to the Python source file. The path is resolved to an absolute path and checked for existence on the client side before sending to the target process.

## Output Format

**Success** — returns the module name as plain text:

```
__main__
```

**Failure (file not imported)** — the file exists but is not loaded in the target process:

```
filepath: /path/to/file.py is not imported in target process.
```

**Failure (file not found)** — the path does not exist on disk (checked client-side):

```
✗ Parse module argument failed: filepath /path/to/file.py does not exist.
```

## Examples

### 1. Main script file

The entry-point script is always `__main__`:

```bash
flight_profiler <pid> --cmd "module /Users/zy/workspace/app/main_script.py" --no-color
```

```
__main__
```

### 2. Standard library module

```bash
flight_profiler <pid> --cmd "module /Users/zy/miniforge3/envs/py39/lib/python3.9/json/__init__.py" --no-color
```

```
json
```

### 3. Module name may differ from file name

`os.path` on POSIX is actually backed by `posixpath.py`. The module command returns the real module name:

```bash
flight_profiler <pid> --cmd "module /Users/zy/miniforge3/envs/py39/lib/python3.9/posixpath.py" --no-color
```

```
posixpath
```

This is why querying the target process is important — the module name depends on `sys.modules`, not the file path structure.

### 4. File exists but not imported by target process

```bash
flight_profiler <pid> --cmd "module /Users/zy/workspace/app/unused_module.py" --no-color
```

```
filepath: /Users/zy/workspace/app/unused_module.py is not imported in target process.
```

This means the file was never imported — the module name cannot be resolved. Check if the code path that uses this file has been triggered.

### 5. File path does not exist

```bash
flight_profiler <pid> --cmd "module /nonexistent/path.py" --no-color
```

```
✗ Parse module argument failed: filepath /nonexistent/path.py does not exist.
```

## Typical Workflow

The module command is a prerequisite step for other diagnostic commands. Use it when you only have a file path:

```bash
# Step 1: Find the module name
flight_profiler <pid> --cmd "module /home/admin/myapp/services/order.py" --no-color
# → myapp.services.order

# Step 2: Use the module name with watch/trace/getglobal
flight_profiler <pid> --cmd "watch myapp.services.order OrderService process_order -n 1" --no-color
flight_profiler <pid> --cmd "trace myapp.services.order OrderService process_order -n 1" --no-color
flight_profiler <pid> --cmd "getglobal myapp.services.order config" --no-color
```

## Tips

- The module name depends on the target process's `sys.path`, which may differ from what you'd expect
- This command queries the target process for the actual module mapping via `sys.modules`, so it always gives the correct name
- If the file is not imported yet (lazy import, conditional import), trigger the code path first, then retry
- For the main entry-point script, the module name is always `__main__`

## Related Commands

- **watch** / **trace** / **reload** / **getglobal** — all require module name as first argument

## Source Files

- CLI plugin: `flight_profiler/plugins/module/cli_plugin_module.py`
- Parser: `flight_profiler/plugins/module/module_parser.py`
- Server plugin: `flight_profiler/plugins/module/server_plugin_module.py`
