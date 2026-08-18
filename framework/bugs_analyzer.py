"""
Bugs Analyzer - Extract Business Rules from Historical Bugs
============================================================

Analyzes bug patterns to:
1. Extract implicit business rules
2. Identify common failure patterns
3. Generate domain knowledge updates
4. Suggest test case improvements

Usage:
    analyzer = BugsAnalyzer()
    rules = analyzer.extract_business_rules(bugs)
    suggestions = analyzer.get_domain_knowledge_suggestions()
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class BusinessRule:
    """Extracted business rule from bugs."""
    rule_id: str
    rule_text: str
    category: str
    confidence: float  # 0.0 to 1.0
    source_bugs: List[str] = field(default_factory=list)
    priority: str = "P1"
    feature_area: str = ""
    test_suggestion: str = ""


@dataclass
class DomainKnowledgeSuggestion:
    """Suggested update to domain knowledge."""
    section: str
    content: str
    source_rules: List[str]
    priority: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class BugsAnalyzer:
    """Analyzes bugs to extract business rules and domain knowledge."""

    # Patterns to identify business rules in bug descriptions
    RULE_PATTERNS = [
        # State-based rules
        (r'(user|users)\s+(should|must|cannot|can\'t|shouldn\'t)\s+(.+?)(?:\.|$)', 'user_behavior'),
        (r'(subscribed|subscription)\s+user[s]?\s+(should|must|cannot)\s+(.+?)(?:\.|$)', 'subscription'),
        (r'(free|new)\s+user[s]?\s+(should|must|cannot)\s+(.+?)(?:\.|$)', 'free_user'),

        # Validation rules
        (r'(must|should)\s+(?:be\s+)?(validate|check|verify)\s+(.+?)(?:\.|$)', 'validation'),
        (r'(cannot|can\'t|shouldn\'t)\s+(.+?)\s+(without|unless|until)\s+(.+?)(?:\.|$)', 'precondition'),

        # Navigation rules
        (r'(redirect|navigate|go)\s+to\s+(.+?)\s+(instead of|not)\s+(.+?)(?:\.|$)', 'navigation'),
        (r'(should|must)\s+(?:be\s+)?(redirect|navigate|take)\s+(?:to\s+)?(.+?)(?:\.|$)', 'navigation'),

        # Display rules
        (r'(display|show|appear|visible)\s+(.+?)\s+(when|after|before|if)\s+(.+?)(?:\.|$)', 'display'),
        (r'(not\s+display|hide|not\s+show|not\s+visible)\s+(.+?)\s+(when|for|if)\s+(.+?)(?:\.|$)', 'display'),

        # Deduction/Payment rules
        (r'(deduct|charge|pay|wallet)\s+(.+?)\s+(should|must|cannot)\s+(.+?)(?:\.|$)', 'payment'),
        (r'(money|coins?|balance)\s+(is|are|should|must)\s+(.+?)(?:\.|$)', 'payment'),

        # Redirection rules (from Navigation Truth Table)
        (r'ON PAYMENT FAILED:\s*Redirect to\s+(.+?)(?:\||$)', 'payment_redirect_failed'),
        (r'ON PAYMENT PENDING:\s*Redirect to\s+(.+?)(?:\||$)', 'payment_redirect_pending'),
        (r'ON PAYMENT SUCCESS:\s*Redirect to\s+(.+?)(?:\||$)', 'payment_redirect_success'),
        (r'Fail->(.+?)(?:,|$)', 'redirect_on_fail'),
        (r'Pending->(.+?)(?:,|$)', 'redirect_on_pending'),
        (r'Success->(.+?)(?:,|$)', 'redirect_on_success'),
        (r'AUTO-REDIRECT ENABLED', 'auto_redirect'),
    ]

    # Category mappings for better organization
    CATEGORY_MAPPING = {
        'subscription': 'Subscription Rules',
        'user_behavior': 'User Behavior Rules',
        'free_user': 'Free User Rules',
        'validation': 'Validation Rules',
        'precondition': 'Precondition Rules',
        'navigation': 'Navigation Rules',
        'display': 'Display Rules',
        'payment': 'Payment/Wallet Rules',
        # Redirection rules from Navigation Truth Table
        'payment_redirect_failed': 'Payment Failed Redirections',
        'payment_redirect_pending': 'Payment Pending Redirections',
        'payment_redirect_success': 'Payment Success Redirections',
        'redirect_on_fail': 'Payment Failed Redirections',
        'redirect_on_pending': 'Payment Pending Redirections',
        'redirect_on_success': 'Payment Success Redirections',
        'auto_redirect': 'Auto Redirect Rules',
    }

    def __init__(self):
        self.extracted_rules: List[BusinessRule] = []
        self.bug_patterns: Dict[str, List[Dict]] = defaultdict(list)

    def analyze_bugs(self, bugs: List[Dict]) -> Dict[str, Any]:
        """
        Analyze a list of bugs to extract patterns and rules.

        Args:
            bugs: List of bug dictionaries

        Returns:
            Analysis results including rules and patterns
        """
        logger.info(f"Analyzing {len(bugs)} bugs for business rules...")

        # Reset state
        self.extracted_rules = []
        self.bug_patterns = defaultdict(list)

        # Group bugs by category and priority
        bugs_by_category = defaultdict(list)
        bugs_by_priority = defaultdict(list)

        for bug in bugs:
            category = bug.get('category', 'General')
            priority = bug.get('priority', 'P2')
            bugs_by_category[category].append(bug)
            bugs_by_priority[priority].append(bug)

        # Extract rules from each bug
        for bug in bugs:
            self._extract_rules_from_bug(bug)

        # Deduplicate and consolidate rules
        self._consolidate_rules()

        # Generate analysis summary
        analysis = {
            'total_bugs': len(bugs),
            'bugs_by_category': {k: len(v) for k, v in bugs_by_category.items()},
            'bugs_by_priority': {k: len(v) for k, v in bugs_by_priority.items()},
            'extracted_rules': len(self.extracted_rules),
            'rules': [self._rule_to_dict(r) for r in self.extracted_rules],
            'patterns': dict(self.bug_patterns),
        }

        logger.info(f"Extracted {len(self.extracted_rules)} business rules from bugs")
        return analysis

    def _extract_rules_from_bug(self, bug: Dict) -> None:
        """Extract business rules from a single bug."""
        title = bug.get('title', '')
        description = bug.get('description', '')
        comments = bug.get('comments', '')

        # Combine all text for analysis
        full_text = f"{title} {description} {comments}".lower()

        # Try each pattern
        for pattern, category in self.RULE_PATTERNS:
            matches = re.finditer(pattern, full_text, re.IGNORECASE)
            for match in matches:
                rule_text = self._format_rule_from_match(match, category)
                if rule_text and len(rule_text) > 10:
                    rule = BusinessRule(
                        rule_id=f"RULE-{hash(rule_text) % 100000:05d}",
                        rule_text=rule_text,
                        category=self.CATEGORY_MAPPING.get(category, category),
                        confidence=self._calculate_confidence(bug, match),
                        source_bugs=[bug.get('bug_id', 'unknown')],
                        priority=bug.get('priority', 'P1'),
                        feature_area=bug.get('feature_name', ''),
                        test_suggestion=self._generate_test_suggestion(rule_text, category)
                    )
                    self.extracted_rules.append(rule)

        # Also extract patterns based on keywords
        self._extract_keyword_patterns(bug)

    def _format_rule_from_match(self, match: re.Match, category: str) -> str:
        """Format a business rule from regex match."""
        groups = match.groups()
        if not groups:
            return ""

        # Clean and format the rule text
        rule_text = " ".join(g for g in groups if g).strip()
        rule_text = re.sub(r'\s+', ' ', rule_text)

        # Capitalize first letter
        if rule_text:
            rule_text = rule_text[0].upper() + rule_text[1:]

        return rule_text

    def _calculate_confidence(self, bug: Dict, match: re.Match) -> float:
        """Calculate confidence score for extracted rule."""
        confidence = 0.5  # Base confidence

        # Higher confidence for P0 bugs
        if bug.get('priority') == 'P0':
            confidence += 0.2
        elif bug.get('priority') == 'P1':
            confidence += 0.1

        # Higher confidence for fixed bugs (validated rules)
        status = bug.get('status', '').lower()
        if 'fixed' in status or 'verified' in status:
            confidence += 0.2

        # Higher confidence for longer matches (more specific)
        if len(match.group(0)) > 50:
            confidence += 0.1

        return min(confidence, 1.0)

    def _generate_test_suggestion(self, rule_text: str, category: str) -> str:
        """Generate a test suggestion based on the rule."""
        rule_lower = rule_text.lower()

        # Payment redirection tests (from Navigation Truth Table)
        if category in ('payment_redirect_failed', 'redirect_on_fail'):
            return f"Redirection test: When payment FAILS, verify user is redirected to {rule_text}"
        elif category in ('payment_redirect_pending', 'redirect_on_pending'):
            return f"Redirection test: When payment is PENDING, verify user is redirected to {rule_text}"
        elif category in ('payment_redirect_success', 'redirect_on_success'):
            return f"Redirection test: When payment SUCCEEDS, verify user is redirected to {rule_text}"
        elif category == 'auto_redirect':
            return "Auto-redirect test: Verify automatic redirection occurs without user action"
        elif 'cannot' in rule_lower or 'shouldn\'t' in rule_lower:
            return f"Negative test: Verify that {rule_text.lower()}"
        elif 'must' in rule_lower or 'should' in rule_lower:
            return f"Positive test: Verify that {rule_text.lower()}"
        elif category == 'navigation':
            return f"Navigation test: Verify correct redirection - {rule_text}"
        elif category == 'display':
            return f"UI test: Verify visibility conditions - {rule_text}"
        elif category == 'payment':
            return f"Payment test: Verify wallet/balance behavior - {rule_text}"
        else:
            return f"Test: Verify {rule_text.lower()}"

    def _extract_keyword_patterns(self, bug: Dict) -> None:
        """Extract patterns based on keywords in bug description."""
        title = bug.get('title', '').lower()

        # Common failure patterns
        patterns_to_check = [
            ('subscription', 'state_check', 'Subscription state not properly checked'),
            ('wallet', 'payment', 'Wallet/payment handling issue'),
            ('redirect', 'navigation', 'Navigation/redirection issue'),
            ('display', 'ui', 'UI display issue'),
            ('deduct', 'payment', 'Incorrect deduction'),
            ('premium', 'access', 'Premium access control issue'),
            ('onboard', 'validation', 'Onboarding validation issue'),
            ('profile', 'state', 'Profile state handling issue'),
        ]

        for keyword, pattern_type, description in patterns_to_check:
            if keyword in title:
                self.bug_patterns[pattern_type].append({
                    'bug_id': bug.get('bug_id'),
                    'title': bug.get('title'),
                    'priority': bug.get('priority'),
                    'description': description
                })

    def _consolidate_rules(self) -> None:
        """Consolidate similar rules and remove duplicates."""
        if not self.extracted_rules:
            return

        # Group similar rules
        consolidated = {}
        for rule in self.extracted_rules:
            # Simple deduplication by rule text similarity
            key = rule.rule_text[:50].lower()
            if key not in consolidated:
                consolidated[key] = rule
            else:
                # Merge source bugs
                consolidated[key].source_bugs.extend(rule.source_bugs)
                # Take higher confidence
                consolidated[key].confidence = max(
                    consolidated[key].confidence, rule.confidence
                )

        self.extracted_rules = list(consolidated.values())

        # Sort by confidence and priority
        self.extracted_rules.sort(
            key=lambda r: (r.priority, -r.confidence),
            reverse=False
        )

    def _rule_to_dict(self, rule: BusinessRule) -> Dict:
        """Convert BusinessRule to dictionary."""
        return {
            'rule_id': rule.rule_id,
            'rule_text': rule.rule_text,
            'category': rule.category,
            'confidence': rule.confidence,
            'source_bugs': list(set(rule.source_bugs)),
            'priority': rule.priority,
            'feature_area': rule.feature_area,
            'test_suggestion': rule.test_suggestion,
        }

    def get_domain_knowledge_suggestions(self) -> List[DomainKnowledgeSuggestion]:
        """
        Generate suggestions for updating domain knowledge.

        Returns:
            List of domain knowledge suggestions
        """
        suggestions = []

        # Group rules by category
        rules_by_category = defaultdict(list)
        for rule in self.extracted_rules:
            rules_by_category[rule.category].append(rule)

        # Generate suggestion for each category
        for category, rules in rules_by_category.items():
            if not rules:
                continue

            # Build content
            content_lines = [f"### {category}\n"]
            content_lines.append("| Rule | Priority | Source | Test Suggestion |")
            content_lines.append("|------|----------|--------|-----------------|")

            for rule in rules[:10]:  # Limit to top 10 per category
                source = rule.source_bugs[0] if rule.source_bugs else "Unknown"
                content_lines.append(
                    f"| {rule.rule_text[:80]}{'...' if len(rule.rule_text) > 80 else ''} "
                    f"| {rule.priority} | {source} | {rule.test_suggestion[:50]}... |"
                )

            suggestion = DomainKnowledgeSuggestion(
                section=category,
                content="\n".join(content_lines),
                source_rules=[r.rule_id for r in rules],
                priority=rules[0].priority if rules else "P2"
            )
            suggestions.append(suggestion)

        return suggestions

    def generate_markdown_update(self) -> str:
        """
        Generate a markdown document with all extracted rules.

        Returns:
            Markdown formatted string
        """
        lines = [
            "# Business Rules Extracted from Bugs",
            "",
            f"> **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"> **Total Rules**: {len(self.extracted_rules)}",
            "",
            "---",
            ""
        ]

        # Group by category
        rules_by_category = defaultdict(list)
        for rule in self.extracted_rules:
            rules_by_category[rule.category].append(rule)

        for category, rules in sorted(rules_by_category.items()):
            lines.append(f"## {category}")
            lines.append("")

            for rule in rules:
                confidence_bar = "█" * int(rule.confidence * 5) + "░" * (5 - int(rule.confidence * 5))
                lines.append(f"### {rule.rule_id}")
                lines.append(f"- **Rule**: {rule.rule_text}")
                lines.append(f"- **Priority**: {rule.priority}")
                lines.append(f"- **Confidence**: {confidence_bar} ({rule.confidence:.0%})")
                lines.append(f"- **Feature**: {rule.feature_area}")
                lines.append(f"- **Source Bugs**: {', '.join(rule.source_bugs[:3])}")
                lines.append(f"- **Test Suggestion**: {rule.test_suggestion}")
                lines.append("")

        # Add patterns section
        if self.bug_patterns:
            lines.append("---")
            lines.append("")
            lines.append("## Common Bug Patterns")
            lines.append("")

            for pattern_type, bugs in self.bug_patterns.items():
                lines.append(f"### {pattern_type.replace('_', ' ').title()}")
                lines.append(f"- **Occurrences**: {len(bugs)}")
                lines.append("- **Examples**:")
                for bug in bugs[:3]:
                    lines.append(f"  - {bug.get('title', 'Unknown')[:60]}...")
                lines.append("")

        return "\n".join(lines)


def analyze_bugs_for_rules(bugs: List[Dict]) -> Dict[str, Any]:
    """
    Convenience function to analyze bugs and extract rules.

    Args:
        bugs: List of bug dictionaries

    Returns:
        Analysis results
    """
    analyzer = BugsAnalyzer()
    return analyzer.analyze_bugs(bugs)
