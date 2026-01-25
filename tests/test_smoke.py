"""Smoke tests to verify the project can start and basic components work."""

import pytest
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
from src.config import settings
from src.cognitive_engine.state import CognitiveState
from src.cognitive_engine.graph import create_cognitive_graph
from src.cognitive_engine.invest import InvestValidator
from src.cognitive_engine.agents.po_agent import ProductOwnerAgent
from src.cognitive_engine.agents.qa_agent import QAAgent
from src.cognitive_engine.agents.developer_agent import DeveloperAgent
from src.cognitive_engine.agents.supervisor import SupervisorAgent
from src.adapters.llm.litellm_adapter import LiteLLMAdapter
from src.adapters.rate_limiter import TokenBucket
from src.infrastructure.di import get_container, DIContainer
from src.ingestion.vector_db import LanceDBAdapter
from src.ingestion.github_loader import load_repository
from src.ingestion.notion_loader import load_notion_pages
from src.ingestion.chunking import chunk_code, chunk_markdown_by_headers
from src.utils.logger import setup_logging, get_logger
from src.utils.tracing import setup_tracing, get_tracer
from src.domain.use_cases import OptimizeArtifactUseCase
from src.main import app


class TestImports:
    """Test that all critical imports work."""

    def test_domain_imports(self):
        """Test domain layer imports."""
        assert CoreArtifact is not None
        assert OptimizationRequest is not None
        assert UASKnowledgeUnit is not None
        assert NormalizedPriority is not None
        assert WorkItemStatus is not None

    def test_interface_imports(self):
        """Test interface imports."""
        assert IIssueTracker is not None
        assert IKnowledgeBase is not None
        assert ILLMProvider is not None
        assert IWebhookIngress is not None

    def test_config_imports(self):
        """Test configuration imports."""
        assert settings is not None
        assert hasattr(settings, "litellm_model")
        assert hasattr(settings, "dry_run")
        assert hasattr(settings, "mode")

    def test_cognitive_engine_imports(self):
        """Test cognitive engine imports."""
        assert CognitiveState is not None
        assert create_cognitive_graph is not None
        assert InvestValidator is not None
        assert ProductOwnerAgent is not None
        assert QAAgent is not None
        assert DeveloperAgent is not None
        assert SupervisorAgent is not None

    def test_adapter_imports(self):
        """Test adapter imports."""
        assert LiteLLMAdapter is not None
        assert TokenBucket is not None

    def test_infrastructure_imports(self):
        """Test infrastructure imports."""
        assert get_container is not None
        assert DIContainer is not None

    def test_ingestion_imports(self):
        """Test ingestion imports."""
        assert LanceDBAdapter is not None
        assert load_repository is not None
        assert load_notion_pages is not None
        assert chunk_code is not None
        assert chunk_markdown_by_headers is not None

    def test_utility_imports(self):
        """Test utility imports."""
        assert setup_logging is not None
        assert get_logger is not None
        assert setup_tracing is not None
        assert get_tracer is not None

    def test_use_case_imports(self):
        """Test use case imports."""
        assert OptimizeArtifactUseCase is not None

    def test_main_app_imports(self):
        """Test main app imports."""
        assert app is not None


class TestConfiguration:
    """Test that configuration loads correctly."""

    def test_settings_object_exists(self):
        """Test that settings object exists."""
        assert settings is not None

    def test_required_settings_fields(self):
        """Test that required settings fields exist."""
        assert hasattr(settings, "litellm_model")
        assert hasattr(settings, "dry_run")
        assert hasattr(settings, "mode")
        assert hasattr(settings, "vector_store_path")

    def test_settings_types(self):
        """Test that settings have correct types."""
        assert isinstance(settings.dry_run, bool)
        assert settings.mode in ["shadow", "comment_only", "autonomous"]


