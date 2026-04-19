---
name: flight-profiler-stack
description: Inspect stack frames of a running Python process including thread stacks, native C-level frames, and async coroutine stacks. Use this to see what each thread is currently doing and diagnose hangs, deadlocks, or stuck async tasks.
---

# flight-profiler-stack

Inspect stack frames of the current running process. Essential for diagnosing hangs, deadlocks, and understanding what the process is doing right now. This is a non-streaming command — it captures a snapshot and returns immediately.

> **Prerequisites:** Read the **flight-profiler-attach** skill first for platform requirements, installation, permissions, and connection details.

## When to Use

- The process appears to hang or is unresponsive — see what each thread is blocked on
- You suspect a deadlock between threads
- You need to identify which thread holds the GIL
- You want to inspect async coroutine/task stacks to find stuck asyncio tasks
- You need native C-level frames (Linux only) for debugging C extension issues or GIL contention
- You want to locate the business code file paths and module names in the target process — stack frames reveal the exact files being executed, which helps determine the correct `module`, `watch`, and `trace` command arguments

## Usage

```
flight_profiler <pid> --cmd "stack [options]" --no-color
```

## Options

| Flag | Platform | Description | Default |
|------|----------|-------------|---------|
| `--native` | Linux only | Display native (C-level) stack frames via pystack | off |
| `-a, --async` | Both | Display async coroutine/task stacks | off |
| `-f, --filepath <value>` | Both | Redirect stack output to file | none |

## Output Format

### Thread Stacks (default, Linux — pystack)

Each thread produces a traceback block:

```
Traceback for thread <tid> (<interpreter>) [<GIL status>] (most recent call last):
    (Python) File "<filename>", line <lineno>, in <funcname>
        <source_line>
```

#### Output Fields

| Field | Description |
|-------|-------------|
| `tid` | OS thread ID (numeric) |
| `interpreter` | Interpreter name (usually `python`) |
| `GIL status` | `Has the GIL`, `Waiting for the GIL`, or empty `[]` |
| `(Python)` | Indicates a Python-level frame |
| `(C)` | Indicates a native C-level frame (only with `--native`) |
| `File ...` | Source file, line number, and function name |
| Source line | The actual source code at that frame |

### Thread Stacks (macOS — CPython dump via server)

On macOS, thread stacks are fetched via the injected server using CPython's `_Py_DumpTracebackThreads`. Thread names are automatically added:

```
(<thread_name>) 0x<hex_tid> (most recent call first):
  File "<filename>", line <lineno> in <funcname>
```

> **Note:** macOS output uses "most recent call **first**" (reverse order), while Linux pystack uses "most recent call **last**" (Python traceback convention).

### Async Coroutine Stacks (`-a`)

When `-a` is used, the output shows all active asyncio tasks grouped by the thread running their event loop:

```
============================================================
Async Coroutine/Task Stacks
============================================================

Thread: <thread_name> (tid: 0x<hex_tid>)
--------------------------------------------------

  Task #1: <task_name>
    State: <state>
    Coroutine: <qualname>
    Stack (<N> frames):
      File "<filename>", line <lineno>, in <funcname>
        <source_line>

============================================================
```

#### Async Output Fields

| Field | Description |
|-------|-------------|
| `Thread` | Thread name and hex TID running the event loop |
| `Task #N` | Task index and name (from `asyncio.create_task(name=...)`) |
| `State` | `PENDING`, `WAITING`, `FINISHED`, `CANCELLED`, or `FAILED` |
| `Coroutine` | Qualified name of the coroutine function |
| `Stack` | The coroutine's `cr_await` chain showing where it is suspended |

If no active coroutines are found:
```
No active coroutines/async tasks found.

Note: Coroutines are only visible when an event loop is running.
```

## Examples

### Show all thread stacks — macOS

```bash
flight_profiler <pid> --cmd "stack" --no-color
```

