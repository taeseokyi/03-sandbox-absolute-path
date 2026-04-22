---
name: workspace-awareness
description: Understanding the workspace and host directory structure, path handling rules, and read-only boundaries
license: MIT
---

# Workspace Awareness Skill

## When to Use
Use this skill when you need to:
- Understand where your files are and what you can access
- Handle file paths correctly
- Troubleshoot path-related errors
- Read reference files from the host directory

## Your Environment

You work in `/tmp/workspace`. This directory has two areas:

### `/tmp/workspace/` — Your Working Directory (Read/Write)

This is where you create, modify, and execute files.

```
/tmp/workspace/
├── your_script.py    ← you create this
├── data/
│   └── input.csv     ← you create this
├── output.txt        ← you create this
└── host/             ← read-only (see below)
```

All file operations (write, edit, execute) happen here by default.

### `host/` — Reference Files (Read-Only)

System-provided configuration and reference files inside the workspace. You can **read** them but **cannot write or edit** them.

```
host/
├── shared/              ← shared libs & skills (no AGENTS.md → not a profile)
│   ├── lib/
│   ├── src/
│   └── skills/          ← skills exposed to all agents
├── data_pipeline/       ← data collection skills (no AGENTS.md → not a profile)
│   ├── lib/
│   ├── src/
│   └── skills/          ← skills selectively exposed to subagents
├── beginner/            ← beginner profile (AGENTS.md present)
│   └── skills/
└── developer/           ← developer profile (AGENTS.md present)
    ├── skills/
    └── subagents/
        ├── code-reviewer/
        ├── data-analyst/
        └── report-writer/
```

## Path Rules

### Allowed Paths

1. **Relative Paths** (Recommended)
   ```python
   write_file(file_path="script.py", content="...")
   read_file(file_path="data/input.txt")
   ```
   Automatically resolved within `/tmp/workspace`.

2. **Current Directory**
   ```python
   ls(path=".")                        # Lists /tmp/workspace
   grep(pattern="test", path=".")
   glob(pattern="**/*.py", path=".")   # Find files by pattern
   ```

3. **Absolute Workspace Paths**
   ```python
   read_file(file_path="/tmp/workspace/script.py")
   write_file(file_path="/tmp/workspace/output.txt", content="...")
   ```

4. **Host Paths (Read-Only)**
   ```python
   read_file(file_path="host/shared/skills/workspace-awareness/SKILL.md")  # OK (relative)
   ls(path="host/developer/subagents")                                      # OK (relative)
   glob(pattern="*.md", path="host/shared/skills")                         # OK (relative)
   read_file(file_path="/tmp/workspace/host/shared/skills/workspace-awareness/SKILL.md")  # OK (absolute)
   write_file(file_path="host/test.txt", content="...")                     # BLOCKED
   edit_file(file_path="host/shared/skills/workspace-awareness/SKILL.md", ...) # BLOCKED
   ```

### Forbidden Paths

These will fail with clear error messages:

```python
# Path traversal
read_file(file_path="../outside.txt")           # BLOCKED
read_file(file_path="../../etc/passwd")         # BLOCKED
```

## Error Messages

### "Path traversal not allowed"
**Cause**: Used `..` or `~` in a path.
**Fix**: Use direct relative paths or absolute paths starting with `/tmp/workspace/`.

### "Cannot write to read-only host path"
**Cause**: Tried to write or edit a file under `host/`.
**Fix**: `host/` is read-only. Write your files to the workspace root instead.

### "File already exists" (write_file)
**Cause**: `write_file` creates new files only. Calling it on an existing path fails.
**Fix**: Use `edit_file` to modify an existing file, or delete it first.

### "string_not_found" (edit_file)
**Cause**: `old_string` was not found in the file.
**Fix**: Re-read the file to confirm the exact string, including whitespace and indentation.

### "multiple_occurrences" (edit_file)
**Cause**: `old_string` matches more than one place and `replace_all` is False.
**Fix**: Use `replace_all=True` or provide a longer, unique `old_string`.

## Tool Behaviors

Non-obvious behaviors to keep in mind for each tool.

### `write_file` — new files only, auto-creates directories

`write_file` **fails if the file already exists**. To modify an existing file, use `edit_file`.

Parent directories are created automatically — no need to create them first.

