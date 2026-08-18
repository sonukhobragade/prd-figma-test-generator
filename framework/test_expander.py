"""Test case expander - converts checklist to detailed CSV test cases."""

import csv
import logging
from pathlib import Path
from typing import List

from framework.models import (
    BackendTestCase,
    BackendTestChecklist,
    BackendTestPoint,
    TestCase,
    TestChecklist,
    TestPoint,
    TruthTableEntry,
)

logger = logging.getLogger(__name__)


class TestExpanderError(Exception):
    """Custom exception for test expander errors."""

    # pytest tries to collect any class named Test*; these are not tests.
    __test__ = False

    pass


class TestCaseExpander:
    """Expand checklist into detailed CSV test cases."""

    # pytest tries to collect any class named Test*; these are not tests.
    __test__ = False

    def __init__(self):
        """Initialize test case expander."""
        self.test_case_counter = 1
        logger.info("Test case expander initialized")

    # Category code mapping for test case IDs
    CATEGORY_CODES = {
        "positive": "POS",
        "negative": "NEG",
        "edge_case": "EC",
        "boundary": "BND",
        "user_journey": "UJ",
        "subscription_state": "SS",
        "navigation": "NAV",
        "ui_compliance": "UI",
        "data_sync": "DS",
        "state_propagation": "SP",
        "feature_gating": "FG",
    }

    # Category names mapping
    CATEGORY_NAMES = {
        "positive": "Happy Path",
        "negative": "Error Handling",
        "edge_case": "Edge Cases",
        "boundary": "Boundary Testing",
        "user_journey": "User Journeys",
        "subscription_state": "Subscription States",
        "navigation": "Navigation Testing",
        "ui_compliance": "UI Compliance",
        "data_sync": "Data Sync",
        "state_propagation": "State Propagation",
        "feature_gating": "Feature Gating",
    }

    def _generate_test_case_id(
        self, priority: str, feature: str, test_type: str = None, scenario: str = ""
    ) -> str:
        """Generate unique test case ID in format TC_UI_[CAT]_[NUM].

        Args:
            priority: Test priority (P0-P2).
            feature: Feature name.
            test_type: Type of test for category code.
            scenario: Test scenario text for uniqueness hash.

        Returns:
            Test case ID (e.g., "TC_UI_NAV_001").
        """
        import hashlib

        # Get category code from test type
        cat_code = self.CATEGORY_CODES.get(test_type, "GEN")

        # Create a short hash from scenario to ensure uniqueness
        scenario_hash = ""
        if scenario:
            hash_input = f"{feature}_{test_type}_{scenario}"
            scenario_hash = hashlib.md5(hash_input.encode()).hexdigest()[:4].upper()

        tc_id = f"TC_UI_{cat_code}_{self.test_case_counter:03d}"
        if scenario_hash:
            tc_id = f"{tc_id}_{scenario_hash}"

        self.test_case_counter += 1
        return tc_id

    def _derive_category(self, test_type: str, feature: str) -> str:
        """Derive category name from test type and feature.

        Args:
            test_type: Type of test.
            feature: Feature name.

        Returns:
            Category name string.
        """
        # Use category name from mapping, or derive from feature
        if test_type in self.CATEGORY_NAMES:
            return self.CATEGORY_NAMES[test_type]

        # Fallback to feature-based category
        feature_lower = feature.lower()
        if "login" in feature_lower or "auth" in feature_lower:
            return "Authentication"
        elif "profile" in feature_lower:
            return "Profile Management"
        elif "subscription" in feature_lower or "payment" in feature_lower:
            return "Subscription & Payments"
        elif "chat" in feature_lower:
            return "Chat Features"
        elif "report" in feature_lower:
            return "Reports"
        elif "navigation" in feature_lower or "menu" in feature_lower:
            return "Navigation"
        else:
            return "General Features"

    def _derive_user_type(self, description: str, test_type: str) -> str:
        """Derive user type from description and test type.

        Args:
            description: Test description.
            test_type: Type of test.

        Returns:
            User type string.
        """
        desc_lower = description.lower()

        if "new user" in desc_lower:
            return "New User"
        elif "existing user" in desc_lower:
            return "Existing User"
        elif "subscribed" in desc_lower or "subscriber" in desc_lower:
            return "Subscribed User"
        elif "free user" in desc_lower or "non-subscribed" in desc_lower:
            return "Free User"
        elif "half-onboarded" in desc_lower or "incomplete" in desc_lower:
            return "Incomplete Profile User"
        elif test_type == "subscription_state":
            return "Subscribed User"  # Default for subscription tests
        else:
            return "Any"

    def _derive_screen_reference(self, description: str, feature: str) -> str:
        """Derive screen reference from description and feature.

        Args:
            description: Test description.
            feature: Feature name.

        Returns:
            Screen reference string.
        """
        desc_lower = description.lower()

        # Common screen references
        screen_mappings = [
            ("home", "Home Page"),
            ("login", "Login Screen"),
            ("otp", "OTP Verification Screen"),
            ("profile", "Profile Screen"),
            ("chat", "Chat Page"),
            ("report", "Reports Page"),
            ("subscription", "Subscription Page"),
            ("payment", "Payment Screen"),
            ("wallet", "Wallet Screen"),
            ("settings", "Settings Screen"),
            ("menu", "Side Menu"),
            ("bottom sheet", "Bottom Sheet"),
            ("modal", "Modal Dialog"),
            ("toast", "Toast Notification"),
            ("expert", "Expert Selection Screen"),
            ("transaction", "Transaction History"),
        ]

        for keyword, screen_name in screen_mappings:
            if keyword in desc_lower:
                return screen_name

        # Fallback to feature name
        return f"{feature} Screen"

    def _derive_precondition(self, description: str, test_type: str) -> str:
        """Derive precondition from description and test type.

        Args:
            description: Test description.
            test_type: Type of test.

        Returns:
            Precondition string.
        """
        desc_lower = description.lower()

        # Extract subscription state for precondition
        subscription_state = ""
        if "subscribed" in desc_lower or "active subscription" in desc_lower:
            subscription_state = "User has active subscription; "
        elif "free user" in desc_lower or "no subscription" in desc_lower:
            subscription_state = "User has no subscription; "
        elif "expired" in desc_lower:
            subscription_state = "User subscription expired; "

        # Test type based preconditions
        if test_type == "subscription_state":
            if not subscription_state:
                subscription_state = "Specific subscription state required; "
            return f"{subscription_state}User logged in"
        elif test_type == "navigation":
            return f"{subscription_state}User on starting screen; CTA visible"
        elif test_type == "ui_compliance":
            return f"{subscription_state}Figma design available for comparison"
        elif test_type == "data_sync":
            return f"{subscription_state}Initial data state noted"
        elif test_type == "feature_gating":
            return f"{subscription_state}User missing required prerequisite"
        elif test_type == "user_journey":
            return f"{subscription_state}User authenticated and on initial screen"
        elif test_type == "negative":
            return f"{subscription_state}Test environment ready for invalid input"
        elif test_type == "boundary":
            return f"{subscription_state}Input field accessible for boundary testing"
        elif test_type == "edge_case":
            return f"{subscription_state}System ready for edge case input"
        else:
            return f"{subscription_state}User logged in" if subscription_state else "User logged in"

    def _format_test_scenario(self, description: str) -> str:
        """Format test scenario to start with 'Verify that...'.

        Args:
            description: Original test description.

        Returns:
            Formatted test scenario starting with 'Verify that...'.
        """
        # Already starts with "Verify that"
        if description.lower().startswith("verify that"):
            return description

        # Common prefixes to replace
        prefixes_to_replace = [
            "test that ", "check that ", "ensure that ", "confirm that ",
            "validate that ", "assert that ", "test ", "check ", "verify "
        ]

        desc_lower = description.lower()
        for prefix in prefixes_to_replace:
            if desc_lower.startswith(prefix):
                remaining = description[len(prefix):]
                return f"Verify that {remaining}"

        # Just prepend "Verify that"
        return f"Verify that {description.lower()}"

    def generate_test_steps(
        self, test_point: TestPoint, include_setup: bool = True
    ) -> str:
        """Generate elegant, specific test steps using detailed prompt templates.

        Uses rich examples and context for each test type to guide better test generation.
        Frontend can style with proper SVG icons.

        Args:
            test_point: Test point to expand.
            include_setup: Whether to include setup steps.

        Returns:
            Formatted test steps for frontend SVG icon rendering.
        """
        description = test_point.description
        feature = test_point.feature

        # Use detailed prompt templates based on test type
        if test_point.test_type == "positive":
            return self._generate_positive_steps(description, feature)
        elif test_point.test_type == "negative":
            return self._generate_negative_steps(description, feature, include_setup)
        elif test_point.test_type == "boundary":
            return self._generate_boundary_steps(description, feature, include_setup)
        elif test_point.test_type == "edge_case":
            return self._generate_edge_case_steps(description, feature, include_setup)
        elif test_point.test_type == "user_journey":
            return self._generate_user_journey_steps(description, feature, test_point.screens or [])
        elif test_point.test_type == "subscription_state":
            return self._generate_subscription_state_steps(description, feature, include_setup)
        elif test_point.test_type == "navigation":
            return self._generate_navigation_steps(description, feature, include_setup)
        elif test_point.test_type == "ui_compliance":
            return self._generate_ui_compliance_steps(description, feature, include_setup)
        elif test_point.test_type == "data_sync":
            return self._generate_data_sync_steps(description, feature, include_setup)
        elif test_point.test_type == "state_propagation":
            return self._generate_state_propagation_steps(description, feature, include_setup)
        elif test_point.test_type == "feature_gating":
            return self._generate_feature_gating_steps(description, feature, include_setup)
        else:
            # Fallback for unknown types
            return f"1. Execute: {description}\n   • Verify expected behavior"

    def _generate_positive_steps(self, description: str, feature: str) -> str:
        """Generate positive/happy path test steps with detailed examples.

        Context: User successfully completes their goal, all UI works as expected.

        Good Example (Login Flow):
        1. Launch app and navigate to login screen
           • "Phone Number" label is visible above input field
           • Input field is active with cursor blinking
           • Country code "+91" is pre-filled
           • "Continue" button is enabled and visible

        2. Enter valid phone number "5550000001"
           • Number appears in input field as typed
           • Format automatically adjusts (e.g., "555-000-0001")
           • "Continue" button remains enabled
           • No error messages displayed

        3. Tap "Continue" button and verify OTP screen transition
           • Smooth animation from login to OTP screen
           • OTP screen displays within 2 seconds
           • 6 OTP input boxes are visible and active
           • Timer shows "Resend OTP in 59 seconds"
           • Back button is visible to return to login
        """
        steps = []

        # Step 1: Initial action with detailed UI verification
        steps.append(
            f"1. {description}\n"
            f"   • All {feature} UI elements are visible and properly positioned\n"
            f"   • Interactive elements (buttons, inputs) are enabled and responsive\n"
            f"   • Labels and instructions are clear and readable"
        )

        # Step 2: Action execution with state verification
        steps.append(
            f"2. Execute the main action for {feature}\n"
            f"   • Action completes without errors or delays\n"
            f"   • UI updates immediately to reflect changes\n"
            f"   • Loading indicators appear if action takes >1 second"
        )

        # Step 3: Success verification
        steps.append(
            f"3. Verify successful completion of {feature}\n"
            f"   • Success confirmation message or visual feedback appears\n"
            f"   • Data is saved and persisted correctly\n"
            f"   • User can proceed to next step or screen\n"
            f"   • No error messages or warnings displayed"
        )

        return "\n".join(steps)

    def _generate_negative_steps(
        self, description: str, feature: str, include_setup: bool
    ) -> str:
        """Generate negative test steps with detailed error handling examples.

        Context: Test invalid inputs, verify error messages, ensure graceful degradation.

        Good Example (Invalid Phone Number):
        1. Setup: Navigate to phone number input screen

        2. Enter invalid phone number "123" (too short)
           • Error message appears: "Phone number must be 10 digits"
           • Error message is displayed in red below input field
           • Warning icon (⚠️) appears next to error text
           • Input field border turns red
           • "Continue" button becomes disabled

        3. Verify system protection and user guidance
           • Tapping disabled "Continue" button shows no action
           • Error message persists until input is corrected
           • App does not crash or freeze
           • Previous valid data is not corrupted

        4. Test user recovery path
           • User can clear the invalid input
           • Error message disappears when valid input entered
           • "Continue" button re-enables with valid input
           • User can successfully proceed after correction
        """
        steps = []
        step_num = 1

        if include_setup:
            steps.append(
                f"{step_num}. Setup: Prepare test environment for negative scenario - {description[:80]}"
            )
            step_num += 1

        # Step: Attempt invalid action
        steps.append(
            f"{step_num}. Attempt invalid action: {description}\n"
            f"   • Invalid input or action is executed\n"
            f"   • System detects the invalid operation\n"
            f"   • Observe immediate system response"
        )
        step_num += 1

        # Step: Verify error handling
        steps.append(
            f"{step_num}. Verify error handling for {feature}\n"
            f"   • Clear error message appears (e.g., 'Invalid {feature}')\n"
            f"   • Error message explains what went wrong\n"
            f"   • Error message suggests how to fix it\n"
            f"   • Visual indicators (red border, warning icon) appear"
        )
        step_num += 1

        # Step: Confirm system protection
        steps.append(
            f"{step_num}. Confirm system protection\n"
            f"   • Invalid operation is blocked/prevented\n"
            f"   • No data corruption or partial saves\n"
            f"   • Application remains stable (no crash or freeze)\n"
            f"   • Other features continue to work normally"
        )
        step_num += 1

        # Step: Verify recovery
        steps.append(
            f"{step_num}. Verify user can recover from error\n"
            f"   • Error message can be dismissed or cleared\n"
            f"   • User can correct the input and retry\n"
            f"   • System accepts valid input after error\n"
            f"   • User can successfully complete action after correction"
        )

        return "\n".join(steps)

    def _generate_boundary_steps(
        self, description: str, feature: str, include_setup: bool = False
    ) -> str:
        """Generate concise, elegant boundary test steps.

        Context: Test minimum and maximum acceptable values, verify limits are enforced.

        Good Example (Text Input Length):
        1. Test minimum boundary (0 characters)
           • Verify error: "This field is required"
           • Submit button is disabled

        2. Test maximum boundary (100 characters)
           • Input is accepted and saved correctly
           • No truncation occurs

        3. Test beyond maximum (101 characters)
           • Input is rejected with clear error message
           • Counter shows "100/100 characters"
        """
        steps = []
        step_num = 1

        # Step: Test at minimum boundary
        steps.append(
            f"{step_num}. Test minimum value: {description}\n"
            f"   • Enter minimum acceptable value\n"
            f"   • Verify acceptance and correct processing"
        )
        step_num += 1

        # Step: Test at maximum boundary
        steps.append(
            f"{step_num}. Test maximum value for {feature}\n"
            f"   • Enter maximum acceptable value\n"
            f"   • Confirm value is accepted and processed"
        )
        step_num += 1

        # Step: Test beyond boundaries
        steps.append(
            f"{step_num}. Test values beyond limits\n"
            f"   • Attempt values below/above boundaries\n"
            f"   • Verify rejection with clear validation message"
        )

        return "\n".join(steps)

    def _generate_edge_case_steps(
        self, description: str, feature: str, include_setup: bool
    ) -> str:
        """Generate edge case test steps for unusual/extreme scenarios.

        Context: Test unusual inputs, special characters, extreme conditions.

        Good Example (Special Characters in Name):
        1. Setup: Navigate to name input field

        2. Enter name with special characters: "O'Brien-Smith Jr."
           • Verify apostrophe (') is accepted
           • Verify hyphen (-) is accepted
           • Verify period (.) is accepted
           • Verify spaces are handled correctly

        3. Test extreme cases
           • Single character name: "X"
           • Name with numbers: "John123"
           • Name with emojis: "John😀Smith"
           • Unicode characters: "José" or "北京"

        4. Verify graceful handling
           • Either accept with success OR
           • Reject with helpful message: "Only letters and spaces allowed"
           • No crashes or unexpected behavior
        """
        steps = []
        step_num = 1

        if include_setup:
            steps.append(
                f"{step_num}. Setup: Configure edge case test environment - {description[:80]}"
            )
            step_num += 1

        # Step: Execute edge case
        steps.append(
            f"{step_num}. Execute edge case scenario: {description}\n"
            f"   • Use unusual or extreme inputs\n"
            f"   • Test special characters, symbols, or formats\n"
            f"   • Try unexpected data types or values"
        )
        step_num += 1

        # Step: Verify handling
        steps.append(
            f"{step_num}. Verify graceful handling of edge case\n"
            f"   • System either accepts unusual input successfully OR\n"
            f"   • System rejects with clear, helpful error message\n"
            f"   • No cryptic errors or technical jargon shown to user"
        )
        step_num += 1

        # Step: Check data integrity
        steps.append(
            f"{step_num}. Confirm data integrity for {feature}\n"
            f"   • No data corruption from edge case input\n"
            f"   • No side effects on other features or data\n"
            f"   • Previously saved data remains intact\n"
            f"   • Database/storage is not corrupted"
        )
        step_num += 1

        # Step: Verify recovery
        steps.append(
            f"{step_num}. Verify system recovery after edge case\n"
            f"   • Normal operations can resume immediately\n"
            f"   • No lasting impact from edge case test\n"
            f"   • System returns to stable state\n"
            f"   • User can continue using other features"
        )

        return "\n".join(steps)

    def _generate_subscription_state_steps(
        self, description: str, feature: str, include_setup: bool
    ) -> str:
        """Generate subscription state test steps.

        Context: Test behavior with different subscription states (subscribed, new, expired).

        Good Example (Subscribed User Chat):
        1. Precondition: Login with Active Subscription (wallet balance = 0)
           • Verify subscription is active in profile/settings
           • Verify wallet balance shows ₹0

        2. Navigate to Premium Expert chat
           • Open Expert list and select a Premium Expert
           • Verify Premium tag is visible on Expert card

        3. Verify subscribed user experience
           • NO low-balance strip appears
           • NO recharge popup shown
           • Chat input is enabled and functional
           • Send message button works without interruption

        4. Send a message and verify no deduction
           • Type and send a message
           • Message is sent successfully
           • NO wallet/coin deduction occurs
           • NO payment prompts appear
        """
        steps = []
        step_num = 1

        if include_setup:
            steps.append(
                f"{step_num}. Precondition: Setup user state for subscription test\n"
                f"   • Login with specified subscription state\n"
                f"   • Verify subscription status in profile/settings\n"
                f"   • Note wallet balance before test"
            )
            step_num += 1

        steps.append(
            f"{step_num}. Execute action: {description}\n"
            f"   • Navigate to the feature being tested\n"
            f"   • Perform the primary action"
        )
        step_num += 1

        steps.append(
            f"{step_num}. Verify subscription-based behavior for {feature}\n"
            f"   • Check that subscription benefits are applied\n"
            f"   • Verify NO paywall/recharge prompts appear (if subscribed)\n"
            f"   • Verify correct prompts appear (if not subscribed)\n"
            f"   • Confirm no unexpected deductions or charges"
        )
        step_num += 1

        steps.append(
            f"{step_num}. Verify state consistency\n"
            f"   • Wallet balance unchanged (if subscription should cover it)\n"
            f"   • Subscription status remains correct\n"
            f"   • UI reflects correct subscription state"
        )

        return "\n".join(steps)

    def _generate_navigation_steps(
        self, description: str, feature: str, include_setup: bool
    ) -> str:
        """Generate navigation/CTA correctness test steps.

        Context: Test that buttons navigate to correct destinations.

        Good Example (Subscribe Now CTA):
        1. Navigate to Home screen
           • Home screen loads completely
           • Subscribe Now CTA is visible

        2. Tap 'Subscribe Now' CTA
           • Button responds to tap
           • Loading indicator appears (if any)

        3. Verify navigation destination
           • Subscription Page opens (NOT Reports Page)
           • Subscription plans are visible
           • Back button is functional

        4. Test back navigation
           • Tap back button
           • Returns to Home screen (not stuck)
           • No crash or freeze
        """
        steps = []
        step_num = 1

        if include_setup:
            steps.append(
                f"{step_num}. Setup: Navigate to starting screen\n"
                f"   • Ensure you're on the correct starting screen\n"
                f"   • Verify the CTA/button is visible"
            )
            step_num += 1

        steps.append(
            f"{step_num}. Execute navigation: {description}\n"
            f"   • Tap/click the CTA or navigation element\n"
            f"   • Observe screen transition"
        )
        step_num += 1

        steps.append(
            f"{step_num}. Verify correct destination for {feature}\n"
            f"   • Confirm you landed on the CORRECT screen\n"
            f"   • Verify it's NOT a wrong screen (e.g., Reports vs Subscription)\n"
            f"   • Check that expected content is displayed"
        )
        step_num += 1

        steps.append(
            f"{step_num}. Verify back navigation\n"
            f"   • Tap hardware back or in-app back button\n"
            f"   • Verify return to previous screen\n"
            f"   • No freeze, crash, or stuck state"
        )

        return "\n".join(steps)

    def _generate_ui_compliance_steps(
        self, description: str, feature: str, include_setup: bool
    ) -> str:
        """Generate UI/Figma compliance test steps.

        Context: Test that visual elements match design specifications.

        Good Example (Premium Tag on Expert Cards):
        1. Navigate to relevant screen
           • Open the screen containing UI elements to verify

        2. Compare with Figma design
           • Check element presence (Premium tag, icons, etc.)
           • Verify colors match design specs
           • Check padding/margins

        3. Verify visual details
           • Strike-through prices visible (if applicable)
           • Discount percentages displayed correctly
           • Shadows and effects match design
           • No legacy UI elements present
        """
        steps = []
        step_num = 1

        if include_setup:
            steps.append(
                f"{step_num}. Setup: Navigate to screen for UI verification\n"
                f"   • Open the relevant screen\n"
                f"   • Have Figma design ready for comparison"
            )
            step_num += 1

        steps.append(
            f"{step_num}. Verify UI element: {description}\n"
            f"   • Check element is present and visible\n"
            f"   • Verify positioning matches Figma"
        )
        step_num += 1

        steps.append(
            f"{step_num}. Compare visual details for {feature}\n"
            f"   • Colors match Figma specs\n"
            f"   • Padding and margins are correct\n"
            f"   • Icons are visible and correct\n"
            f"   • Shadows and effects match design"
        )
        step_num += 1

        steps.append(
            f"{step_num}. Check for absence of legacy elements\n"
            f"   • No old/deprecated UI elements present\n"
            f"   • Design matches current Figma version\n"
            f"   • No visual regressions"
        )

        return "\n".join(steps)

    def _generate_data_sync_steps(
        self, description: str, feature: str, include_setup: bool
    ) -> str:
        """Generate real-time data sync test steps.

        Context: Test immediate data updates after actions.

        Good Example (Balance Update After Purchase):
        1. Note current state before action
           • Check My Balance screen
           • Note current balance/status

        2. Perform action that should trigger update
           • Complete purchase/subscription
           • Wait for success confirmation

        3. Verify immediate data update
           • Navigate to My Balance
           • Verify updated status WITHOUT relaunch
           • No stale data displayed
        """
        steps = []
        step_num = 1

        if include_setup:
            steps.append(
                f"{step_num}. Setup: Note current data state\n"
                f"   • Record current values before action\n"
                f"   • Take screenshot for comparison"
            )
            step_num += 1

        steps.append(
            f"{step_num}. Execute action: {description}\n"
            f"   • Perform the action that should trigger data update\n"
            f"   • Wait for action completion confirmation"
        )
        step_num += 1

        steps.append(
            f"{step_num}. Verify immediate update for {feature}\n"
            f"   • Data reflects new state WITHOUT app relaunch\n"
            f"   • No stale/cached data displayed\n"
            f"   • Update visible within seconds of action"
        )
        step_num += 1

        steps.append(
            f"{step_num}. Verify data consistency across screens\n"
            f"   • Navigate to related screens\n"
            f"   • Same updated data reflected everywhere\n"
            f"   • No conflicting information displayed"
        )

        return "\n".join(steps)

    def _generate_state_propagation_steps(
        self, description: str, feature: str, include_setup: bool
    ) -> str:
        """Generate cross-feature state propagation test steps.

        Context: Test how state changes in one feature affect others.

        Good Example (Subscription Affects Chat):
        1. Establish initial state
           • Verify user state (e.g., subscribed)
           • Note behavior before state change

        2. Change state in Feature A
           • Purchase subscription
           • Verify subscription is active

        3. Verify state propagation to Feature B
           • Navigate to Chat feature
           • Verify subscription benefits apply
           • No paywall prompts appear
        """
        steps = []
        step_num = 1

        if include_setup:
            steps.append(
                f"{step_num}. Setup: Establish initial state\n"
                f"   • Verify current user state\n"
                f"   • Note behavior in related features"
            )
            step_num += 1

        steps.append(
            f"{step_num}. Execute state change: {description}\n"
            f"   • Perform action that changes state\n"
            f"   • Verify state change is confirmed"
        )
        step_num += 1

        steps.append(
            f"{step_num}. Verify state propagation to {feature}\n"
            f"   • Navigate to affected feature\n"
            f"   • Check that new state is reflected\n"
            f"   • Verify expected behavior based on new state"
        )
        step_num += 1

        steps.append(
            f"{step_num}. Verify no unintended side effects\n"
            f"   • Other features work correctly\n"
            f"   • No unexpected behavior or errors\n"
            f"   • Data integrity maintained"
        )

        return "\n".join(steps)

    def _generate_feature_gating_steps(
        self, description: str, feature: str, include_setup: bool
    ) -> str:
        """Generate feature gating/prerequisite test steps.

        Context: Test features that require prerequisites to access.

        Good Example (Subscription Requires Complete Profile):
        1. Setup: Use half-onboarded user
           • Login with incomplete profile
           • Verify profile is incomplete

        2. Attempt to access gated feature
           • Try to purchase subscription
           • Observe blocking behavior

        3. Verify gating message and redirect
           • Clear message: 'Complete Profile to Subscribe'
           • Redirect to onboarding/profile completion
           • Feature is properly blocked
        """
        steps = []
        step_num = 1

        if include_setup:
            steps.append(
                f"{step_num}. Setup: Prepare user without prerequisite\n"
                f"   • Login with user missing required prerequisite\n"
                f"   • Verify prerequisite is not met"
            )
            step_num += 1

        steps.append(
            f"{step_num}. Attempt to access gated feature: {description}\n"
            f"   • Try to access the feature requiring prerequisite\n"
            f"   • Observe system response"
        )
        step_num += 1

        steps.append(
            f"{step_num}. Verify feature gating for {feature}\n"
            f"   • Feature is blocked/inaccessible\n"
            f"   • Clear message explains what's required\n"
            f"   • No partial access or errors"
        )
        step_num += 1

        steps.append(
            f"{step_num}. Verify redirect to prerequisite completion\n"
            f"   • User is redirected to complete prerequisite\n"
            f"   • After completing prerequisite, feature becomes accessible\n"
            f"   • Flow is smooth and intuitive"
        )

        return "\n".join(steps)

    def _generate_user_journey_steps(
        self, description: str, feature: str, screens: List[str]
    ) -> str:
        """Generate user journey test steps for end-to-end flows.

        Context: Test complete user workflows that span multiple screens/features.

        Good Example (Complete Purchase Journey):
        1. Start: Open app and navigate to product catalog
           • Product list loads successfully
           • All product images and details are visible
           • Search and filter options are available

        2. Screen: Product Catalog → Product Details
           • Tap on a product to view details
           • Product details screen opens within 2 seconds
           • All product information (price, description, images) displays
           • "Add to Cart" button is visible and enabled

        3. Screen: Product Details → Shopping Cart
           • Tap "Add to Cart" button
           • Success message appears: "Added to cart"
           • Cart icon shows updated item count
           • Navigate to cart screen
           • Selected product appears in cart

        4. Screen: Shopping Cart → Checkout
           • Tap "Proceed to Checkout"
           • Checkout screen loads with order summary
           • Delivery address form is visible
           • Payment options are available

        5. Screen: Checkout → Payment
           • Fill in delivery address
           • Select payment method
           • Review order summary
           • All prices and totals are correct

        6. Complete: Payment → Order Confirmation
           • Tap "Place Order" button
           • Payment processing indicator appears
           • Order confirmation screen displays
           • Order ID and estimated delivery date shown
           • Confirmation email sent to user

        Args:
            description: User journey description
            feature: Main feature/flow name
            screens: List of screen names in the journey

        Returns:
            Formatted multi-screen journey steps
        """
        steps = []
        step_num = 1

        # Opening step
        steps.append(
            f"{step_num}. Start: {description}\n"
            f"   • User begins the journey from initial screen\n"
            f"   • All initial UI elements are loaded and functional\n"
            f"   • User is authenticated if required"
        )
        step_num += 1

        # Generate steps for each screen in the journey
        if screens and len(screens) > 1:
            for i in range(len(screens) - 1):
                current_screen = screens[i]
                next_screen = screens[i + 1]
                steps.append(
                    f"{step_num}. Screen: {current_screen} → {next_screen}\n"
                    f"   • Execute primary action on {current_screen}\n"
                    f"   • Transition to {next_screen} occurs smoothly\n"
                    f"   • {next_screen} loads within 2 seconds\n"
                    f"   • All {next_screen} UI elements are visible and functional\n"
                    f"   • Data from previous screen is carried forward correctly"
                )
                step_num += 1

            # Final screen/completion step
            final_screen = screens[-1]
            steps.append(
                f"{step_num}. Complete: Reach {final_screen}\n"
                f"   • User successfully completes the journey\n"
                f"   • {final_screen} shows success confirmation\n"
                f"   • All data is saved and persisted\n"
                f"   • User can view results or proceed to next action"
            )
        else:
            # Fallback if no screens specified
            steps.append(
                f"{step_num}. Execute end-to-end flow for {feature}\n"
                f"   • Navigate through all required screens\n"
                f"   • Complete all necessary actions\n"
                f"   • Verify data flow between screens"
            )
            step_num += 1

            steps.append(
                f"{step_num}. Verify successful journey completion\n"
                f"   • All steps complete without errors\n"
                f"   • Final state is achieved\n"
                f"   • User sees confirmation of success"
            )

        # Add journey-wide verification
        step_num += 1
        steps.append(
            f"{step_num}. Verify journey integrity\n"
            f"   • Data consistency maintained across all screens\n"
            f"   • No data loss during screen transitions\n"
            f"   • Back navigation works correctly at each step\n"
            f"   • User can complete journey in single session"
        )

        return "\n".join(steps)

    def _generate_expected_result(self, test_point: TestPoint) -> str:
        """Generate elegant, specific expected results with each point on a new line.

        Creates clear expected outcomes that match the test steps, avoiding vague
        "completes successfully" patterns.

        Args:
            test_point: Test point.

        Returns:
            Specific expected result description with newlines.
        """
        feature = test_point.feature
        description = test_point.description

        if test_point.test_type == "positive":
            return (
                f"✓ {description} completes successfully\n"
                f"✓ All {feature} UI elements display correctly\n"
                f"✓ Data is saved and persisted\n"
                f"✓ User sees confirmation of success\n"
                f"✓ No errors or warnings appear"
            )
        elif test_point.test_type == "negative":
            return (
                f"✓ System rejects invalid action: {description}\n"
                f"✓ Clear error message appears (e.g., 'Invalid {feature}')\n"
                f"✓ No data is corrupted or partially saved\n"
                f"✓ User can dismiss error and retry\n"
                f"✓ Application remains stable (no crash)"
            )
        elif test_point.test_type == "edge_case":
            return (
                f"✓ System handles edge case: {description}\n"
                f"✓ {feature} behaves correctly with unusual inputs\n"
                f"✓ No unexpected side effects occur\n"
                f"✓ Data integrity is maintained\n"
                f"✓ Normal operations can resume"
            )
        elif test_point.test_type == "boundary":
            return (
                f"✓ Boundary values for {feature} are accepted within limits\n"
                f"✓ {description} validates correctly\n"
                f"✓ Values beyond limits are rejected with clear message\n"
                f"✓ No data corruption at boundary conditions\n"
                f"✓ System remains stable at min/max values"
            )
        elif test_point.test_type == "user_journey":
            screens_text = " → ".join(test_point.screens) if test_point.screens else "all screens"
            return (
                f"✓ User journey completes successfully: {description}\n"
                f"✓ User navigates through {screens_text} without errors\n"
                f"✓ Data flows correctly between screens\n"
                f"✓ All screen transitions are smooth and timely\n"
                f"✓ Final goal is achieved and confirmed\n"
                f"✓ User can navigate back at any step\n"
                f"✓ Journey can be completed in single session"
            )
        elif test_point.test_type == "subscription_state":
            return (
                f"✓ Subscription state test passes: {description}\n"
                f"✓ {feature} respects subscription status correctly\n"
                f"✓ NO unexpected paywalls/popups for subscribed users\n"
                f"✓ NO wallet/coin deductions for subscribed users\n"
                f"✓ Correct prompts shown for non-subscribed users\n"
                f"✓ Subscription benefits applied correctly"
            )
        elif test_point.test_type == "navigation":
            return (
                f"✓ Navigation test passes: {description}\n"
                f"✓ CTA navigates to CORRECT destination\n"
                f"✓ NOT navigating to wrong screen\n"
                f"✓ Back button returns to previous screen\n"
                f"✓ No freeze or crash during navigation\n"
                f"✓ Screen transitions are smooth"
            )
        elif test_point.test_type == "ui_compliance":
            return (
                f"✓ UI compliance test passes: {description}\n"
                f"✓ Visual elements match Figma specs\n"
                f"✓ Colors, padding, margins are correct\n"
                f"✓ Icons visible and properly sized\n"
                f"✓ Shadows and effects match design\n"
                f"✓ No legacy UI elements present"
            )
        elif test_point.test_type == "data_sync":
            return (
                f"✓ Data sync test passes: {description}\n"
                f"✓ Data updates immediately after action\n"
                f"✓ NO stale/cached data displayed\n"
                f"✓ No app relaunch required\n"
                f"✓ Data consistent across all screens\n"
                f"✓ Update visible within seconds"
            )
        elif test_point.test_type == "state_propagation":
            return (
                f"✓ State propagation test passes: {description}\n"
                f"✓ State change in one feature propagates to {feature}\n"
                f"✓ Cross-feature behavior is consistent\n"
                f"✓ No unexpected side effects\n"
                f"✓ Data integrity maintained\n"
                f"✓ All affected features reflect new state"
            )
        elif test_point.test_type == "feature_gating":
            return (
                f"✓ Feature gating test passes: {description}\n"
                f"✓ {feature} blocked for users without prerequisite\n"
                f"✓ Clear message explains what's required\n"
                f"✓ User redirected to complete prerequisite\n"
                f"✓ After completing prerequisite, feature accessible\n"
                f"✓ No partial access or security bypass"
            )
        else:
            return f"✓ {description} executes as expected for {feature}"

    def _generate_notes(self, test_point: TestPoint) -> str:
        """Generate additional notes for test case.

        Args:
            test_point: Test point.

        Returns:
            Notes string.
        """
        notes = []

        # Add priority-specific notes
        if test_point.priority == "P0":
            notes.append("CRITICAL: Must be tested before release")
        elif test_point.priority == "P1":
            notes.append("HIGH PRIORITY: Essential for core functionality")

        # Add test type specific notes
        if test_point.test_type == "negative":
            notes.append("Test error handling and validation")
        elif test_point.test_type == "boundary":
            notes.append("Test minimum and maximum acceptable values")
        elif test_point.test_type == "edge_case":
            notes.append("Test unusual or extreme conditions")
        elif test_point.test_type == "user_journey":
            screens_count = len(test_point.screens) if test_point.screens else 0
            if screens_count > 0:
                notes.append(f"End-to-end flow across {screens_count} screens")
            else:
                notes.append("End-to-end user journey test")
        elif test_point.test_type == "subscription_state":
            notes.append("Test behavior with specific subscription state")
        elif test_point.test_type == "navigation":
            notes.append("Verify CTA navigates to correct destination")
        elif test_point.test_type == "ui_compliance":
            notes.append("Compare with Figma design specs")
        elif test_point.test_type == "data_sync":
            notes.append("Verify real-time data updates without relaunch")
        elif test_point.test_type == "state_propagation":
            notes.append("Test cross-feature state changes")
        elif test_point.test_type == "feature_gating":
            notes.append("Verify prerequisite enforcement")

        return " | ".join(notes) if notes else ""

    def _format_steps_numbered(self, test_steps: str) -> str:
        """Format test steps as numbered list with each step on a new line.

        Args:
            test_steps: Original test steps string.

        Returns:
            Numbered steps with each step on a new line.
        """
        # Split by numbered steps and clean up
        lines = test_steps.split("\n")
        numbered_steps = []
        current_step = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if it's a step number (1., 2., etc.)
            if line and line[0].isdigit() and ". " in line[:4]:
                if current_step:
                    numbered_steps.append(current_step.strip())
                # Extract just the main step, not bullet points
                step_content = line.split(". ", 1)[1] if ". " in line else line
                # Remove any content after newline or bullet
                step_content = step_content.split("\n")[0]
                step_content = step_content.split("   •")[0]
                current_step = step_content
            elif line.startswith("•"):
                # Skip bullet points in numbered output
                continue

        if current_step:
            numbered_steps.append(current_step.strip())

        # Format with each step on a NEW LINE for better readability
        formatted = "\n".join([f"{i+1}. {step}" for i, step in enumerate(numbered_steps)])
        return formatted if formatted else test_steps

    def expand_test_point(self, test_point: TestPoint) -> TestCase:
        """Expand single test point into detailed test case using new professional format.

        Args:
            test_point: Test point to expand.

        Returns:
            TestCase instance with all professional QA fields.
        """
        test_type = test_point.test_type or "positive"

        # Generate test case ID with category code and scenario hash for uniqueness
        test_case_id = self._generate_test_case_id(
            test_point.priority, test_point.feature, test_type, test_point.description
        )

        # Derive all the new fields
        category = self._derive_category(test_type, test_point.feature)
        user_type = self._derive_user_type(test_point.description, test_type)
        screen_reference = self._derive_screen_reference(test_point.description, test_point.feature)
        precondition = self._derive_precondition(test_point.description, test_type)

        # Format test scenario to start with "Verify that..."
        test_scenario = self._format_test_scenario(test_point.description)

        # Generate test steps and format as numbered list
        test_steps_detailed = self.generate_test_steps(test_point)
        steps_to_execute = self._format_steps_numbered(test_steps_detailed)

        # Generate expected result and comments
        expected_result = self._generate_expected_result(test_point)
        comments = self._generate_notes(test_point)

        # Map priority P3 to P2 (new format only has P0, P1, P2)
        priority = test_point.priority if test_point.priority in ["P0", "P1", "P2"] else "P2"

        test_case = TestCase(
            test_case_id=test_case_id,
            priority=priority,
            category=category,
            user_type=user_type,
            screen_reference=screen_reference,
            precondition=precondition,
            test_scenario=test_scenario,
            steps_to_execute=steps_to_execute,
            expected_result=expected_result,
            dev_status="Not Started",
            qa_status="Not Started",
            comments=comments,
            feature=test_point.feature,
            screenshot_url=test_point.screenshot_url,
            test_type=test_type,
        )

        logger.debug(f"Expanded test point to test case: {test_case_id}")
        return test_case

    def expand_checklist(self, checklist: TestChecklist) -> List[TestCase]:
        """Expand entire checklist into detailed test cases.

        Args:
            checklist: TestChecklist to expand.

        Returns:
            List of TestCase instances.

        Raises:
            TestExpanderError: If expansion fails.
        """
        try:
            test_cases = []

            # Reset counter for new checklist
            self.test_case_counter = 1

            # Expand each test point
            for test_point in checklist.test_points:
                test_case = self.expand_test_point(test_point)
                test_cases.append(test_case)

            logger.info(
                f"Expanded {len(checklist.test_points)} test points into "
                f"{len(test_cases)} test cases"
            )

            return test_cases

        except Exception as e:
            error_msg = f"Failed to expand checklist: {e}"
            logger.error(error_msg)
            raise TestExpanderError(error_msg) from e

    def export_to_csv(self, test_cases: List[TestCase], output_path: Path) -> None:
        """Export test cases to CSV format.

        Args:
            test_cases: List of test cases to export.
            output_path: Path to output CSV file.

        Raises:
            TestExpanderError: If export fails.
        """
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(TestCase.csv_header())

                # Write test cases
                for test_case in test_cases:
                    writer.writerow(test_case.to_csv_row())

            logger.info(f"Exported {len(test_cases)} test cases to CSV: {output_path}")

        except Exception as e:
            error_msg = f"Failed to export CSV: {e}"
            logger.error(error_msg)
            raise TestExpanderError(error_msg) from e

    def export_truth_table_to_csv(
        self, entries: List[TruthTableEntry], output_path: Path, feature_filter: str = None
    ) -> None:
        """Export truth table entries to CSV format.

        Args:
            entries: List of truth table entries to export.
            output_path: Path to output CSV file.
            feature_filter: Optional feature name to filter by.

        Raises:
            TestExpanderError: If export fails.
        """
        try:
            # Filter by feature if specified
            if feature_filter:
                entries = [e for e in entries if e.feature.lower() == feature_filter.lower()]

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(TruthTableEntry.csv_header())

                # Write entries
                for entry in entries:
                    writer.writerow(entry.to_csv_row())

            logger.info(f"Exported {len(entries)} truth table entries to CSV: {output_path}")

        except Exception as e:
            error_msg = f"Failed to export truth table CSV: {e}"
            logger.error(error_msg)
            raise TestExpanderError(error_msg) from e

    def generate_summary_report(self, test_cases: List[TestCase]) -> dict:
        """Generate summary statistics for test cases.

        Args:
            test_cases: List of test cases.

        Returns:
            Dictionary with summary statistics.
        """
        if not test_cases:
            return {
                "total_cases": 0,
                "by_priority": {},
                "by_feature": {},
                "by_type": {},
            }

        # Count by priority
        priority_counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
        for tc in test_cases:
            priority_counts[tc.priority] += 1

        # Count by feature
        feature_counts = {}
        for tc in test_cases:
            feature_counts[tc.feature] = feature_counts.get(tc.feature, 0) + 1

        # Estimate test types from notes/requirements
        type_counts = {
            "positive": 0, "negative": 0, "edge_case": 0, "boundary": 0, "user_journey": 0,
            "subscription_state": 0, "navigation": 0, "ui_compliance": 0,
            "data_sync": 0, "state_propagation": 0, "feature_gating": 0
        }
        for tc in test_cases:
            # Use test_type if available, otherwise fall back to heuristic
            if tc.test_type:
                type_counts[tc.test_type] = type_counts.get(tc.test_type, 0) + 1
            else:
                # Simple heuristic based on notes
                notes_lower = tc.notes.lower()
                if "journey" in notes_lower or "end-to-end" in notes_lower:
                    type_counts["user_journey"] += 1
                elif "error" in notes_lower or "negative" in notes_lower:
                    type_counts["negative"] += 1
                elif "boundary" in notes_lower or "minimum" in notes_lower:
                    type_counts["boundary"] += 1
                elif "edge" in notes_lower or "unusual" in notes_lower:
                    type_counts["edge_case"] += 1
                else:
                    type_counts["positive"] += 1

        summary = {
            "total_cases": len(test_cases),
            "by_priority": priority_counts,
            "by_feature": feature_counts,
            "by_type": type_counts,
        }

        logger.info(f"Generated summary report: {summary['total_cases']} total cases")
        return summary

    # ==========================================================================
    # BACKEND TEST CASE EXPANSION (API, Database, Security, Performance)
    # ==========================================================================

    # Backend category code mapping for test case IDs
    BACKEND_CATEGORY_CODES = {
        "API": "API",
        "Database": "DB",
        "Security": "SEC",
        "Performance": "PERF",
        "Config": "CFG",
        "Analytics": "AN",
        "Backend": "BE",
        "Cache": "CACHE",
    }

    def _generate_backend_test_case_id(
        self, category: str, test_type: str, counter: int, scenario: str = ""
    ) -> str:
        """Generate unique backend test case ID in format TC_API_[CAT]_[NUM]_[HASH].

        Args:
            category: Test category (e.g., Profile Creation).
            test_type: Type of backend test (API, Database, etc.).
            counter: Unique counter number.
            scenario: Test scenario text for uniqueness hash.

        Returns:
            Test case ID (e.g., "TC_API_PC_001_A1B2").
        """
        import hashlib

        # Get category code from test type
        type_code = self.BACKEND_CATEGORY_CODES.get(test_type, "BE")

        # Create short category code from category name
        cat_words = category.replace("-", " ").split()
        cat_code = "".join(w[0].upper() for w in cat_words[:2]) if cat_words else "GEN"

        # Create a short hash from scenario to ensure uniqueness
        scenario_hash = ""
        if scenario:
            hash_input = f"{category}_{test_type}_{scenario}"
            scenario_hash = hashlib.md5(hash_input.encode()).hexdigest()[:4].upper()

        tc_id = f"TC_{type_code}_{cat_code}_{counter:03d}"
        if scenario_hash:
            tc_id = f"{tc_id}_{scenario_hash}"

        return tc_id

    def expand_backend_test_point(
        self, test_point: BackendTestPoint, counter: int
    ) -> BackendTestCase:
        """Expand single backend test point into detailed test case.

        Args:
            test_point: Backend test point to expand.
            counter: Unique counter for test case ID.

        Returns:
            BackendTestCase instance.
        """
        # Generate test case ID with scenario hash for uniqueness
        test_case_id = self._generate_backend_test_case_id(
            test_point.category, test_point.test_type, counter, test_point.test_scenario
        )

        test_case = BackendTestCase(
            test_case_id=test_case_id,
            category=test_point.category,
            subcategory=test_point.subcategory,
            api_component=test_point.api_component,
            test_scenario=test_point.test_scenario,
            precondition=test_point.precondition,
            verification_method=test_point.verification_method,
            expected_result=test_point.expected_result,
            priority=test_point.priority,
            test_type=test_point.test_type,
        )

        logger.debug(f"Expanded backend test point to test case: {test_case_id}")
        return test_case

    def expand_backend_checklist(
        self, checklist: BackendTestChecklist
    ) -> List[BackendTestCase]:
        """Expand backend checklist into detailed test cases.

        Args:
            checklist: BackendTestChecklist to expand.

        Returns:
            List of BackendTestCase instances.

        Raises:
            TestExpanderError: If expansion fails.
        """
        try:
            test_cases = []
            counter = 1

            # Expand each backend test point
            for test_point in checklist.test_points:
                test_case = self.expand_backend_test_point(test_point, counter)
                test_cases.append(test_case)
                counter += 1

            logger.info(
                f"Expanded {len(checklist.test_points)} backend test points into "
                f"{len(test_cases)} test cases"
            )

            return test_cases

        except Exception as e:
            error_msg = f"Failed to expand backend checklist: {e}"
            logger.error(error_msg)
            raise TestExpanderError(error_msg) from e

    def export_backend_to_csv(
        self, test_cases: List[BackendTestCase], output_path: Path
    ) -> None:
        """Export backend test cases to CSV format matching user's format.

        CSV Format:
        Test Case ID,Category,Subcategory,API/Component,Test Scenario,
        Precondition,Verification Method,Expected Result,Priority,Test Type

        Args:
            test_cases: List of backend test cases to export.
            output_path: Path to output CSV file.

        Raises:
            TestExpanderError: If export fails.
        """
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                # Write header (matching user's CSV format)
                writer.writerow(BackendTestCase.csv_header())

                # Write test cases
                for test_case in test_cases:
                    writer.writerow(test_case.to_csv_row())

            logger.info(
                f"Exported {len(test_cases)} backend test cases to CSV: {output_path}"
            )

        except Exception as e:
            error_msg = f"Failed to export backend CSV: {e}"
            logger.error(error_msg)
            raise TestExpanderError(error_msg) from e

    def generate_backend_summary_report(
        self, test_cases: List[BackendTestCase]
    ) -> dict:
        """Generate summary statistics for backend test cases.

        Args:
            test_cases: List of backend test cases.

        Returns:
            Dictionary with summary statistics.
        """
        if not test_cases:
            return {
                "total_cases": 0,
                "by_priority": {},
                "by_category": {},
                "by_test_type": {},
            }

        # Count by priority
        priority_counts = {"P0": 0, "P1": 0, "P2": 0}
        for tc in test_cases:
            priority_counts[tc.priority] = priority_counts.get(tc.priority, 0) + 1

        # Count by category
        category_counts = {}
        for tc in test_cases:
            category_counts[tc.category] = category_counts.get(tc.category, 0) + 1

        # Count by test type
        type_counts = {
            "API": 0, "Database": 0, "Security": 0, "Performance": 0,
            "Config": 0, "Analytics": 0, "Backend": 0, "Cache": 0
        }
        for tc in test_cases:
            type_counts[tc.test_type] = type_counts.get(tc.test_type, 0) + 1

        summary = {
            "total_cases": len(test_cases),
            "by_priority": priority_counts,
            "by_category": category_counts,
            "by_test_type": type_counts,
        }

        logger.info(
            f"Generated backend summary report: {summary['total_cases']} total cases"
        )
        return summary
