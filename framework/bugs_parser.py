"""
Multi-Format Bug CSV Parser
===========================

Supports 4 CSV formats with auto-detection:
- Format A: Frontend Bugs (Bugs, Dev, Priority, Dev Status, QA Status, Comments)
- Format B: UI/Visual Bugs (#, Bugs, Priority, Dev Status, QA Status, Comments)
- Format C: API/Backend Test Results (Test Suite, TC, Test Description, ...)
- Format D: Navigation Truth Table (Screen, CheckPoint, Failed, Pending, Successful, ...)

All formats are normalized to a unified BugDocument schema for RAG indexing.
"""

import csv
import re
import hashlib
import logging
from io import StringIO
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Tuple
from enum import Enum


class BugFormat(Enum):
    FRONTEND_BUGS = "frontend_bugs"
    UI_VISUAL_BUGS = "ui_visual_bugs"
    API_BACKEND = "api_backend"
    NAVIGATION_TRUTH_TABLE = "navigation_truth_table"
    GENERIC = "generic"


@dataclass
class BugDocument:
    """Unified bug document schema for RAG indexing."""
    bug_id: str
    title: str
    description: str
    category: str
    priority: str
    screen: str
    expected: str
    actual: str
    dev_type: str
    status: str
    root_cause: str
    comments: str
    source_format: str
    feature_name: str
    source_file: str
    uploaded_at: str

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_rag_text(self) -> str:
        """Convert to searchable text for RAG embedding."""
        parts = [
            f"Bug: {self.title}",
            f"Feature: {self.feature_name}",
            f"Category: {self.category}",
            f"Priority: {self.priority}",
        ]
        if self.screen:
            parts.append(f"Screen: {self.screen}")
        if self.description and self.description != self.title:
            parts.append(f"Description: {self.description}")
        if self.expected:
            parts.append(f"Expected: {self.expected}")
        if self.actual:
            parts.append(f"Actual: {self.actual}")
        if self.root_cause:
            parts.append(f"Root Cause: {self.root_cause}")
        if self.comments:
            parts.append(f"Comments: {self.comments}")
        parts.append(f"Dev Type: {self.dev_type}")
        parts.append(f"Status: {self.status}")

        return "\n".join(parts)


