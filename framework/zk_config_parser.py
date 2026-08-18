"""
ZK Config Behavior Parser
=========================

Parses ZK_CONFIG_BEHAVIOR_GUIDE.md to extract structured config documentation.
Each config's behavioral impact, type, examples, and implementation references
are extracted for RAG indexing and test generation enhancement.

Usage:
    parser = ZKConfigBehaviorParser()
    docs = parser.parse_markdown(content)
    # docs is a list of ZKConfigDoc objects
"""

import re
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class ZKConfigDoc:
    """Structured documentation for a single ZK config."""
    config_name: str                    # e.g., "minSupportedVersion"
    category: str                       # e.g., "App Versioning & Force Update"
    config_type: str                    # boolean, string, number, object, array
    description: str                    # What it does (short)
    behavioral_impact: str              # Detailed impact description
    examples: List[Dict[str, str]] = field(default_factory=list)  # [{value: X, effect: Y}]
    implementation_ref: str = ""        # e.g., "hooks/app/useForceUpdate.ts:48-50"
    default_value: str = ""             # Default value if mentioned
    related_configs: List[str] = field(default_factory=list)  # Other configs that interact
    raw_markdown: str = ""              # Original markdown section for reference

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_embedding_text(self) -> str:
        """Generate text optimized for embedding/RAG search."""
        parts = [
            f"Config: {self.config_name}",
            f"Category: {self.category}",
            f"Type: {self.config_type}",
            f"Description: {self.description}",
            f"Behavioral Impact: {self.behavioral_impact}",
        ]
        if self.examples:
            examples_text = " | ".join([
                f"{ex.get('value', '')}: {ex.get('effect', '')}"
                for ex in self.examples[:5]  # Limit examples
            ])
            parts.append(f"Examples: {examples_text}")
        if self.implementation_ref:
            parts.append(f"Implementation: {self.implementation_ref}")
        return " | ".join(parts)


