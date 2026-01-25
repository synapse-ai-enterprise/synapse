"""Smoke tests to verify the project can start and basic components work."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test that all critical imports work."""
    print("Testing imports...")
    
    try:
        # Domain layer
        from src.domain.schema import (
            CoreArtifact,
            OptimizationRequest,
            UASKnowledgeUnit,
            NormalizedPriority,
            WorkItemStatus,
        )
        from src.domain.interfaces import (
            IIssueTracker,
            IKnowledgeBase,
            ILLMProvider,
            IWebhookIngress,
        )
        print("  ✅ Domain layer imports")
        
        # Configuration
        from src.config import settings
        print("  ✅ Configuration imports")
        
        # Cognitive engine
        from src.cognitive_engine.state import CognitiveState
        from src.cognitive_engine.graph import create_cognitive_graph
        from src.cognitive_engine.invest import InvestValidator
        from src.cognitive_engine.agents.po_agent import ProductOwnerAgent
        from src.cognitive_engine.agents.qa_agent import QAAgent
        from src.cognitive_engine.agents.developer_agent import DeveloperAgent
        print("  ✅ Cognitive engine imports")
        
        # Adapters
        from importlib import import_module
        from src.adapters.llm.litellm_adapter import LiteLLMAdapter
        from src.adapters.rate_limiter import TokenBucket

        def import_adapter(adapter_path: str) -> None:
            module_path, _, class_name = adapter_path.partition(":")
            if not module_path or not class_name:
                raise ValueError(
                    f"Invalid adapter path '{adapter_path}'. Expected 'module.path:ClassName'."
                )
            module = import_module(module_path)
            getattr(module, class_name)

        issue_tracker_provider = settings.issue_tracker_provider.strip().lower()
        webhook_provider = settings.webhook_provider.strip().lower()
        issue_tracker_path = settings.issue_tracker_adapter_path.strip()
        if not issue_tracker_path:
            issue_tracker_path = settings.issue_tracker_adapters.get(issue_tracker_provider, "")
        webhook_path = settings.webhook_ingress_adapter_path.strip()
        if not webhook_path:
            webhook_path = settings.webhook_ingress_adapters.get(webhook_provider, "")
        if not issue_tracker_path:
            raise ValueError(f"Unsupported issue tracker provider: {issue_tracker_provider}")
        if not webhook_path:
            raise ValueError(f"Unsupported webhook provider: {webhook_provider}")

        import_adapter(issue_tracker_path)
        import_adapter(webhook_path)
        print("  ✅ Adapter imports")
        
        # Infrastructure
        from src.infrastructure.di import get_container, DIContainer
        from src.infrastructure.queue import get_queue, enqueue_optimization_request
        from src.infrastructure.workers import process_optimization
        print("  ✅ Infrastructure imports")
        
        # Ingestion
        from src.ingestion.vector_db import LanceDBAdapter
        from src.ingestion.github_loader import load_repository
        from src.ingestion.notion_loader import load_notion_pages
        from src.ingestion.chunking import chunk_code, chunk_markdown_by_headers
        print("  ✅ Ingestion imports")
        
        # Utils
        from src.utils.logger import setup_logging, get_logger
        from src.utils.tracing import setup_tracing, get_tracer, get_trace_id
        print("  ✅ Utility imports")
        
        # Use cases
        from src.domain.use_cases import OptimizeArtifactUseCase
        print("  ✅ Use case imports")
        
        # Main app
        from src.main import app
        print("  ✅ Main app imports")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Unexpected error during imports: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_configuration():
    """Test that configuration loads correctly."""
    print("\nTesting configuration...")
    
    try:
        from src.config import settings
        
        # Check that settings object exists
        assert settings is not None, "Settings object is None"
        print("  ✅ Settings object created")
        
        # Check that required fields exist (even if empty)
        assert hasattr(settings, "litellm_model"), "Missing litellm_model"
        assert hasattr(settings, "dry_run"), "Missing dry_run"
        assert hasattr(settings, "mode"), "Missing mode"
        assert hasattr(settings, "vector_store_path"), "Missing vector_store_path"
        print("  ✅ Required configuration fields present")
        
        # Check default values
        assert settings.dry_run is False or settings.dry_run is True, "dry_run must be bool"
        assert settings.mode in ["shadow", "comment_only", "autonomous"], f"Invalid mode: {settings.mode}"
        print("  ✅ Configuration defaults valid")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Configuration error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_schema_creation():
    """Test that schema models can be instantiated."""
    print("\nTesting schema models...")
    
    try:
        from src.domain.schema import (
            CoreArtifact,
            OptimizationRequest,
            UASKnowledgeUnit,
            NormalizedPriority,
            WorkItemStatus,
        )
        
        # Test OptimizationRequest
        request = OptimizationRequest(
            artifact_id="test-id",
            artifact_type="issue",
            source_system="linear",
            trigger="manual",
            dry_run=True,
        )
        assert request.artifact_id == "test-id"
        print("  ✅ OptimizationRequest creation")
        
        # Test CoreArtifact
        artifact = CoreArtifact(
            source_system="linear",
            source_id="test-source-id",
            human_ref="LIN-123",
            url="https://linear.app/test",
            title="Test Issue",
            description="Test description",
            type="Story",
            status=WorkItemStatus.TODO,
            priority=NormalizedPriority.MEDIUM,
        )
        assert artifact.title == "Test Issue"
        assert artifact.priority == NormalizedPriority.MEDIUM
        print("  ✅ CoreArtifact creation")
        
        # Test UASKnowledgeUnit
        knowledge_unit = UASKnowledgeUnit(
            id="test-kb-id",
            content="Test content",
            summary="Test summary",
            source="github",
            last_updated="2024-01-01T00:00:00",
            location="/path/to/file.py",
        )
        assert knowledge_unit.source == "github"
        print("  ✅ UASKnowledgeUnit creation")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Schema creation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_di_container():
    """Test that DI container can be instantiated."""
    print("\nTesting DI container...")
    
    try:
        from src.infrastructure.di import get_container
        
        container = get_container()
        assert container is not None, "Container is None"
        print("  ✅ DI container created")
        
        # Test LLM provider (should work without API key for instantiation)
        llm_provider = container.get_llm_provider()
        assert llm_provider is not None, "LLM provider is None"
        print("  ✅ LLM provider retrieved")
        
        # Test issue tracker (should work without API key for instantiation)
        issue_tracker = container.get_issue_tracker()
        assert issue_tracker is not None, "Issue tracker is None"
        print("  ✅ Issue tracker retrieved")
        
        return True
        
    except Exception as e:
        print(f"  ❌ DI container error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agents():
    """Test that agents can be instantiated."""
    print("\nTesting agents...")
    
    try:
        from src.infrastructure.di import get_container
        from src.cognitive_engine.agents.po_agent import ProductOwnerAgent
        from src.cognitive_engine.agents.qa_agent import QAAgent
        from src.cognitive_engine.agents.developer_agent import DeveloperAgent
        
        container = get_container()
        llm_provider = container.get_llm_provider()
        
        # Test PO Agent
        po_agent = ProductOwnerAgent(llm_provider)
        assert po_agent is not None
        assert hasattr(po_agent, "draft_artifact")
        assert hasattr(po_agent, "synthesize_feedback")
        print("  ✅ ProductOwnerAgent created")
        
        # Test QA Agent
        qa_agent = QAAgent(llm_provider)
        assert qa_agent is not None
        assert hasattr(qa_agent, "critique_artifact")
        print("  ✅ QAAgent created")
        
        # Test Developer Agent
        dev_agent = DeveloperAgent(llm_provider)
        assert dev_agent is not None
        assert hasattr(dev_agent, "assess_feasibility")
        print("  ✅ DeveloperAgent created")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Agent creation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_invest_validator():
    """Test INVEST validator."""
    print("\nTesting INVEST validator...")
    
    try:
        from src.cognitive_engine.invest import InvestValidator
        from src.domain.schema import CoreArtifact, NormalizedPriority, WorkItemStatus
        
        validator = InvestValidator()
        assert validator is not None
        
        # Test validation
        artifact = CoreArtifact(
            source_system="linear",
            source_id="test",
            human_ref="LIN-123",
            url="https://test.com",
            title="Test",
            description="Test description",
            type="Story",
            status=WorkItemStatus.TODO,
            priority=NormalizedPriority.MEDIUM,
        )
        
        violations = validator.validate(artifact)
        assert isinstance(violations, list)
        print(f"  ✅ INVEST validator works (found {len(violations)} violations)")
        
        return True
        
    except Exception as e:
        print(f"  ❌ INVEST validator error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fastapi_app():
    """Test that FastAPI app can be created."""
    print("\nTesting FastAPI app...")
    
    try:
        from src.main import app
        
        assert app is not None, "App is None"
        assert app.title == "Agentic AI PoC", f"Unexpected title: {app.title}"
        print("  ✅ FastAPI app created")
        
        # Check routes exist
        routes = [route.path for route in app.routes]
        assert "/health" in routes, "Health endpoint missing"
        assert "/webhooks/issue-tracker" in routes, "Webhook endpoint missing"
        print("  ✅ FastAPI routes registered")
        
        return True
        
    except Exception as e:
        print(f"  ❌ FastAPI app error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_logging_tracing():
    """Test that logging and tracing can be initialized."""
    print("\nTesting logging and tracing...")
    
    try:
        from src.utils.logger import setup_logging, get_logger
        from src.utils.tracing import setup_tracing, get_tracer
        
        # Setup logging
        setup_logging()
        logger = get_logger(__name__)
        logger.info("test_message", test="value")
        print("  ✅ Logging initialized")
        
        # Setup tracing
        setup_tracing()
        tracer = get_tracer(__name__)
        assert tracer is not None
        print("  ✅ Tracing initialized")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Logging/tracing error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rate_limiter():
    """Test rate limiter."""
    print("\nTesting rate limiter...")
    
    try:
        from src.adapters.rate_limiter import TokenBucket
        import asyncio
        
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket is not None
        assert bucket.capacity == 10
        assert bucket.refill_rate == 1.0
        print("  ✅ TokenBucket created")
        
        # Test async acquire (should work immediately with tokens available)
        async def test_acquire():
            await bucket.acquire()
            return True
        
        result = asyncio.run(test_acquire())
        assert result is True
        print("  ✅ TokenBucket.acquire() works")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Rate limiter error: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all smoke tests."""
    print("=" * 80)
    print("SMOKE TEST: Verifying project can start")
    print("=" * 80)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_configuration),
        ("Schema Creation", test_schema_creation),
        ("DI Container", test_di_container),
        ("Agents", test_agents),
        ("INVEST Validator", test_invest_validator),
        ("FastAPI App", test_fastapi_app),
        ("Logging & Tracing", test_logging_tracing),
        ("Rate Limiter", test_rate_limiter),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print("=" * 80)
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 80)
    
    if passed == total:
        print("\n🎉 All smoke tests passed! Project is ready to start.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please fix issues before starting.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
