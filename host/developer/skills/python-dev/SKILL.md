---
name: python-dev
description: Professional Python development practices including code quality, testing, error handling, and debugging techniques
license: MIT
---

# Python Development Skill

## When to Use
Use this skill when you need to:
- Write production-quality Python code
- Follow Python best practices
- Implement proper error handling
- Debug Python applications

## Code Quality Standards

- Use descriptive variable names
- Add docstrings to functions
- Follow PEP 8 style guidelines
- Handle exceptions properly
- Add type hints where appropriate

## Testing Approach

```python
# Always test your code after creating it
execute(command="python script.py")
```

## Common Patterns

### Function Template
```python
def function_name(param: int) -> int:
    """
    Brief description.

    Args:
        param: Description

    Returns:
        Description
    """
    # Implementation
    return result
```

### Error Handling
```python
try:
    # risky operation
    result = some_function()
except SpecificError as e:
    print(f"Error: {e}")
    # handle error
```

## Debugging Tips

1. Add print statements to track execution
2. Check variable types with `type()`
3. Use `dir()` to inspect objects
4. Test with simple inputs first

## Example Workflow

```python
# 1. Write with proper structure
write(file_path="calculator.py", content="""
def add(a: int, b: int) -> int:
    '''Add two numbers and return the result.'''
    return a + b

if __name__ == '__main__':
    result = add(5, 3)
    print(f'Result: {result}')
""")

# 2. Test it
execute(command="python calculator.py")

# 3. Verify output
# Expected: Result: 8
```
