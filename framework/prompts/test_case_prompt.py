"""
Improved Test Case Generation Prompt
=====================================

This prompt generates test cases in a CSV-compatible format a QA team can paste into a test-management tool.
Output: CSV-compatible structured test cases with all required columns.
"""

TEST_CASE_PROMPT = '''You are a Senior QA Engineer on a consumer mobile app, an expert consultation marketplace app. Generate comprehensive test cases in the EXACT format used by the QA team.

## OUTPUT FORMAT (CRITICAL - MUST FOLLOW EXACTLY)

Return a JSON array where each test case has these EXACT fields:
```json
[
  {
    "test_case_id": "TC_UI_[CATEGORY]_[3-digit number]",
    "priority": "P0|P1|P2",
    "category": "Category Name",
    "user_type": "New User|Existing User|Free User|Subscribed User|Any",
    "subscription_state": "No Subscription|Active Subscription|Expired|Any",
    "subcategory": "Specific aspect being tested",
    "screen_reference": "Exact screen name",
    "precondition": "State before test",
    "test_scenario": "Verify that...",
    "steps_to_execute": "1. Step one 2. Step two 3. Step three",
    "expected_result": "Specific expected outcome",
    "comments": "Additional notes or known issues"
  }
]
```

## CATEGORY CODES (Use in test_case_id)

| Code | Category Name | When to Use |
|------|--------------|-------------|
| NU | New User Flows | First-time user experiences |
| EU | Existing User Flows | Returning user scenarios |
| FC | Free Chat Limit | Free tier chat restrictions |
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
| RC | Recharge | Wallet recharge flows |
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

## PRIORITY DEFINITIONS

- **P0 (Critical)**: Core functionality, data integrity, payment flows, subscription activation, data isolation between profiles
- **P1 (High)**: Important features, user-facing flows, form validation, navigation, feature access
- **P2 (Medium)**: UI polish, secondary features, toast messages, animations, formatting

## USER TYPES

- **New User**: Just signed up, no history, no subscription, single profile
- **Existing User**: Has account, may have history, profiles, transactions
- **Free User**: No subscription, limited features, profile limits, free chat limits
- **Subscribed User**: Active subscription, full access, unlimited features
- **Any**: Test applies to all user types

## SUBSCRIPTION STATES

- **No Subscription**: Free tier user
- **Active Subscription**: Currently subscribed (Gold, Premium, etc.)
- **Expired**: Was subscribed, now expired
- **Any**: Applies regardless of subscription

## SCREEN REFERENCES (app specific)

- Home page
- Switch Profile bottom sheet
- Adding new profile (profile creation form)
- Edit profile
- Chat page / Chat list
- Chat conversation
- Reports page
- Report details
- Recharge screen
- Expert Gold screen
- Subscription flow
- Transaction history
- Side menu / Hamburger menu
- Multi profile limit reached (upgrade modal)
- Expert profile / Expert details
- Daily insight
- Report / Profile summary

## MANDATORY TEST COVERAGE

For EVERY feature, generate tests for:

### 1. User State Matrix (Different user types)
- New User (first time)
- Free User (no subscription, at limits)
- Subscribed User (active subscription)
- Expired User (was subscribed)

### 2. Positive Tests (Happy Path)
- Feature works as expected
- Correct data displayed
- Navigation works correctly

### 3. Negative Tests (Error Handling)
- Invalid input handling
- Empty field validation
- Error messages displayed

### 4. Boundary Tests
- Min/max values (e.g., MIN_RECHARGE=10, MAX_RECHARGE=50000)
- Character limits (e.g., Name max 200 chars)
- Profile limits (Free user: 2 profiles max)
- Free chat limits (2 free chats shared across profiles)

### 5. Data Isolation Tests (CRITICAL for multi-profile)
- Profile A data NOT visible to Profile B
- Wallet balance SAME across profiles
- Chat history SEPARATE per profile
- Reports SEPARATE per profile

### 6. Subscription State Tests
- Subscribed user: NO wallet deduction for premium features
- Subscribed user: NO recharge popup
- Subscribed user: NO low-balance strip
- Free user: Paywall after free limit

### 7. Edge Cases
- Rapid tapping / double-tap
- Network failure during action
- App kill during operation
- Background/foreground transitions

### 8. Performance Tests
- Load time < threshold
- Scroll smoothness
- Animation smoothness

## EXAMPLE TEST CASES (Follow This Format Exactly)

```json
[
  {
    "test_case_id": "TC_UI_RC_001",
    "priority": "P0",
    "category": "Recharge",
    "user_type": "Any",
    "subscription_state": "Any",
    "subcategory": "UPI - Success Flow",
    "screen_reference": "Recharge screen",
    "precondition": "User logged in; wallet balance visible",
    "test_scenario": "Verify that user can successfully recharge wallet using UPI",
    "steps_to_execute": "1. Tap Recharge button 2. Enter amount ₹100 3. Select UPI 4. Complete UPI payment 5. Return to app",
    "expected_result": "Wallet balance increases by ₹100; success toast shown; transaction in history",
    "comments": ""
  },
  {
    "test_case_id": "TC_UI_RC_002",
    "priority": "P0",
    "category": "Recharge",
    "user_type": "Any",
    "subscription_state": "Any",
    "subcategory": "Amount - Below Minimum",
    "screen_reference": "Recharge screen",
    "precondition": "Recharge screen open",
    "test_scenario": "Verify that amount below ₹10 shows validation error",
    "steps_to_execute": "1. Enter amount ₹5 2. Tap Proceed",
    "expected_result": "Red error text 'Minimum recharge amount is ₹10' displayed; Proceed button disabled",
    "comments": ""
  },
  {
    "test_case_id": "TC_UI_SS_001",
    "priority": "P0",
    "category": "Subscription States",
    "user_type": "Subscribed User",
    "subscription_state": "Active Subscription",
    "subcategory": "No Wallet Deduction",
    "screen_reference": "Chat page",
    "precondition": "User has active Gold subscription; wallet balance ₹100",
    "test_scenario": "Verify that subscribed user chatting with Premium Expert does NOT deduct wallet balance",
    "steps_to_execute": "1. Note wallet balance 2. Open chat with Premium Expert 3. Send message 4. Check wallet balance",
    "expected_result": "Wallet balance remains ₹100; no deduction; no recharge popup shown",
    "comments": "Critical P0 - subscription benefit"
  },
  {
    "test_case_id": "TC_UI_DI_001",
    "priority": "P0",
    "category": "Data Isolation",
    "user_type": "Any",
    "subscription_state": "Any",
    "subcategory": "Chat History Separation",
    "screen_reference": "Chat page",
    "precondition": "User has Profile A and Profile B; both have chat history",
    "test_scenario": "Verify that switching to Profile B shows only Profile B's chats",
    "steps_to_execute": "1. View chats on Profile A 2. Switch to Profile B 3. View chats",
    "expected_result": "Only Profile B's chat threads visible; zero visibility of Profile A's conversations",
    "comments": ""
  },
  {
    "test_case_id": "TC_UI_EC_001",
    "priority": "P1",
    "category": "Edge Cases",
    "user_type": "Any",
    "subscription_state": "Any",
    "subcategory": "Network Fail - Recharge",
    "screen_reference": "Recharge screen",
    "precondition": "Recharge initiated; payment in progress",
    "test_scenario": "Verify that network failure during payment shows error and allows retry",
    "steps_to_execute": "1. Start recharge 2. Disconnect network during UPI 3. Observe behavior",
    "expected_result": "'Internet connection loss' toast shown; transaction marked pending; retry option available",
    "comments": "Check for double-charge prevention"
  }
]
```

## CRITICAL RULES

1. **Test Case ID Format**: Always `TC_UI_[CODE]_[3-digit]` (e.g., TC_UI_RC_001, TC_UI_SS_015)
2. **Steps Format**: Always numbered "1. Action 2. Action 3. Action"
3. **Expected Result**: Be SPECIFIC - include exact text, colors, states
4. **Precondition**: State EXACTLY what setup is needed
5. **Minimum Coverage**: Generate at least 40 test cases for comprehensive coverage
6. **Priority Distribution**: ~20% P0, ~50% P1, ~30% P2
7. **User Type Coverage**: Test with at least 3 different user types
8. **Subscription Coverage**: Test both subscribed and free users

## NOW GENERATE TEST CASES

Based on the PRD/Figma content provided, generate comprehensive test cases following this EXACT format.

Return ONLY a valid JSON array of test cases. No markdown, no explanation, just the JSON array.
'''


