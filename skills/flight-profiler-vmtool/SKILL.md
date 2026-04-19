---
name: flight-profiler-vmtool
description: Inspect live Python class instances in a running process — find all instances of a class, examine their attributes/state, or invoke methods on them. Also supports forcing GC. Use this when you need to probe object-level runtime state beyond what watch/getglobal can provide.
---

# flight-profiler-vmtool

Inspect live Python class instances at runtime. The primary use case is **state inspection** — find all instances of a given class and examine their current attributes — and **method invocation** — call methods on found instances via `-e` expressions. Also supports forcing a garbage collection cycle.

> **Prerequisites:** Read the **flight-profiler-attach** skill first for platform requirements, installation, permissions, and connection details.

## When to Use

- You want to find all live instances of a specific class and inspect their current attribute values (e.g., connection status, queue size, internal flags)
- You need to invoke a method on a live instance to trigger a diagnostic action (e.g., `instances[0].get_stats()`, `instances[0].dump_state()`)
- You want to check how many instances of a class exist (potential memory leak investigation)
- You need to filter instances by attribute to find the ones in a specific state (e.g., all connections with `status == "error"`)
- You suspect objects aren't being garbage collected and want to force GC

## Usage

```
flight_profiler <pid> --cmd "vmtool -a <action> [options]" --no-color
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-a, --action` | Action: `forceGc` or `getInstances` | required |
| `-c, --class` | Class locator: `module class` | required for getInstances |
| `-e, --expr <value>` | Expression to evaluate on found instances. Variable is `instances` (a list). | `instances` |
| `-x, --expand <value>` | Object tree expand level (1-6) | `1` |
| `-n, --limit <value>` | Max instances to collect (-1 for unlimited) | `10` |
| `-r, --raw` | Use `__str__` (equivalent to `print(obj)`) instead of default JSON serialization | off |
| `-v, --verbose` | Display all nested items in list/dict without truncation | off |

## Choosing the Right `-e` Expression

`-e` directly controls what you see in the output. **Always match the user's intent to the right expression** — the default `instances` dumps all found objects.

| User intent | `-e` value |
|------------|------------|
| See all instances | `instances` (default) |
| Count how many instances exist | `len(instances)` |
| Inspect a single instance in detail | `instances[0]` (combine with `-x 2`) |
| Filter instances by attribute | `[i for i in instances if i.attr=='val']` |
| Extract one field from all instances | `[i.field for i in instances]` |
| Check if any instance matches a condition | `any(i.status=='error' for i in instances)` |
| Invoke a diagnostic method on an instance | `instances[0].get_stats()` |
| Invoke a method on all instances | `[i.get_status() for i in instances]` |

## Output Format

### forceGc

Returns a plain text message:

```
Gc execute successfully, totally 76 unreachable objects are freed.
```

### getInstances

Returns an expression result block (same format as getglobal/watch):

```
  EXPR:       instances
  TYPE:       <class 'list'>
  VALUE:      [
                Connection({'host': 'queue', 'port': 5672, 'status': 'error'}),
                Connection({'host': 'cache', 'port': 6379, 'status': 'idle'}),
                Connection({'host': 'db-replica', 'port': 5433, 'status': 'active'}),
                Connection({'host': 'db-primary', 'port': 5432, 'status': 'active'})
              ]
```

| Field | Description |
|-------|-------------|
| `EXPR` | The expression used (default `instances`) |
| `TYPE` | Python type of the expression result |
| `VALUE` | The value, formatted as JSON (or `__str__` if `-r`) |

## Examples

### 1. Force garbage collection

```bash
flight_profiler <pid> --cmd "vmtool -a forceGc" --no-color
```

```
Gc execute successfully, totally 76 unreachable objects are freed.
```

### 2. Find all instances of a class

```bash
flight_profiler <pid> --cmd "vmtool -a getInstances -c __main__ Connection" --no-color
```

```
  EXPR:       instances
  TYPE:       <class 'list'>
  VALUE:      [
                Connection({'host': 'queue', 'port': 5672, 'status': 'error'}),
                Connection({'host': 'cache', 'port': 6379, 'status': 'idle'}),
                Connection({'host': 'db-replica', 'port': 5433, 'status': 'active'}),
                Connection({'host': 'db-primary', 'port': 5432, 'status': 'active'})
              ]
```

### 3. Count instances

```bash
flight_profiler <pid> --cmd "vmtool -a getInstances -c __main__ Connection -e len(instances)" --no-color
```

```
  EXPR:       len(instances)
  TYPE:       <class 'int'>
  VALUE:      4
```

### 4. Inspect a specific instance with expanded attributes

Use `-e instances[0]` to pick one instance and `-x 2` to expand its attributes:

```bash
flight_profiler <pid> --cmd "vmtool -a getInstances -c __main__ Connection -e instances[0] -x 2" --no-color
```