Output — each thread shows its name, hex TID, and Python call stack (most recent call **first**):
```
(cpu-worker) 0x0000000170da3000 (most recent call first):
  File "stack_demo_script.py", line 28 in cpu_worker
  File "/Users/zy/miniforge3/envs/py39/lib/python3.9/threading.py", line 888 in run
  File "/Users/zy/miniforge3/envs/py39/lib/python3.9/threading.py", line 950 in _bootstrap_inner
  File "/Users/zy/miniforge3/envs/py39/lib/python3.9/threading.py", line 908 in _bootstrap

(lock-holder) 0x000000016fd97000 (most recent call first):
  File "stack_demo_script.py", line 20 in lock_holder
  File "/Users/zy/miniforge3/envs/py39/lib/python3.9/threading.py", line 888 in run
  ...

(io-worker) 0x000000016ed8b000 (most recent call first):
  File "stack_demo_script.py", line 13 in io_worker
  File "/Users/zy/miniforge3/envs/py39/lib/python3.9/threading.py", line 888 in run
  ...

(async-loop) 0x0000000171daf000 (most recent call first):
  File "/Users/zy/miniforge3/envs/py39/lib/python3.9/selectors.py", line 562 in select
  File "/Users/zy/miniforge3/envs/py39/lib/python3.9/asyncio/base_events.py", line 1854 in _run_once
  File "/Users/zy/miniforge3/envs/py39/lib/python3.9/asyncio/base_events.py", line 596 in run_forever
  ...
  File "stack_demo_script.py", line 57 in start_async_thread
  ...

(MainThread) 0x0000000207ede240 (most recent call first):
  File "stack_demo_script.py", line 74 in <module>
```