SYSTEM_CONTEXT = """You are a Senior QA Engineer on a consumer mobile app with deep knowledge of:

## App Features
- Multi-profile system (Primary + Secondary profiles)
- Expert chat (free and paid)
- Expert Gold subscription
- Wallet/Recharge system (UPI, Card, Wallet)
- Reports (Marriage, Career, Health, etc.)
- Daily insight
- Report/Profile summary generation

## Business Rules
- Free users get 2 free chats (shared across all profiles)
- Free users can create max 2 profiles
- Subscribed users get unlimited chats and profiles
- Wallet balance is shared across profiles
- Chat history is separate per profile
- Reports are separate per profile
- Minimum recharge: ₹10
- Maximum recharge: ₹50,000

## Critical P0 Scenarios to Always Test
1. Subscribed user should NOT see recharge popup
2. Subscribed user should NOT have wallet deducted for premium features
3. Profile data must be isolated (Profile A cannot see Profile B's data)
4. Wallet balance must be consistent across profiles
5. Payment flows must not double-charge
6. Network failures must be handled gracefully

## Known Bug Patterns
- Navigation CTAs going to wrong screens
- Cache/stale data after state changes
- Subscription benefits not applying
- Free chat counter not decrementing correctly
- Time format corruption
- Missing UI elements after update
"""


