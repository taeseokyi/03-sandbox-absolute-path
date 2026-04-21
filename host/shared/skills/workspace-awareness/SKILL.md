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
# System paths
read_file(file_path="/etc/passwd")              # BLOCKED
write_file(file_path="/usr/bin/tool", content="...")  # BLOCKED

# Root access
ls(path="/")                          # BLOCKED

# Path traversal
read_file(file_path="../outside.txt")           # BLOCKED
```

## Error Messages

### "WORKSPACE BOUNDARY VIOLATION"
**Cause**: Tried to access a path outside `/tmp/workspace`.
**Fix**: Use relative paths or paths starting with `/tmp/workspace/`.

### "PATH TRAVERSAL ATTACK BLOCKED"
**Cause**: Used `..` to navigate outside workspace.
**Fix**: Use direct paths within workspace.

### "Cannot write to read-only host path"
**Cause**: Tried to write or edit a file under `host/`.
**Fix**: `host/` is read-only. Write your files to the workspace root instead.

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

   # Lines 500–699
   read_file(file_path="data.csv", offset=500, limit=200)
   ```
   Output includes line numbers (`cat -n` format) and a summary when the file has more lines remaining.

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
   ```python
   write_todos(todos=["step 1", "step 2", "step 3"])   # Create todo list
   write_todos(todos=["~~step 1~~", "step 2", "step 3"])  # Mark step 1 done
   ```

7. **Delegate to Subagents**
   ```python
   task(subagent="data-analyst", content="analyze data.csv and summarize")
   task(subagent="code-reviewer", content="review src/main.py for issues")
   ```
   Available subagents are defined under `host/{profile}/subagents/`.

## Quick Reference

| What You Want | How to Do It |
|---------------|--------------|
| Create file | `write_file("file.txt", "...")` |
| Read file (first 100 lines) | `read_file("file.txt")` |
| Read file (next page) | `read_file("file.txt", offset=100, limit=100)` |
| Read specific line range | `read_file("file.txt", offset=499, limit=50)` |
| Edit file | `edit_file("file.txt", "old", "new")` |
| List directory | `ls(".")` |
| Search content | `grep("pattern", ".")` |
| Find by pattern | `glob("**/*.py", ".")` |
| Run command | `execute("pwd")` |
| Manage todos | `write_todos(todos=["task1", "task2"])` |
| Call subagent | `task(subagent="data-analyst", content="...")` |
| Read host file | `read_file("host/shared/skills/workspace-awareness/SKILL.md")` |
| List host dir | `ls("host/developer/subagents")` |
| Find host skills | `glob("**/SKILL.md", "host")` |