**Reading this output:**
- `(cpu-worker)` — currently at `cpu_worker` line 28, doing computation
- `(lock-holder)` — at `lock_holder` line 20, sleeping while holding a lock
- `(io-worker)` — at `io_worker` line 13, sleeping in I/O wait
- `(async-loop)` — the event loop thread, blocked in `selectors.select` (normal for async — use `-a` to see coroutine details)
- `(MainThread)` — main thread at line 74, the `while True: time.sleep(1)` loop
- Note: macOS output also includes `flight-profiler-agent` and `flight-profiler-recv-*` threads (PyFlightProfiler's internal threads) — these can be ignored

### Show all thread stacks — Linux

```bash
flight_profiler <pid> --cmd "stack" --no-color
```

Output — Linux uses pystack, showing GIL status and "most recent call **last**" order:
```
Traceback for thread 170938 (python) [Has the GIL] (most recent call last):
* - Unable to merge native stack due to insufficient native information - *
    (Python) File "/home/admin/miniforge3/lib/python3.10/threading.py", line 973, in _bootstrap
        self._bootstrap_inner()
    (Python) File "/home/admin/miniforge3/lib/python3.10/threading.py", line 1016, in _bootstrap_inner
        self.run()
    (Python) File "/home/admin/miniforge3/lib/python3.10/threading.py", line 953, in run
        self._target(*self._args, **self._kwargs)
    (Python) File "stack_demo_script.py", line 40, in cpu_worker
        total += i

Traceback for thread 170937 (python) [] (most recent call last):
    ...
    (Python) File "stack_demo_script.py", line 32, in lock_holder
        time.sleep(5)

Traceback for thread 170936 (python) [] (most recent call last):
    ...
    (Python) File "stack_demo_script.py", line 22, in io_worker
        time.sleep(2)

Traceback for thread 170934 (python) [] (most recent call last):
    ...
    (Python) File "stack_demo_script.py", line 97, in main
        time.sleep(1)
```

**Reading this output:**
- Thread `170938` (cpu_worker) `[Has the GIL]` — this thread currently holds the GIL, actively computing
- Thread `170937` (lock_holder) `[]` — sleeping in `time.sleep(5)`, holding a lock
- Thread `170936` (io_worker) `[]` — sleeping in `time.sleep(2)`
- Thread `170934` (main) `[]` — the main thread, sleeping in `time.sleep(1)`

### Key differences between macOS and Linux output

| | macOS | Linux |
|---|---|---|
| Stack order | Most recent call **first** | Most recent call **last** |
| Thread identifier | `(thread-name) 0xHEX_TID` | `thread NUMERIC_TID (python) [GIL status]` |
| GIL status | Not shown | `[Has the GIL]`, `[Waiting for the GIL]`, or `[]` |
| Source code lines | Not shown (file + line number only) | Shown inline |
| Native frames | Not supported | Supported via `--native` |

### Show native C-level frames (`--native`, Linux only)

```bash
flight_profiler <pid> --cmd "stack --native" --no-color
```

Output — mixed Python + C frames, useful for debugging C extensions or GIL contention:
```
Traceback for thread 170938 (python) [Has the GIL] (most recent call last):
    (C) File "???", line 0, in __clone (/usr/lib64/libc-2.32.so)
    (C) File "???", line 0, in start_thread (/usr/lib64/libpthread-2.32.so)
    (C) File ".../Python/thread_pthread.h", line 248, in pythread_wrapper (python3.10)
    (C) File ".../Modules/_threadmodule.c", line 1100, in thread_run (python3.10)
    (Python) File "/home/admin/miniforge3/lib/python3.10/threading.py", line 973, in _bootstrap
        self._bootstrap_inner()
    ...
    (Python) File "stack_demo_script.py", line 40, in cpu_worker
        total += i

Traceback for thread 170937 (python) [] (most recent call last):
    (C) File "???", line 0, in __clone (/usr/lib64/libc-2.32.so)
    (C) File "???", line 0, in start_thread (/usr/lib64/libpthread-2.32.so)
    ...
    (Python) File "stack_demo_script.py", line 32, in lock_holder
        time.sleep(5)
    (C) File ".../Modules/timemodule.c", line 370, in time_sleep (python3.10)
    (C) File ".../Modules/timemodule.c", line 2076, in pysleep (inlined) (python3.10)
    (C) File "???", line 0, in __select (/usr/lib64/libc-2.32.so)

Traceback for thread 170934 (python) [] (most recent call last):
    (C) File "???", line 0, in _start (python3.10)
    (C) File "???", line 0, in __libc_start_main (/usr/lib64/libc-2.32.so)
    (C) File ".../Modules/main.c", line 1094, in Py_BytesMain (python3.10)
    ...
    (Python) File "stack_demo_script.py", line 97, in main
        time.sleep(1)
    (C) File ".../Modules/timemodule.c", line 370, in time_sleep (python3.10)
    (C) File ".../Modules/timemodule.c", line 2076, in pysleep (inlined) (python3.10)
    (C) File "???", line 0, in __select (/usr/lib64/libc-2.32.so)
```

**Reading this output:**
- `(C)` frames show the native call stack — you can see `time.sleep` going into CPython's `pysleep` then into the OS `__select` syscall
- `[Has the GIL]` vs `[Waiting for the GIL]` helps identify GIL contention
- Native frames are interleaved with Python frames to show the full execution path

### Show async coroutine stacks (`-a`)

```bash
flight_profiler <pid> --cmd "stack -a" --no-color
```

Output — all active asyncio tasks grouped by thread, with their coroutine call chain (same format on both macOS and Linux):
```
============================================================
Async Coroutine/Task Stacks
============================================================

Thread: async-loop (tid: 0x171daf000)
--------------------------------------------------

  Task #1: periodic-heartbeat
    State: WAITING
    Coroutine: periodic_task
    Stack (2 frames):
      File "stack_demo_script.py", line 44, in periodic_task
        await asyncio.sleep(1)
      File ".../asyncio/tasks.py", line 649, in sleep
        return await future

  Task #2: Task-1
    State: WAITING
    Coroutine: run_async_loop
    Stack (1 frames):
      File "stack_demo_script.py", line 53, in run_async_loop
        await asyncio.gather(*tasks)

  Task #3: process-item-42
    State: WAITING
    Coroutine: process_item
    Stack (2 frames):
      File "stack_demo_script.py", line 38, in process_item
        await asyncio.sleep(3600)
      File ".../asyncio/tasks.py", line 649, in sleep
        return await future

  Task #4: fetch-api-data
    State: WAITING
    Coroutine: fetch_data
    Stack (2 frames):
      File "stack_demo_script.py", line 33, in fetch_data
        await asyncio.sleep(3600)
      File ".../asyncio/tasks.py", line 649, in sleep
        return await future

============================================================
```

**Reading this output:**
- All 4 tasks are `WAITING` — they are suspended at an `await` point
- `fetch-api-data` and `process-item-42` are waiting on `asyncio.sleep(3600)` — long-running waits, potential indicators of stuck tasks
- `periodic-heartbeat` is waiting on `asyncio.sleep(1)` — a healthy periodic task
- `Task-1` (the `run_async_loop` gather) is waiting for its child tasks to complete
- Task names come from `asyncio.create_task(name=...)` — unnamed tasks show as `Task-N`

### Save stack output to file (`-f`)

```bash
flight_profiler <pid> --cmd "stack -f ./stack.log" --no-color
```

Output:
```
✓ Write stack to ./stack.log successfully!
```

The file contains the same thread stack output as the default `stack` command. Useful when:
- The output is too long to read in the terminal
- You want to save snapshots for comparison over time
- You need to share the output with others

## Troubleshooting: No Output or Errors

### No output at all
- **Process exited** — the target process may have terminated. Verify with `ps -p <pid>`
- **Wrong PID** — for multi-process applications (gunicorn, multiprocessing), make sure you're targeting the right worker process

### `symbol _Py_DumpTracebackThreads not found`
- This occurs on macOS when the CPython binary doesn't export the required symbol. Ensure you're using a standard CPython build (not PyPy or a stripped build)

### No async tasks shown with `-a`
- **No event loop running** — coroutines are only visible when an event loop is actively running in the target process
- **All tasks completed** — finished tasks are filtered out. Only pending/waiting tasks are shown
- **flight_profiler internal tasks are filtered** — tasks belonging to flight_profiler's own agent are hidden automatically

### Permission errors
- Check target process ownership with `ps -p <pid> -o user=`
- If the target runs as root, use `sudo flight_profiler <pid> ...`
- On Linux, verify `ptrace_scope`: `cat /proc/sys/kernel/yama/ptrace_scope` (should be `0`)

## Tips

- Take multiple stack snapshots a few seconds apart to distinguish between a thread that is **stuck** vs one that is just **slow**
- Look for `[Has the GIL]` in thread stacks to identify which thread is holding the GIL — if a CPU-bound thread holds it for too long, other threads will show `[Waiting for the GIL]`
- For async applications, **always use `-a`** to see coroutine stacks — thread stacks alone will just show the event loop waiting in `epoll_wait`/`select`
- Use `--native` when debugging C extension crashes or hangs — it reveals the C-level call stack beneath Python frames
- Save snapshots with `-f` before and after a suspected issue for comparison
- The `* - Unable to merge native stack due to insufficient native information - *` line in default mode is normal — it means native frames are available but not requested (use `--native` to see them)
- **Use `stack` as the first step to locate business code** — before running `watch`, `trace`, or `module`, run `stack` to discover the file paths and module names active in the target process. The stack frames show exactly which files are being executed (e.g., `File "myapp/services/order.py", line 42, in process_order`), so you can derive the correct module name for subsequent commands

## Platform Notes

- **Linux**: uses [pystack](https://github.com/bloomberg/pystack) (Bloomberg) for stack analysis, supports native C frames via `--native`
- **macOS**: fetches thread stacks via the injected agent server using CPython's `_Py_DumpTracebackThreads`
- **Async stacks** (`-a`): always fetched via server communication on both platforms (requires access to the target's event loop)

## Related Commands

- **watch** — observe function arguments, return values, and timing at each invocation
- **perf** — if you need a statistical view of where time is spent (flamegraph), use perf instead of repeated stack snapshots
- **gilstat** — if threads are contending on the GIL, use gilstat to confirm and measure contention rate

## Source Files

- CLI plugin: `flight_profiler/plugins/stack/cli_plugin_stack.py`
- Parser: `flight_profiler/plugins/stack/stack_parser.py`
- Server plugin: `flight_profiler/plugins/stack/server_plugin_stack.py`
