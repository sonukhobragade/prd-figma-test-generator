#!/usr/bin/env python3
"""
Simple CLI to parse your React Native codebase.

Usage:
    python parse_codebase.py /path/to/your/react-native-project

Example:
    python parse_codebase.py /path/to/your/mobile-app
    
This will:
1. Scan your entire React Native project
2. Extract screens, components, APIs, validation rules
3. Generate knowledge base files in docs/knowledge_base/
4. Print a summary of what was found
"""

import sys
import os
from pathlib import Path

# Add framework to path
sys.path.insert(0, str(Path(__file__).parent))

from framework.code_parser import ReactNativeParser, CodeKnowledgeGenerator


def main():
    print("=" * 60)
    print("🔍 React Native Code Parser")
    print("=" * 60)
    
    # Get project path from command line or ask user
    if len(sys.argv) > 1:
        project_path = sys.argv[1]
    else:
        print("\n📁 Enter the path to your React Native project:")
        print("   Example: /path/to/your/mobile-app")
        print()
        project_path = input("Path: ").strip()
    
    # Validate path
    if not project_path:
        print("❌ Error: No path provided")
        sys.exit(1)
    
    project_path = os.path.expanduser(project_path)
    
    if not os.path.exists(project_path):
        print(f"❌ Error: Path does not exist: {project_path}")
        sys.exit(1)
    
    # Check if it looks like a React Native project
    indicators = ['package.json', 'App.tsx', 'App.js', 'index.js', 'app.json']
    found_indicators = [f for f in indicators if os.path.exists(os.path.join(project_path, f))]
    
    if not found_indicators:
        print("⚠️  Warning: This doesn't look like a React Native project")
        print(f"   Expected to find: {', '.join(indicators)}")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(0)
    else:
        print(f"✅ Found React Native project indicators: {', '.join(found_indicators)}")
    
    print()
    print("🔄 Parsing codebase... (this may take a minute)")
    print()
    
    try:
        # Parse the codebase
        parser = ReactNativeParser(project_path)
        result = parser.parse_all()
        
        # Print summary
        print("=" * 60)
        print("📊 PARSING COMPLETE - SUMMARY")
        print("=" * 60)
        print()
        print(f"📱 Screens found:        {len(result.screens)}")
        print(f"🧩 Components found:     {len(result.components)}")
        print(f"🌐 API endpoints found:  {len(result.api_endpoints)}")
        print(f"✅ Validation rules:     {len(result.validation_rules)}")
        print(f"📏 Business constants:   {len(result.business_constants)}")
        print(f"👤 User types found:     {len(result.user_types)}")
        print(f"❌ Error codes found:    {len(result.error_codes)}")
        print()
        
        # Show some examples
        if result.screens:
            print("📱 SCREENS DETECTED:")
            print("-" * 40)
            for screen in result.screens[:15]:  # Show first 15
                nav = f" → {', '.join(screen.navigation_targets)}" if screen.navigation_targets else ""
                print(f"   • {screen.name}{nav}")
            if len(result.screens) > 15:
                print(f"   ... and {len(result.screens) - 15} more")
            print()
        
        if result.api_endpoints:
            print("🌐 API ENDPOINTS DETECTED:")
            print("-" * 40)
            for api in result.api_endpoints[:10]:  # Show first 10
                print(f"   • {api.method:6} {api.url}")
            if len(result.api_endpoints) > 10:
                print(f"   ... and {len(result.api_endpoints) - 10} more")
            print()
        
        if result.validation_rules:
            print("✅ VALIDATION RULES DETECTED:")
            print("-" * 40)
            for rule in result.validation_rules[:10]:
                print(f"   • {rule.field_name}: {', '.join(rule.rules)}")
            if len(result.validation_rules) > 10:
                print(f"   ... and {len(result.validation_rules) - 10} more")
            print()
        
        if result.business_constants:
            print("📏 BUSINESS CONSTANTS DETECTED:")
            print("-" * 40)
            for const in result.business_constants[:10]:
                print(f"   • {const.name} = {const.value}")
            if len(result.business_constants) > 10:
                print(f"   ... and {len(result.business_constants) - 10} more")
            print()
        
        # Generate knowledge base
        print("=" * 60)
        print("📝 GENERATING KNOWLEDGE BASE FILES...")
        print("=" * 60)
        
        kb_dir = Path(__file__).parent / "docs" / "knowledge_base"
        generator = CodeKnowledgeGenerator(result)
        generator.save_to_knowledge_base(str(kb_dir))
        
        print()
        print("✅ Knowledge base files generated at:")
        print(f"   {kb_dir}")
        print()
        print("Generated files:")
        print("   • app_structure.md     - All screens and components")
        print("   • api_endpoints.md     - API endpoints for testing")
        print("   • validation_rules.md  - Input validation rules")
        print("   • business_rules.md    - Business constants & limits")
        print("   • user_states.md       - User types & state matrix")
        print("   • code_context.json    - JSON for LLM injection")
        print()
        
        # Also save raw JSON
        json_output = Path(__file__).parent / "output" / "parsed_codebase.json"
        json_output.parent.mkdir(exist_ok=True)
        json_output.write_text(result.to_json())
        print(f"📄 Raw JSON saved to: {json_output}")
        print()
        
        # Save markdown summary
        md_output = Path(__file__).parent / "output" / "codebase_summary.md"
        md_output.write_text(result.to_markdown())
        print(f"📄 Markdown summary saved to: {md_output}")
        print()
        
        print("=" * 60)
        print("🎉 SUCCESS! Your codebase has been parsed.")
        print("=" * 60)
        print()
        print("NEXT STEPS:")
        print("1. Review the generated files in docs/knowledge_base/")
        print("2. Add any missing business rules manually")
        print("3. Run the test generator - it will now use this context!")
        print()
        
    except Exception as e:
        print(f"❌ Error during parsing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
