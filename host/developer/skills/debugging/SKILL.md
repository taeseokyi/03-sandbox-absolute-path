---
name: debugging
description: Systematic debugging approach for identifying and resolving code issues, including error analysis and workspace troubleshooting
license: MIT
---

# Debugging Skill

## When to Use
Use this skill when you need to:
- Troubleshoot code errors
- Diagnose workspace-related issues
- Verify file paths and imports
- Debug Python syntax errors

## Systematic Debugging Approach

1. **Read Error Messages Carefully**
   - Note the error type
   - Check line numbers
   - Understand the stack trace

2. **Verify File Paths**
```python
   # Always check if files exist
   ls(path=".")
```

3. **Check Syntax Before Running**
```python
   # Use Python's syntax checker
   execute(command="python -m py_compile script.py")
```

4. **Add Debug Output**
```python
   # Add print statements strategically
   print(f"Debug: variable value = {value}")
```

5. **Test Incrementally**
   - Start with minimal code
   - Add complexity gradually
   - Verify each step works

## Common Issues

### Import Errors
```python
# Check if module is installed
execute(command="python -c 'import module_name'")
```

### Path Issues
```python
# Verify working directory
execute(command="pwd")
# List directory contents
ls(path=".")

# Writable area: /tmp/workspace (relative paths or /tmp/workspace/...)
# Read-only area: host/ (skills, system_prompts, subagents)
# ❌ Blocked: /etc, /usr, /, .. etc.
```

### Workspace Boundary Errors
```python
# "WORKSPACE BOUNDARY VIOLATION":
# - Tried to access outside /tmp/workspace
# - Fix: use relative paths or /tmp/workspace/... paths

# "PATH TRAVERSAL ATTACK BLOCKED":
# - Used ".." in a path
# - Fix: use direct paths within workspace

# "Cannot write to read-only host path":
# - Tried to write/edit under host/
# - Fix: write to workspace root instead
```

### Syntax Errors
- Check quotes matching
- Verify indentation
- Ensure parentheses balance

## Debug Workflow Example

```python
# 1. Check if file exists
files = ls(path=".")
print(f"Files in workspace: {[f['name'] for f in files]}")

# 2. Verify syntax
execute(command="python -m py_compile my_script.py")

# 3. Add debug output
content = read(file_path="my_script.py")
print(f"Script content:\n{content}")

# 4. Run with error handling
result = execute(command="python my_script.py")
if result.exit_code != 0:
    print(f"Error occurred: {result.output}")
```
