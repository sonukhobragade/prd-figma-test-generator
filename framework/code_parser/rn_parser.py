"""
React Native Code Parser

Parses React Native TypeScript/JavaScript codebase to extract:
- Component names and locations
- Props interfaces and types
- API endpoints and methods
- Validation rules (yup, zod, custom)
- Navigation routes and screens
- State management patterns
- Business logic and constants

Usage:
    parser = ReactNativeParser("/path/to/rn/project")
    result = parser.parse_all()
    print(result.to_markdown())
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ComponentInfo:
    """Information about a React Native component."""
    name: str
    file_path: str
    component_type: str  # 'functional', 'class', 'screen', 'modal'
    props: List[Dict[str, str]] = field(default_factory=list)
    states: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    navigation_targets: List[str] = field(default_factory=list)


@dataclass
class APIEndpoint:
    """Information about an API endpoint."""
    url: str
    method: str  # GET, POST, PUT, DELETE
    file_path: str
    function_name: Optional[str] = None
    request_type: Optional[str] = None
    response_type: Optional[str] = None


@dataclass
class ValidationRule:
    """Information about a validation rule."""
    field_name: str
    rules: List[str]
    file_path: str
    schema_name: Optional[str] = None


@dataclass
class NavigationRoute:
    """Information about a navigation route."""
    route_name: str
    screen_component: str
    file_path: str
    params: List[str] = field(default_factory=list)


@dataclass
class BusinessConstant:
    """Business constants and configuration values."""
    name: str
    value: Any
    file_path: str
    category: str  # 'limit', 'price', 'duration', 'config'


@dataclass
class ParseResult:
    """Complete parse result from React Native codebase."""
    components: List[ComponentInfo] = field(default_factory=list)
    screens: List[ComponentInfo] = field(default_factory=list)
    api_endpoints: List[APIEndpoint] = field(default_factory=list)
    validation_rules: List[ValidationRule] = field(default_factory=list)
    navigation_routes: List[NavigationRoute] = field(default_factory=list)
    business_constants: List[BusinessConstant] = field(default_factory=list)
    user_types: List[str] = field(default_factory=list)
    error_codes: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "components": [vars(c) for c in self.components],
            "screens": [vars(s) for s in self.screens],
            "api_endpoints": [vars(e) for e in self.api_endpoints],
            "validation_rules": [vars(v) for v in self.validation_rules],
            "navigation_routes": [vars(n) for n in self.navigation_routes],
            "business_constants": [vars(b) for b in self.business_constants],
            "user_types": self.user_types,
            "error_codes": self.error_codes,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    def to_markdown(self) -> str:
        """Convert to markdown for knowledge base."""
        md = []
        
        # Screens
        if self.screens:
            md.append("## Screens\n")
            for screen in self.screens:
                md.append(f"### {screen.name}")
                md.append(f"- **File**: `{screen.file_path}`")
                md.append(f"- **Type**: {screen.component_type}")
                if screen.props:
                    md.append(f"- **Props**: {', '.join([p.get('name', '') for p in screen.props])}")
                if screen.navigation_targets:
                    md.append(f"- **Navigates to**: {', '.join(screen.navigation_targets)}")
                md.append("")
        
        # API Endpoints
        if self.api_endpoints:
            md.append("## API Endpoints\n")
            md.append("| Method | Endpoint | Function | File |")
            md.append("|--------|----------|----------|------|")
            for api in self.api_endpoints:
                md.append(f"| {api.method} | `{api.url}` | {api.function_name or '-'} | `{api.file_path}` |")
            md.append("")
        
        # Validation Rules
        if self.validation_rules:
            md.append("## Validation Rules\n")
            for rule in self.validation_rules:
                md.append(f"### {rule.field_name}")
                md.append(f"- **Schema**: {rule.schema_name or 'inline'}")
                md.append(f"- **Rules**: {', '.join(rule.rules)}")
                md.append(f"- **File**: `{rule.file_path}`")
                md.append("")
        
        # Business Constants
        if self.business_constants:
            md.append("## Business Constants\n")
            md.append("| Name | Value | Category | File |")
            md.append("|------|-------|----------|------|")
            for const in self.business_constants:
                md.append(f"| `{const.name}` | {const.value} | {const.category} | `{const.file_path}` |")
            md.append("")
        
        # Navigation Routes
        if self.navigation_routes:
            md.append("## Navigation Routes\n")
            md.append("| Route | Screen | Params |")
            md.append("|-------|--------|--------|")
            for route in self.navigation_routes:
                params = ', '.join(route.params) if route.params else '-'
                md.append(f"| `{route.route_name}` | {route.screen_component} | {params} |")
            md.append("")
        
        # User Types
        if self.user_types:
            md.append("## User Types\n")
            for user_type in self.user_types:
                md.append(f"- {user_type}")
            md.append("")
        
        # Error Codes
        if self.error_codes:
            md.append("## Error Codes\n")
            md.append("| Code | Message |")
            md.append("|------|---------|")
            for code, message in self.error_codes.items():
                md.append(f"| `{code}` | {message} |")
            md.append("")
        
        return "\n".join(md)


class ReactNativeParser:
    """Parser for React Native TypeScript/JavaScript projects."""
    
    # File extensions to parse
    EXTENSIONS = {'.ts', '.tsx', '.js', '.jsx'}
    
    # Directories to skip
    SKIP_DIRS = {
        'node_modules', '.git', 'build', 'dist', 'coverage',
        '__tests__', '__mocks__', '.expo', 'android/build',
        'ios/build', 'ios/Pods', '.gradle'
    }
    
    def __init__(self, project_path: str):
        """Initialize parser with project path.
        
        Args:
            project_path: Path to React Native project root
        """
        self.project_path = Path(project_path)
        if not self.project_path.exists():
            raise ValueError(f"Project path does not exist: {project_path}")
        
        self.result = ParseResult()
        self._parsed_files: Set[str] = set()
        
        logger.info(f"Initialized React Native parser for: {project_path}")
    
    def parse_all(self) -> ParseResult:
        """Parse entire project and return results.
        
        Returns:
            ParseResult with all extracted information
        """
        logger.info("Starting full project parse...")
        
        # Find all relevant files
        files = self._find_files()
        logger.info(f"Found {len(files)} files to parse")
        
        # Parse each file
        for file_path in files:
            try:
                self._parse_file(file_path)
            except Exception as e:
                logger.warning(f"Error parsing {file_path}: {e}")
        
        # Post-process: identify screens vs components
        self._categorize_components()
        
        # Deduplicate
        self._deduplicate_results()
        
        logger.info(f"Parse complete: {len(self.result.components)} components, "
                   f"{len(self.result.screens)} screens, "
                   f"{len(self.result.api_endpoints)} API endpoints, "
                   f"{len(self.result.validation_rules)} validation rules")
        
        return self.result
    
    def parse_directory(self, dir_name: str) -> ParseResult:
        """Parse only a specific directory.
        
        Args:
            dir_name: Directory name relative to project root (e.g., 'src/screens')
            
        Returns:
            ParseResult with extracted information
        """
        target_dir = self.project_path / dir_name
        if not target_dir.exists():
            raise ValueError(f"Directory does not exist: {target_dir}")
        
        files = self._find_files(target_dir)
        for file_path in files:
            try:
                self._parse_file(file_path)
            except Exception as e:
                logger.warning(f"Error parsing {file_path}: {e}")
        
        self._categorize_components()
        self._deduplicate_results()
        
        return self.result
    
    def _find_files(self, base_path: Optional[Path] = None) -> List[Path]:
        """Find all parseable files in project."""
        base = base_path or self.project_path
        files = []
        
        for root, dirs, filenames in os.walk(base):
            # Skip unwanted directories
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            
            for filename in filenames:
                if Path(filename).suffix in self.EXTENSIONS:
                    files.append(Path(root) / filename)
        
        return files
    
    def _parse_file(self, file_path: Path) -> None:
        """Parse a single file and extract information."""
        if str(file_path) in self._parsed_files:
            return
        
        self._parsed_files.add(str(file_path))
        
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.warning(f"Could not read file {file_path}: {e}")
            return
        
        relative_path = str(file_path.relative_to(self.project_path))
        
        # Extract different information
        self._extract_components(content, relative_path)
        self._extract_api_endpoints(content, relative_path)
        self._extract_validation_rules(content, relative_path)
        self._extract_navigation_routes(content, relative_path)
        self._extract_business_constants(content, relative_path)
        self._extract_user_types(content, relative_path)
        self._extract_error_codes(content, relative_path)
    
    def _extract_components(self, content: str, file_path: str) -> None:
        """Extract React components from file."""
        
        # Pattern for functional components with arrow function
        # const ComponentName = (props) => { ... }
        # const ComponentName: React.FC<Props> = (props) => { ... }
        arrow_pattern = r'(?:export\s+)?(?:const|let)\s+([A-Z][a-zA-Z0-9]*)\s*(?::\s*React\.(?:FC|FunctionComponent)(?:<[^>]+>)?)?\s*=\s*\([^)]*\)\s*(?::\s*[^=]+)?\s*=>'
        
        # Pattern for function components
        # function ComponentName(props) { ... }
        # export function ComponentName(props) { ... }
        function_pattern = r'(?:export\s+)?function\s+([A-Z][a-zA-Z0-9]*)\s*\([^)]*\)'
        
        # Pattern for class components
        # class ComponentName extends React.Component { ... }
        class_pattern = r'class\s+([A-Z][a-zA-Z0-9]*)\s+extends\s+(?:React\.)?(?:Component|PureComponent)'
        
        # Extract props interface
        r'interface\s+([A-Z][a-zA-Z0-9]*Props)\s*\{([^}]+)\}'
        r'type\s+([A-Z][a-zA-Z0-9]*Props)\s*=\s*\{([^}]+)\}'
        
        # Find all components
        for match in re.finditer(arrow_pattern, content):
            name = match.group(1)
            props = self._extract_props_for_component(content, name)
            hooks = self._extract_hooks(content)
            nav_targets = self._extract_navigation_targets(content)
            
            component = ComponentInfo(
                name=name,
                file_path=file_path,
                component_type='functional',
                props=props,
                hooks=hooks,
                navigation_targets=nav_targets
            )
            self.result.components.append(component)
        
        for match in re.finditer(function_pattern, content):
            name = match.group(1)
            if not any(c.name == name for c in self.result.components):
                props = self._extract_props_for_component(content, name)
                hooks = self._extract_hooks(content)
                nav_targets = self._extract_navigation_targets(content)
                
                component = ComponentInfo(
                    name=name,
                    file_path=file_path,
                    component_type='functional',
                    props=props,
                    hooks=hooks,
                    navigation_targets=nav_targets
                )
                self.result.components.append(component)
        
        for match in re.finditer(class_pattern, content):
            name = match.group(1)
            component = ComponentInfo(
                name=name,
                file_path=file_path,
                component_type='class',
                props=self._extract_props_for_component(content, name)
            )
            self.result.components.append(component)
    
    def _extract_props_for_component(self, content: str, component_name: str) -> List[Dict[str, str]]:
        """Extract props interface for a component."""
        props = []
        
        # Look for interface ComponentNameProps { ... }
        pattern = rf'(?:interface|type)\s+{component_name}Props\s*[=]?\s*\{{([^}}]+)\}}'
        match = re.search(pattern, content)
        
        if match:
            props_content = match.group(1)
            # Parse individual props
            prop_pattern = r'(\w+)(\?)?:\s*([^;,\n]+)'
            for prop_match in re.finditer(prop_pattern, props_content):
                props.append({
                    'name': prop_match.group(1),
                    'optional': prop_match.group(2) == '?',
                    'type': prop_match.group(3).strip()
                })
        
        return props
    
    def _extract_hooks(self, content: str) -> List[str]:
        """Extract React hooks used in component."""
        hooks = []
        hook_pattern = r'use[A-Z][a-zA-Z]*'
        
        for match in re.finditer(hook_pattern, content):
            hook = match.group(0)
            if hook not in hooks:
                hooks.append(hook)
        
        return hooks
    
    def _extract_navigation_targets(self, content: str) -> List[str]:
        """Extract navigation targets from component."""
        targets = []
        
        # navigation.navigate('ScreenName') or navigation.navigate("ScreenName")
        pattern = r'navigation\.(?:navigate|push|replace)\s*\(\s*[\'"]([^"\']+)[\'"]'
        
        for match in re.finditer(pattern, content):
            target = match.group(1)
            if target not in targets:
                targets.append(target)
        
        return targets
    
    def _extract_api_endpoints(self, content: str, file_path: str) -> None:
        """Extract API endpoints from file."""
        
        # Patterns for API calls
        patterns = [
            # axios.get('/endpoint')
            r'axios\.(\w+)\s*\(\s*[`\'"]([^`\'"]+)[`\'"]',
            # fetch('/endpoint')
            r'fetch\s*\(\s*[`\'"]([^`\'"]+)[`\'"](?:.*?method:\s*[\'"](\w+)[\'"])?',
            # api.get('/endpoint')
            r'api\.(\w+)\s*\(\s*[`\'"]([^`\'"]+)[`\'"]',
            # apiClient.get('/endpoint')
            r'apiClient\.(\w+)\s*\(\s*[`\'"]([^`\'"]+)[`\'"]',
            # BASE_URL + '/endpoint'
            r'(?:BASE_URL|baseURL|API_URL)\s*\+\s*[`\'"]([^`\'"]+)[`\'"]',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, content):
                groups = match.groups()
                
                if len(groups) == 2:
                    method = groups[0].upper() if groups[0] else 'GET'
                    url = groups[1]
                else:
                    method = 'GET'
                    url = groups[0]
                
                # Skip if already found
                if any(e.url == url for e in self.result.api_endpoints):
                    continue
                
                # Try to find function name
                func_pattern = r'(?:async\s+)?(?:function\s+)?(\w+)\s*(?:=\s*async)?\s*\([^)]*\)[^{]*\{[^}]*' + re.escape(match.group(0))
                func_match = re.search(func_pattern, content)
                func_name = func_match.group(1) if func_match else None
                
                endpoint = APIEndpoint(
                    url=url,
                    method=method,
                    file_path=file_path,
                    function_name=func_name
                )
                self.result.api_endpoints.append(endpoint)
    
    def _extract_validation_rules(self, content: str, file_path: str) -> None:
        """Extract validation rules (yup, zod, custom)."""
        
        # Yup validation patterns
        yup_schema_pattern = r'(\w+Schema)\s*=\s*yup\.object\(\)\s*\.shape\(\{([^}]+)\}\)'
        yup_field_pattern = r'(\w+):\s*yup\.(\w+)\(\)([^,}]+)?'
        
        # Zod validation patterns
        zod_schema_pattern = r'(\w+Schema)\s*=\s*z\.object\(\{([^}]+)\}\)'
        zod_field_pattern = r'(\w+):\s*z\.(\w+)\(\)([^,}]+)?'
        
        # Extract Yup schemas
        for schema_match in re.finditer(yup_schema_pattern, content, re.DOTALL):
            schema_name = schema_match.group(1)
            fields_content = schema_match.group(2)
            
            for field_match in re.finditer(yup_field_pattern, fields_content):
                field_name = field_match.group(1)
                field_type = field_match.group(2)
                modifiers = field_match.group(3) or ''
                
                rules = [field_type]
                if '.required()' in modifiers:
                    rules.append('required')
                if '.min(' in modifiers:
                    min_match = re.search(r'\.min\((\d+)\)', modifiers)
                    if min_match:
                        rules.append(f'min:{min_match.group(1)}')
                if '.max(' in modifiers:
                    max_match = re.search(r'\.max\((\d+)\)', modifiers)
                    if max_match:
                        rules.append(f'max:{max_match.group(1)}')
                if '.email()' in modifiers:
                    rules.append('email')
                if '.phone()' in modifiers or '.matches(' in modifiers:
                    rules.append('pattern')
                
                validation = ValidationRule(
                    field_name=field_name,
                    rules=rules,
                    file_path=file_path,
                    schema_name=schema_name
                )
                self.result.validation_rules.append(validation)
        
        # Extract Zod schemas
        for schema_match in re.finditer(zod_schema_pattern, content, re.DOTALL):
            schema_name = schema_match.group(1)
            fields_content = schema_match.group(2)
            
            for field_match in re.finditer(zod_field_pattern, fields_content):
                field_name = field_match.group(1)
                field_type = field_match.group(2)
                modifiers = field_match.group(3) or ''
                
                rules = [field_type]
                if '.min(' in modifiers:
                    min_match = re.search(r'\.min\((\d+)\)', modifiers)
                    if min_match:
                        rules.append(f'min:{min_match.group(1)}')
                if '.max(' in modifiers:
                    max_match = re.search(r'\.max\((\d+)\)', modifiers)
                    if max_match:
                        rules.append(f'max:{max_match.group(1)}')
                if '.email()' in modifiers:
                    rules.append('email')
                if '.optional()' not in modifiers:
                    rules.append('required')
                
                validation = ValidationRule(
                    field_name=field_name,
                    rules=rules,
                    file_path=file_path,
                    schema_name=schema_name
                )
                self.result.validation_rules.append(validation)
    
    def _extract_navigation_routes(self, content: str, file_path: str) -> None:
        """Extract navigation route definitions."""
        
        # Stack.Screen patterns
        screen_pattern = r'<Stack\.Screen\s+name=[\'"]([^"\']+)[\'"]\s+component=\{([^}]+)\}'
        
        # createStackNavigator / createNativeStackNavigator
        r'(\w+):\s*\{\s*screen:\s*(\w+)'
        
        # React Navigation v6+ pattern
        nav6_pattern = r'<(?:Stack|Tab|Drawer)\.Screen[^>]*name=[\'"]([^"\']+)[\'"][^>]*component=\{(\w+)\}'
        
        for match in re.finditer(screen_pattern, content):
            route = NavigationRoute(
                route_name=match.group(1),
                screen_component=match.group(2),
                file_path=file_path
            )
            self.result.navigation_routes.append(route)
        
        for match in re.finditer(nav6_pattern, content):
            route_name = match.group(1)
            if not any(r.route_name == route_name for r in self.result.navigation_routes):
                route = NavigationRoute(
                    route_name=route_name,
                    screen_component=match.group(2),
                    file_path=file_path
                )
                self.result.navigation_routes.append(route)
    
    def _extract_business_constants(self, content: str, file_path: str) -> None:
        """Extract business constants and configuration values."""
        
        # Patterns for constants
        const_patterns = [
            # MIN/MAX values: const MIN_AMOUNT = 10
            (r'(?:export\s+)?const\s+((?:MIN|MAX|LIMIT)_\w+)\s*[=:]\s*(\d+)', 'limit'),
            # Price/Amount: const SUBSCRIPTION_PRICE = 999
            (r'(?:export\s+)?const\s+(\w*(?:PRICE|AMOUNT|COST|FEE)\w*)\s*[=:]\s*(\d+)', 'price'),
            # Duration: const SESSION_TIMEOUT = 30
            (r'(?:export\s+)?const\s+(\w*(?:TIMEOUT|DURATION|INTERVAL|DELAY)\w*)\s*[=:]\s*(\d+)', 'duration'),
            # Config booleans: const ENABLE_FEATURE = true
            (r'(?:export\s+)?const\s+(ENABLE_\w+|IS_\w+|ALLOW_\w+)\s*[=:]\s*(true|false)', 'config'),
        ]
        
        for pattern, category in const_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                name = match.group(1)
                value = match.group(2)
                
                # Skip if already found
                if any(c.name == name for c in self.result.business_constants):
                    continue
                
                constant = BusinessConstant(
                    name=name,
                    value=value,
                    file_path=file_path,
                    category=category
                )
                self.result.business_constants.append(constant)
    
    def _extract_user_types(self, content: str, file_path: str) -> None:
        """Extract user type definitions."""
        
        # Enum patterns
        enum_pattern = r'enum\s+(?:UserType|UserRole|SubscriptionType|MembershipType)\s*\{([^}]+)\}'
        
        # Type union patterns
        type_pattern = r'type\s+(?:UserType|UserRole|SubscriptionType)\s*=\s*([^;]+);'
        
        for match in re.finditer(enum_pattern, content):
            enum_content = match.group(1)
            for value in re.findall(r'(\w+)\s*(?:=|,|})', enum_content):
                if value not in self.result.user_types:
                    self.result.user_types.append(value)
        
        for match in re.finditer(type_pattern, content):
            type_content = match.group(1)
            for value in re.findall(r'[\'"](\w+)[\'"]', type_content):
                if value not in self.result.user_types:
                    self.result.user_types.append(value)
    
    def _extract_error_codes(self, content: str, file_path: str) -> None:
        """Extract error codes and messages."""
        
        # Error code patterns
        patterns = [
            # ERROR_CODES = { INVALID_INPUT: 'Invalid input provided' }
            r'(\w+_ERROR|\w+_CODE)\s*:\s*[\'"]([^"\']+)[\'"]',
            # errorMessages = { E001: 'Error message' }
            r'[\'"]?(E\d+|ERR_\w+)[\'"]?\s*:\s*[\'"]([^"\']+)[\'"]',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, content):
                code = match.group(1)
                message = match.group(2)
                if code not in self.result.error_codes:
                    self.result.error_codes[code] = message
    
    def _categorize_components(self) -> None:
        """Categorize components into screens, modals, etc."""
        screen_indicators = ['Screen', 'Page', 'View', 'Container']
        modal_indicators = ['Modal', 'Dialog', 'Popup', 'Sheet', 'Drawer']
        
        screens_to_move = []
        
        for component in self.result.components:
            # Check if it's a screen
            is_screen = (
                any(ind in component.name for ind in screen_indicators) or
                'screens/' in component.file_path.lower() or
                '/screen/' in component.file_path.lower()
            )
            
            # Check if it's a modal
            is_modal = any(ind in component.name for ind in modal_indicators)
            
            if is_screen:
                component.component_type = 'screen'
                screens_to_move.append(component)
            elif is_modal:
                component.component_type = 'modal'
        
        # Move screens to separate list
        for screen in screens_to_move:
            self.result.components.remove(screen)
            self.result.screens.append(screen)
    
    def _deduplicate_results(self) -> None:
        """Remove duplicate entries."""
        # Deduplicate components by name
        seen_components = set()
        unique_components = []
        for comp in self.result.components:
            if comp.name not in seen_components:
                seen_components.add(comp.name)
                unique_components.append(comp)
        self.result.components = unique_components
        
        # Deduplicate screens by name
        seen_screens = set()
        unique_screens = []
        for screen in self.result.screens:
            if screen.name not in seen_screens:
                seen_screens.add(screen.name)
                unique_screens.append(screen)
        self.result.screens = unique_screens
        
        # Deduplicate API endpoints by URL+method
        seen_apis = set()
        unique_apis = []
        for api in self.result.api_endpoints:
            key = f"{api.method}:{api.url}"
            if key not in seen_apis:
                seen_apis.add(key)
                unique_apis.append(api)
        self.result.api_endpoints = unique_apis
