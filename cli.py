#!/usr/bin/env python3
"""CLI interface for PRD-to-Figma test case generator."""

import os
import sys
from pathlib import Path

import click

from framework.figma_client import FigmaClient
from framework.llm_analyzer import LLMAnalyzer
from framework.prd_uploader import PRDUploader
from framework.test_expander import TestCaseExpander
from framework.utils import load_environment, setup_logging


@click.group()
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Logging level",
)
@click.option("--env-file", default=".env", type=click.Path(), help="Path to .env file")
def cli(log_level: str, env_file: str) -> None:
    """PRD-to-Figma Test Case Generator CLI.

    Transform PRD screenshots and Figma designs into comprehensive test cases.
    """
    # Setup logging
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    setup_logging(log_level=log_level, log_file=log_dir / "generator.log")

    # Load environment
    load_environment(Path(env_file))


@cli.command()
@click.option(
    "--prd", required=True, type=click.Path(exists=True), help="Path to PRD file"
)
@click.option(
    "--output",
    default="output/checklist.md",
    type=click.Path(),
    help="Output path for checklist",
)
@click.option(
    "--feature-name", default=None, help="Optional feature name for the analysis"
)
def analyze(prd: str, output: str, feature_name: str) -> None:
    """Analyze PRD and generate test checklist."""
    try:
        prd_path = Path(prd)
        output_path = Path(output)

        click.echo(f"📄 Analyzing PRD: {prd_path.name}")

        # Upload PRD
        uploader = PRDUploader()
        prd_doc = uploader.upload(prd_path, process_images=True, extract_text=False)
        click.echo(f"✓ Uploaded: {prd_doc.file_size_mb:.2f}MB")

        # Analyze with LLM
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            click.echo("❌ Error: ANTHROPIC_API_KEY not found in environment", err=True)
            sys.exit(1)

        analyzer = LLMAnalyzer(api_key=api_key)
        click.echo("🤖 Analyzing with Claude...")

        # Use PRD content or placeholder
        content = prd_doc.content or f"Analyze this PRD document: {prd_path.name}"
        checklist = analyzer.analyze_prd(
            content=content, images=prd_doc.images, feature_name=feature_name
        )

        click.echo(
            f"✓ Generated {len(checklist.test_points)} test points "
            f"(Coverage: {checklist.coverage_score:.1f}%)"
        )

        # Save checklist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown = analyzer.generate_checklist_markdown(checklist)
        output_path.write_text(markdown)

        click.echo(f"✓ Saved checklist: {output_path}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--url", required=True, help="Figma URL with node-id")
