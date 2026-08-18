"""
Knowledge Generator

Converts parsed React Native code into knowledge base content
that can be used by the LLM analyzer for better test case generation.

Usage:
    from framework.code_parser import ReactNativeParser, CodeKnowledgeGenerator
    
    parser = ReactNativeParser("/path/to/rn/project")
    result = parser.parse_all()
    
    generator = CodeKnowledgeGenerator(result)
    generator.save_to_knowledge_base("/path/to/knowledge_base")
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from .rn_parser import ParseResult

logger = logging.getLogger(__name__)


class CodeKnowledgeGenerator:
    """Generates knowledge base content from parsed code."""
    
    def __init__(self, parse_result: ParseResult):
        """Initialize with parse result.
        
        Args:
            parse_result: Result from ReactNativeParser
        """
        self.result = parse_result
    
    def generate_app_structure_md(self) -> str:
        """Generate app structure knowledge base file."""
        lines = [
            "# App Structure",
            "",
            f"> **Auto-generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "> **Purpose**: Provides app structure context for test case generation",
            "",
            "---",
            "",
        ]
        
        # Screens section
        if self.result.screens:
            lines.append("## Screens\n")
            lines.append("| Screen Name | File | Navigates To |")
            lines.append("|-------------|------|--------------|")
            for screen in sorted(self.result.screens, key=lambda x: x.name):
                nav_targets = ', '.join(screen.navigation_targets) if screen.navigation_targets else '-'
                lines.append(f"| `{screen.name}` | `{screen.file_path}` | {nav_targets} |")
            lines.append("")
            
            # Screen details
            lines.append("### Screen Details\n")
            for screen in self.result.screens:
                lines.append(f"#### {screen.name}")
                lines.append(f"- **File**: `{screen.file_path}`")
                if screen.props:
                    props_str = ', '.join([f"`{p['name']}: {p['type']}`" for p in screen.props])
                    lines.append(f"- **Props**: {props_str}")
                if screen.hooks:
                    lines.append(f"- **Hooks**: {', '.join(screen.hooks)}")
                if screen.navigation_targets:
                    lines.append(f"- **Can navigate to**: {', '.join(screen.navigation_targets)}")
                lines.append("")
        
        # Components section
        if self.result.components:
            lines.append("## Reusable Components\n")
            lines.append("| Component | Type | File |")
            lines.append("|-----------|------|------|")
            for comp in sorted(self.result.components, key=lambda x: x.name)[:50]:  # Limit to 50
                lines.append(f"| `{comp.name}` | {comp.component_type} | `{comp.file_path}` |")
            lines.append("")
        
        # Navigation routes
        if self.result.navigation_routes:
            lines.append("## Navigation Routes\n")
            lines.append("| Route Name | Screen Component | Params |")
            lines.append("|------------|------------------|--------|")
            for route in self.result.navigation_routes:
                params = ', '.join(route.params) if route.params else '-'
                lines.append(f"| `{route.route_name}` | `{route.screen_component}` | {params} |")
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_api_endpoints_md(self) -> str:
        """Generate API endpoints knowledge base file."""
        lines = [
            "# API Endpoints",
            "",
            f"> **Auto-generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "> **Purpose**: API endpoint reference for test case generation",
            "",
            "---",
            "",
        ]
        
        if not self.result.api_endpoints:
            lines.append("*No API endpoints found in codebase.*")
            return "\n".join(lines)
        
        # Group by method
        endpoints_by_method = {}
        for endpoint in self.result.api_endpoints:
            method = endpoint.method.upper()
            if method not in endpoints_by_method:
                endpoints_by_method[method] = []
            endpoints_by_method[method].append(endpoint)
        
        for method in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']:
            if method in endpoints_by_method:
                lines.append(f"## {method} Endpoints\n")
                lines.append("| Endpoint | Function | File |")
                lines.append("|----------|----------|------|")
                for ep in endpoints_by_method[method]:
                    func = ep.function_name or '-'
                    lines.append(f"| `{ep.url}` | `{func}` | `{ep.file_path}` |")
                lines.append("")
        
        # Test scenarios for APIs
        lines.append("## Suggested API Test Scenarios\n")
        lines.append("For each endpoint, consider testing:")
        lines.append("- ✅ Success response (200/201)")
        lines.append("- ❌ Error responses (400, 401, 403, 404, 500)")
        lines.append("- ⏱️ Timeout handling")
        lines.append("- 🔄 Retry logic")
        lines.append("- 📶 Network failure")
        lines.append("- 🔒 Authentication required")
        lines.append("")
        
        return "\n".join(lines)
    
    def generate_validation_rules_md(self) -> str:
        """Generate validation rules knowledge base file."""
        lines = [
            "# Validation Rules",
            "",
            f"> **Auto-generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "> **Purpose**: Input validation rules for boundary/negative testing",
            "",
            "---",
            "",
        ]
        
        if not self.result.validation_rules:
            lines.append("*No validation schemas found in codebase.*")
            lines.append("")
            lines.append("**Note**: If your app uses inline validation, add them manually to this file.")
            return "\n".join(lines)
        
        # Group by schema
        rules_by_schema = {}
        for rule in self.result.validation_rules:
            schema = rule.schema_name or 'Inline'
            if schema not in rules_by_schema:
                rules_by_schema[schema] = []
            rules_by_schema[schema].append(rule)
        
        for schema, rules in rules_by_schema.items():
            lines.append(f"## {schema}\n")
            lines.append("| Field | Rules | Test Scenarios |")
            lines.append("|-------|-------|----------------|")
            for rule in rules:
                rules_str = ', '.join(rule.rules)
                # Generate test scenarios based on rules
                scenarios = []
                if 'required' in rule.rules:
                    scenarios.append("Empty value")
                if any('min:' in r for r in rule.rules):
                    scenarios.append("Below min")
                if any('max:' in r for r in rule.rules):
                    scenarios.append("Above max")
                if 'email' in rule.rules:
                    scenarios.append("Invalid email format")
                if 'pattern' in rule.rules:
                    scenarios.append("Invalid pattern")
                scenarios_str = ', '.join(scenarios) if scenarios else '-'
                lines.append(f"| `{rule.field_name}` | {rules_str} | {scenarios_str} |")
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_business_rules_md(self) -> str:
        """Generate business rules knowledge base file."""
        lines = [
            "# Business Rules & Constants",
            "",
            f"> **Auto-generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "> **Purpose**: Business constants for boundary testing",
            "",
            "---",
            "",
        ]
        
        if not self.result.business_constants:
            lines.append("*No business constants found. Add them manually below.*")
            lines.append("")
            lines.append("## Example Format")
            lines.append("```")
            lines.append("MIN_RECHARGE_AMOUNT = 10")
            lines.append("MAX_RECHARGE_AMOUNT = 50000")
            lines.append("FREE_CHAT_LIMIT = 2")
            lines.append("SESSION_TIMEOUT_MINUTES = 30")
            lines.append("```")
            return "\n".join(lines)
        
        # Group by category
        consts_by_category = {}
        for const in self.result.business_constants:
            cat = const.category
            if cat not in consts_by_category:
                consts_by_category[cat] = []
            consts_by_category[cat].append(const)
        
        category_titles = {
            'limit': '## Limits & Boundaries',
            'price': '## Prices & Amounts',
            'duration': '## Timeouts & Durations',
            'config': '## Feature Flags & Config'
        }
        
        for category, consts in consts_by_category.items():
            lines.append(f"{category_titles.get(category, f'## {category.title()}')}\n")
            lines.append("| Constant | Value | Test Scenarios |")
            lines.append("|----------|-------|----------------|")
            for const in consts:
                # Generate test scenarios
                scenarios = []
                if 'MIN' in const.name:
                    scenarios.extend([f"Value = {const.value}", f"Value = {int(const.value) - 1} (below min)"])
                elif 'MAX' in const.name:
                    scenarios.extend([f"Value = {const.value}", f"Value = {int(const.value) + 1} (above max)"])
                elif 'LIMIT' in const.name:
                    scenarios.extend([f"At limit ({const.value})", f"Exceed limit ({int(const.value) + 1})"])
                elif 'TIMEOUT' in const.name or 'DURATION' in const.name:
                    scenarios.append(f"Wait {const.value} seconds")
                scenarios_str = ', '.join(scenarios) if scenarios else '-'
                lines.append(f"| `{const.name}` | `{const.value}` | {scenarios_str} |")
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_user_states_md(self) -> str:
        """Generate user states knowledge base file."""
        lines = [
            "# User States & Types",
            "",
            f"> **Auto-generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "> **Purpose**: User state matrix for test case generation",
            "",
            "---",
            "",
        ]
        
        if self.result.user_types:
            lines.append("## Detected User Types\n")
            for user_type in self.result.user_types:
                lines.append(f"- `{user_type}`")
            lines.append("")
        
        # Add common user states template
        lines.append("## User State Matrix\n")
        lines.append("Test each feature with these user states:")
        lines.append("")
        lines.append("| User State | Description | Key Test Scenarios |")
        lines.append("|------------|-------------|-------------------|")
        lines.append("| **New User** | Just installed, never logged in | Onboarding flow, first-time experience |")
        lines.append("| **Guest User** | Using without account | Limited features, upgrade prompts |")
        lines.append("| **Registered User** | Has account, no subscription | Free features, paywall triggers |")
        lines.append("| **Subscribed User** | Active subscription | Premium features work, no paywalls |")
        lines.append("| **Expired Subscription** | Was subscribed, now expired | Renewal prompts, feature lockout |")
        lines.append("| **Half-Onboarded** | Incomplete profile | Profile completion prompts |")
        lines.append("| **Zero Balance** | Subscribed but wallet empty | No coin deduction for premium features |")
        lines.append("")
        
        # Error codes
        if self.result.error_codes:
            lines.append("## Error Codes\n")
            lines.append("| Code | Message | Test Scenario |")
            lines.append("|------|---------|---------------|")
            for code, message in self.result.error_codes.items():
                lines.append(f"| `{code}` | {message} | Trigger this error and verify handling |")
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_test_context_json(self) -> str:
        """Generate JSON context for direct LLM injection."""
        context = {
            "app_info": {
                "total_screens": len(self.result.screens),
                "total_components": len(self.result.components),
                "total_api_endpoints": len(self.result.api_endpoints),
            },
            "screens": [
                {
                    "name": s.name,
                    "navigates_to": s.navigation_targets
                }
                for s in self.result.screens
            ],
            "api_endpoints": [
                {
                    "method": e.method,
                    "url": e.url,
                    "function": e.function_name
                }
                for e in self.result.api_endpoints
            ],
            "validation_rules": [
                {
                    "field": v.field_name,
                    "rules": v.rules
                }
                for v in self.result.validation_rules
            ],
            "business_constants": [
                {
                    "name": c.name,
                    "value": c.value,
                    "category": c.category
                }
                for c in self.result.business_constants
            ],
            "user_types": self.result.user_types,
            "error_codes": self.result.error_codes
        }
        
        return json.dumps(context, indent=2)
    
    def save_to_knowledge_base(self, kb_dir: str) -> None:
        """Save all generated knowledge base files.
        
        Args:
            kb_dir: Path to knowledge base directory
        """
        kb_path = Path(kb_dir)
        kb_path.mkdir(parents=True, exist_ok=True)
        
        files_to_generate = [
            ("app_structure.md", self.generate_app_structure_md()),
            ("api_endpoints.md", self.generate_api_endpoints_md()),
            ("validation_rules.md", self.generate_validation_rules_md()),
            ("business_rules.md", self.generate_business_rules_md()),
            ("user_states.md", self.generate_user_states_md()),
            ("code_context.json", self.generate_test_context_json()),
        ]
        
        for filename, content in files_to_generate:
            file_path = kb_path / filename
            file_path.write_text(content, encoding='utf-8')
            logger.info(f"Generated: {file_path}")
        
        # Update README
        readme_content = self._generate_readme()
        (kb_path / "README.md").write_text(readme_content, encoding='utf-8')
        
        logger.info(f"Knowledge base updated at: {kb_path}")
    
    def _generate_readme(self) -> str:
        """Generate README for knowledge base."""
        return f"""# Knowledge Base

