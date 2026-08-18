# Test Coverage Rules

> **Purpose**: Rules and dimensions for comprehensive test coverage
> **Last Updated**: 2025-11-26
> **How to Use**: Apply these rules when generating test cases

---

## Coverage Dimensions

### A. User State Matrix Testing

Test every feature with different user states:

| User State | Test Scenarios |
|------------|----------------|
| New User (never subscribed) | Free limits, paywall behavior |
| entitled account (active) | No deductions, no paywalls |
| Expired Subscription | Back to paywall |
| Half-Onboarded | Feature blocking until complete |
| Subscribed with ₹0 wallet | Should still work |
| Free exhausted + no subscription | Paywall active |
| Free exhausted + then subscribed | No free strip |

### B. Negative UI Assertions

Test that elements DO NOT appear in certain states:

```
✓ entitled account: NO low-balance strip
✓ Entitled account: NO upgrade prompt
✓ Entitled account: NO balance deduction
✓ entitled account: NO "Continue without Subscription" option
✓ Entitled account: NO free-tier banner
```

### C. Cross-Feature State Propagation

Test how state changes affect other features:

| State Change | Affected Features |
|--------------|-------------------|
| Buy subscription | Chat, Reports, Balance, Hamburger menu |
| Complete profile | Subscription access unlocked |
| Add money | Wallet, Transaction history |
| Exhaust the free allowance | Paywall appears |

### D. CTA/Navigation Correctness

Test every button leads to correct destination:

| CTA | Source | Expected Destination | Wrong Destination |
|-----|--------|---------------------|-------------------|
| Subscribe Now | Home | Subscription Page | NOT Reports Page |
| Buy Now | Reports | Report Details | NOT Report List |
| Open a document from a summary card | Summary | Document detail | NOT the profile screen |
| Guided Reading | Subscription | Guided Reading | NOT blocked |

### E. Real-time Data Synchronization

Test immediate updates without app relaunch:

| Action | Data to Verify |
|--------|----------------|
| Buy subscription | My Balance, Hamburger badge, Subscribe button text |
| Add money | Wallet balance, Transaction history |
| Complete profile | Subscription access |

### F. Feature Gating

Test prerequisites are enforced:

| Feature | Prerequisite | Blocking Message |
|---------|--------------|------------------|
| Subscription | Complete profile | "Complete Profile to Subscribe" |
| Paid feature | Entitlement OR balance | Upgrade prompt |
| Reports | Subscription OR purchase | Payment flow |

### G. Post-Action Flow Completion

Test correct behavior after actions:

| Action | Expected Flow |
|--------|---------------|
| Subscription success | Redirect to Home |
| Payment success | Processing → Success → Return |
| Cancel subscription | 1 popup → Home |
| Payment via Chat | Back button works |

### H. UI/Figma Compliance

Test visual elements match design:

| Element | Check |
|---------|-------|
| Colors | Match Figma hex codes |
| Padding/Margins | Match Figma spacing |
| Icons | Visible, correct size |
| Shadows | Present where specified |
| Tags/Badges | Premium tag, [Active] badge |
| Strike-through | Original prices shown |

---

## Test Type Definitions

| Type | Purpose | When to Use |
|------|---------|-------------|
| `positive` | Valid inputs, happy paths | Normal user flows |
| `negative` | Invalid inputs, error handling | Error scenarios |
| `edge_case` | Unusual inputs, extreme conditions | Corner cases |
| `boundary` | Min/max values, limits | Input limits |
| `subscription_state` | User state-specific behavior | Subscription features |
| `navigation` | CTA destinations, back button | All navigation |
| `ui_compliance` | Figma matching | Visual verification |
| `data_sync` | Real-time updates | After state changes |
| `state_propagation` | Cross-feature effects | State changes |
| `feature_gating` | Prerequisites | Blocked features |
| `user_journey` | End-to-end flows | Complete workflows |

---

## Minimum Coverage Targets

| Test Type | Target % | Minimum Count |
|-----------|----------|---------------|
| positive | 30% | 6+ |
| negative | 20% | 4+ |
| subscription_state | 15% | 3+ |
| navigation | 10% | 2+ |
| ui_compliance | 10% | 2+ |
| data_sync | 5% | 1+ |
| edge_case | 5% | 1+ |
| boundary | 3% | 1+ |
| feature_gating | 2% | 1+ |

**Total Minimum**: 20+ test cases per feature

---

## Priority Guidelines

| Priority | Criteria | Examples |
|----------|----------|----------|
| P0 | Critical, blocks usage | Payment fails, subscription not applied |
| P1 | High, major feature broken | Navigation wrong, deductions for subscribed |
| P2 | Medium, minor issues | UI misalignment, wrong icon |
| P3 | Low, cosmetic | Spacing slightly off |

---

## Precondition Testing Matrix

For each feature, test with these preconditions:

```
□ New user (first time)
□ entitled account (active)
□ entitled account (zero wallet)
□ Expired subscription user
□ Account that has exhausted the free allowance
□ User who exhausted free + subscribed
□ Half-onboarded user
```

---

## Negative Assertion Patterns

Always test what should NOT happen:

```
Pattern: "Verify [element] does NOT appear when [condition]"

Examples:
- "Verify the upgrade prompt does NOT appear for an entitled account"
- "Verify no balance deduction happens for an entitled account"
- "Verify the free-tier banner does NOT show after purchase"
- "Verify 'Continue without Subscription' does NOT show for subscribed"
```

---

## How to Update

Add new rules as patterns emerge:

```markdown
### New Rule Name

| Condition | Expected | To Test |
|-----------|----------|---------|
| When X | Then Y | Verify Z |
```
