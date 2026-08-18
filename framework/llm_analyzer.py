"""LLM-powered test analysis engine."""

import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import List, Literal, Optional

from anthropic import Anthropic, APIStatusError

# OverloadedError is only exported by newer anthropic releases, while
# requirements.txt allows >=0.18.0. Importing it unconditionally made this
# module fail to import on a supported version. An overload is HTTP 529 on
# every release, so match the status code and keep the named class when it is
# available.
try:  # pragma: no cover - depends on the installed SDK version
    from anthropic import OverloadedError
except ImportError:  # pragma: no cover
    OverloadedError = None

from openai import OpenAI
from pydantic import ValidationError

from framework.models import (
    BackendTestChecklist,
    BackendTestPoint,
    CoverageAnalysis,
    FeatureCoverage,
    RiskAssessment,
    TestAnalysisRequest,
    TestChecklist,
    TestPoint,
    TestTypeDistribution,
    TruthTableEntry,
)
from framework.knowledge_base import get_knowledge_base

# HTTP status the API returns when it is overloaded.
_OVERLOADED_STATUS = 529

# Lazy import for RAG integration to avoid circular imports
_rag_integration = None


def get_rag_integration():
    """Get RAG integration module lazily."""
    global _rag_integration
    if _rag_integration is None:
        try:
            from framework import rag_integration
            _rag_integration = rag_integration
        except ImportError:
            _rag_integration = None
    return _rag_integration

logger = logging.getLogger(__name__)

# Provider type
LLMProvider = Literal["anthropic", "openai"]


class LLMAnalysisError(Exception):
    """Custom exception for LLM analysis errors."""

    pass


