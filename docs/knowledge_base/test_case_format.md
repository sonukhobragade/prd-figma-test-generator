# Test Case Format

> **Purpose**: Template and examples for test case generation
> **Last Updated**: 2024-12-20
> **Format**: Matches the official QA test case spreadsheet format

---

## Test Case ID Convention

Format: `TC_UI_[CATEGORY]_[NUMBER]`

| Category Code | Full Name | Description |
|---------------|-----------|-------------|
| NU | New User Flows | First-time user experiences |
| EU | Existing User Flows | Returning user scenarios |
| FT | Free Tier Limit | Free tier restrictions |
| PC | Profile Creation | Creating new profiles |
| PS | Profile Switching | Switching between profiles |
| PE | Profile Editing | Editing profile details |
| PD | Profile Deletion | Deleting profiles |
| SM | Side Menu | Hamburger menu functionality |
| RP | Reports Page | Report generation and viewing |
| CP | Chat Page | Chat functionality |
| TH | Transaction History | Payment and transaction records |
| SS | Subscription States | Subscription-related behavior |
| DI | Data Isolation | Profile data separation |
| TU | Top Up | Balance top-up flows |
| AG | Expert Gold | Gold subscription features |
| PAY | Payment | Payment processing |
| UPI | UPI Payment | UPI-specific flows |
| COMP | UI Components | Generic UI elements |
| FF | Feature Flags | Feature toggle behavior |
| PERF | Performance | Speed and responsiveness |
| EC | Edge Cases | Unusual scenarios |
| OFF | Offline | Offline behavior |
| NOT | Notifications | Push notifications |
| AN | Analytics | Event tracking |
| BC | Backward Compatibility | Version migration |

---

## Priority Definitions

| Priority | Name | Definition | Examples |
|----------|------|------------|----------|
| P0 | Critical | Core functionality, data integrity, payment flows | Payment processing, subscription activation, data isolation |
| P1 | High | Important features, user-facing flows | Profile creation, switching, form validation |
| P2 | Medium | UI polish, secondary features | Toast messages, animations, formatting |
| P3 | Low | Nice-to-have, edge cases | Analytics events, rare edge cases |

---

## User Types

| User Type | Description | Key Characteristics |
|-----------|-------------|---------------------|
| New User | Just signed up | No history, no subscription, single profile |
| Existing User | Has account | May have history, profiles, transactions |
| Free account | No entitlement | Limited features, profile limits, allowance limits |
| entitled account | Active subscription | Full access, unlimited features |
| Expired User | Subscription ended | Was subscribed, now limited |
| Any | Applies to all | Universal functionality |

---

## Subscription States

| State | Description |
|-------|-------------|
| No Subscription | Free tier user |
| Active Subscription | Currently subscribed |
| Expired Subscription | Was subscribed, now expired |
| Trial | On free trial period |
| Any | Applies regardless of subscription |

---

## Screen References (app specific)

| Screen | Description |
|--------|-------------|
| Home page | Main dashboard |
| Switch Profile bottom sheet | Profile switcher modal |
| Adding new profile | Profile creation form |
| Edit profile | Profile editing form |
| Chat page | Chat list and conversations |
| Reports page | Report categories and downloads |
| Top-up screen | Balance top-up flow |
| Expert Gold screen | Gold subscription purchase |
| Transaction history | Payment and purchase history |
| Side menu | Hamburger menu |
| Subscription flow | Subscription purchase screens |
| Multi profile limit reached | Upgrade modal for free users |

---

## Example Test Cases (Gold Standard)

### Example 1: Critical Data Isolation Test
```
Test Case ID: TC_UI_DI_005
Priority: P0
Category: Data Isolation
User Type: Any
Subscription State: Any
Subcategory: No Cross Profile Data
Screen Reference: Chat page
Precondition: Active on Profile B
Test Scenario: Verify that Profile B cannot see Profile A's chat messages
Steps to Execute: 1. Switch to B 2. Check all chats
Expected Result: Zero visibility of Profile A's conversations
```

### Example 2: Form Validation Test
```
Test Case ID: TC_UI_PC_007
Priority: P1
Category: Profile Creation
User Type: Any
Subscription State: Any
Subcategory: Form - Name Max 200 Chars
Screen Reference: Adding new profile
Precondition: Profile creation form open
Test Scenario: Verify that Name field accepts up to 200 characters
Steps to Execute: 1. Enter 200 character name 2. Try to enter more
Expected Result: Field accepts 200 chars; blocks or truncates beyond
```

### Example 3: Subscription State Test
```
Test Case ID: TC_UI_SS_002
Priority: P0
Category: Subscription States
User Type: Free User
Subscription State: No Subscription
Subcategory: Free - Limit Modal
Screen Reference: Multi profile limit reached
Precondition: Free user at 2 profile limit
Test Scenario: Verify that modal appears with upgrade CTA when free user at limit
Steps to Execute: 1. Tap Avatar 2. Tap Add Profile
Expected Result: Modal with 'Unlock unlimited profiles' and button
```

### Example 4: Performance Test
```
Test Case ID: TC_UI_PERF_001
Priority: P1
Category: Performance
User Type: Any
Subscription State: Any
Subcategory: Switch Speed
Screen Reference: Any screen
Precondition: Multiple profiles exist
Test Scenario: Verify that profile switch completes UI update within 2 seconds
Steps to Execute: 1. Initiate profile switch 2. Time UI update
Expected Result: All UI elements update in < 2 seconds
```

### Example 5: Edge Case Test
```
Test Case ID: TC_UI_EC_003
Priority: P1
Category: Edge Cases
User Type: Any
Subscription State: Any
Subcategory: Network Fail - Create
Screen Reference: Adding new profile
Precondition: Network disconnected
Test Scenario: Verify that network error during create shows toast; user must retry save manually
Steps to Execute: 1. Fill form 2. Disconnect 3. Save
Expected Result: 'Internet connection loss' toast; no draft save; user taps Save again to retry
```

---

## Subcategory Naming Patterns

Use consistent naming for subcategories:

| Pattern | Example | Use For |
|---------|---------|---------|
| `[Element] - [State]` | "Form - Name Empty Error" | Form field states |
| `[Action] - [Target]` | "Switch - Active Badge Moves" | User actions |
| `[Component] Visible` | "Avatar Visible" | Visibility checks |
| `[Feature] - [Behavior]` | "Limit Modal Appears" | Feature behavior |
| `[Screen] - [Element]` | "Sheet - Header" | Screen elements |
| `[State] - [Condition]` | "Free - Add Enabled" | State-based tests |

---

## Steps to Execute Format

Always use numbered steps:
- Start with "1. "
- Use action verbs: Tap, Observe, Enter, Navigate, Wait, Scroll
- Be specific about UI elements
- Separate distinct actions

Good: `1. Tap Avatar in top-left corner 2. Observe profile list`
Bad: `Click avatar and check profiles`

---

## Expected Result Format

- Be specific and measurable
- Include exact text when relevant
- Use semicolons to separate multiple conditions
- Describe visual states clearly

Good: `Green 'Active' badge visible on the card; name displays correctly`
Bad: `Badge shows up`

---

## Comments Field Usage

Use Comments for:
- Known issues: "This may be Backend Issue, Add in Bugs as well"
- Dependencies: "Requires feature flag enabled"
- Clarifications: "Not Implemented yet"
- Related bugs: "See BUG-123"

---

## QA Status Values

| Status | Meaning |
|--------|---------|
| Not Started | Test not yet executed |
| Passed | Test executed successfully |
| Failed | Test found a bug |
| Blocked | Cannot test due to dependency |
| Not Ready | Feature not implemented yet |