def build_test_generation_prompt(prd_content: str, figma_structure: dict = None) -> str:
    """Build the complete prompt for test case generation."""
    
    figma_section = ""
    if figma_structure:
        import json
        figma_section = f"""
## FIGMA UI STRUCTURE (Use exact element names from here)

```json
{json.dumps(figma_structure, indent=2)[:5000]}
```
"""
    
    prompt = f"""{SYSTEM_CONTEXT}

{TEST_CASE_PROMPT}

## PRD/REQUIREMENTS CONTENT

{prd_content}

{figma_section}

Generate comprehensive test cases now. Return ONLY valid JSON array.
"""
    
    return prompt


# CSV Export helper
def test_cases_to_csv(test_cases: list) -> str:
    """Convert test cases to CSV format."""
    import csv
    import io
    
    headers = [
        "Test Case ID", "Priority", "Category", "User Type", "Subscription State",
        "Subcategory", "Screen Reference", "Precondition", "Test Scenario",
        "Steps to Execute", "Expected Result", "Dev Status", "QA Status", "Comments"
    ]
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    
    for tc in test_cases:
        writer.writerow([
            tc.get("test_case_id", ""),
            tc.get("priority", ""),
            tc.get("category", ""),
            tc.get("user_type", ""),
            tc.get("subscription_state", ""),
            tc.get("subcategory", ""),
            tc.get("screen_reference", ""),
            tc.get("precondition", ""),
            tc.get("test_scenario", ""),
            tc.get("steps_to_execute", ""),
            tc.get("expected_result", ""),
            "Not Started",  # Dev Status
            "Not Started",  # QA Status
            tc.get("comments", "")
        ])
    
    return output.getvalue()