class ZKConfigBehaviorParser:
    """Parses ZK_CONFIG_BEHAVIOR_GUIDE.md into structured config documents."""

    # Regex patterns for extraction
    CATEGORY_PATTERN = re.compile(r'^## (.+)$', re.MULTILINE)
    CONFIG_PATTERN = re.compile(r'^### `([^`]+)`', re.MULTILINE)
    TYPE_PATTERN = re.compile(r'\*\*Type:\*\*\s*`([^`]+)`', re.IGNORECASE)
    DEFAULT_PATTERN = re.compile(r'\*\*Default:\*\*\s*`([^`]+)`', re.IGNORECASE)
    IMPL_PATTERN = re.compile(r'\*\*Implementation:\*\*\s*`([^`]+)`', re.IGNORECASE)

    def __init__(self):
        self.docs: List[ZKConfigDoc] = []
        self.categories: Dict[str, List[str]] = {}
        self.parse_errors: List[str] = []

    def parse_markdown(self, content: str) -> List[ZKConfigDoc]:
        """
        Parse the full markdown content and extract config documentation.

        Args:
            content: Full markdown content of ZK_CONFIG_BEHAVIOR_GUIDE.md

        Returns:
            List of ZKConfigDoc objects
        """
        self.docs = []
        self.categories = {}
        self.parse_errors = []

        logger.info("Starting to parse ZK Config Behavior Guide...")

        # Split content by top-level categories (## headers)
        category_sections = self._split_by_categories(content)

        for category_name, category_content in category_sections.items():
            # Skip non-config sections
            if category_name.lower() in ['table of contents', 'summary', 'testing checklist', 'quick reference table']:
                continue

            # Extract configs from this category
            configs = self._extract_configs_from_category(category_name, category_content)
            self.docs.extend(configs)

            if configs:
                self.categories[category_name] = [c.config_name for c in configs]

        logger.info(f"Parsed {len(self.docs)} config docs from {len(self.categories)} categories")
        if self.parse_errors:
            logger.warning(f"Parse errors: {len(self.parse_errors)}")

        return self.docs

    def _split_by_categories(self, content: str) -> Dict[str, str]:
        """Split content into category sections."""
        categories = {}

        # Find all ## headers and their positions
        matches = list(self.CATEGORY_PATTERN.finditer(content))

        for i, match in enumerate(matches):
            category_name = match.group(1).strip()
            start = match.end()

            # End is either next category or end of content
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(content)

            category_content = content[start:end].strip()
            categories[category_name] = category_content

        return categories

    def _extract_configs_from_category(self, category: str, content: str) -> List[ZKConfigDoc]:
        """Extract all configs from a category section."""
        configs = []

        # Find all ### `configName` sections
        matches = list(self.CONFIG_PATTERN.finditer(content))

        for i, match in enumerate(matches):
            config_name = match.group(1).strip()
            start = match.start()

            # End is either next config or end of content
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(content)

            config_content = content[start:end].strip()

            try:
                doc = self._parse_config_section(config_name, category, config_content)
                if doc:
                    configs.append(doc)
            except Exception as e:
                self.parse_errors.append(f"Error parsing {config_name}: {str(e)}")
                logger.error(f"Error parsing config {config_name}: {e}")

        return configs

    def _parse_config_section(self, config_name: str, category: str, content: str) -> Optional[ZKConfigDoc]:
        """Parse a single config section into a ZKConfigDoc."""

        # Extract type
        config_type = "unknown"
        type_match = self.TYPE_PATTERN.search(content)
        if type_match:
            config_type = type_match.group(1).strip()

        # Extract default value
        default_value = ""
        default_match = self.DEFAULT_PATTERN.search(content)
        if default_match:
            default_value = default_match.group(1).strip()

        # Extract implementation reference
        impl_ref = ""
        impl_match = self.IMPL_PATTERN.search(content)
        if impl_match:
            impl_ref = impl_match.group(1).strip()

        # Extract description (first paragraph after the header)
        description = self._extract_description(content)

        # Extract behavioral impact (What It Does section)
        behavioral_impact = self._extract_behavioral_impact(content)

        # Extract examples from tables
        examples = self._extract_examples(content)

        # Find related configs mentioned in this section
        related_configs = self._find_related_configs(content, config_name)

        return ZKConfigDoc(
            config_name=config_name,
            category=category,
            config_type=config_type,
            description=description,
            behavioral_impact=behavioral_impact,
            examples=examples,
            implementation_ref=impl_ref,
            default_value=default_value,
            related_configs=related_configs,
            raw_markdown=content
        )

    def _extract_description(self, content: str) -> str:
        """Extract the short description (first meaningful paragraph)."""
        # Look for "What It Does:" section first
        what_it_does_match = re.search(r'\*\*What It Does:\*\*\s*\n([^\n]+)', content, re.IGNORECASE)
        if what_it_does_match:
            return what_it_does_match.group(1).strip()

        # Otherwise, find first paragraph after type declaration
        lines = content.split('\n')
        _in_paragraph = False
        paragraph_lines = []

        for line in lines:
            line = line.strip()
            # Skip headers, type declarations, code blocks
            if line.startswith('#') or line.startswith('**Type') or line.startswith('```'):
                continue
            if line.startswith('|'):  # Skip tables
                continue
            if line and not line.startswith('-'):
                paragraph_lines.append(line)
                if len(paragraph_lines) >= 2:
                    break

        return ' '.join(paragraph_lines)[:500] if paragraph_lines else ""

    def _extract_behavioral_impact(self, content: str) -> str:
        """Extract detailed behavioral impact description."""
        impacts = []

        # Look for bullet points describing behavior
        bullet_pattern = re.compile(r'^[-•]\s*(.+)$', re.MULTILINE)
        bullets = bullet_pattern.findall(content)

        for bullet in bullets[:10]:  # Limit to 10 bullets
            # Clean up the bullet text
            text = bullet.strip()
            if text and len(text) > 10:  # Skip very short bullets
                impacts.append(text)

        # Also look for "What It Does" section content
        what_section = re.search(
            r'\*\*What It Does:\*\*\s*([\s\S]*?)(?=\*\*|###|$)',
            content,
            re.IGNORECASE
        )
        if what_section:
            section_text = what_section.group(1).strip()
            # Extract content from tables in this section
            if '|' in section_text:
                table_content = self._extract_table_text(section_text)
                if table_content:
                    impacts.extend(table_content)

        return ' | '.join(impacts[:15]) if impacts else ""

    def _extract_examples(self, content: str) -> List[Dict[str, str]]:
        """Extract examples from markdown tables."""
        examples = []

        # Find all tables (rows starting with |)
        table_rows = re.findall(r'^\|(.+)\|$', content, re.MULTILINE)

        current_headers = []
        for row in table_rows:
            cells = [c.strip() for c in row.split('|')]
            cells = [c for c in cells if c]  # Remove empty cells

            # Skip separator rows
            if all(c.replace('-', '').replace(':', '') == '' for c in cells):
                continue

            # First non-separator row is headers
            if not current_headers:
                current_headers = cells
                continue

            # Create example from row
            if len(cells) >= 2:
                example = {
                    'value': cells[0],
                    'effect': ' | '.join(cells[1:])
                }
                examples.append(example)

        return examples[:20]  # Limit examples

    def _extract_table_text(self, content: str) -> List[str]:
        """Extract meaningful text from table cells."""
        texts = []
        table_rows = re.findall(r'^\|(.+)\|$', content, re.MULTILINE)

        for row in table_rows:
            cells = [c.strip() for c in row.split('|')]
            for cell in cells:
                # Skip empty, separator, or header-like cells
                if cell and not cell.replace('-', '').replace(':', '') == '':
                    if len(cell) > 5 and not cell.startswith('`'):
                        texts.append(cell)

        return texts

    def _find_related_configs(self, content: str, current_config: str) -> List[str]:
        """Find other config names mentioned in this section."""
        related = []

        # Look for backtick-wrapped config names
        config_refs = re.findall(r'`([a-zA-Z][a-zA-Z0-9_\.]+)`', content)

        for ref in config_refs:
            # Skip the current config and common non-config patterns
            if ref == current_config:
                continue
            if ref.endswith('.ts') or ref.endswith('.js') or ref.endswith('.tsx'):
                continue
            if '/' in ref:  # File paths
                continue
            # Only include camelCase or with dots (config-like patterns)
            if re.match(r'^[a-z][a-zA-Z0-9]*(\.[a-zA-Z0-9]+)*$', ref):
                if ref not in related:
                    related.append(ref)

        return related[:10]  # Limit related configs

    def get_stats(self) -> Dict[str, Any]:
        """Get parsing statistics."""
        return {
            'total_configs': len(self.docs),
            'categories': len(self.categories),
            'category_breakdown': {
                cat: len(configs) for cat, configs in self.categories.items()
            },
            'parse_errors': len(self.parse_errors),
            'errors': self.parse_errors[:10]  # First 10 errors
        }

    def get_configs_by_category(self) -> Dict[str, List[ZKConfigDoc]]:
        """Group parsed configs by category."""
        by_category = {}
        for doc in self.docs:
            if doc.category not in by_category:
                by_category[doc.category] = []
            by_category[doc.category].append(doc)
        return by_category

    def find_config(self, config_name: str) -> Optional[ZKConfigDoc]:
        """Find a specific config by name."""
        for doc in self.docs:
            if doc.config_name.lower() == config_name.lower():
                return doc
        return None

    def search_configs(self, query: str) -> List[ZKConfigDoc]:
        """Simple text search across config docs."""
        query_lower = query.lower()
        results = []

        for doc in self.docs:
            score = 0
            # Check config name
            if query_lower in doc.config_name.lower():
                score += 10
            # Check category
            if query_lower in doc.category.lower():
                score += 5
            # Check description
            if query_lower in doc.description.lower():
                score += 3
            # Check behavioral impact
            if query_lower in doc.behavioral_impact.lower():
                score += 2

            if score > 0:
                results.append((score, doc))

        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in results]


def parse_zk_config_guide(content: str) -> Dict[str, Any]:
    """
    Convenience function to parse ZK config guide.

    Args:
        content: Full markdown content

    Returns:
        Dictionary with parsed docs and stats
    """
    parser = ZKConfigBehaviorParser()
    docs = parser.parse_markdown(content)

    return {
        'success': True,
        'docs': [doc.to_dict() for doc in docs],
        'stats': parser.get_stats(),
        'categories': parser.get_configs_by_category()
    }
