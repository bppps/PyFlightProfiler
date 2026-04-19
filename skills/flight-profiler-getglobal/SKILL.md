---
name: flight-profiler-getglobal
description: Inspect Python module global field or class static field value in a running Python process. Use this for safe, read-only inspection of global variables, configuration objects, or class-level state.
---

# flight-profiler-getglobal

Inspect Python module global field or class static field value. A safe, read-only way to check configuration, feature flags, counters, or any module-level / class-level state.

> **Prerequisites:** Read the **flight-profiler-attach** skill first for platform requirements, installation, permissions, and connection details.

## When to Use

- You want to check the current value of a global variable or config setting
- You need to inspect a class static field
- You want a safe, read-only alternative to opening a console
- You need to evaluate an expression on a global object

## Usage

```
flight_profiler <pid> --cmd "getglobal module [class] field [options]" --no-color
```

## Positional Arguments

- `module` — the module name as it would be imported in the target process. For example, if the target code does `from myapp.config import settings`, then module is `myapp.config`. PyFlightProfiler locates the module via `importlib.import_module`. If you're unsure of the module name, run a separate command to resolve it first: `flight_profiler <pid> --cmd "module /absolute/path/to/file.py" --no-color`, then use the returned module name here.
- `class` (optional) — class name for static field inspection
- `field` — field name to inspect

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-x, --expand <value>` | Object tree expand level (1-6, or -1 for unlimited) | `2` |
| `-e, --expr <value>` | Expression to evaluate on the target. The variable `target` refers to the resolved field value. | `target` |
| `-r, --raw` | Use `__str__` (equivalent to `print(obj)`) instead of default JSON serialization | off |
| `-v, --verbose` | Display all nested items in list/dict without truncation | off |

## Choosing the Right `-e` Expression

`-e` directly controls what you see in the output. **Always match the user's intent to the right expression** — the default `target` shows the entire object.

| User intent | `-e` value |
|------------|------------|
| See the entire variable | `target` (default) |
| See a specific dict key | `target['key']` |
| See a nested field | `target['a']['b']` |
| See an object attribute | `target.attr` |
| Get the length / count | `len(target)` |
| Check a condition | `target['key'] == expected` |
| List all keys | `list(target.keys())` |

## Output Format

getglobal returns immediately with a single result block:

```
  EXPR:       target
  TYPE:       <class 'dict'>
  VALUE:      {
                "database_url": "postgresql://localhost:5432/mydb",
                "debug": True,
                "max_connections": 10,
                "nested": {
                  "level1": {'level2': 'deep_value'}
                }
              }
```

### Output Fields

| Field | Description |
|-------|-------------|
| `EXPR` | The expression used to extract the displayed value (default `target`) |
| `TYPE` | Python type of the expression result |
| `VALUE` | The value, formatted as JSON (or `__str__` if `-r`) |

When the expression fails (e.g., accessing a nonexistent attribute):

```
  EXPR:               target.nonexistent
  FAILED_REASON:      AttributeError: 'dict' object has no attribute 'nonexistent'
```

## Examples

### 1. Module global variable (dict)

```bash
flight_profiler <pid> --cmd "getglobal __main__ config" --no-color
```

```
  EXPR:       target
  TYPE:       <class 'dict'>
  VALUE:      {
                "database_url": "postgresql://localhost:5432/mydb",
                "debug": True,
                "max_connections": 10,
                "nested": {
                  "level1": {'level2': 'deep_value'}
                }
              }
```

Note: at default expand level (`-x 2`), the `nested.level1` dict is shown as a compact repr. Use `-x 3` to expand deeper (see example 5).

### 2. Module global variable (simple type)

```bash
flight_profiler <pid> --cmd "getglobal __main__ counter" --no-color
```

```
  EXPR:       target
  TYPE:       <class 'int'>
  VALUE:      61
```

The value reflects the live state — `counter` was 42 at startup but has been incrementing.

### 3. Class static field

```bash
flight_profiler <pid> --cmd "getglobal __main__ AppConfig VERSION" --no-color
```

```
  EXPR:       target
  TYPE:       <class 'str'>
  VALUE:      "2.1.0"
```

### 4. Class static field (dict)

```bash
flight_profiler <pid> --cmd "getglobal __main__ AppConfig FEATURES" --no-color
```

```
  EXPR:       target
  TYPE:       <class 'dict'>
  VALUE:      {
                "caching": False,
                "logging": True,
                "metrics": True
              }