> **Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This directory contains knowledge base files used by the test case generator.

## Auto-Generated Files

These files are generated from parsing the React Native codebase:

| File | Description |
|------|-------------|
| `app_structure.md` | Screens, components, navigation routes |
| `api_endpoints.md` | API endpoints extracted from code |
| `validation_rules.md` | Yup/Zod validation schemas |
| `business_rules.md` | Business constants (limits, prices) |
| `user_states.md` | User types and state matrix |
| `code_context.json` | JSON context for LLM injection |

## Manual Files

These files should be maintained manually:

| File | Description |
|------|-------------|
| `bug_patterns.md` | Real bugs found in testing |
| `domain_knowledge.md` | App-specific domain knowledge |
| `test_case_examples.md` | Good test case examples |
| `user_journeys.md` | User flow descriptions |
| `test_coverage_rules.md` | Coverage requirements |

## Regenerating Auto-Generated Files

```python
from framework.code_parser import ReactNativeParser, CodeKnowledgeGenerator

# Parse codebase
parser = ReactNativeParser("/path/to/your/rn/project")
result = parser.parse_all()

# Generate knowledge base
generator = CodeKnowledgeGenerator(result)
generator.save_to_knowledge_base("./docs/knowledge_base")
```

## Stats

- **Screens**: {len(self.result.screens)}
- **Components**: {len(self.result.components)}
- **API Endpoints**: {len(self.result.api_endpoints)}
- **Validation Rules**: {len(self.result.validation_rules)}
- **Business Constants**: {len(self.result.business_constants)}
- **User Types**: {len(self.result.user_types)}
- **Error Codes**: {len(self.result.error_codes)}
"""
