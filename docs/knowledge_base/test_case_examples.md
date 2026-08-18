> **This file is a template, not data.**
>
> It originally held test cases generated against a former employer's product.
> Replace the examples with your own; `parse_codebase.py` regenerates this file
> from your sources.

# Test case examples

Worked examples in the format the generator emits. The generator few-shots from
these, so their quality sets the quality of everything it writes.

| TC ID | Category | Title | Steps | Expected Result |
|-------|----------|-------|-------|-----------------|
| TC001 | Entitlement | Entitled account is not shown an upsell | 1. Sign in with an active entitlement 2. Open the paid feature | Feature opens directly. No upgrade prompt, no balance deduction |
| TC002 | Entitlement | Free-tier limit triggers the paywall | 1. Sign in as a new account 2. Use the free allowance to exhaustion 3. Attempt one more | Paywall appears with plan options |
| TC003 | Entitlement | Purchase takes effect without a restart | 1. Purchase a plan 2. Return to the account screen | Entitlement shown immediately |
| TC004 | Navigation | Cancel returns to the originating screen | 1. Open the confirmation dialog from a detail screen 2. Cancel | Detail screen retains focus |
| TC005 | Payment | Failed payment leaves no partial entitlement | 1. Begin a purchase 2. Force the payment to fail | Account is unchanged and an actionable error is shown |
| TC006 | Registration | Required fields are enforced | 1. Register 2. Leave a required field empty 3. Continue | Continue is blocked, the missing field is named |

## What makes these usable as examples

Each has a precondition in step 1, a single action, and an expected result that
is checkable rather than descriptive. "Works correctly" is not an expected
result; "no upgrade prompt, no balance deduction" is.

Categories should match the ones in `domain_knowledge.md`, since the generator
uses them to route a new case to the right template.
