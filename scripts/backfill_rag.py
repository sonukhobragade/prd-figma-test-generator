#!/usr/bin/env python3
"""
Backfill RAG with existing test cases from output/ directory.

This script indexes all existing test case CSV files into the Qdrant
vector database for retrieval augmented generation.

Usage:
    python scripts/backfill_rag.py                    # Index all CSV files
    python scripts/backfill_rag.py --limit 10        # Index only first 10 files
    python scripts/backfill_rag.py --file testcases_figma_20251220.csv  # Index specific file
"""

import asyncio
import argparse
import csv
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from framework.rag_integration import TestCaseRAG  # noqa: E402  (needs the path/env setup above)
from framework.models import TestCase, TestChecklist  # noqa: E402  (needs the path/env setup above)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Qdrant port (match the one used by the app)
QDRANT_PORT = 6335
OUTPUT_DIR = Path("output")


def normalize_test_type(test_type: str) -> str:
    """Normalize test_type to valid TestCase values.

    Args:
        test_type: Raw test type string from CSV.

    Returns:
        Valid test type string.
    """
    valid_types = {
        'positive', 'negative', 'edge_case', 'boundary', 'user_journey',
        'subscription_state', 'navigation', 'ui_compliance', 'data_sync',
        'state_propagation', 'feature_gating'
    }

    if not test_type or test_type.lower() == 'general':
        return 'positive'  # Default to positive for unspecified types

    normalized = test_type.lower().replace(' ', '_').replace('-', '_')

    if normalized in valid_types:
        return normalized

    # Map common variations
    type_mapping = {
        'edge': 'edge_case',
        'edgecase': 'edge_case',
        'boundary_value': 'boundary',
        'user_flow': 'user_journey',
        'user_journey_test': 'user_journey',
        'nav': 'navigation',
        'ui': 'ui_compliance',
        'sync': 'data_sync',
        'state': 'state_propagation',
        'gating': 'feature_gating',
        'functional': 'positive',
        'happy_path': 'positive',
        'error': 'negative',
        'validation': 'negative',
    }

    return type_mapping.get(normalized, 'positive')


def parse_csv_file(csv_path: Path) -> list[TestCase]:
    """Parse a CSV file into TestCase objects.

    Args:
        csv_path: Path to the CSV file.

    Returns:
        List of TestCase objects.
    """
    test_cases = []

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    # Get and normalize test_type
                    raw_test_type = row.get("Test Type", row.get("TestType", row.get("test_type", "")))
                    test_type = normalize_test_type(raw_test_type)

                    # Handle various CSV column naming conventions
                    tc = TestCase(
                        test_case_id=row.get("Test Case ID", row.get("TestCaseID", row.get("test_case_id", ""))),
                        feature=row.get("Feature", row.get("feature", "")),
                        requirement_description=row.get("Requirement Description", row.get("RequirementDescription", row.get("requirement_description", ""))),
                        test_step=row.get("Test Steps", row.get("TestStep", row.get("test_step", row.get("Steps to Execute", "")))),
                        expected_result=row.get("Expected Result", row.get("ExpectedResult", row.get("expected_result", ""))),
                        priority=row.get("Priority", row.get("priority", "P2")),
                        notes=row.get("Notes", row.get("notes", row.get("Comments", ""))),
                        test_type=test_type,
                        screenshot_url=row.get("ScreenshotURL", row.get("Screenshot URL", None)),
                    )
                    test_cases.append(tc)
                except Exception as e:
                    logger.warning(f"Error parsing row in {csv_path.name}: {e}")
                    continue

    except Exception as e:
        logger.error(f"Error reading {csv_path}: {e}")

    return test_cases