class TestSchemaCreation:
    """Test that schema models can be instantiated."""

    def test_optimization_request_creation(self):
        """Test OptimizationRequest creation."""
        request = OptimizationRequest(
            artifact_id="test-id",
            artifact_type="issue",
            source_system="linear",
            trigger="manual",
            dry_run=True,
        )
        assert request.artifact_id == "test-id"
        assert request.dry_run is True
        assert request.source_system == "linear"

    def test_core_artifact_creation(self):
        """Test CoreArtifact creation."""
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
        assert artifact.status == WorkItemStatus.TODO

    def test_knowledge_unit_creation(self):
        """Test UASKnowledgeUnit creation."""
        knowledge_unit = UASKnowledgeUnit(
            id="test-kb-id",
            content="Test content",
            summary="Test summary",
            source="github",
            last_updated="2024-01-01T00:00:00Z",
            location="/path/to/file.py",
        )
        assert knowledge_unit.source == "github"
        assert knowledge_unit.id == "test-kb-id"


class TestDIContainer:
    """Test that DI container can be instantiated."""

    def test_container_creation(self):
        """Test that container can be created."""
        container = get_container()
        assert container is not None
        assert isinstance(container, DIContainer)

    def test_llm_provider_retrieval(self):
        """Test that LLM provider can be retrieved."""
        container = get_container()
        llm_provider = container.get_llm_provider()
        assert llm_provider is not None

    def test_issue_tracker_retrieval(self):
        """Test that issue tracker can be retrieved."""
        container = get_container()
        issue_tracker = container.get_issue_tracker()
        assert issue_tracker is not None


class TestAgents:
    """Test that agents can be instantiated."""

    def test_po_agent_creation(self, mock_llm_provider):
        """Test ProductOwnerAgent creation."""
        agent = ProductOwnerAgent(mock_llm_provider)
        assert agent is not None
        assert hasattr(agent, "draft_artifact")
        assert hasattr(agent, "synthesize_feedback")

    def test_qa_agent_creation(self, mock_llm_provider):
        """Test QAAgent creation."""
        agent = QAAgent(mock_llm_provider)
        assert agent is not None
        assert hasattr(agent, "critique_artifact")

    def test_developer_agent_creation(self, mock_llm_provider):
        """Test DeveloperAgent creation."""
        agent = DeveloperAgent(mock_llm_provider)
        assert agent is not None
        assert hasattr(agent, "assess_feasibility")

    def test_supervisor_agent_creation(self, mock_llm_provider):
        """Test SupervisorAgent creation."""
        supervisor = SupervisorAgent(mock_llm_provider)
        assert supervisor is not None
        assert hasattr(supervisor, "decide_next_action")


class TestInvestValidator:
    """Test INVEST validator."""

    def test_validator_creation(self):
        """Test that validator can be created."""
        validator = InvestValidator()
        assert validator is not None

    def test_validator_validation(self, sample_artifact):
        """Test that validator can validate artifacts."""
        validator = InvestValidator()
        violations = validator.validate(sample_artifact)
        assert isinstance(violations, list)


class TestFastAPIApp:
    """Test that FastAPI app can be created."""

    def test_app_creation(self):
        """Test that app exists and has correct title."""
        assert app is not None
        assert app.title == "Agentic AI PoC"

    def test_health_endpoint_exists(self):
        """Test that health endpoint exists."""
        routes = [route.path for route in app.routes]
        assert "/health" in routes

    def test_webhook_endpoint_exists(self):
        """Test that webhook endpoint exists."""
        routes = [route.path for route in app.routes]
        assert "/webhooks/issue-tracker" in routes


class TestLoggingTracing:
    """Test that logging and tracing can be initialized."""

    def test_logging_setup(self):
        """Test logging setup."""
        setup_logging()
        logger = get_logger(__name__)
        assert logger is not None
        # Test that we can log without errors
        logger.info("test_message", test="value")

    def test_tracing_setup(self):
        """Test tracing setup."""
        setup_tracing()
        tracer = get_tracer(__name__)
        assert tracer is not None


class TestRateLimiter:
    """Test rate limiter."""

    @pytest.mark.asyncio
    async def test_token_bucket_creation(self):
        """Test TokenBucket creation."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket is not None
        assert bucket.capacity == 10
        assert bucket.refill_rate == 1.0

    @pytest.mark.asyncio
    async def test_token_bucket_acquire(self):
        """Test TokenBucket.acquire()."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        await bucket.acquire()
        assert bucket.tokens < bucket.capacity
