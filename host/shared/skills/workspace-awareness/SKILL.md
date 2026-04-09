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
├── skills/              ← skill definitions
│   ├── basic-python/
│   ├── debugging/
│   ├── python-dev/
│   └── workspace-awareness/
├── system_prompts/      ← system prompt files
│   ├── AGENTS-beginner.md
│   └── AGENTS-developer.md
└── subagents/           ← sub-agent configurations
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
   ls(path=".")          # Lists /tmp/workspace
   grep(pattern="test", path=".")
   ```

3. **Absolute Workspace Paths**
   ```python
   read_file(file_path="/tmp/workspace/script.py")
   write_file(file_path="/tmp/workspace/output.txt", content="...")
   ```

4. **Host Paths (Read-Only)**
   ```python
   read_file(file_path="host/skills/basic-python/SKILL.md")     # OK (relative)
   ls(path="host/subagents")                           # OK (relative)
   read_file(file_path="/tmp/workspace/host/skills/basic-python/SKILL.md")  # OK (absolute)
   write_file(file_path="host/test.txt", content="...")          # BLOCKED
   edit_file(file_path="host/skills/basic-python/SKILL.md", ...) # BLOCKED
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
   ls(path=".")         # See workspace contents
   ```

4. **Read Host References When Needed**
   ```python
   # Check available skills
   ls(path="host/skills")
   # Read a skill definition
   read_file(file_path="host/skills/debugging/SKILL.md")
   ```

## Quick Reference

| What You Want | How to Do It |
|---------------|--------------|
| Create file | `write_file("file.txt", "...")` |
| Read file | `read_file("file.txt")` |
| Edit file | `edit_file("file.txt", "old", "new")` |
| List workspace | `ls(".")` |
| Search files | `grep("pattern", ".")` |
| Check location | `execute("pwd")` |
| Read host file | `read_file("host/skills/basic-python/SKILL.md")` |
| List host dir | `ls"host/subagents")` |