```
  EXPR:       instances[0]
  TYPE:       <class '__main__.Connection'>
  VALUE:      Connection({
                "host": "queue",
                "port": 5672,
                "status": "error"
              })
```

### 5. Filter instances by attribute

Find only instances with `status == "error"`. Note: list comprehension expressions with quotes need careful shell escaping:

```bash
flight_profiler <pid> --cmd 'vmtool -a getInstances -c __main__ Connection -e "[i for i in instances if i.status==\"error\"]"' --no-color
```

```
  EXPR:       [i for i in instances if i.status=="error"]
  TYPE:       <class 'list'>
  VALUE:      [
                Connection({'host': 'queue', 'port': 5672, 'status': 'error'})
              ]
```

### 6. Raw mode `-r` (use `__str__` instead of JSON)

```bash
flight_profiler <pid> --cmd "vmtool -a getInstances -c __main__ Connection -r" --no-color
```

```
  EXPR:       instances
  TYPE:       <class 'list'>
  VALUE:      [<__main__.Connection object at 0x1056debb0>, <__main__.Connection object at 0x1056dec10>, ...]
```

Shows Python's default `__str__` representation for each object.

### 7. Limit collected instances with `-n`

`-n 2` collects at most 2 instances:

```bash
flight_profiler <pid> --cmd "vmtool -a getInstances -c __main__ Connection -n 2" --no-color
```

```
  EXPR:       instances
  TYPE:       <class 'list'>
  VALUE:      [
                Connection({'host': 'queue', 'port': 5672, 'status': 'error'}),
                Connection({'host': 'cache', 'port': 6379, 'status': 'idle'})
              ]
```

### 8. Inspect instances of a different class

```bash
flight_profiler <pid> --cmd "vmtool -a getInstances -c __main__ Task -e instances[0] -x 2" --no-color
```

```
  EXPR:       instances[0]
  TYPE:       <class '__main__.Task'>
  VALUE:      Task({
                "name": "cleanup_logs",
                "priority": 1,
                "task_id": 3
              })
```

## `-e` Expression Guide

The `-e` option accepts any valid Python expression. The variable `instances` is a list containing the found class instances.

**Common patterns:**

```bash
# Default: show all instances
-e instances

# Count instances
-e len(instances)

# Pick a specific instance
-e instances[0]

# Filter by attribute
-e "[i for i in instances if i.status=='error']"

# Get a specific attribute from all instances
-e "[i.host for i in instances]"

# Check if any instance matches a condition
-e "any(i.status=='error' for i in instances)"

# Aggregate values
-e "sum(i.priority for i in instances)"

# Invoke a method on an instance
-e instances[0].get_stats()
-e instances[0].health_check()

# Invoke a method on all instances
-e "[i.get_status() for i in instances]"
```

**Note:** When using list comprehensions or expressions with quotes in shell, use single quotes for the outer `--cmd` and escaped double quotes inside the expression (see example 5).

**Note:** `-e` expressions execute inside the target process. Invoking methods on instances will actually run them — use this for read-only diagnostic methods (e.g., `get_stats()`, `dump_state()`). Avoid calling methods with side effects unless you intend to.

## Handling Command Output

- **Long output**: if many instances are found or instance attributes are large, redirect the output to a file for the user to review later:
  ```bash
  flight_profiler <pid> --cmd "vmtool -a getInstances -c __main__ Connection -n -1 -v" --no-color > /tmp/vmtool_output.txt
  ```
- **Short output**: if the result is brief (e.g., a count via `-e len(instances)`, or a few instances), display the full result directly to the user so they can see it immediately.

## Handling Large Objects

When an object is too large to serialize or the output is truncated/incomplete:

1. **Prefer minimal extraction** — use `-e` to extract only the fields you need, instead of the entire instance:
   ```bash
   # Instead of serializing the entire instance:
   -e instances[0]
   # Extract only the field you care about:
   -e instances[0].status
   -e [i.host for i in instances]
   -e type(instances[0]),len(vars(instances[0]))
   ```

2. **Use `-v` (verbose)** — if you do need the full object, add `-v` to disable truncation so all nested items in lists/dicts are shown completely.

## Tips

- Use `-e` expressions to filter and analyze instances without dumping everything
- The `instances` variable in `-e` is a list — you can use any Python list operation on it
- Use `-n` to limit collection when you only need a sample — collecting all instances of a very common class can be slow
- Instance order is determined by `gc.get_referrers()` — it may not match creation order

## Related Commands

- **getglobal** — inspect a known global variable (vmtool is for finding unknown instances)
- **console** — for more complex inspection logic

## Source Files

- CLI plugin: `flight_profiler/plugins/vmtool/cli_plugin_vmtool.py`
- Parser: `flight_profiler/plugins/vmtool/vmtool_parser.py`
- Server plugin: `flight_profiler/plugins/vmtool/server_plugin_vmtool.py`
