# Priority 1: Fix Agent API Response Handling

## Problem
Anthropic API 0.86.0 returns raw string, not object with .content attribute.

## Solution for EACH agent (.py file)

### Template: Update agent response handling

```python
# OLD CODE (causes errors):
resp = self.client.messages.create(...)
content = resp.content[0].text  # BREAKS HERE

# NEW CODE (handles both formats):
resp = self.client.messages.create(...)
if isinstance(resp, str):
    content = resp
elif hasattr(resp, 'content') and isinstance(resp.content, list):
    if hasattr(resp.content[0], 'text'):
        content = resp.content[0].text
    else:
        content = str(resp.content[0])
else:
    content = str(resp)
```

## Files to Update

This pattern must be applied to ALL agent files:
1. `qiskitsage/agents/syntax_agent.py` ~line 32
2. `qiskitsage/agents/performance_agent.py` ~line 33  
3. `qiskitsage/agents/semantic_agent.py` ~line 35
4. `qiskitsage/agents/ffi_agent.py` ~line 93

## Quick Script

```bash
# Apply fix to all agent files
for agent in syntax performance semantic ffi; do
    file="qiskitsage/agents/${agent}_agent.py"
    
    # Create backup
    cp "$file" "$file.backup"
    
    # Apply fix (use Python for proper escaping)
    python -c "
    import re
    with open('$file', 'r') as f:
        content = f.read()
    
    # Replace the problematic line
    old_pattern = r'(\s+resp = self\.client\.messages\.create\([^)]+\))(\s+content = resp\.content\[0\]\.text)'
    new_code = '''resp = self.client.messages.create(model=self.model, max_tokens=self.max_tokens, temperature=self.temperature, system=SYSTEM_PROMPT, messages=[{\'role\': \'user\', \'content\': user_prompt}])
        
        # Parse JSON response - handle both string and object responses
        if isinstance(resp, str):
            content = resp
        elif hasattr(resp, \'content\') and isinstance(resp.content, list):
            if hasattr(resp.content[0], \'text\'):
                content = resp.content[0].text
            else:
                content = str(resp.content[0])
        else:
            content = str(resp)'''
    
    content = re.sub(old_pattern, new_code, content, flags=re.MULTILINE)
    
    with open('$file', 'w') as f:
        f.write(content)
    
    print(\"Fixed: $file\")
    "
done
```

## Expected Result

All agents should handle both response formats:
```
✅ Syntax agent: works
✅ Performance agent: works  
✅ Semantic agent: works
✅ FFI agent: works
```

---
*Part of Priority 1 fixes*