```

### 5. Deeper expand with `-x 3`

Expands nested objects one level deeper than default:

```bash
flight_profiler <pid> --cmd "getglobal __main__ config -x 3" --no-color
```

```
  EXPR:       target
  TYPE:       <class 'dict'>
  VALUE:      {
                "database_url": "postgresql://localhost:5432/mydb",
                "debug": True,
                "max_connections": 10,
                "nested": {
                  "level1": {
                    "level2": "deep_value"
                  }
                }
              }
```

Compare with example 1 — `nested.level1.level2` is now fully expanded.

### 6. Expression — extract a specific field

Use `-e` to drill into the object without expanding the entire tree:

```bash
flight_profiler <pid> --cmd "getglobal __main__ config -e target['database_url']" --no-color
```

```
  EXPR:       target['database_url']
  TYPE:       <class 'str'>
  VALUE:      "postgresql://localhost:5432/mydb"
```

### 7. Expression — compute a value

```bash
flight_profiler <pid> --cmd "getglobal __main__ active_users -e len(target)" --no-color
```

```
  EXPR:       len(target)
  TYPE:       <class 'int'>
  VALUE:      5
```

### 8. Expression on class static field

```bash
flight_profiler <pid> --cmd "getglobal __main__ CacheManager _store -e target['user:1']" --no-color
```

```
  EXPR:       target['user:1']
  TYPE:       <class 'dict'>
  VALUE:      {
                "age": 30,
                "name": "alice"
              }
```

### 9. Raw mode `-r` (use `__str__` instead of JSON)

```bash
flight_profiler <pid> --cmd "getglobal __main__ config -r" --no-color
```

```
  EXPR:       target
  TYPE:       <class 'dict'>
  VALUE:      {'database_url': 'postgresql://localhost:5432/mydb', 'debug': True, 'max_connections': 10, 'nested': {'level1': {'level2': 'deep_value'}}}
```

Entire dict on one line using Python's native `__str__` representation.

### 10. Verbose mode `-v`

Shows all items in lists/dicts without truncation. Useful when collections are large and default output truncates them:

```bash
flight_profiler <pid> --cmd "getglobal __main__ active_users -v" --no-color
```

```
  EXPR:       target
  TYPE:       <class 'list'>
  VALUE:      [
                "alice",
                "bob",
                "charlie",
                "dave",
                "eve"
              ]
```

## `-e` Expression Guide

The `-e` option accepts any valid Python expression. The variable `target` refers to the resolved global variable or class static field.

**Common patterns:**

```bash
# Default: show the entire variable
-e target

# Access a dict key
-e target['key']

# Access a nested field
-e target['nested']['level1']

# Access an attribute
-e target.attribute

# Get length
-e len(target)

# Get type
-e type(target)

# List comprehension
-e [k for k in target.keys()]

# Check a condition
-e target['debug'] == True

# Slice a list
-e target[:3]
```

## Handling Command Output

- **Long output**: if the inspected object is large (e.g., a big dict or deeply nested config), redirect the output to a file for the user to review later:
  ```bash
  flight_profiler <pid> --cmd "getglobal __main__ config -x 4 -v" --no-color > /tmp/getglobal_output.txt
  ```
- **Short output**: if the result is brief (a single value, small dict, or simple type), display the full result directly to the user so they can see it immediately.

## Handling Large Objects

When an object is too large to serialize or the output is truncated/incomplete:

1. **Prefer minimal extraction** — use `-e` to extract only the fields you need, instead of the entire object:
   ```bash
   # Instead of serializing the entire config:
   -e target
   # Extract only the field you care about:
   -e target['database_url']
   -e target['nested']['key']
   -e type(target),len(target)
   ```

2. **Use `-v` (verbose)** — if you do need the full object, add `-v` to disable truncation so all nested items in lists/dicts are shown completely.

## Tips

- getglobal is read-only and safe — it never modifies the target process state
- Default expand level is 2 (deeper than watch's default of 1) — use `-x 3` or higher for deeply nested objects
- Use `-e` expressions to drill into nested objects without expanding the entire tree
- `-r` (raw) uses `__str__` (like `print(obj)`) — useful for objects with custom `__str__` or when you want the native Python representation
- For writable operations or complex logic, use `console` instead
- Combine with `module` command if you only know the file path

## Related Commands

- **console** — interactive REPL for read-write access (getglobal is read-only and safer)
- **vmtool getInstances** — find instances by class (getglobal accesses known variables)
- **watch** — observe a function's inputs/outputs over time (getglobal is for point-in-time inspection)

## Source Files

- CLI plugin: `flight_profiler/plugins/getglobal/cli_plugin_getglobal.py`
- Parser: `flight_profiler/plugins/getglobal/getglobal_parser.py`
- Server plugin: `flight_profiler/plugins/getglobal/server_plugin_getglobal.py`
