> **This file is a template, not data.**
>
> The knowledge base is generated from your own sources by `parse_codebase.py`
> and grows as you feed it real defects and specs. What shipped here originally
> was generated from a former employer's tracker, so it has been replaced with
> the format and a worked example. Regenerate it against your product; the
> loader in `framework/knowledge_base.py` reads whatever is here.

# User journeys

End-to-end flows the generator uses to build scenario tests. One journey per
heading, numbered steps, and an explicit expected outcome.

## Journey: first purchase

1. Register a new account
2. Complete the required registration fields
3. Open the paid feature and hit the free-tier limit
4. Choose a plan and pay
5. Return to the feature

**Expected:** the feature is available immediately, with no restart, and the
account screen shows the entitlement.

**Failure modes worth testing:** payment succeeds but entitlement does not
appear; user is returned to the wrong screen; limit still enforced after
purchase.

## Journey: cancel and resume

1. Start from an entitled account
2. Cancel the entitlement
3. Confirm in the dialog
4. Reopen the paid feature

**Expected:** access continues until the paid period ends, and the account
screen reflects the cancelled state.

## Format

Keep journeys to the flows that carry revenue or that users hit daily. A journey
with no expected outcome is a click path, not a test.