class BugsParser:
    """Multi-format bug CSV parser with auto-detection."""

    # Priority normalization mapping
    PRIORITY_MAP = {
        'p0': 'P0', 'p1': 'P1', 'p2': 'P2', 'p3': 'P2',
        'critical': 'P0', 'high': 'P1', 'medium': 'P2', 'low': 'P2',
        '0': 'P0', '1': 'P1', '2': 'P2', '3': 'P2',
    }

    # Status normalization mapping
    STATUS_MAP = {
        'fixed': 'Fixed', 'done': 'Fixed', 'closed': 'Fixed', 'resolved': 'Fixed',
        'open': 'Open', 'pending': 'Open', 'in progress': 'Open', 'wip': 'Open',
        'verified': 'Verified', 'tested': 'Verified', 'passed': 'Verified',
        'fail': 'Failed', 'failed': 'Failed', 'failing': 'Failed',
    }

    # Category extraction patterns
    CATEGORY_PATTERNS = [
        (r'subscri|wallet|payment|recharge|balance', 'Subscription'),
        (r'navig|redirect|route|screen.*to|goes.*to', 'Navigation'),
        (r'ui|visual|display|show|appear|color|font|layout', 'UI/Visual'),
        (r'api|backend|server|request|response|endpoint', 'API'),
        (r'chat|message|conversation', 'Chat'),
        (r'profile|user|account', 'Profile'),
        (r'report|insight|match|flag|score', 'Report'),
        (r'auth|login|otp|verify', 'Authentication'),
        (r'cache|sync|refresh|load', 'Data/Cache'),
    ]

    def __init__(self):
        self.bugs: List[BugDocument] = []
        self.format: BugFormat = BugFormat.GENERIC
        self.stats: Dict = {
            'total': 0,
            'p0': 0,
            'p1': 0,
            'p2': 0,
            'by_category': {},
            'by_status': {}
        }

    def detect_format(self, columns: List[str]) -> BugFormat:
        """Auto-detect CSV format from column headers."""
        columns_lower = [c.lower().strip() for c in columns]
        columns_str = ' '.join(columns_lower)

        # Format C: API/Backend Test Results
        if 'test suite' in columns_str and ('root cause' in columns_str or 'actual result' in columns_str):
            return BugFormat.API_BACKEND

        # Format D: Navigation Truth Table
        if 'checkpoint' in columns_str and 'redirected' in columns_str:
            return BugFormat.NAVIGATION_TRUTH_TABLE

        # Format B: UI/Visual Bugs (has # column)
        if '#' in columns and 'bugs' in columns_lower:
            return BugFormat.UI_VISUAL_BUGS

        # Format A: Frontend Bugs
        if 'bugs' in columns_lower and 'dev' in columns_lower:
            return BugFormat.FRONTEND_BUGS

        return BugFormat.GENERIC

    def _normalize_priority(self, priority: str) -> str:
        """Normalize priority to P0/P1/P2."""
        if not priority:
            return 'P2'
        priority_lower = priority.lower().strip()
        return self.PRIORITY_MAP.get(priority_lower, 'P2')

    def _normalize_status(self, status: str) -> str:
        """Normalize status."""
        if not status:
            return 'Open'
        status_lower = status.lower().strip()
        for key, value in self.STATUS_MAP.items():
            if key in status_lower:
                return value
        return status.title() if status else 'Open'

    def _extract_category(self, text: str) -> str:
        """Extract category from bug text using patterns."""
        text_lower = text.lower()
        for pattern, category in self.CATEGORY_PATTERNS:
            if re.search(pattern, text_lower):
                return category
        return 'General'

    def _extract_screen(self, text: str) -> str:
        """Extract screen name from bug text."""
        # Common screen patterns
        screen_patterns = [
            r'(?:on|in|at)\s+(\w+(?:\s+\w+)?)\s+(?:screen|page)',
            r'(\w+Screen)',
            r'(\w+Page)',
            r'(?:Home|Chat|Profile|Wallet|Recharge|Subscription|Report|Reports?|Settings?)',
        ]

        for pattern in screen_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) if match.lastindex else match.group(0)

        return ''

    def _generate_bug_id(self, content: str, index: int) -> str:
        """Generate unique bug ID."""
        hash_input = f"{content}:{index}:{datetime.now().isoformat()}"
        return f"BUG-{hashlib.md5(hash_input.encode()).hexdigest()[:8].upper()}"

    def _parse_frontend_bugs(self, rows: List[Dict], feature_name: str, source_file: str) -> List[BugDocument]:
        """Parse Format A: Frontend Bugs."""
        import logging
        logger = logging.getLogger(__name__)

        bugs = []
        skipped = 0
        for idx, row in enumerate(rows):
            bug_text = row.get('Bugs', row.get('bugs', ''))
            if not bug_text or not bug_text.strip():
                skipped += 1
                if skipped <= 3:
                    logger.warning(f"[BugsParser] Row {idx} skipped - empty 'Bugs' column. Row keys: {list(row.keys())[:5]}")
                continue

            bugs.append(BugDocument(
                bug_id=self._generate_bug_id(bug_text, idx),
                title=bug_text.strip()[:200],
                description=bug_text.strip(),
                category=self._extract_category(bug_text),
                priority=self._normalize_priority(row.get('Priority', row.get('priority', ''))),
                screen=self._extract_screen(bug_text),
                expected=row.get('Expected', ''),
                actual=row.get('Actual', ''),
                dev_type=row.get('Dev', row.get('dev', 'Frontend')),
                status=self._normalize_status(row.get('Dev Status', row.get('dev status', ''))),
                root_cause='',
                comments=row.get('Comments', row.get('comments', '')),
                source_format=BugFormat.FRONTEND_BUGS.value,
                feature_name=feature_name,
                source_file=source_file,
                uploaded_at=datetime.now().isoformat()
            ))

        logger.info(f"[BugsParser] Frontend bugs: {len(bugs)} parsed, {skipped} skipped (empty Bugs column)")
        return bugs

    def _parse_ui_visual_bugs(self, rows: List[Dict], feature_name: str, source_file: str) -> List[BugDocument]:
        """Parse Format B: UI/Visual Bugs."""
        import logging
        logger = logging.getLogger(__name__)

        bugs = []
        skipped = 0
        for idx, row in enumerate(rows):
            bug_text = row.get('Bugs', row.get('bugs', ''))
            if not bug_text or not bug_text.strip():
                skipped += 1
                if skipped <= 3:
                    logger.warning(f"[BugsParser] UI Row {idx} skipped - empty 'Bugs'. Row keys: {list(row.keys())[:5]}")
                continue

            bugs.append(BugDocument(
                bug_id=self._generate_bug_id(bug_text, idx),
                title=bug_text.strip()[:200],
                description=bug_text.strip(),
                category='UI/Visual',
                priority=self._normalize_priority(row.get('Priority', row.get('priority', ''))),
                screen=self._extract_screen(bug_text),
                expected='',
                actual='',
                dev_type='Frontend',
                status=self._normalize_status(row.get('Dev Status', row.get('dev status', ''))),
                root_cause='',
                comments=row.get('Comments', row.get('comments', '')),
                source_format=BugFormat.UI_VISUAL_BUGS.value,
                feature_name=feature_name,
                source_file=source_file,
                uploaded_at=datetime.now().isoformat()
            ))

        logger.info(f"[BugsParser] UI/Visual: {len(bugs)} parsed, {skipped} skipped (empty Bugs column)")
        return bugs

    def _parse_api_backend(self, rows: List[Dict], feature_name: str, source_file: str) -> List[BugDocument]:
        """Parse Format C: API/Backend Test Results.

        Includes ALL rows - even 'Pass' status because:
        - Pass = Bug was found, tested, and verified fixed (still valuable knowledge)
        - Fail = Bug still exists
        - Not a bug = Assumption that was incorrect (valuable for knowledge)
        """
        import logging
        logger = logging.getLogger(__name__)

        bugs = []
        skipped = 0
        for idx, row in enumerate(rows):
            test_desc = row.get('Test Description', row.get('test description', ''))
            if not test_desc or not test_desc.strip():
                skipped += 1
                continue

            # Get status from Status column, fallback to QA Status
            row_status = row.get('Status', row.get('status', ''))
            if not row_status:
                row_status = row.get('QA Status', row.get('qa status', ''))

            bugs.append(BugDocument(
                bug_id=self._generate_bug_id(test_desc, idx),
                title=test_desc.strip()[:200],
                description=test_desc.strip(),
                category='API',
                priority=self._normalize_priority('P1'),  # Default API issues to P1
                screen='',
                expected=row.get('Expected Result', row.get('expected result', '')),
                actual=row.get('Actual Result', row.get('actual result', '')),
                dev_type='Backend',
                status=self._normalize_status(row_status),
                root_cause=row.get('Root Cause', row.get('root cause', '')),
                comments=row.get('Comments', row.get('comments', '')),
                source_format=BugFormat.API_BACKEND.value,
                feature_name=feature_name,
                source_file=source_file,
                uploaded_at=datetime.now().isoformat()
            ))

        logger.info(f"[BugsParser] API/Backend: {len(bugs)} parsed, {skipped} skipped (empty Test Description)")
        return bugs

    def _parse_navigation_truth_table(self, rows: List[Dict], feature_name: str, source_file: str) -> List[BugDocument]:
        """Parse Format D: Navigation Truth Table.

        Captures ALL redirection rules because:
        - Failed Payment Redirections - Where users go when payment fails
        - Pending Payment Redirections - Where users go during processing
        - Passed/Successful Redirections - Where users land after success
        - Auto Redirection Rules - Which screens auto-redirect vs require action

        Even passing rows = CORRECT behavior that tests should verify.
        """
        logger = logging.getLogger(__name__)
        bugs = []
        bugs_count = 0
        rules_count = 0

        for idx, row in enumerate(rows):
            screen = row.get('Screen', row.get('screen', ''))
            checkpoint = row.get('CheckPoint', row.get('checkpoint', ''))
            results = row.get('Results', row.get('results', '')).strip().lower()
            expected = row.get('Expected', row.get('expected', '')).strip().lower()
            fix_results = row.get('Fix Results', row.get('fix results', '')).strip()

            # Get all redirection targets
            failed_to = row.get('Failed (Redirected To)', row.get('failed (redirected to)', '')).strip()
            pending_to = row.get('Pending (Redirected To)', row.get('pending (redirected to)', '')).strip()
            success_to = row.get('Successful (Redirected To)', row.get('successful (redirected to)', '')).strip()

            # Skip rows with no meaningful data
            if not screen and not checkpoint:
                continue

            # Determine if this is a bug or a rule
            is_bug = results and expected and results != expected

            # Build comprehensive description
            description_parts = []
            description_parts.append(f"Screen: {screen}")
            description_parts.append(f"Checkpoint: {checkpoint}")

            # Add redirection rules (this is the KEY knowledge!)
            if failed_to:
                description_parts.append(f"ON PAYMENT FAILED: Redirect to {failed_to}")
            if pending_to:
                description_parts.append(f"ON PAYMENT PENDING: Redirect to {pending_to}")
            if success_to:
                description_parts.append(f"ON PAYMENT SUCCESS: Redirect to {success_to}")

            # Check for auto-redirection (usually mentioned in comments or inferred)
            auto_redirect_hint = ''
            if 'auto' in str(row).lower():
                auto_redirect_hint = 'AUTO-REDIRECT ENABLED'
                description_parts.append(auto_redirect_hint)

            description = " | ".join(description_parts)

            # Determine category and priority
            if is_bug:
                category = 'Navigation Bug'
                priority = 'P0'  # Navigation bugs are critical
                title = f"BUG: {screen} - {checkpoint} (Expected: {expected}, Got: {results})"
                status = self._normalize_status(fix_results) if fix_results else 'Open'
                bugs_count += 1
            else:
                category = 'Redirection Rule'
                priority = 'P1'  # Rules are important for test generation
                title = f"RULE: {screen} - {checkpoint}"
                status = 'Verified' if results == expected else 'Documented'
                rules_count += 1

            # Add redirection summary to title
            redirects = []
            if failed_to:
                redirects.append(f"Fail->{failed_to}")
            if pending_to:
                redirects.append(f"Pending->{pending_to}")
            if success_to:
                redirects.append(f"Success->{success_to}")
            if redirects:
                title = f"{title} [{', '.join(redirects)}]"[:200]

            bugs.append(BugDocument(
                bug_id=self._generate_bug_id(f"{screen}_{checkpoint}_{idx}", idx),
                title=title,
                description=description,
                category=category,
                priority=priority,
                screen=screen,
                expected=expected if expected else 'Not specified',
                actual=results if results else 'Not tested',
                dev_type='Frontend',
                status=status,
                root_cause=f"Failed: {failed_to}, Pending: {pending_to}, Success: {success_to}",
                comments=fix_results,
                source_format=BugFormat.NAVIGATION_TRUTH_TABLE.value,
                feature_name=feature_name,
                source_file=source_file,
                uploaded_at=datetime.now().isoformat()
            ))

        logger.info(f"[BugsParser] Navigation Truth Table: {len(bugs)} total ({bugs_count} bugs, {rules_count} rules)")
        return bugs

    def _parse_generic(self, rows: List[Dict], feature_name: str, source_file: str) -> List[BugDocument]:
        """Parse unknown format - best effort."""
        bugs = []
        for idx, row in enumerate(rows):
            # Find the most likely bug description field
            bug_text = ''
            for key in ['bugs', 'bug', 'description', 'title', 'issue', 'error', 'problem']:
                for col in row.keys():
                    if key in col.lower():
                        bug_text = row[col]
                        break
                if bug_text:
                    break

            if not bug_text:
                # Use first non-empty field
                for val in row.values():
                    if val and isinstance(val, str) and len(val) > 10:
                        bug_text = val
                        break

            if not bug_text or not bug_text.strip():
                continue

            # Try to find priority
            priority = ''
            for key in ['priority', 'severity', 'p']:
                for col in row.keys():
                    if key in col.lower():
                        priority = row[col]
                        break
                if priority:
                    break

            # Try to find status
            status = ''
            for key in ['status', 'state', 'dev status']:
                for col in row.keys():
                    if key in col.lower():
                        status = row[col]
                        break
                if status:
                    break

            bugs.append(BugDocument(
                bug_id=self._generate_bug_id(bug_text, idx),
                title=bug_text.strip()[:200],
                description=bug_text.strip(),
                category=self._extract_category(bug_text),
                priority=self._normalize_priority(priority),
                screen=self._extract_screen(bug_text),
                expected='',
                actual='',
                dev_type='Unknown',
                status=self._normalize_status(status),
                root_cause='',
                comments='',
                source_format=BugFormat.GENERIC.value,
                feature_name=feature_name,
                source_file=source_file,
                uploaded_at=datetime.now().isoformat()
            ))

        return bugs

    def parse_csv(self, csv_content: str, feature_name: str, source_file: str) -> Tuple[List[BugDocument], Dict]:
        """
        Parse CSV content and return normalized bug documents.

        Args:
            csv_content: CSV file content as string
            feature_name: Feature name for grouping (e.g., "Subscription Flow")
            source_file: Original filename

        Returns:
            Tuple of (list of BugDocument, stats dict)
        """
        import logging
        logger = logging.getLogger(__name__)

        # Parse CSV
        reader = csv.DictReader(StringIO(csv_content))
        columns = reader.fieldnames or []
        rows = list(reader)

        logger.info(f"[BugsParser] File: {source_file}")
        logger.info(f"[BugsParser] Columns: {columns}")
        logger.info(f"[BugsParser] Total CSV rows: {len(rows)}")

        if not rows:
            return [], {'total': 0, 'format': 'empty'}

        # Detect format
        self.format = self.detect_format(columns)
        logger.info(f"[BugsParser] Detected format: {self.format.value}")

        # Parse based on format
        if self.format == BugFormat.FRONTEND_BUGS:
            self.bugs = self._parse_frontend_bugs(rows, feature_name, source_file)
        elif self.format == BugFormat.UI_VISUAL_BUGS:
            self.bugs = self._parse_ui_visual_bugs(rows, feature_name, source_file)
        elif self.format == BugFormat.API_BACKEND:
            self.bugs = self._parse_api_backend(rows, feature_name, source_file)
        elif self.format == BugFormat.NAVIGATION_TRUTH_TABLE:
            self.bugs = self._parse_navigation_truth_table(rows, feature_name, source_file)
        else:
            self.bugs = self._parse_generic(rows, feature_name, source_file)

        # Calculate stats
        self.stats = {
            'total': len(self.bugs),
            'format': self.format.value,
            'p0': sum(1 for b in self.bugs if b.priority == 'P0'),
            'p1': sum(1 for b in self.bugs if b.priority == 'P1'),
            'p2': sum(1 for b in self.bugs if b.priority == 'P2'),
            'by_category': {},
            'by_status': {}
        }

        for bug in self.bugs:
            self.stats['by_category'][bug.category] = self.stats['by_category'].get(bug.category, 0) + 1
            self.stats['by_status'][bug.status] = self.stats['by_status'].get(bug.status, 0) + 1

        return self.bugs, self.stats


# Utility function for quick parsing
def parse_bugs_csv(csv_content: str, feature_name: str, source_file: str) -> Tuple[List[BugDocument], Dict]:
    """
    Quick utility to parse a bugs CSV file.

    Args:
        csv_content: CSV file content as string
        feature_name: Feature name for grouping
        source_file: Original filename

    Returns:
        Tuple of (list of BugDocument, stats dict)
    """
    parser = BugsParser()
    return parser.parse_csv(csv_content, feature_name, source_file)
