> **This file is a template, not data.**
>
> The knowledge base is generated from your own sources by `parse_codebase.py`
> and grows as you feed it real defects and specs. What shipped here originally
> was generated from a former employer's tracker, so it has been replaced with
> the format and a worked example. Regenerate it against your product; the
> loader in `framework/knowledge_base.py` reads whatever is here.

# Learned rules

Rules mined from resolved defects. Each rule is a behaviour that broke once, so
a test for it is worth more than a test written from a spec that never failed.

## RULE-00001

- **Rule**: After a successful purchase, the entitlement must be visible on the
  account screen without the user restarting the app.
- **Priority**: P0
- **Confidence**: █████ (100%)
- **Feature**: Purchases
- **Source Bugs**: BUG-00000001
- **Test Suggestion**: Positive test. Complete a purchase, return to the account
  screen without restarting, and assert the entitlement is shown.

## RULE-00002

- **Rule**: Cancelling from a confirmation dialog returns the user to the screen
  they came from, not to the home screen.
- **Priority**: P1
- **Confidence**: ████░ (80%)
- **Feature**: Navigation
- **Source Bugs**: BUG-00000002
- **Test Suggestion**: Navigation test. Open the dialog from a detail screen,
  cancel, and assert the detail screen is still in focus.

## Format

Keep one rule per defect cluster. `Source Bugs` should carry your tracker's own
identifiers so a rule can be traced back. Do not paste raw ticket text: it tends
to contain customer details, colleague names and internal handles.