```python
write_file(file_path="result.txt", content="hello")         # OK — creates new file
write_file(file_path="src/utils/helper.py", content="...")  # OK — src/utils/ auto-created
write_file(file_path="result.txt", content="updated")       # ERROR — file already exists
edit_file(file_path="result.txt", old_string="hello", new_string="updated")  # OK
```

### `edit_file` — read before editing, optional replace_all

Always `read_file` the target file first. `edit_file` matches `old_string` exactly (including indentation and whitespace).

```python
# Correct workflow
read_file(file_path="config.py")                          # 1. read first
edit_file(file_path="config.py", old_string="debug=True",
          new_string="debug=False")                        # 2. then edit

# Replace all occurrences (e.g. rename a variable)
edit_file(file_path="app.py", old_string="old_name",
          new_string="new_name", replace_all=True)
```

`replace_all=False` (default) requires exactly one match — fails if the string appears 0 times or multiple times. When it fails due to multiple matches, the error message includes the actual count so you know to use `replace_all=True`.

### `read_file` — paging, line numbers, large files

`read_file` returns up to **100 lines** by default. Use `limit` to read more at once (backend supports up to ~2000 per call).

```python
read_file(file_path="data.csv")                         # lines 1–100 (default)
read_file(file_path="data.csv", offset=100, limit=100)  # lines 101–200
read_file(file_path="data.csv", offset=500, limit=50)   # lines 501–550
read_file(file_path="data.csv", limit=500)              # lines 1–500
```

**`offset`** = number of lines to skip (0-based). `offset=0` starts at line 1; `offset=100` starts at line 101.

**Output format**: 6-digit right-aligned line numbers followed by a tab.

```
     1	first line
     2	second line
```

**Footer when more lines remain**:
```
[Showing lines 1-100 of 5000 total. Use offset=100 to continue.]
```

**Special cases**:
- Empty file → `[File is empty]`
- Line longer than 2000 chars → `[TRUNCATED: N chars total]` appended
- File not found → error string with suggestions (not an exception)
- Directory path → `Error reading file: Is a directory` — use `ls()` instead

### `grep` — literal search, output_mode, glob filter

`grep` searches for **literal strings**, not regular expressions. Special characters like `(`, `|`, `.*` are matched as-is.

Use `output_mode` to control what is returned:

```python
grep(pattern="import os", path=".")                         # files_with_matches (default)
grep(pattern="import os", path=".", output_mode="content")  # matching lines with context
grep(pattern="import os", path=".", output_mode="count")    # per-file match count
```

Use `glob` to restrict search to specific file types:

```python
grep(pattern="TODO", path=".", glob="*.py")      # Python files only
grep(pattern="error", path=".", glob="**/*.log") # all .log files recursively
```

### `execute` — cd does not persist, optional timeout

`cd` inside `execute` does **not** affect subsequent calls. Each call starts from `/tmp/workspace`.

```python
execute(command="cd src && python main.py")   # OK — chained in one call
execute(command="cd src")                     # has no effect on next execute()
execute(command="python src/main.py")         # use path directly instead
```

Use `timeout` to override the default 30-second limit:

```python
execute(command="python train.py")             # default 30s timeout
execute(command="python train.py", timeout=120) # allow 2 minutes
execute(command="pip install -r req.txt", timeout=0)  # no timeout (0 = unlimited)
```

stdout and stderr are merged into a single output string. Output longer than ~10 000 characters is truncated with `[Output was truncated due to size limits]`.

### `task` — subagent delegation, parallel execution

`task` delegates work to a specialized subagent. When you call multiple `task()` tools **in the same turn**, they run in **parallel** — use this whenever tasks are independent.

```python
# Sequential (only when task B needs task A's result)
task(description="collect data from source A", subagent_type="data-collector")
# ... wait for result, then:
task(description="summarize the collected data", subagent_type="report-writer")

# Parallel (independent tasks — much faster)
# Call both in the same response:
task(description="analyze sales.csv for trends", subagent_type="data-analyst")
task(description="review src/main.py for bugs", subagent_type="code-reviewer")
```

Available subagents are defined under `host/{profile}/subagents/`.

### `start_async_task` / `check_async_task` — background tasks (optional feature)

These tools are only available when the agent is configured with `AsyncSubAgent` specs. If present, they let you launch tasks that run in the background on a remote server and poll for results without blocking.

```python
# Start and immediately get a task_id (non-blocking)
task_id = start_async_task(description="...", subagent_type="data-collector")

# Check later (poll when needed — don't loop automatically)
result = check_async_task(task_id=task_id)  # returns status + result when done

# Other async management tools (if available):
update_async_task(task_id=task_id, message="focus on Q4 only")
cancel_async_task(task_id=task_id)
list_async_tasks(status_filter="running")  # or "success", "error", "all"
```

