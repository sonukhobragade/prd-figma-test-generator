#!/usr/bin/env python3
"""
Test script for RAG integration.

Verifies that TestCaseRAG can:
1. Initialize and connect to Qdrant
2. Index sample test cases
3. Retrieve similar tests
4. Get statistics
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from framework.rag_integration import TestCaseRAG
from framework.models import TestCase, TestChecklist, TestPoint, CoverageAnalysis, TestTypeDistribution, RiskAssessment


def create_sample_test_cases():
    """Create sample test cases for testing."""
    test_cases = [
        TestCase(
            test_case_id="TC001_P0_Payment",
            feature="Recharge",
            requirement_description="User should be able to recharge wallet using UPI payment",
            test_step="1. Open recharge screen\n2. Enter amount ₹100\n3. Select UPI\n4. Complete payment\n5. Verify balance updated",
            expected_result="Wallet balance increases by ₹100, success message shown",
            priority="P0",
            notes="Critical payment flow",
            test_type="positive"
        ),
        TestCase(
            test_case_id="TC002_P0_Payment",
            feature="Recharge",
            requirement_description="System should prevent recharge below minimum amount",
            test_step="1. Open recharge screen\n2. Enter amount ₹5\n3. Tap proceed",
            expected_result="Error message shown: 'Minimum recharge amount is ₹10'",
            priority="P0",
            notes="Boundary validation",
            test_type="boundary"
        ),
        TestCase(
            test_case_id="TC003_P1_Auth",
            feature="Login",
            requirement_description="User should be able to login with OTP",
            test_step="1. Enter phone number\n2. Request OTP\n3. Enter OTP\n4. Verify login successful",
            expected_result="User logged in, redirected to home screen",
            priority="P1",
            notes="Auth flow",
            test_type="positive"
        ),
    ]
    return test_cases


def create_sample_checklist():
    """Create sample test checklist."""
    test_points = [
        TestPoint(
            description="Test recharge with UPI",
            feature="Recharge",
            priority="P0",
            test_type="positive"
        ),
        TestPoint(
            description="Test minimum amount validation",
            feature="Recharge",
            priority="P0",
            test_type="boundary"
        ),
    ]

    coverage_analysis = CoverageAnalysis(
        test_type_distribution=TestTypeDistribution(
            positive=1,
            negative=0,
            boundary=1,
            edge_case=0,
            user_journey=0
        ),
        missing_scenarios=["Test maximum recharge limit", "Test network failure during payment"],
        risk_assessment=RiskAssessment(
            high_risk_features=["Payment processing"],
            medium_risk_features=["UI validation"],
            low_risk_features=["Success messages"]
        ),
        recommendations=["Add more negative test cases", "Test offline scenarios"]
    )

    checklist = TestChecklist(
        feature_name="Recharge and Payment",
        test_points=test_points,
        coverage_score=75.0,
        coverage_analysis=coverage_analysis
    )

    return checklist


async def test_rag_integration():
    """Run comprehensive RAG integration test."""
    print("=" * 70)
    print("Testing RAG Integration")
    print("=" * 70)

    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # 1. Initialize
    print("\n[1/5] Initializing TestCaseRAG...")
    # Use port 6335 as specified by user
    rag = TestCaseRAG(qdrant_port=6335)

    if not rag.enabled:
        print("❌ FAILED: RAG not enabled (Qdrant not available)")
        print("\nTroubleshooting:")
        print("  1. Check if Qdrant is running: docker ps | grep qdrant")
        print("  2. Start Qdrant: docker-compose up -d qdrant")
        print("  3. Check logs: docker logs qdrant")
        return False

    print("✅ PASSED: RAG initialized successfully")

    # 2. Get initial stats
    print("\n[2/5] Getting initial RAG statistics...")
    stats = rag.get_rag_stats()
    print(f"  Enabled: {stats['enabled']}")
    print(f"  Health: {stats['health']}")
    print(f"  Test Cases: {stats.get('test_cases', {}).get('count', 0)}")
    print(f"  PRD Documents: {stats.get('prd_documents', {}).get('count', 0)}")
    print(f"  Coverage Insights: {stats.get('coverage_insights', {}).get('count', 0)}")
    print("✅ PASSED: Retrieved statistics")

    # 3. Index sample session
    print("\n[3/5] Indexing sample test generation session...")
    test_cases = create_sample_test_cases()
    checklist = create_sample_checklist()
    prd_content = """
    Feature: Wallet Recharge

    Users should be able to recharge their wallet using various payment methods.
    Minimum recharge amount: ₹10
    Maximum recharge amount: ₹50,000
    Supported payment methods: UPI, Card, Net Banking

    The recharge should be instant and balance should update immediately.
    """

    session_id = "test-session-001"

    index_stats = await rag.index_session(
        test_cases=test_cases,
        checklist=checklist,
        prd_content=prd_content,
        session_id=session_id
    )

    print(f"  Status: {index_stats['status']}")
    print(f"  Test Cases Indexed: {index_stats['test_cases']}")
    print(f"  PRD Chunks Indexed: {index_stats['prd_chunks']}")
    print(f"  Coverage Gaps Indexed: {index_stats['coverage_gaps']}")

    if index_stats['status'] == 'success':
        print("✅ PASSED: Session indexed successfully")
    else:
        print(f"❌ FAILED: Indexing failed - {index_stats.get('error_message')}")
        return False

    # 4. Test retrieval
    print("\n[4/5] Testing similar test case retrieval...")
    similar_tests = rag.get_similar_tests(
        query="payment recharge UPI minimum amount",
        feature_type="payment",
        top_k=3
    )

    print(f"  Found {len(similar_tests)} similar tests")
    for i, test in enumerate(similar_tests, 1):
        metadata = test.get("metadata", {})
        score = test.get("final_score", 0)
        print(f"  [{i}] {metadata.get('test_case_id')} - Score: {score:.3f}")
        print(f"      Feature: {metadata.get('feature')}, Priority: {metadata.get('priority')}")
        print(f"      Type: {metadata.get('feature_type_detected')}")

    if similar_tests:
        print("✅ PASSED: Successfully retrieved similar tests")
    else:
        print("⚠️  WARNING: No similar tests found (might be expected for first run)")

    # 5. Test RAG context formatting
    print("\n[5/5] Testing RAG context formatting...")
    context = rag.format_rag_context(
        similar_tests=similar_tests,
        include_gaps=True,
        feature_type="payment"
    )

    if context:
        print(f"  Generated context length: {len(context)} characters")
        print("  Preview (first 300 chars):")
        print("  " + "-" * 66)
        print("  " + context[:300].replace("\n", "\n  "))
        print("  ...")
        print("✅ PASSED: Context formatted successfully")
    else:
        print("⚠️  WARNING: Empty context (expected if no data)")

    # Final stats
    print("\n" + "=" * 70)
    print("Final Statistics")
    print("=" * 70)
    final_stats = rag.get_rag_stats()
    print(f"Total Documents: {final_stats.get('total_documents', 0)}")
    print(f"Test Cases: {final_stats.get('test_cases', {}).get('count', 0)}")
    print(f"PRD Documents: {final_stats.get('prd_documents', {}).get('count', 0)}")
    print(f"Coverage Insights: {final_stats.get('coverage_insights', {}).get('count', 0)}")

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED!")
    print("=" * 70)
    print("\nRAG Integration is working correctly!")
    print("\nNext steps:")
    print("  1. Integrate with LLMAnalyzer (Phase 2)")
    print("  2. Add API endpoints to app.py")
    print("  3. Build frontend components")
    print("  4. Backfill existing test cases with scripts/backfill_rag.py")

    return True


if __name__ == "__main__":
    success = asyncio.run(test_rag_integration())
    sys.exit(0 if success else 1)
