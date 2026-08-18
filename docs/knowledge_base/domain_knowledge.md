> **This file is a template, not data.**
>
> The knowledge base is generated from your own sources by `parse_codebase.py`
> and grows as you feed it real defects and specs. What shipped here originally
> was generated from a former employer's tracker, so it has been replaced with
> the format and a worked example. Regenerate it against your product; the
> loader in `framework/knowledge_base.py` reads whatever is here.

# Domain knowledge

App-specific terminology, concepts and business rules. The generator uses this
to write tests that reference real product behaviour rather than generic CRUD.

## App overview

Describe what the product does in three or four lines. The generator quotes this
when a test needs context.

## Core concepts

| Concept | Description | Notes |
|---|---|---|
| Account | A registered user | Owns one or more profiles |
| Entitlement | What an account has paid for | Subscription or one-off |
| Profile | A record an account acts on behalf of | Optional, multiple allowed |

## User states

| State | Description | Behaviour |
|---|---|---|
| New | Registered, never purchased | Free tier limits apply |
| Entitled | Active subscription | Limits lifted |
| Lapsed | Subscription ended | Back to free tier |
| Incomplete | Registration not finished | Blocked from paid actions |

## Business rules

State the rules that a test can assert. Be specific about limits, resets and
precedence, since those are where defects cluster.

- **Free tier**: state the allowance and when it resets.
- **Entitlement precedence**: state what an active entitlement overrides.
- **Payment**: state accepted methods, verification time, and failure handling.
- **Required fields**: state what registration demands and what it does not.

Write these from your own product's specification. Do not copy a previous
employer's rules, including limits and pricing: those are theirs.