## Best Practices

1. **Default to Relative Paths**
   ```python
   write_file(file_path="app.py", content="...")       # Good
   write_file(file_path="/tmp/workspace/app.py", content="...")  # Unnecessary
   ```

2. **Organize with Subdirectories**
   ```python
   write_file(file_path="src/main.py", content="...")
   write_file(file_path="tests/test_main.py", content="...")
   ```

3. **Check Your Location**
   ```python
   execute(command="pwd")    # /tmp/workspace
   ls(path=".")              # See workspace contents
   ```

4. **Read Large Files in Pages**

   `read_file` returns up to 100 lines by default. Use `offset` and `limit` to page through large files:
   ```python
   # First 100 lines (default)
   read_file(file_path="data.csv")

   # Next 100 lines
   read_file(file_path="data.csv", offset=100, limit=100)

   # Lines 501–700 (larger chunk)
   read_file(file_path="data.csv", offset=500, limit=200)
   ```
   When more lines remain, the footer shows: `[Showing lines 1-100 of 5000 total. Use offset=100 to continue.]`

5. **Read Host References When Needed**
   ```python
   # Check available shared skills
   ls(path="host/shared/skills")
   # Find all skill definitions
   glob(pattern="**/SKILL.md", path="host")
   # Read a skill definition
   read_file(file_path="host/shared/skills/workspace-awareness/SKILL.md")
   ```

6. **Track Progress with Todos**

   Each todo is a dict with `content` (text) and `status` (`"pending"`, `"in_progress"`, `"completed"`).
   Call `write_todos` with the **full updated list** every time — it replaces the previous list entirely.

   ```python
   # Create initial list
   write_todos(todos=[
       {"content": "step 1", "status": "pending"},
       {"content": "step 2", "status": "pending"},
       {"content": "step 3", "status": "pending"},
   ])

   # Mark step 1 done, step 2 in progress
   write_todos(todos=[
       {"content": "step 1", "status": "completed"},
       {"content": "step 2", "status": "in_progress"},
       {"content": "step 3", "status": "pending"},
   ])
   ```

7. **Run Independent Tasks in Parallel**

   Use multiple `task()` calls in the same turn — they run concurrently:
   ```python
   # Same turn → parallel execution
   task(description="analyze q1_sales.csv", subagent_type="data-analyst")
   task(description="analyze q2_sales.csv", subagent_type="data-analyst")
   task(description="analyze q3_sales.csv", subagent_type="data-analyst")
   ```

## Quick Reference

| What You Want | How to Do It |
|---------------|--------------|
| Create new file | `write_file(file_path="file.txt", content="...")` |
| Modify existing file | `edit_file(file_path="file.txt", old_string="old", new_string="new")` |
| Rename/replace all occurrences | `edit_file(file_path="file.txt", old_string="x", new_string="y", replace_all=True)` |
| Read file (first 100 lines) | `read_file(file_path="file.txt")` |
| Read file (next page) | `read_file(file_path="file.txt", offset=100, limit=100)` |
| Read specific line range | `read_file(file_path="file.txt", offset=500, limit=50)` |
| List directory | `ls(path=".")` |
| Search — file paths only | `grep(pattern="TODO", path=".")` |
| Search — matching lines | `grep(pattern="TODO", path=".", output_mode="content")` |
| Search — count per file | `grep(pattern="TODO", path=".", output_mode="count")` |
| Search in specific file type | `grep(pattern="import", path=".", glob="*.py")` |
| Find files by pattern | `glob(pattern="**/*.py", path=".")` |
| Run command (default 30s) | `execute(command="python script.py")` |
| Run with custom timeout | `execute(command="python train.py", timeout=120)` |
| Run without timeout | `execute(command="pip install ...", timeout=0)` |
| Manage todos | `write_todos(todos=[{"content": "task", "status": "pending"}])` |
| Call subagent | `task(description="...", subagent_type="data-analyst")` |
| Call subagents in parallel | Multiple `task()` in the same turn |
| Read host file | `read_file(file_path="host/shared/skills/workspace-awareness/SKILL.md")` |
| List host dir | `ls(path="host/developer/subagents")` |
| Find host skills | `glob(pattern="**/SKILL.md", path="host")` |
