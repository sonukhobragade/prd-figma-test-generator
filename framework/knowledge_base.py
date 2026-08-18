"""Knowledge base loader for test case generation context."""

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """Loads and manages knowledge base files for test generation."""

    # Default knowledge base directory relative to project root
    DEFAULT_KB_DIR = "docs/knowledge_base"

    # Knowledge base file names
    KB_FILES = {
        "bug_patterns": "bug_patterns.md",
        "user_journeys": "user_journeys.md",
        "test_examples": "test_case_examples.md",
        "domain_knowledge": "domain_knowledge.md",
        "coverage_rules": "test_coverage_rules.md",
    }

    def __init__(self, kb_dir: Optional[Path] = None):
        """Initialize knowledge base loader.

        Args:
            kb_dir: Optional path to knowledge base directory.
                   Defaults to docs/knowledge_base relative to project root.
        """
        if kb_dir:
            self.kb_dir = Path(kb_dir)
        else:
            # Find project root (where framework/ is located)
            framework_dir = Path(__file__).parent
            project_root = framework_dir.parent
            self.kb_dir = project_root / self.DEFAULT_KB_DIR

        self._cache: Dict[str, str] = {}
        self._loaded = False
        logger.info(f"Knowledge base initialized at: {self.kb_dir}")

    def _load_file(self, filename: str) -> str:
        """Load a single knowledge base file.

        Args:
            filename: Name of the file to load.

        Returns:
            File contents as string, or empty string if not found.
        """
        file_path = self.kb_dir / filename
        try:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                logger.debug(f"Loaded knowledge base file: {filename} ({len(content)} chars)")
                return content
            else:
                logger.warning(f"Knowledge base file not found: {file_path}")
                return ""
        except Exception as e:
            logger.error(f"Error loading knowledge base file {filename}: {e}")
            return ""

    def load_all(self) -> None:
        """Load all knowledge base files into cache."""
        for key, filename in self.KB_FILES.items():
            self._cache[key] = self._load_file(filename)
        self._loaded = True
        logger.info(f"Loaded {len(self._cache)} knowledge base files")

    def get(self, key: str) -> str:
        """Get a specific knowledge base section.

        Args:
            key: Key name (bug_patterns, user_journeys, etc.)

        Returns:
            Content string or empty string if not found.
        """
        if not self._loaded:
            self.load_all()
        return self._cache.get(key, "")

    def get_bug_patterns(self) -> str:
        """Get bug patterns knowledge."""
        return self.get("bug_patterns")

    def get_user_journeys(self) -> str:
        """Get user journeys knowledge."""
        return self.get("user_journeys")

    def get_test_examples(self) -> str:
        """Get test case examples."""
        return self.get("test_examples")

    def get_domain_knowledge(self) -> str:
        """Get domain-specific knowledge."""
        return self.get("domain_knowledge")

    def get_coverage_rules(self) -> str:
        """Get test coverage rules."""
        return self.get("coverage_rules")

    def get_combined_context(self, max_chars: int = 50000) -> str:
        """Get combined knowledge base context for prompt.

        Combines all knowledge base files into a single context string,
        prioritizing the most important sections.

        Args:
            max_chars: Maximum characters to include (to manage token limits).

        Returns:
            Combined context string.
        """
        if not self._loaded:
            self.load_all()

        sections = []

        # Priority order for inclusion
        priority_order = [
            ("coverage_rules", "## Test Coverage Rules"),
            ("bug_patterns", "## Bug Patterns to Catch"),
            ("test_examples", "## Test Case Examples"),
            ("domain_knowledge", "## Domain Knowledge"),
            ("user_journeys", "## User Journeys"),
        ]

        total_chars = 0
        for key, header in priority_order:
            content = self._cache.get(key, "")
            if content and total_chars + len(content) < max_chars:
                sections.append(f"\n{header}\n{content}")
                total_chars += len(content)
            elif content:
                # Truncate to fit
                remaining = max_chars - total_chars - len(header) - 100
                if remaining > 500:
                    truncated = content[:remaining] + "\n\n[... truncated for brevity ...]"
                    sections.append(f"\n{header}\n{truncated}")
                    total_chars += remaining
                break

        combined = "\n".join(sections)
        logger.info(f"Combined knowledge base context: {len(combined)} chars")
        return combined

    def get_summary_context(self) -> str:
        """Get a condensed summary for prompt context.

        Returns only the most critical rules and patterns.

        Returns:
            Condensed context string.
        """
        summary = """
## Knowledge Base Summary

### Critical Test Types
- subscription_state: Test with different user states (subscribed, new, expired)
- navigation: Verify CTAs navigate to correct destinations
- ui_compliance: Match Figma design specs
- data_sync: Verify real-time updates without relaunch
- state_propagation: Test cross-feature state effects
- feature_gating: Verify prerequisites are enforced

### Critical Bug Patterns to Catch
1. Subscribed user: NO wallet/coin deduction, NO recharge popup, NO low-balance strip
2. Navigation: CTAs must go to CORRECT destination (e.g., Subscribe Now → Subscription Page, NOT Reports)
3. Data sync: Balance/status must update immediately without app relaunch
4. Free tier: New user gets exactly 2 free chats, counter works correctly
5. Profile gating: Cannot subscribe until profile is complete

### User States to Test
- New User (never subscribed)
- Subscribed User (active subscription)
- Subscribed with zero wallet (should still work)
- Half-onboarded (profile incomplete)
- Free exhausted then subscribed (no free strip)

### Negative Assertions (test what should NOT appear)
- "NO recharge popup for subscribed user"
- "NO coin deduction for subscribed user"
- "NO 'Continue without Subscription' for subscribed user"
- "NO free chat strip after subscription"
"""
        return summary

    def is_available(self) -> bool:
        """Check if knowledge base directory exists and has files."""
        if not self.kb_dir.exists():
            return False
        return any(
            (self.kb_dir / filename).exists()
            for filename in self.KB_FILES.values()
        )

    def list_available_files(self) -> list:
        """List available knowledge base files."""
        available = []
        for key, filename in self.KB_FILES.items():
            file_path = self.kb_dir / filename
            if file_path.exists():
                available.append({
                    "key": key,
                    "filename": filename,
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                })
        return available


# Global instance for easy access
_default_kb: Optional[KnowledgeBase] = None


def get_knowledge_base(enable_rag: bool = True) -> KnowledgeBase:
    """Get or create the default knowledge base instance.
    
    Args:
        enable_rag: If True, try to use RAG-enhanced knowledge base
        
    Returns:
        KnowledgeBase or EnhancedKnowledgeBase instance
    """
    global _default_kb
    
    if _default_kb is None:
        # Try to use enhanced KB with RAG if available
        if enable_rag:
            try:
                from rag.enhanced_kb import EnhancedKnowledgeBase
                _default_kb = EnhancedKnowledgeBase()
                logger.info("Using RAG-enhanced knowledge base")
            except ImportError:
                logger.debug("RAG not available, using standard knowledge base")
                _default_kb = KnowledgeBase()
            except Exception as e:
                logger.warning(f"Failed to initialize RAG KB: {e}. Using standard KB.")
                _default_kb = KnowledgeBase()
        else:
            _default_kb = KnowledgeBase()
    
    return _default_kb
