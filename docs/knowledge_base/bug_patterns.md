> **This file is a template, not data.**
>
> The knowledge base is generated from your own sources by `parse_codebase.py`
> and grows as you feed it real defects and specs. What shipped here originally
> was generated from a former employer's tracker, so it has been replaced with
> the format and a worked example. Regenerate it against your product; the
> loader in `framework/knowledge_base.py` reads whatever is here.

# Bug patterns

Recurring shapes of defect, used to generate negative tests. Patterns generalise
across products; the examples do not, so replace them.

| ID | Pattern | Expected | Actual |
|---|---|---|---|
| NAV-001 | Action from a detail screen returns to home | Return to detail | Returns home |
| NAV-002 | Back after a deep link exits the app | Return to previous screen | App exits |
| STATE-001 | Purchased state not reflected until restart | Immediate | Requires restart |
| STATE-002 | Cached value shown after a server-side change | Fresh value | Stale value |
| UI-001 | Content overflows on small screens | Wraps or scrolls | Clipped |
| UI-002 | Loading state absent during a slow call | Spinner shown | Blank screen |

## Using these

Each row becomes a negative test template. The value is in the Expected/Actual
pair: it states the assertion, which is the part a generator cannot invent.

Add rows as your own defects resolve. A pattern earns its place after it has
occurred twice.