async def backfill_single_file(csv_path: Path, rag: TestCaseRAG) -> dict:
    """Backfill a single CSV file into RAG.

    Args:
        csv_path: Path to the CSV file.
        rag: TestCaseRAG instance.

    Returns:
        Statistics dictionary.
    """
    logger.info(f"Processing: {csv_path.name}")

    # Parse test cases from CSV
    test_cases = parse_csv_file(csv_path)

    if not test_cases:
        logger.warning(f"No test cases found in {csv_path.name}")
        return {"file": csv_path.name, "status": "empty", "count": 0}

    # Extract feature name from filename
    # e.g., testcases_figma_20251220_221851.csv -> figma_20251220_221851
    feature_name = csv_path.stem.replace("testcases_", "")

    # Create a mock checklist for indexing
    checklist = TestChecklist(
        feature_name=feature_name,
        test_points=[],
        coverage_score=75.0,  # Default score for backfilled data
        coverage_analysis=None,
    )

    # Create session ID from filename
    session_id = f"backfill-{csv_path.stem}"

    # Index the session
    try:
        stats = await rag.index_session(
            test_cases=test_cases,
            checklist=checklist,
            prd_content="",  # No PRD content for backfill
            session_id=session_id,
        )

        logger.info(f"  Indexed {stats['test_cases']} test cases from {csv_path.name}")
        return {
            "file": csv_path.name,
            "status": "success",
            "count": stats['test_cases'],
        }

    except Exception as e:
        logger.error(f"  Error indexing {csv_path.name}: {e}")
        return {"file": csv_path.name, "status": "error", "error": str(e)}


async def main():
    """Main backfill function."""
    parser = argparse.ArgumentParser(description="Backfill RAG with existing test cases")
    parser.add_argument("--limit", type=int, help="Limit number of files to process")
    parser.add_argument("--file", type=str, help="Process a specific file only")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without indexing")
    args = parser.parse_args()

    print("=" * 70)
    print("RAG Backfill Script - Indexing Existing Test Cases")
    print("=" * 70)

    # Initialize RAG
    print("\n[1/4] Initializing RAG connection...")
    rag = TestCaseRAG(qdrant_port=QDRANT_PORT)

    if not rag.enabled:
        print("ERROR: RAG not enabled. Is Qdrant running?")
        print("\nTroubleshooting:")
        print("  1. Check if Qdrant is running: docker ps | grep qdrant")
        print("  2. Start Qdrant: docker-compose up -d qdrant")
        print(f"  3. Verify port: {QDRANT_PORT}")
        sys.exit(1)

    print("RAG initialized successfully")

    # Get initial stats
    initial_stats = rag.get_rag_stats()
    initial_count = initial_stats.get('test_cases', {}).get('count', 0)
    print(f"  Current indexed test cases: {initial_count}")

    # Find CSV files
    print("\n[2/4] Finding CSV files...")

    if args.file:
        csv_files = [OUTPUT_DIR / args.file]
        if not csv_files[0].exists():
            print(f"ERROR: File not found: {args.file}")
            sys.exit(1)
    else:
        csv_files = sorted(OUTPUT_DIR.glob("testcases_*.csv"))

    if args.limit:
        csv_files = csv_files[:args.limit]

    print(f"  Found {len(csv_files)} CSV files to process")

    if not csv_files:
        print("No CSV files found in output/ directory")
        sys.exit(0)

    # Preview files
    print("\n  Files to process:")
    for i, f in enumerate(csv_files[:10], 1):
        size = f.stat().st_size / 1024
        print(f"    {i}. {f.name} ({size:.1f} KB)")
    if len(csv_files) > 10:
        print(f"    ... and {len(csv_files) - 10} more files")

    if args.dry_run:
        print("\n[DRY RUN] Would process above files. Exiting.")
        sys.exit(0)

    # Process files
    print("\n[3/4] Processing CSV files...")

    results = []
    total_indexed = 0
    errors = 0

    for i, csv_path in enumerate(csv_files, 1):
        print(f"\n[{i}/{len(csv_files)}] ", end="")
        result = await backfill_single_file(csv_path, rag)
        results.append(result)

        if result["status"] == "success":
            total_indexed += result["count"]
        elif result["status"] == "error":
            errors += 1

    # Final stats
    print("\n[4/4] Backfill complete!")
    print("=" * 70)

    final_stats = rag.get_rag_stats()
    final_count = final_stats.get('test_cases', {}).get('count', 0)

    print("\nSummary:")
    print(f"  Files processed:      {len(csv_files)}")
    print(f"  Test cases indexed:   {total_indexed}")
    print(f"  Errors:               {errors}")
    print("")
    print(f"  Before backfill:      {initial_count} test cases")
    print(f"  After backfill:       {final_count} test cases")
    print(f"  New test cases added: {final_count - initial_count}")

    print("\n" + "=" * 70)
    print("RAG is now ready with your historical test cases!")
    print("=" * 70)

    # Show any errors
    if errors > 0:
        print("\nFiles with errors:")
        for result in results:
            if result["status"] == "error":
                print(f"  - {result['file']}: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())