@click.option(
    "--output",
    default="output/checklist.md",
    type=click.Path(),
    help="Output path for checklist",
)
@click.option("--scale", default=2.0, type=float, help="Screenshot scale (1-4)")
def figma(url: str, output: str, scale: float) -> None:
    """Import design from Figma and generate test checklist."""
    try:
        output_path = Path(output)

        click.echo("🎨 Importing from Figma...")

        # Import from Figma
        api_token = os.getenv("FIGMA_API_TOKEN")
        if not api_token:
            click.echo("❌ Error: FIGMA_API_TOKEN not found in environment", err=True)
            sys.exit(1)

        figma_client = FigmaClient(api_token=api_token)
        design = figma_client.import_from_url(url, scale=scale)
        click.echo(f"✓ Downloaded: {design.name}")

        # Analyze with LLM
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            click.echo("❌ Error: ANTHROPIC_API_KEY not found in environment", err=True)
            sys.exit(1)

        analyzer = LLMAnalyzer(api_key=anthropic_key)
        click.echo("🤖 Analyzing design with Claude...")

        content = f"Analyze this Figma design for {design.name}"
        images = [design.screenshot_path] if design.screenshot_path else []

        checklist = analyzer.analyze_prd(
            content=content, images=images, feature_name=design.name
        )

        click.echo(
            f"✓ Generated {len(checklist.test_points)} test points "
            f"(Coverage: {checklist.coverage_score:.1f}%)"
        )

        # Save checklist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown = analyzer.generate_checklist_markdown(checklist)
        output_path.write_text(markdown)

        click.echo(f"✓ Saved checklist: {output_path}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--checklist",
    required=True,
    type=click.Path(exists=True),
    help="Path to checklist markdown",
)
@click.option(
    "--testcases",
    default="output/testcases.csv",
    type=click.Path(),
    help="Output path for CSV test cases",
)
def expand(checklist: str, testcases: str) -> None:
    """Expand checklist to detailed CSV test cases."""
    try:
        # NOTE: This is a simplified version
        # In practice, you'd need to parse the markdown back to TestChecklist
        click.echo(
            "⚠️  Note: This command requires a checklist object, not markdown file."
        )
        click.echo("    Use the 'generate' command for end-to-end workflow instead.")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--prd", required=True, type=click.Path(exists=True), help="Path to PRD file"
)
@click.option(
    "--checklist",
    default="output/checklist.md",
    type=click.Path(),
    help="Output path for checklist",
)
@click.option(
    "--testcases",
    default="output/testcases.csv",
    type=click.Path(),
    help="Output path for CSV test cases",
)
@click.option("--feature-name", default=None, help="Optional feature name")
def generate(prd: str, checklist: str, testcases: str, feature_name: str) -> None:
    """Full workflow: PRD → Checklist → CSV test cases."""
    try:
        prd_path = Path(prd)
        checklist_path = Path(checklist)
        testcases_path = Path(testcases)

        click.echo(f"🚀 Starting full workflow for: {prd_path.name}")
        click.echo()

        # Step 1: Upload PRD
        click.echo("📄 Step 1/3: Uploading PRD...")
        uploader = PRDUploader()
        prd_doc = uploader.upload(prd_path, process_images=True, extract_text=False)
        click.echo(f"   ✓ Uploaded: {prd_doc.file_size_mb:.2f}MB")
        click.echo()

        # Step 2: Analyze with LLM
        click.echo("🤖 Step 2/3: Analyzing with Claude...")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            click.echo("❌ Error: ANTHROPIC_API_KEY not found in environment", err=True)
            sys.exit(1)

        analyzer = LLMAnalyzer(api_key=api_key)
        content = prd_doc.content or f"Analyze this PRD document: {prd_path.name}"
        test_checklist = analyzer.analyze_prd(
            content=content, images=prd_doc.images, feature_name=feature_name
        )

        click.echo(
            f"   ✓ Generated {len(test_checklist.test_points)} test points "
            f"(Coverage: {test_checklist.coverage_score:.1f}%)"
        )

        # Save checklist
        checklist_path.parent.mkdir(parents=True, exist_ok=True)
        markdown = analyzer.generate_checklist_markdown(test_checklist)
        checklist_path.write_text(markdown)
        click.echo(f"   ✓ Saved checklist: {checklist_path}")
        click.echo()

        # Step 3: Expand to test cases
        click.echo("📝 Step 3/3: Expanding to detailed test cases...")
        expander = TestCaseExpander()
        test_cases = expander.expand_checklist(test_checklist)
        expander.export_to_csv(test_cases, testcases_path)

        summary = expander.generate_summary_report(test_cases)
        click.echo(f"   ✓ Generated {summary['total_cases']} detailed test cases")
        click.echo(f"   ✓ Saved CSV: {testcases_path}")
        click.echo()

        # Summary
        click.echo("✅ Workflow complete!")
        click.echo(f"   📊 Priority breakdown: {summary['by_priority']}")
        click.echo(f"   📁 Checklist: {checklist_path}")
        click.echo(f"   📁 Test cases: {testcases_path}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--input-dir",
    required=True,
    type=click.Path(exists=True),
    help="Directory with PRD files",
)
@click.option(
    "--output-dir", default="output", type=click.Path(), help="Output directory"
)
def batch(input_dir: str, output_dir: str) -> None:
    """Batch process multiple PRD files."""
    try:
        input_path = Path(input_dir)
        output_path = Path(output_dir)

        # Find all PRD files
        prd_files = []
        for ext in [".pdf", ".png", ".jpg", ".jpeg"]:
            prd_files.extend(input_path.glob(f"*{ext}"))

        if not prd_files:
            click.echo(f"❌ No PRD files found in {input_dir}", err=True)
            sys.exit(1)

        click.echo(f"📦 Batch processing {len(prd_files)} files...")
        click.echo()

        # Process each file
        for i, prd_file in enumerate(prd_files, 1):
            click.echo(f"[{i}/{len(prd_files)}] Processing: {prd_file.name}")

            try:
                # Generate output paths
                base_name = prd_file.stem
                _checklist_path = output_path / f"{base_name}_checklist.md"
                _testcases_path = output_path / f"{base_name}_testcases.csv"

                # Run generation
                # (Reuse logic from generate command)
                click.echo(
                    "   ⏩ Skipping detailed generation (use 'generate' command)"
                )

            except Exception as e:
                click.echo(f"   ❌ Failed: {e}")
                continue

        click.echo()
        click.echo("✅ Batch processing complete!")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