class LLMAnalyzer:
    """LLM-powered test analysis engine supporting multiple providers."""

    # Default models for each provider
    DEFAULT_MODELS = {
        "anthropic": "claude-sonnet-4-20250514",
        "openai": "gpt-4-turbo",  # Using turbo as gpt-4o has stricter content moderation
    }

    def __init__(
        self,
        api_key: str,
        provider: LLMProvider = "anthropic",
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        """Initialize LLM analyzer.

        Args:
            api_key: API key for the selected provider.
            provider: LLM provider - "anthropic" or "openai".
            model: Model to use (defaults based on provider).
            max_tokens: Maximum tokens in response.
            temperature: Temperature setting.
        """
        self.provider = provider
        self.api_key = api_key

        # Initialize the appropriate client
        # Use longer timeout (5 minutes) for complex PRD analysis
        if provider == "anthropic":
            self.client = Anthropic(
                api_key=api_key,
                max_retries=2,
                timeout=300.0,
            )
            self.model = model or self.DEFAULT_MODELS["anthropic"]
        elif provider == "openai":
            self.client = OpenAI(
                api_key=api_key,
                timeout=300.0,
            )
            self.model = model or self.DEFAULT_MODELS["openai"]
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        self.max_tokens = max_tokens if max_tokens is not None else 16000
        self.temperature = (
            temperature
            if temperature is not None
            else float(os.getenv("LLM_TEMPERATURE", "0.7"))
        )

        self._last_request_time = 0
        self._min_request_interval = 3.0

        # Initialize knowledge base
        self.knowledge_base = get_knowledge_base()
        if self.knowledge_base.is_available():
            self.knowledge_base.load_all()
            logger.info("Knowledge base loaded successfully")
        else:
            logger.warning("Knowledge base not available - using built-in rules only")

        # Initialize RAG integration for similar test retrieval
        self.rag = None
        rag_module = get_rag_integration()
        if rag_module:
            try:
                self.rag = rag_module.TestCaseRAG()
                if self.rag.enabled:
                    logger.info("RAG integration enabled for similar test retrieval")
                else:
                    logger.info("RAG integration available but Qdrant not connected")
                    self.rag = None
            except Exception as e:
                logger.warning(f"Failed to initialize RAG integration: {e}")
                self.rag = None
        else:
            logger.info("RAG integration not available")

        logger.info(
            f"LLM Analyzer initialized with provider: {self.provider}, model: {self.model}, "
            f"max_tokens: {self.max_tokens}, temperature: {self.temperature}"
        )

    def _rate_limited_api_call(
        self,
        messages: list,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        """Make rate-limited API call with exponential backoff.

        Args:
            messages: Messages to send to API (Anthropic format)
            max_tokens: Maximum tokens in response (uses instance default if None)
            temperature: Temperature setting (uses instance default if None)

        Returns:
            API response text content

        Raises:
            LLMAnalysisError: If all retries exhausted
        """
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        temperature = temperature if temperature is not None else self.temperature

        # Enforce minimum interval between requests
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            wait_time = self._min_request_interval - elapsed
            logger.info(f"Rate limiting: waiting {wait_time:.2f}s before next request")
            time.sleep(wait_time)

        max_retries = 6
        base_delay = 5.0

        for attempt in range(max_retries):
            try:
                if self.provider == "anthropic":
                    response = self._call_anthropic(messages, max_tokens, temperature)
                else:
                    response = self._call_openai(messages, max_tokens, temperature)

                self._last_request_time = time.time()
                return response

            except APIStatusError as e:
                if getattr(e, "status_code", None) != _OVERLOADED_STATUS:
                    raise
                if attempt == max_retries - 1:
                    raise LLMAnalysisError(
                        f"API overloaded after {max_retries} attempts: {e}"
                    )
                delay = base_delay * (2**attempt)
                logger.warning(
                    f"API overloaded, attempt {attempt + 1}/{max_retries}. Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)

            except Exception as e:
                logger.error(f"API error: {e}")
                raise LLMAnalysisError(f"API error: {e}")

        raise LLMAnalysisError("Maximum retries exceeded")

    def _call_anthropic(
        self, messages: list, max_tokens: int, temperature: float
    ):
        """Call Anthropic API."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        return response

    def _call_openai(
        self, messages: list, max_tokens: int, temperature: float
    ):
        """Call OpenAI API, converting Anthropic message format to OpenAI format."""
        # Convert Anthropic message format to OpenAI format
        openai_messages = self._convert_messages_for_openai(messages)

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=openai_messages,
        )
        return response

    def _convert_messages_for_openai(self, anthropic_messages: list) -> list:
        """Convert Anthropic message format to OpenAI format.

        Anthropic format: {"role": "user", "content": [{"type": "text", "text": "..."}]}
        OpenAI format: {"role": "user", "content": "..." or [{"type": "text", "text": "..."}]}
        """
        # Add system message to establish legitimate QA context
        openai_messages = [
            {
                "role": "system",
                "content": "You are a professional QA engineer at a software company. Your job is to create test cases for mobile applications based on product requirement documents (PRDs). You analyze requirements and generate comprehensive test cases in JSON format. This is standard software quality assurance work."
            }
        ]

        for msg in anthropic_messages:
            role = msg["role"]
            content = msg["content"]

            if isinstance(content, str):
                # Simple text message
                openai_messages.append({"role": role, "content": content})
            elif isinstance(content, list):
                # Complex message with multiple parts (text, images)
                openai_content = []
                for part in content:
                    if part.get("type") == "text":
                        openai_content.append({
                            "type": "text",
                            "text": part["text"]
                        })
                    elif part.get("type") == "image":
                        # Convert Anthropic image format to OpenAI format
                        source = part.get("source", {})
                        if source.get("type") == "base64":
                            media_type = source.get("media_type", "image/png")
                            data = source.get("data", "")
                            openai_content.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{data}"
                                }
                            })
                openai_messages.append({"role": role, "content": openai_content})

        return openai_messages

    def _extract_response_text(self, response) -> str:
        """Extract text content from API response (handles both providers)."""
        if self.provider == "anthropic":
            return response.content[0].text
        else:  # openai
            return response.choices[0].message.content

    def _encode_image(self, image_path: Path) -> tuple[str, str]:
        """Encode image to base64 for API.

        Args:
            image_path: Path to image file.

        Returns:
            Tuple of (media_type, base64_data).
        """
        image_data = image_path.read_bytes()

        # Determine media type
        suffix = image_path.suffix.lower()
        media_type_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
        }
        media_type = media_type_map.get(suffix, "image/png")

        encoded = base64.standard_b64encode(image_data).decode("utf-8")
        return media_type, encoded

    def _summarize_figma_structure(
        self, structure: dict, max_depth: int = 5, max_children: int = 20
    ) -> dict:
        """Summarize Figma structure to reduce token usage.

        Extracts key information while limiting depth and breadth.

        Args:
            structure: Full Figma structure from extract_ui_elements().
            max_depth: Maximum tree depth to include.
            max_children: Maximum children per node to include.

        Returns:
            Summarized structure dictionary.
        """

        def summarize_node(node: dict, current_depth: int = 0) -> dict:
            """Recursively summarize a node."""
            if current_depth >= max_depth:
                return None

            # Extract only essential fields
            summary = {
                "type": node.get("type"),
                "name": node.get("name"),
            }

            # Include text content if present
            if "text" in node and node["text"]:
                summary["text"] = node["text"][:100]  # Limit text length

            # Process children (limit count)
            children = node.get("children", [])
            if children and current_depth < max_depth - 1:
                summarized_children = []
                for child in children[:max_children]:
                    summarized = summarize_node(child, current_depth + 1)
                    if summarized:
                        summarized_children.append(summarized)

                if summarized_children:
                    summary["children"] = summarized_children

                # Indicate if there are more children
                if len(children) > max_children:
                    summary["_more_children"] = len(children) - max_children

            return summary

        ui_elements = structure.get("ui_elements", {})
        summarized_ui = summarize_node(ui_elements)

        return {
            "file_name": structure.get("file_name"),
            "file_key": structure.get("file_key"),
            "node_id": structure.get("node_id"),
            "ui_elements": summarized_ui,
            "_note": f"Summarized structure (max_depth={max_depth}, max_children={max_children})",
        }

    def _get_rag_context(
        self, feature_name: Optional[str], prd_content: str
    ) -> str:
        """Get RAG context with similar test cases from past projects.

        Args:
            feature_name: Optional feature name for targeted search.
            prd_content: PRD content to use for similarity search.

        Returns:
            Formatted RAG context string for prompt injection.
        """
        if not self.rag:
            return ""

        try:
            # Build search query from feature name and PRD content
            query_parts = []
            if feature_name:
                query_parts.append(feature_name)

            # Extract key terms from PRD (first 500 chars)
            prd_snippet = prd_content[:500] if prd_content else ""
            if prd_snippet:
                query_parts.append(prd_snippet)

            query = " ".join(query_parts)
            if not query:
                return ""

            # Get similar test cases from RAG
            similar_tests = self.rag.get_similar_tests(query=query, top_k=5)

            if not similar_tests:
                logger.info("No similar test cases found in RAG")
                return ""

            # Format RAG context for prompt
            rag_context = self.rag.format_rag_context(similar_tests)

            if rag_context:
                logger.info(f"Retrieved {len(similar_tests)} similar test cases from RAG")

            return rag_context

        except Exception as e:
            logger.warning(f"Failed to get RAG context: {e}")
            return ""

    def _build_analysis_prompt(
        self, request: TestAnalysisRequest, figma_structure: Optional[dict] = None,
        rag_context: str = "", frontend_doc: Optional[str] = None
    ) -> str:
        """Build comprehensive analysis prompt with enhanced methodology.

        Args:
            request: Test analysis request.
            figma_structure: Optional structured Figma UI elements data.
            rag_context: RAG-retrieved similar test cases for context.
            frontend_doc: Optional Frontend LLD document with screen flows, components, state management.

        Returns:
            Formatted prompt string.
        """
        # Build Frontend LLD section if provided
        frontend_lld_section = ""
        if frontend_doc:
            frontend_lld_section = f"""
**FRONTEND LLD (Technical Specifications):**
{frontend_doc}

**IMPORTANT - USE THE LLD DOCUMENT:**
The Frontend LLD above contains EXACT technical specifications. Use it to:
1. Extract EXACT screen routes (e.g., /match-making, /add-user-details)
2. Use EXACT component names (e.g., MatchCard, ProfileSwitcher, DetailsForm)
3. Test ALL component states mentioned (Empty, Listing, Loading, Error states)
4. Verify component props with actual values (score, matchType, partners)
5. Test feature flags and limits mentioned in the LLD
6. Test subscription flows and locked sections
7. Test navigation flows between screens
8. Verify UI behaviors match LLD specifications

**Generate tests for EVERY component, screen, and state defined in the LLD.**

"""

        # Build Figma structure section if provided
        figma_section = ""
        if figma_structure:
            # Summarize structure to reduce token usage
            summarized = self._summarize_figma_structure(figma_structure)

            figma_section = f"""
**Figma UI Structure:**
File: {summarized.get("file_name", "Unknown")}
Structured UI Elements (extracted from Figma API, summarized):
```json
{json.dumps(summarized.get("ui_elements", {}), indent=2)}
```

Use this structured data to understand:
- UI element names and hierarchy
- Text content (exact text from designs)
- Component types (FRAME, TEXT, BUTTON, etc.)
- Element relationships and grouping

Note: Structure has been summarized for efficiency. Focus on the UI elements, text labels, and component types shown.
"""

        # Load knowledge base context
        kb_context = ""
        if self.knowledge_base.is_available():
            kb_context = self.knowledge_base.get_summary_context()
            logger.debug("Knowledge base context loaded for prompt")

        # Build codebase RAG section if context provided
        rag_section = ""
        if rag_context:
            rag_section = f"""
## Codebase Context (React Native Code Reference)

The following code snippets from the actual codebase are relevant to this feature. Use them to:
- Understand the actual implementation (component names, props, states)
- Identify API endpoints and data structures to test
- Find validation rules and error handling in the code
- Ensure test cases use correct screen/component names

{rag_context}

**Important**: Use this codebase knowledge to make test cases SPECIFIC to the actual implementation. Reference real component names, API endpoints, and validation rules from the code above.

"""
            logger.debug("Codebase RAG context injected into prompt")

        # Use simpler prompt for OpenAI to avoid content moderation issues
        if self.provider == "openai":
            return self._build_openai_prompt(request, figma_section, kb_context, rag_section, frontend_lld_section)

        # Full detailed prompt for Anthropic
        prompt = f"""You are an expert QA engineer specializing in test case design. Analyze the provided PRD/Figma design and generate comprehensive test points.

{kb_context}
{rag_section}
{frontend_lld_section}
**PRD Content:**
{request.prd_content}
{figma_section}
**Test Design Methods to Apply:**
{", ".join(request.apply_methods) if request.apply_methods else "Equivalence Partitioning, Boundary Value Analysis, Decision Tables, Scenario Method, State Transition, Error Guessing"}

**Methodology:**
1. **OCR & Requirement Extraction**: Extract requirements, modules, and features from PRD images
2. **Systematic Test Design Application**:
   - **Single condition validation**: Prioritize equivalence classes + boundary values
   - **Multi-condition combinations**: Use decision tables / cause-effect diagrams
   - **Business processes**: Use scenario method
   - **State changes**: Use state transition method
   - **Fill gaps**: Combine error guessing method
   - **Required field validation**
   - **Exception scenario supplementation**

3. **Critical Rules**:
   - ❌ Do NOT add checklist items that don't exist in requirement documents or UI diagrams
   - ✅ Only generate test points based on provided PRD/designs
   - ✅ Adapt test coverage based on what features are ACTUALLY present in the requirements
   - ✅ **Ask for clarification if requirements are uncertain** rather than making assumptions

4. Generate test points with:
   - **SPECIFIC, ACTIONABLE descriptions** - Use exact UI element names and user actions from the Figma/PRD
   - Feature categorization
   - Priority (P0=Critical, P1=High, P2=Medium, P3=Low)
   - Test type (use the most appropriate):
     * positive - Happy path, valid flows
     * negative - Error handling, invalid inputs
     * edge_case - Unusual inputs, extreme conditions
     * boundary - Min/max values, limits
     * subscription_state - User state-specific tests (subscribed, new, expired)
     * navigation - CTA correctness, button destinations, back button behavior
     * ui_compliance - Figma matching, visual consistency
     * data_sync - Real-time updates, no stale data
     * state_propagation - Cross-feature state effects
     * feature_gating - Prerequisites, blocked features

   **DESCRIPTION EXAMPLES** (be this specific):
   ✅ GOOD: "User taps 'Rate Us' button and rating modal appears with 5-star selector"
   ✅ GOOD: "Enter invalid phone number '123' (too short) and verify error message appears"
   ✅ GOOD: "Test maximum character limit (100 chars) in 'Name' input field"
   ❌ BAD: "Validate Rating Bottom Sheet display and interaction" (too generic)
   ❌ BAD: "Test phone number input" (not specific)

   **NEW TEST TYPE EXAMPLES** (include these scenarios):
   ✅ subscription_state: "Subscribed user with zero wallet opens Premium Expert chat - no recharge popup shown"
   ✅ subscription_state: "After exhausting 2 free chats + purchasing subscription, no free-chat strip appears"
   ✅ navigation: "'Subscribe Now' CTA on Home navigates to Subscription Page, not Reports Page"
   ✅ navigation: "Back button works after payment via Chat - returns to Chat without freeze"
   ✅ ui_compliance: "Premium tag and discount strike-through display on Expert cards per Figma"
   ✅ data_sync: "My Balance updates immediately after subscription purchase without relaunch"
   ✅ state_propagation: "After buying subscription, Report Details shows 'Use Subscription' only, no 'Continue without'"
   ✅ feature_gating: "Half-onboarded user trying to subscribe sees 'Complete Profile' block + redirect"

   **Note**: Your descriptions will be expanded by test_expander.py into detailed test steps automatically.
   Focus on WHAT to test (specific feature/action), not HOW to format steps.

5. Ensure comprehensive coverage across all relevant dimensions:
   - Happy paths (positive scenarios)
   - Error handling (negative scenarios)
   - Edge cases and boundaries
   - Required field validation
   - Exception scenarios
   - Security considerations
   - State transitions (if applicable)
   - User lifecycle scenarios (creation, updates, deletion, recovery - if present)
   - Data privacy and retention (if applicable)
   - Authentication and authorization (if applicable)
   - Integration points and dependencies (if applicable)

6. **CRITICAL: ADVANCED COVERAGE DIMENSIONS** (often missed but essential):

   **A. User State Matrix Testing:**
   - Test with different user states: new user, subscribed user, expired subscription,
     half-onboarded user, guest user, premium user with zero balance
   - Each feature should be tested across relevant user states
   - Example: "Subscribed user with wallet balance 0 opens Premium Expert chat"

   **B. Negative UI Assertions (Element Absence Testing):**
   - Test that certain UI elements DO NOT appear in specific states
   - Example: "No low-balance strip appears for subscribed user"
   - Example: "No 'Continue without Subscription' option for subscribed user"
   - Example: "Recharge popup should NOT appear after subscription purchase"

   **C. Cross-Feature State Propagation:**
   - Test how state changes in one feature affect other features
   - Example: "After buying subscription, chat works without coin deduction"
   - Example: "After exhausting free chats + subscribing, no free-chat strip in chat"
   - Example: "Subscription status reflects in Reports, Chat, and Balance screens"

   **D. CTA/Navigation Correctness:**
   - Test that buttons/CTAs navigate to CORRECT destinations
   - Example: "'Subscribe Now' on Home opens Subscription Page, NOT Reports Page"
   - Example: "'Buy Now' on report opens THAT report's details, not another"
   - Example: "'Download Report' from Insight opens Report Details, not Profile"
   - Test back button behavior after complex flows (payment, subscription)

   **E. Real-time Data Synchronization:**
   - Test immediate data updates after purchases/actions
   - Example: "My Balance updates immediately after purchase without relaunch"
   - Example: "Transaction History shows payment within seconds of completion"
   - Example: "No stale data displayed after state changes"

   **F. Feature Gating & Prerequisites:**
   - Test features that require prerequisites (completed profile, subscription, etc.)
   - Example: "Subscription blocked until profile complete with message"
   - Example: "Premium content locked for non-subscribed users with clear CTA"
   - Test redirect to complete required flows (onboarding, verification)

   **G. Post-Action Flow Completion:**
   - Test correct behavior AFTER successful actions
   - Example: "Cancel subscription → OK on success popup → redirects to Home"
   - Example: "Only ONE confirmation screen shown, not multiple"
   - Example: "Back button works after payment via Chat (no freeze/crash)"

   **H. UI/Figma Compliance Testing:**
   - Test visual elements match design specifications
   - Example: "Premium tag visible on eligible Expert cards"
   - Example: "Strike-through and discount shown per Figma specs"
   - Example: "Backgrounds, padding, icons, shadows match design"
   - Test for absence of legacy UI elements

   **I. Post-Purchase/Post-Action State Updates:**
   - Test that UI reflects new state immediately after purchase/action
   - Example: "Subscribe Now button changes to 'Manage Subscription' after purchase"
   - Example: "Hamburger menu shows [Active] badge after subscription"
   - Example: "Transaction history shows the purchase immediately"

   **J. Data Format & Display Correctness:**
   - Test that data is displayed in correct format
   - Example: "Time displays as '2h:30m' not '489524574h:10m'"
   - Example: "Currency shows proper formatting (₹999 not 999)"
   - Example: "Dates show proper locale format"

   **K. Feature Entitlement & Free Tier Testing:**
   - Test free tier limits and premium unlocks
   - Example: "New user gets exactly 2 free chats before paywall"
   - Example: "Subscribed user gets unlimited chats"
   - Example: "Free reports display for users who bought subscription"

7. **REAL-WORLD BUG PATTERNS TO CATCH** (generate tests that would find these bugs):

   **Navigation/Redirection Bugs:**
   - "Subscribe Now on Home navigates to Subscription Page (not Reports)"
   - "Buy Now on Report opens Report Details (not Report List)"
   - "Download Report from Insight opens Report Details (not Profile)"
   - "After successful payment, user is redirected to Home (not stuck)"
   - "Cancel subscription flow shows ONE popup, then redirects to Home"

   **Cache/State Sync Bugs:**
   - "My Balance updates immediately after purchase (no stale data)"
   - "Subscription status updates in Hamburger menu without relaunch"
   - "Transaction history reflects payment immediately"
   - "Subscribe button text changes after purchase"

   **UI/Visual Bugs:**
   - "Strike-through prices display on Expert cards"
   - "Discount percentages show correctly"
   - "Padding/margins match Figma specs"
   - "Icons are visible (not missing)"
   - "Shadows display on swipeable cards"
   - "Bottom tab uses new design (not legacy)"

   **Free Tier/Entitlement Bugs:**
   - "New user receives 2 free chats"
   - "Free chat counter decrements correctly"
   - "Premium features locked for non-subscribers"

   **Data Format Bugs:**
   - "Time displays in proper format (HH:MM, not corrupted)"
   - "Amounts show with currency symbol"
   - "Read-only vs clickable elements styled correctly"

   **CRITICAL: Subscription State Bugs (P0 Priority):**
   - "Subscribed user: NO wallet/coin deduction when chatting with Premium Expert"
   - "Subscribed user: NO low-balance strip appears"
   - "Subscribed user: NO recharge popup appears when sending message"
   - "Subscribed user: NO 'Continue without Subscription' option in Report purchase"
   - "Subscribed user: Report shows 'Use Subscription' only"
   - "New user who bought subscription directly: NO free chat strip displayed"
   - "After exhausting free chats + subscribing: NO recharge sheet on chat"
   - "Subscription upgrade: User can upgrade to bigger plan"
   - "Premium tag visible on eligible Expert cards"

   **Precondition-Based Testing (test with specific user states):**
   - Test with: New User (never subscribed)
   - Test with: Subscribed User (active subscription)
   - Test with: Expired Subscription User
   - Test with: User who exhausted free chats then subscribed
   - Test with: Half-onboarded User (incomplete profile)
   - Test with: Subscribed User with zero wallet balance

   **Flow Completion & Navigation Bugs:**
   - "Back button works after payment via Chat (no freeze)"
   - "Navigate to Guided Reading from Cancel/View Subscription screen"
   - "Cancel subscription → single popup → redirect to Home"
   - "Successful payment → redirect to Home (not stuck)"

   **Onboarding/Prerequisite Bugs:**
   - "User cannot buy subscription until profile is complete"
   - "Clear message: 'Complete Profile to Subscribe'"
   - "Redirect to onboarding flow if profile incomplete"

   **Performance Bugs:**
   - "App remains responsive after 30+ minutes of use"
   - "API responses within acceptable time limits"
   - "No memory leaks or degradation over time"

8. **MINIMUM COVERAGE TARGETS** (aim for comprehensive testing):
   - **Positive scenarios**: At least 40% of test points (happy paths, valid flows)
   - **Negative scenarios**: At least 30% of test points (error handling, invalid inputs)
   - **Boundary scenarios**: At least 15% of test points (min/max values, limits)
   - **Edge cases**: At least 15% of test points (unusual inputs, special conditions)
   - **MINIMUM TOTAL**: Generate at least 40-50 test points for simple features, 70+ for complex features
   - For each UI element/field: Test valid input, invalid input, boundary values, and edge cases
   - For each user action: Test success path, error path, and recovery path

**CRITICAL: ALWAYS return valid JSON, even if information is insufficient.**

**Output Format:**
You MUST return a JSON object with this EXACT structure:
{{
  "feature_name": "Name of the feature or 'Unknown'",
  "test_points": [
    {{
      "description": "Clear test point description",
      "feature": "Feature/component name",
      "priority": "P0|P1|P2|P3",
      "test_type": "positive|negative|edge_case|boundary|subscription_state|navigation|ui_compliance|data_sync|state_propagation|feature_gating"
    }}
  ],
  "truth_table_entries": [
    {{
      "screen": "Starting screen name (e.g., Home Screen, Wallet, SideBar)",
      "checkpoint": "Navigation path (e.g., 'Home -> Tap Subscribe CTA -> Subscription Page')",
      "failed_redirect": "Where it redirects on failure (e.g., 'Home Screen (with error toast)')",
      "pending_redirect": "Where it redirects when pending (e.g., 'Loading Screen')",
      "successful_redirect": "Where it redirects on success (e.g., 'Subscription Page')",
      "auto_redirect_failed": "Pass|NA",
      "auto_redirect_pending": "Pass|NA",
      "auto_redirect_success": "Pass|NA",
      "result": "Not Tested",
      "expected": "Expected behavior description",
      "feature": "Feature name",
      "priority": "P0|P1|P2",
      "test_type": "navigation|payment_redirect|state_transition|deep_link"
    }}
  ],
  "truth_table_features": ["Feature1", "Feature2"],
  "coverage_score": 0-100,
  "needs_more_info": false,
  "error_message": null,
  "coverage_analysis": {{
    "feature_coverage": [
      {{
        "feature": "Feature name from test_points",
        "coverage_percentage": 0-100,
        "test_count": number,
        "missing_scenarios": ["scenario1", "scenario2"],
        "risk_level": "high|medium|low"
      }}
    ],
    "test_type_distribution": {{
      "positive": number,
      "negative": number,
      "boundary": number,
      "edge_case": number
    }},
    "missing_scenarios": [
      "What test scenarios are missing (e.g., 'No tests for error handling', 'No accessibility tests')"
    ],
    "risk_assessment": {{
      "high_risk_features": ["Features with P0 gaps or <30% coverage"],
      "medium_risk_features": ["Features with 30-70% coverage"],
      "low_risk_features": ["Features with >70% coverage"]
    }},
    "recommendations": [
      "AI recommendations for improving test coverage (e.g., 'Add negative tests for form validation', 'Test slow network scenarios')"
    ]
  }}
}}

**TRUTH TABLE / TEST MATRIX GENERATION:**
For navigation flows, payment redirections, subscription states, and screen transitions,
also generate **truth_table_entries** following this format:

1. **screen**: Starting screen (SideBar, Home Screen, Wallet, Chat Screen, etc.)
2. **checkpoint**: Navigation path describing the flow (Screen -> Action -> Destination)
3. **failed_redirect**: Where user goes if action fails
4. **pending_redirect**: Where user goes during loading/pending state
5. **successful_redirect**: Where user goes on success
6. **auto_redirect_failed/pending/success**: "Pass" if auto-redirect works, "NA" if not applicable
7. **expected**: Clear description of expected behavior

**Generate truth table entries for:**
- CTA clicks and button navigations
- Payment flow redirections (success/failure/pending)
- Subscription state transitions
- Deep link navigation
- Profile/account state changes
- Any multi-outcome navigation flow

**Example truth_table_entry:**
{{
  "screen": "Home Screen",
  "checkpoint": "Home -> Tap 'Add Money' -> Add Cash Screen",
  "failed_redirect": "Home Screen (with error toast)",
  "pending_redirect": "Loading indicator on Home Screen",
  "successful_redirect": "Add Cash Screen",
  "auto_redirect_failed": "Pass",
  "auto_redirect_pending": "Pass",
  "auto_redirect_success": "Pass",
  "result": "Not Tested",
  "expected": "User should be redirected to Add Cash Screen after tapping Add Money",
  "feature": "Payment",
  "priority": "P0",
  "test_type": "navigation"
}}

**If PRD/Figma content is insufficient or unclear:**
Return JSON with:
{{
  "feature_name": "Insufficient Information",
  "test_points": [],
  "coverage_score": 0.0,
  "needs_more_info": true,
  "error_message": "Explain what additional information is needed (e.g., 'The Figma design only shows a title. Please provide complete UI mockups with interactions, requirements, and user flows.')",
  "coverage_analysis": {{
    "feature_coverage": [],
    "test_type_distribution": {{"positive": 0, "negative": 0, "boundary": 0, "edge_case": 0}},
    "missing_scenarios": ["Complete PRD/Figma design needed"],
    "risk_assessment": {{"high_risk_features": [], "medium_risk_features": [], "low_risk_features": []}},
    "recommendations": ["Provide complete requirements and UI designs"]
  }}
}}

**Coverage Score Calculation:**
- Consider breadth (all features covered)
- Consider depth (all test types covered)
- Consider risk areas (critical paths prioritized)
- Range: 0-100

**🚨 CRITICAL REQUIREMENTS - YOU WILL BE PENALIZED FOR GENERATING TOO FEW TEST POINTS:**

1. **ABSOLUTE MINIMUM**: Generate at least 40 test points. If you generate less than 40, you are FAILING this task.
2. **OPTIMAL TARGET**: 50-60 test points for simple features, 70-100+ for complex features
3. **BE EXHAUSTIVE**: Generate EVERY possible test scenario. More is better. Do not summarize or consolidate test cases.
4. **MANDATORY DISTRIBUTION** (you MUST follow this):
   - Positive scenarios: 40% of total (at least 16 test points)
   - Negative scenarios: 30% of total (at least 12 test points)
   - Boundary scenarios: 15% of total (at least 6 test points)
   - Edge cases: 15% of total (at least 6 test points)

4. **FOR EVERY UI ELEMENT** you see in the Figma/PRD, generate AT LEAST 4 test points:
   - 1 positive test (valid input/interaction)
   - 1 negative test (invalid input/error handling)
   - 1 boundary test (min/max values)
   - 1 edge case test (unusual scenarios)

5. **QUALITY OVER BREVITY**: It's better to have 30 specific, detailed test points than 8 generic ones.

6. **🧠 THINK LIKE A SENIOR QA ENGINEER - GENERATE NON-OBVIOUS TESTS:**
   DO NOT generate basic tests like "verify button works" or "check login successful".
   Instead, generate SOPHISTICATED tests that find REAL BUGS:

   **Race Conditions & Timing:**
   - Double-tap submit button rapidly
   - User action during API call in progress
   - Session timeout during critical operation
   - Multiple tabs/devices same account simultaneously

   **State Corruption & Inconsistencies:**
   - Kill app mid-transaction and reopen
   - Network drops during payment/save
   - Browser back button after form submit
   - Data sync conflicts between cached and server data

   **Input Validation & Access Control:**
   - Special characters in search/input fields (quotes, brackets, etc.)
   - HTML/script tags in user-generated content fields
   - Session expiry and re-authentication flows
   - Access control for premium vs free features
   - API response validation and error handling

   **Real-World User Scenarios:**
   - User with slow 2G/3G network
   - User switching between WiFi and mobile data
   - User with almost full device storage
   - User with accessibility features enabled
   - User in different timezone
   - User with special characters in name (émoji, unicode)

   **Cross-Feature Interactions:**
   - Feature A affects Feature B unexpectedly
   - Settings change impact on other screens
   - Logout/Login clears expected data

   **Time-Based Bugs:**
   - Subscription expires mid-session
   - Time-limited offers at boundary
   - Daylight saving time transitions
   - End of month/year date handling

7. **COUNT YOUR TEST POINTS BEFORE RESPONDING**: If your test_points array has less than 40 items, ADD MORE TESTS!

CRITICAL INSTRUCTIONS FOR YOUR RESPONSE:
- Your ENTIRE response must be ONLY the JSON object
- Do NOT include any explanatory text before or after the JSON
- Do NOT wrap the JSON in markdown code blocks
- Do NOT add any comments or notes
- Start your response with {{ and end with }}
- Return ONLY valid, parseable JSON

Generate comprehensive test points now.

⚠️ FINAL REMINDER:
- MINIMUM 40 test points required
- NO basic "happy path" tests only - include edge cases, race conditions, robustness tests
- Think like a QA engineer finding bugs before users do
- Think like a user on a bad network connection
- Think like a user who does things in unexpected order

Respond with ONLY the JSON object (no other text):"""

        return prompt

    def _build_openai_prompt(
        self, request: TestAnalysisRequest, figma_section: str, kb_context: str,
        rag_section: str = "", frontend_lld_section: str = ""
    ) -> str:
        """Build a simpler, OpenAI-friendly prompt for test generation.

        OpenAI's content moderation can be stricter, so this prompt avoids
        language that might trigger refusals while still generating quality tests.
        """
        # Include knowledge base context for quality test generation
        prompt = f"""You are a professional software QA engineer helping create test cases for a mobile application. Your task is to analyze product requirements and generate comprehensive test cases in JSON format.

{kb_context}
{rag_section}
{frontend_lld_section}

**Requirements Document:**
{request.prd_content}
{figma_section}

**Your Task:**
Generate a comprehensive list of test cases covering:
1. **Positive tests** - Verify features work correctly with valid inputs
2. **Negative tests** - Verify proper error handling with invalid inputs
3. **Boundary tests** - Test min/max values and limits
4. **Edge cases** - Unusual but valid scenarios
5. **User state tests** - Different user types (new, subscribed, expired)
6. **Navigation tests** - Buttons go to correct destinations
7. **UI tests** - Visual elements match specifications
8. **Data tests** - Information displays correctly and updates properly

**Test Design Methods:**
{", ".join(request.apply_methods) if request.apply_methods else "Equivalence Partitioning, Boundary Value Analysis, Decision Tables, State Transition"}

**Requirements:**
- Generate at least 40-50 test cases for thorough coverage
- Each test should be specific and actionable
- Include the exact UI elements and expected behaviors
- Cover both success and failure scenarios

**Output Format - Return ONLY this JSON structure:**
{{
  "feature_name": "Name of the feature",
  "test_points": [
    {{
      "description": "Specific test description with exact steps",
      "feature": "Feature/component name",
      "priority": "P0|P1|P2|P3",
      "test_type": "positive|negative|edge_case|boundary|subscription_state|navigation|ui_compliance|data_sync|state_propagation|feature_gating"
    }}
  ],
  "truth_table_entries": [
    {{
      "screen": "Starting screen (e.g., Home Screen)",
      "checkpoint": "Navigation path (e.g., 'Home -> Tap Subscribe -> Subscription Page')",
      "failed_redirect": "Where it redirects on failure",
      "pending_redirect": "Where it redirects when pending",
      "successful_redirect": "Where it redirects on success",
      "auto_redirect_failed": "Pass|NA",
      "auto_redirect_pending": "Pass|NA",
      "auto_redirect_success": "Pass|NA",
      "result": "Not Tested",
      "expected": "Expected behavior description",
      "feature": "Feature name",
      "priority": "P0|P1|P2",
      "test_type": "navigation|payment_redirect|state_transition|deep_link"
    }}
  ],
  "truth_table_features": ["Feature1", "Feature2"],
  "coverage_score": 0-100,
  "needs_more_info": false,
  "error_message": null,
  "coverage_analysis": {{
    "feature_coverage": [
      {{
        "feature": "Feature name",
        "coverage_percentage": 0-100,
        "test_count": 0,
        "missing_scenarios": [],
        "risk_level": "high|medium|low"
      }}
    ],
    "test_type_distribution": {{
      "positive": 0,
      "negative": 0,
      "boundary": 0,
      "edge_case": 0
    }},
    "missing_scenarios": [],
    "risk_assessment": {{
      "high_risk_features": [],
      "medium_risk_features": [],
      "low_risk_features": []
    }},
    "recommendations": []
  }}
}}

**Truth Table Generation:**
For navigation flows, payment redirections, and state transitions, generate truth_table_entries showing:
- Where user navigates FROM (screen)
- The navigation path (checkpoint)
- Where user goes on failure/pending/success
- Expected behavior

If the document is unclear or insufficient, return:
{{
  "feature_name": "Insufficient Information",
  "test_points": [],
  "coverage_score": 0,
  "needs_more_info": true,
  "error_message": "Description of what additional information is needed",
  "coverage_analysis": {{
    "feature_coverage": [],
    "test_type_distribution": {{"positive": 0, "negative": 0, "boundary": 0, "edge_case": 0}},
    "missing_scenarios": [],
    "risk_assessment": {{"high_risk_features": [], "medium_risk_features": [], "low_risk_features": []}},
    "recommendations": []
  }}
}}

Generate comprehensive test cases now. Return ONLY the JSON object, no other text."""

        return prompt

    def analyze_prd(
        self,
        content: str,
        images: Optional[List[Path]] = None,
        feature_name: Optional[str] = None,
        apply_methods: Optional[List[str]] = None,
        figma_structure: Optional[dict] = None,
        frontend_doc: Optional[str] = None,
    ) -> TestChecklist:
        """Analyze PRD content and generate test checklist.

        Args:
            content: PRD text content.
            images: Optional list of image paths (fallback if figma_structure not provided).
            feature_name: Optional feature name override.
            apply_methods: Optional list of test design methods to apply.
            figma_structure: Optional structured Figma UI data from extract_ui_elements().
                           If provided, uses structured data instead of images for better accuracy.
            frontend_doc: Optional Frontend LLD document with screen flows, components, state management.
                        When provided, generates more comprehensive frontend tests using exact component specs.

        Returns:
            TestChecklist instance.

        Raises:
            LLMAnalysisError: If analysis fails.
        """
        start_time = time.time()

        # Create request
        request = TestAnalysisRequest(
            prd_content=content,
            images=images or [],
            feature_name=feature_name,
            apply_methods=apply_methods or [],
        )

        # Get codebase RAG context (React Native code patterns, components, APIs)
        # This is DIFFERENT from test case RAG - we use codebase knowledge to inform generation
        codebase_context = ""
        zk_config_context = ""

        # Build query from feature name and PRD content
        query_terms = []
        if feature_name:
            query_terms.append(feature_name)
        # Extract key terms from PRD (first 500 chars)
        prd_snippet = content[:500] if content else ""
        import re
        # Look for screen/feature names
        screens = re.findall(r'([A-Z][a-z]+(?:Screen|Page|View|Modal|Card))', prd_snippet)
        query_terms.extend(screens[:3])
        # Look for key actions
        actions = re.findall(r'\b(recharge|payment|subscription|chat|wallet|login|signup|profile|report|expert)\b', prd_snippet.lower())
        query_terms.extend(list(set(actions))[:3])

        query = " ".join(query_terms[:5]) if query_terms else feature_name or "app"

        # 1. Get Codebase Context (the indexed React Native codebase)
        if hasattr(self.knowledge_base, 'get_rag_context'):
            try:
                if query:
                    codebase_context = self.knowledge_base.get_rag_context(query, top_k=12)
                    if codebase_context:
                        logger.info(f"Codebase RAG context retrieved for: {query}")
            except Exception as e:
                logger.warning(f"Failed to get codebase RAG context: {e}")

        # 2. Get ZK Config Context (Live app configurations)
        # OPTIMIZED: Limit to 5 configs, 300 chars each to keep context small
        try:
            rag_module = get_rag_integration()
            if rag_module:
                rag_instance = rag_module.get_test_case_rag()
                if rag_instance and hasattr(rag_instance, 'get_live_config_context'):
                    zk_results = rag_instance.get_live_config_context(query, top_k=5)
                    # Filter to only highly relevant (score > 0.2)
                    zk_results = [r for r in zk_results if r.get('score', 0) > 0.2]
                    if zk_results:
                        zk_config_context = "\n\n=== ZK Live Configs (Reference) ===\n"
                        for config in zk_results[:3]:  # Max 3 configs
                            config_path = config.get('metadata', {}).get('path', config.get('path', 'Unknown'))
                            config_data = config.get('text', config.get('content', ''))[:300]  # Truncate
                            zk_config_context += f"• {config_path}: {config_data}\n"
                        logger.info(f"ZK Live context: {len(zk_results)} configs (showing top 3)")
        except Exception as e:
            logger.warning(f"Failed to get ZK config context: {e}")

        # 3. Get ZK Config Behavioral Documentation (what each config DOES)
        # IMPORTANT: Only include configs that are HIGHLY relevant to avoid test case clutter
        # ZK configs rarely change, so only include when directly relevant to the feature
        zk_behavior_context = ""
        try:
            rag_module = get_rag_integration()
            if rag_module:
                rag_instance = rag_module.get_test_case_rag()
                if rag_instance and hasattr(rag_instance, 'get_config_behavior_context'):
                    behavior_results = rag_instance.get_config_behavior_context(query, top_k=5)
                    # Filter to only highly relevant configs (score > 0.25)
                    relevant_configs = [c for c in behavior_results if c.get('score', 0) > 0.25]
                    if relevant_configs:
                        zk_behavior_context = rag_instance.format_config_behavior_context(relevant_configs)
                        logger.info(f"ZK Config behavior context: {len(relevant_configs)} highly relevant configs (filtered from {len(behavior_results)})")
                    else:
                        logger.info(f"No highly relevant ZK configs found for: {query} (all scores < 0.25)")
        except Exception as e:
            logger.warning(f"Failed to get ZK config behavior context: {e}")

        # 4. Get Bugs Knowledge (known bugs in similar features)
        # Helps generate tests that prevent regression of known issues
        bugs_context = ""
        try:
            rag_module = get_rag_integration()
            if rag_module:
                rag_instance = rag_module.get_test_case_rag()
                if rag_instance and hasattr(rag_instance, 'get_bugs_context'):
                    bugs_results = rag_instance.get_bugs_context(query, top_k=5)
                    # Filter to relevant bugs (score > 0.2)
                    relevant_bugs = [b for b in bugs_results if b.get('score', 0) > 0.2]
                    if relevant_bugs:
                        bugs_context = rag_instance.format_bugs_context(relevant_bugs)
                        logger.info(f"Bugs context: {len(relevant_bugs)} relevant bugs found")
        except Exception as e:
            logger.warning(f"Failed to get bugs context: {e}")

        # Combine contexts
        combined_context = codebase_context
        if zk_config_context:
            combined_context = (combined_context + "\n\n" + zk_config_context) if combined_context else zk_config_context
        if zk_behavior_context:
            combined_context = (combined_context + "\n\n" + zk_behavior_context) if combined_context else zk_behavior_context
        if bugs_context:
            combined_context = (combined_context + "\n\n" + bugs_context) if combined_context else bugs_context

        # Build messages
        messages = []

        # Log context usage
        if combined_context:
            context_sources = []
            if codebase_context:
                context_sources.append("Codebase")
            if zk_config_context:
                context_sources.append("ZK Config Values")
            if zk_behavior_context:
                context_sources.append("ZK Config Behaviors")
            if bugs_context:
                context_sources.append("Bugs Knowledge")
            logger.info(f"Using RAG context from: {', '.join(context_sources)}")

        # Prefer structured Figma data over images if available
        if figma_structure:
            # Use structured data (text-only, more efficient)
            logger.info("Using structured Figma data for analysis (text-based)")
            messages.append(
                {
                    "role": "user",
                    "content": self._build_analysis_prompt(request, figma_structure, combined_context, frontend_doc),
                }
            )
        elif images:
            # Fallback to image-based analysis
            logger.info(f"Using image-based analysis ({len(images)} images)")
            content_parts = []
            for img_path in images:
                try:
                    media_type, encoded_image = self._encode_image(img_path)
                    content_parts.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": encoded_image,
                            },
                        }
                    )
                    logger.info(f"Added image to analysis: {img_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to encode image {img_path}: {e}")

            # Add text prompt
            content_parts.append(
                {"type": "text", "text": self._build_analysis_prompt(request, rag_context=combined_context, frontend_doc=frontend_doc)}
            )
            messages.append({"role": "user", "content": content_parts})
        else:
            # Text only (no images or Figma data)
            logger.info("Using text-only analysis (no images or Figma data)")
            messages.append(
                {"role": "user", "content": self._build_analysis_prompt(request, rag_context=combined_context, frontend_doc=frontend_doc)}
            )

        # Call Claude API with rate limiting
        try:
            logger.info(f"Sending request to {self.provider.upper()} API...")
            # OpenAI has lower max_tokens limit (4096) vs Anthropic (16000)
            max_tokens_limit = 4096 if self.provider == "openai" else 16000
            response = self._rate_limited_api_call(
                messages=messages,
                max_tokens=max_tokens_limit,
                temperature=0.6,   # Slightly higher for more diverse test scenarios
            )

            # Extract JSON from response
            response_text = self._extract_response_text(response)
            logger.info(f"LLM Response (first 1000 chars): {response_text[:1000]}")

            # Parse JSON response (json already imported at module level)
            # Try to extract JSON from markdown code blocks if present
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
            else:
                # No code blocks - extract just the JSON object
                # Find the start of the JSON (first '{')
                json_start = response_text.find("{")
                if json_start == -1:
                    logger.error(f"No JSON found in response. Full response: {response_text}")
                    raise LLMAnalysisError(f"No JSON object found in response. Response was: {response_text[:500]}")

                # Find the end of the JSON by counting braces
                brace_count = 0
                json_end = json_start
                for i, char in enumerate(response_text[json_start:], start=json_start):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break

                json_str = response_text[json_start:json_end].strip()

            data = json.loads(json_str)

            # Create TestChecklist
            test_points = [TestPoint(**tp) for tp in data["test_points"]]

            # Parse truth table entries if present
            truth_table_entries = []
            if "truth_table_entries" in data and data["truth_table_entries"]:
                for entry in data["truth_table_entries"]:
                    try:
                        truth_table_entries.append(TruthTableEntry(**entry))
                    except ValidationError as e:
                        logger.warning(f"Skipping invalid truth table entry: {e}")

            truth_table_features = data.get("truth_table_features", [])

            # Parse coverage_analysis from LLM response
            coverage_analysis = None
            ca_data = data.get("coverage_analysis")
            if ca_data:
                try:
                    # Parse feature coverage
                    feature_coverage = []
                    for fc in ca_data.get("feature_coverage", []):
                        feature_coverage.append(FeatureCoverage(
                            feature=fc.get("feature", "Unknown"),
                            coverage_percentage=fc.get("coverage_percentage", 0),
                            test_count=fc.get("test_count", 0),
                            missing_scenarios=fc.get("missing_scenarios", []),
                            risk_level=fc.get("risk_level", "low"),
                        ))

                    # Parse test type distribution
                    ttd = ca_data.get("test_type_distribution", {})
                    test_type_distribution = TestTypeDistribution(
                        positive=ttd.get("positive", 0),
                        negative=ttd.get("negative", 0),
                        boundary=ttd.get("boundary", 0),
                        edge_case=ttd.get("edge_case", 0),
                    )

                    # Parse risk assessment
                    ra = ca_data.get("risk_assessment", {})
                    risk_assessment = RiskAssessment(
                        high_risk_features=ra.get("high_risk_features", []),
                        medium_risk_features=ra.get("medium_risk_features", []),
                        low_risk_features=ra.get("low_risk_features", []),
                    )

                    coverage_analysis = CoverageAnalysis(
                        feature_coverage=feature_coverage,
                        test_type_distribution=test_type_distribution,
                        missing_scenarios=ca_data.get("missing_scenarios", []),
                        risk_assessment=risk_assessment,
                        recommendations=ca_data.get("recommendations", []),
                    )
                    logger.info(f"Parsed coverage_analysis: {len(feature_coverage)} features, {len(ca_data.get('missing_scenarios', []))} missing scenarios")
                except Exception as e:
                    logger.warning(f"Failed to parse coverage_analysis: {e}")

            # IMPORTANT: User-provided feature_name takes priority over LLM extraction
            checklist = TestChecklist(
                feature_name=feature_name or data.get("feature_name", "Unknown"),
                test_points=test_points,
                coverage_score=data.get("coverage_score", 0.0),
                needs_more_info=data.get("needs_more_info", False),
                error_message=data.get("error_message"),
                truth_table_entries=truth_table_entries,
                truth_table_features=truth_table_features,
                coverage_analysis=coverage_analysis,
            )

            analysis_time = time.time() - start_time

            # Check if more info is needed (log but don't raise exception - let UI handle it)
            if checklist.needs_more_info:
                logger.warning(f"Analysis incomplete: {checklist.error_message}")
                logger.info(
                    f"Returning checklist with needs_more_info=True (0 test points) in {analysis_time:.2f}s"
                )
            else:
                tt_count = len(truth_table_entries)
                logger.info(
                    f"Analysis complete: {len(test_points)} test points, {tt_count} truth table entries generated in {analysis_time:.2f}s"
                )

            return checklist

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse LLM response as JSON: {e}"
            logger.error(error_msg)
            logger.error(f"Raw LLM response: {response_text}")
            logger.error(
                f"Attempted to parse: {json_str[:500] if len(json_str) > 500 else json_str}"
            )
            raise LLMAnalysisError(error_msg) from e

        except ValidationError as e:
            error_msg = f"Invalid test checklist format: {e}"
            logger.error(error_msg)
            raise LLMAnalysisError(error_msg) from e

        except Exception as e:
            error_msg = f"LLM analysis failed: {e}"
            logger.error(error_msg)
            raise LLMAnalysisError(error_msg) from e

    def generate_checklist_markdown(self, checklist: TestChecklist) -> str:
        """Generate markdown formatted checklist.

        Args:
            checklist: TestChecklist instance.

        Returns:
            Markdown formatted string.
        """
        return checklist.to_markdown()

    def analyze_screenshot(
        self,
        screenshot_path: Path,
        prd_content: str = "",
        feature_name: Optional[str] = None,
        apply_methods: Optional[List[str]] = None,
    ) -> TestChecklist:
        """Analyze screenshot of UI flows and generate test checklist.

        Uses Claude's vision capabilities to understand the screenshot,
        then generates test cases based on the UI elements and flows shown.

        Args:
            screenshot_path: Path to screenshot file (PNG, JPG, etc).
            prd_content: Optional PRD text to combine with screenshot analysis.
            feature_name: Optional feature name override.
            apply_methods: Optional list of test design methods to apply.

        Returns:
            TestChecklist instance with generated test points.

        Raises:
            LLMAnalysisError: If analysis fails.
        """
        start_time = time.time()

        try:
            # Encode screenshot to base64
            media_type, encoded_image = self._encode_image(screenshot_path)

            # Create analysis request
            TestAnalysisRequest(
                prd_content=prd_content or "Analysis of UI screenshot flows",
                images=[screenshot_path],
                feature_name=feature_name,
                apply_methods=apply_methods or [],
            )

            # NOTE: RAG context is NOT injected into prompts anymore.
            # We use post-generation gap analysis instead (Strategy A).

            # Build screenshot analysis prompt
            prd_section = f"**Additional PRD Context:**\n{prd_content}\n" if prd_content else ""
            methods_str = ", ".join(apply_methods or ["Equivalence Partitioning", "Boundary Value Analysis", "Decision Tables", "Scenario Method", "State Transition", "Error Guessing"])

            prompt = f"""You are an expert QA engineer specializing in test case design. Analyze the provided UI screenshot and generate comprehensive test points.

**UI Screenshot Analysis:**
Examine the user interface shown in the screenshot. Identify:
- UI elements and their interactions
- User flows and navigation paths
- Forms, inputs, and buttons
- Display states and conditions
- Error/success scenarios visible in the design

{prd_section}
**Test Design Methods to Apply:**
{methods_str}

**Methodology:**
1. **UI Element Extraction**: Identify all interactive and display elements
2. **Flow Analysis**: Map out user journeys and interactions
3. **Systematic Test Design**:
   - Element validation (positive, negative, boundary)
   - Flow scenarios (happy path, error paths)
   - State transitions and edge cases
4. **Coverage**: Test all visible elements and interactions

**Critical Rules:**
- Do NOT invent UI elements not visible in screenshot
- Only generate test points based on screenshot content
- Focus on what users actually see and interact with

Generate test points with:
- **SPECIFIC, ACTIONABLE descriptions** - Use exact UI element names from screenshot
- Feature categorization
- Priority (P0=Critical, P1=High, P2=Medium, P3=Low)
- Test type (positive, negative, edge_case, boundary)

**MINIMUM COVERAGE**: Generate at least 40-50 test points for the visible UI flows. Be exhaustive - more test points is better.

**Output Format:**
You MUST return a JSON object with this EXACT structure:
{{
  "feature_name": "Feature name from screenshot",
  "test_points": [
    {{
      "description": "Clear test point description",
      "feature": "Feature/component name",
      "priority": "P0|P1|P2|P3",
      "test_type": "positive|negative|edge_case|boundary"
    }}
  ],
  "coverage_score": 0-100,
  "needs_more_info": false,
  "error_message": null,
  "coverage_analysis": {{
    "feature_coverage": [],
    "test_type_distribution": {{"positive": num, "negative": num, "boundary": num, "edge_case": num}},
    "missing_scenarios": [],
    "risk_assessment": {{"high_risk_features": [], "medium_risk_features": [], "low_risk_features": []}},
    "recommendations": []
  }}
}}

CRITICAL: Your ENTIRE response must be ONLY the JSON object (no other text).

Analyze the screenshot and generate comprehensive test points:"""

            # Call Claude API with vision
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": encoded_image,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ]

            logger.info("Sending screenshot to Claude for analysis...")
            response = self._rate_limited_api_call(
                messages=messages,
                max_tokens=8000,  # Vision API limited to 8192 max, using 8000 to be safe
                temperature=0.5,
            )

            # Extract JSON from response
            response_text = self._extract_response_text(response)
            logger.debug(f"Screenshot Analysis Response: {response_text[:500]}...")

            # Parse JSON response
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
            else:
                json_start = response_text.find("{")
                if json_start == -1:
                    raise LLMAnalysisError("No JSON object found in response")
                brace_count = 0
                json_end = json_start
                for i, char in enumerate(response_text[json_start:], start=json_start):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                json_str = response_text[json_start:json_end].strip()

            data = json.loads(json_str)

            # Create TestChecklist
            # IMPORTANT: User-provided feature_name takes priority over LLM extraction
            test_points = [TestPoint(**tp) for tp in data["test_points"]]
            checklist = TestChecklist(
                feature_name=feature_name or data.get("feature_name", "Screenshot Analysis"),
                test_points=test_points,
                coverage_score=data.get("coverage_score", 0.0),
                needs_more_info=data.get("needs_more_info", False),
                error_message=data.get("error_message"),
            )

            analysis_time = time.time() - start_time

            if checklist.needs_more_info:
                logger.warning(f"Analysis incomplete: {checklist.error_message}")
                logger.info(
                    f"Returning checklist with needs_more_info=True (0 test points) in {analysis_time:.2f}s"
                )
            else:
                logger.info(
                    f"Screenshot analysis complete: {len(test_points)} test points generated in {analysis_time:.2f}s"
                )

            return checklist

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse LLM response as JSON: {e}"
            logger.error(error_msg)
            logger.error(f"Raw LLM response: {response_text}")
            raise LLMAnalysisError(error_msg) from e

        except ValidationError as e:
            error_msg = f"Invalid test checklist format: {e}"
            logger.error(error_msg)
            raise LLMAnalysisError(error_msg) from e

        except Exception as e:
            error_msg = f"Screenshot analysis failed: {e}"
            logger.error(error_msg)
            raise LLMAnalysisError(error_msg) from e

    def estimate_coverage(self, checklist: TestChecklist) -> float:
        """Estimate test coverage percentage.

        This is a heuristic based on:
        - Number of test points
        - Distribution across priorities
        - Distribution across test types

        Args:
            checklist: TestChecklist instance.

        Returns:
            Coverage score (0-100).
        """
        if not checklist.test_points:
            return 0.0

        # Use the LLM-provided score if available and reasonable
        if 0 <= checklist.coverage_score <= 100:
            return checklist.coverage_score

        # Fallback heuristic calculation
        total_points = len(checklist.test_points)

        # Check priority distribution
        priorities = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
        for point in checklist.test_points:
            priorities[point.priority] += 1

        priority_score = (
            (priorities["P0"] > 0) * 25
            + (priorities["P1"] > 0) * 20
            + (priorities["P2"] > 0) * 10
            + (priorities["P3"] > 0) * 5
        )

        # Check test type distribution (core types for scoring, others counted separately)
        test_types = {
            "positive": 0, "negative": 0, "edge_case": 0, "boundary": 0,
            "user_journey": 0, "subscription_state": 0, "navigation": 0,
            "ui_compliance": 0, "data_sync": 0, "state_propagation": 0,
            "feature_gating": 0
        }
        for point in checklist.test_points:
            if point.test_type in test_types:
                test_types[point.test_type] += 1

        # Score based on core test type coverage
        type_score = (
            (test_types["positive"] > 0) * 10
            + (test_types["negative"] > 0) * 10
            + (test_types["edge_case"] > 0) * 10
            + (test_types["boundary"] > 0) * 10
        )

        # Volume score (more points = better coverage, with diminishing returns)
        volume_score = min(total_points * 2, 40)

        total_score = min(priority_score + type_score + volume_score, 100)
        logger.info(f"Calculated coverage score: {total_score:.1f}%")

        return total_score

    def _build_backend_analysis_prompt(
        self, prd_content: str, feature_name: Optional[str] = None, backend_doc: Optional[str] = None
    ) -> str:
        """Build prompt for backend API/Database test case generation.

        Args:
            prd_content: PRD text content.
            feature_name: Optional feature name.
            backend_doc: Optional Backend LLD document content with API specs, DB schema.

        Returns:
            Formatted prompt string for backend test generation.
        """
        # Build Backend LLD section if provided
        backend_lld_section = ""
        if backend_doc:
            backend_lld_section = f"""
**BACKEND LLD (Technical Specifications):**
{backend_doc}

**IMPORTANT - USE THE LLD DOCUMENT:**
The Backend LLD above contains EXACT technical specifications. Use it to:
1. Extract EXACT API endpoints (routes, methods, headers)
2. Use EXACT database table names and column definitions
3. Generate tests for EACH API endpoint in the LLD
4. Test ALL fields mentioned in request/response schemas
5. Validate EXACT header requirements (userId, relationshipId, etc.)
6. Test JSONB field structures as specified
7. Verify error codes and validation rules from the LLD

"""

        prompt = f"""You are an expert Backend QA Engineer specializing in API testing, database validation, and security testing. Analyze the provided PRD and generate comprehensive BACKEND test cases.

**PRD Content:**
{prd_content}
{backend_lld_section}
**Feature Name:** {feature_name or "Unknown Feature"}

**YOUR TASK:**
Generate backend-specific test cases covering:

1. **API Testing (Test Type: "API")**
   - CRUD operations (Create, Read, Update, Delete)
   - Request/Response validation
   - HTTP status codes (200, 201, 400, 401, 403, 404, 500)
   - Request body validation (required fields, data types, formats)
   - Response body structure validation
   - Pagination and filtering
   - Rate limiting behavior

2. **Database Testing (Test Type: "Database")**
   - Record creation and persistence
   - Foreign key constraints and relationships
   - Data integrity (UNIQUE constraints, NOT NULL)
   - JSONB/JSON field storage and retrieval
   - Soft delete vs hard delete verification
   - Index usage and query performance
   - Transaction isolation and rollback

3. **Security Testing (Test Type: "Security")**
   - Authentication (401 for missing/invalid tokens)
   - Authorization (403 for unauthorized access)
   - Cross-user data access prevention
   - SQL injection prevention
   - XSS payload sanitization
   - Input sanitization for special characters
   - GDPR data export compliance
   - Sensitive data exposure prevention

4. **Performance Testing (Test Type: "Performance")**
   - API response time thresholds
   - Concurrent request handling
   - Database query performance
   - Memory and resource usage
   - Load testing scenarios

5. **Configuration Testing (Test Type: "Config")**
   - Feature flag behavior
   - Environment-specific settings
   - Rate limits and quotas
   - Dynamic configuration updates

6. **Analytics Testing (Test Type: "Analytics")**
   - Event tracking accuracy
   - Event payload validation
   - Logging correctness

**OUTPUT FORMAT:**
Return a JSON object with this EXACT structure:
{{
  "feature_name": "{feature_name or 'Backend API Tests'}",
  "test_points": [
    {{
      "category": "High-level category (e.g., Profile Creation, Security, Data Isolation)",
      "subcategory": "Specific area (e.g., Validation - Empty Name, DB Record Created)",
      "api_component": "API endpoint or component (e.g., POST /contacts/link, Database)",
      "test_scenario": "Verify that... (specific test description)",
      "precondition": "Setup required (e.g., Valid auth token, Existing profile)",
      "verification_method": "How to test (e.g., Call API, Query database, Check config)",
      "expected_result": "Success criteria (e.g., 400 Bad Request with validation error)",
      "priority": "P0|P1|P2",
      "test_type": "API|Database|Security|Performance|Config|Analytics|Backend|Cache"
    }}
  ],
  "coverage_score": 0-100,
  "needs_more_info": false,
  "error_message": null,
  "api_test_count": number,
  "database_test_count": number,
  "security_test_count": number,
  "performance_test_count": number
}}

**EXAMPLE TEST CASES:**

1. API Validation Test:
{{
  "category": "Profile Creation",
  "subcategory": "Validation - Empty Name",
  "api_component": "POST /contacts/link",
  "test_scenario": "Verify that API returns 400 for empty name",
  "precondition": "Request with name: ''",
  "verification_method": "Call API; inspect response",
  "expected_result": "400 Bad Request with validation error message",
  "priority": "P1",
  "test_type": "API"
}}

2. Database Test:
{{
  "category": "Profile Creation",
  "subcategory": "DB Record Created",
  "api_component": "Database",
  "test_scenario": "Verify that new row created in linked_contacts table with owner_id set",
  "precondition": "Secondary profile created via API",
  "verification_method": "Query linked_contacts WHERE owner_id = user.id",
  "expected_result": "New row with correct name, dob, tob, pob, relationship, owner_id = authenticated user ID",
  "priority": "P0",
  "test_type": "Database"
}}

3. Security Test:
{{
  "category": "Security",
  "subcategory": "SQL Injection - Name",
  "api_component": "POST /contacts/link",
  "test_scenario": "Verify that SQL injection in name field is sanitized",
  "precondition": "name: \"'; DROP TABLE users; --\"",
  "verification_method": "Call API; check database",
  "expected_result": "Input sanitized; no SQL execution",
  "priority": "P0",
  "test_type": "Security"
}}

4. Performance Test:
{{
  "category": "Performance",
  "subcategory": "API Response Time",
  "api_component": "All profile APIs",
  "test_scenario": "Verify that profile APIs respond within 200ms (99th percentile)",
  "precondition": "Normal load",
  "verification_method": "Monitor API response times",
  "expected_result": "99th percentile < 200ms",
  "priority": "P1",
  "test_type": "Performance"
}}

**MINIMUM REQUIREMENTS:**
- Generate at least 50-80 backend test cases
- Cover all API endpoints mentioned in the PRD
- Include both happy path (positive) and error handling (negative) scenarios
- Test all validation rules and constraints
- Include security tests for every endpoint that handles user data
- Test database integrity for all data operations

**CRITICAL:**
- Focus ONLY on backend/API testing - NO UI/frontend tests
- Every test must be verifiable via API calls or database queries
- Include specific HTTP status codes and response formats
- Be specific about database table names and column expectations

Return ONLY the JSON object (no other text):"""

        return prompt

    def analyze_prd_backend(
        self,
        content: str,
        feature_name: Optional[str] = None,
        backend_doc: Optional[str] = None,
    ) -> BackendTestChecklist:
        """Analyze PRD content and generate BACKEND test checklist.

        Generates API, Database, Security, and Performance test cases
        specifically for backend testing (no UI tests).

        Args:
            content: PRD text content.
            feature_name: Optional feature name override.
            backend_doc: Optional Backend LLD document with API specs, DB schema.
                        When provided, generates more comprehensive tests using exact endpoints.

        Returns:
            BackendTestChecklist instance with backend-specific test cases.

        Raises:
            LLMAnalysisError: If analysis fails.
        """
        start_time = time.time()

        # Build backend-specific prompt (include backend_doc if provided)
        prompt = self._build_backend_analysis_prompt(content, feature_name, backend_doc)

        # Build messages
        messages = [{"role": "user", "content": prompt}]

        try:
            logger.info(f"Sending BACKEND analysis request to {self.provider.upper()} API...")

            # Call LLM API
            max_tokens_limit = 4096 if self.provider == "openai" else 16000
            response = self._rate_limited_api_call(
                messages=messages,
                max_tokens=max_tokens_limit,
                temperature=0.5,  # Lower temperature for more consistent backend test generation
            )

            # Extract JSON from response
            response_text = self._extract_response_text(response)
            logger.info(f"Backend LLM Response (first 1000 chars): {response_text[:1000]}")

            # Parse JSON response
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
            else:
                # Find the JSON object
                json_start = response_text.find("{")
                if json_start == -1:
                    logger.error(f"No JSON found in response. Full response: {response_text}")
                    raise LLMAnalysisError(f"No JSON object found in response. Response was: {response_text[:500]}")

                # Find the end of the JSON by counting braces
                brace_count = 0
                json_end = json_start
                for i, char in enumerate(response_text[json_start:], start=json_start):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break

                json_str = response_text[json_start:json_end].strip()

            data = json.loads(json_str)

            # Create BackendTestPoint objects
            test_points = []
            for tp in data.get("test_points", []):
                try:
                    test_points.append(BackendTestPoint(**tp))
                except ValidationError as e:
                    logger.warning(f"Skipping invalid backend test point: {e}")
                    continue

            # Calculate test type counts
            api_count = sum(1 for tp in test_points if tp.test_type == "API")
            db_count = sum(1 for tp in test_points if tp.test_type == "Database")
            sec_count = sum(1 for tp in test_points if tp.test_type == "Security")
            perf_count = sum(1 for tp in test_points if tp.test_type == "Performance")

            # Create BackendTestChecklist
            # IMPORTANT: User-provided feature_name takes priority over LLM extraction
            checklist = BackendTestChecklist(
                feature_name=feature_name or data.get("feature_name", "Backend API Tests"),
                test_points=test_points,
                coverage_score=data.get("coverage_score", 0.0),
                needs_more_info=data.get("needs_more_info", False),
                error_message=data.get("error_message"),
                api_test_count=data.get("api_test_count", api_count),
                database_test_count=data.get("database_test_count", db_count),
                security_test_count=data.get("security_test_count", sec_count),
                performance_test_count=data.get("performance_test_count", perf_count),
            )

            analysis_time = time.time() - start_time

            if checklist.needs_more_info:
                logger.warning(f"Backend analysis incomplete: {checklist.error_message}")
            else:
                logger.info(
                    f"Backend analysis complete: {len(test_points)} test points "
                    f"(API: {api_count}, DB: {db_count}, Security: {sec_count}, Perf: {perf_count}) "
                    f"generated in {analysis_time:.2f}s"
                )

            return checklist

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse Backend LLM response as JSON: {e}"
            logger.error(error_msg)
            logger.error(f"Raw LLM response: {response_text}")
            raise LLMAnalysisError(error_msg) from e

        except ValidationError as e:
            error_msg = f"Invalid backend test checklist format: {e}"
            logger.error(error_msg)
            raise LLMAnalysisError(error_msg) from e

        except Exception as e:
            error_msg = f"Backend LLM analysis failed: {e}"
            logger.error(error_msg)
            raise LLMAnalysisError(error_msg) from e
