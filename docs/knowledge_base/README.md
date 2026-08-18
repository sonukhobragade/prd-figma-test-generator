# Knowledge Base

> This folder contains the knowledge base files that enhance test case generation.

## Files

| File | Purpose | When to Update |
|------|---------|----------------|
| `bug_patterns.md` | Real-world bugs to catch | After discovering new bugs |
| `user_journeys.md` | App flows and user stories | When flows change or new features added |
| `test_case_examples.md` | Reference test cases | When good examples emerge |
| `domain_knowledge.md` | App-specific concepts | When terminology or business rules change |
| `test_coverage_rules.md` | Coverage dimensions | When new test types needed |

## How It Works

1. **LLM Analyzer** loads these files at startup
2. **Prompt Builder** includes relevant context from these files
3. **Test Generation** uses this knowledge to generate better test cases

## How to Update

### Adding New Bugs

Edit `bug_patterns.md` and add to the appropriate section:

```markdown
| BUG-XXX | Description | Expected | Actual |
```

### Adding New Flows

Edit `user_journeys.md` and add:

```markdown
### Flow X.X: Flow Name

STEPS:
1. Step description
   → Details

TEST POINTS:
- Key test point 1
```

### Adding New Test Examples

Edit `test_case_examples.md` and add:

```markdown
| TC0XX | Category | Title | Steps | Expected Result |
```

### Adding Domain Knowledge

Edit `domain_knowledge.md` and add to relevant section.

### Adding Coverage Rules

Edit `test_coverage_rules.md` and add new rules or dimensions.

## File Size Considerations

- Keep files focused and concise
- The system uses a summary for prompts (to manage token limits)
- Full files are available for detailed reference

## Verification

After updating, you can verify the knowledge base is loaded by checking logs:

```
Knowledge base loaded successfully
```

Or by running:

```python
from framework.knowledge_base import get_knowledge_base

kb = get_knowledge_base()
print(kb.list_available_files())
```
