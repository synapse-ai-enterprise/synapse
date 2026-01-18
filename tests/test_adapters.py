"""Tests for adapter implementations."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.adapters.egress.linear_egress import LinearEgressAdapter
from src.adapters.ingress.linear_ingress import LinearIngressAdapter
from src.adapters.llm.litellm_adapter import LiteLLMAdapter
from src.adapters.rate_limiter import TokenBucket
from src.domain.schema import (
    CoreArtifact,
    NormalizedPriority,
    OptimizationRequest,
    WorkItemStatus,
)


class TestLinearEgressAdapter:
    """Tests for LinearEgressAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter instance with mocked config."""
        with patch("src.adapters.egress.linear_egress.settings") as mock_settings:
            mock_settings.linear_api_key = "test-key"
            mock_settings.linear_team_id = "test-team-id"
            mock_settings.dry_run = False
            mock_settings.mode = "autonomous"
            mock_settings.require_approval_label = "ai-refined"
            adapter = LinearEgressAdapter()
            return adapter

    @pytest.mark.asyncio
    async def test_get_issue(self, adapter):
        """Test fetching an issue."""
        mock_response_data = {
            "data": {
                "issue": {
                    "id": "test-id",
                    "identifier": "LIN-123",
                    "title": "Test Issue",
                    "description": "Test description",
                    "priority": 2,
                    "state": {"name": "Todo", "type": "unstarted"},
                    "type": "Story",
                    "url": "https://linear.app/test",
                    "updatedAt": "2024-01-01T00:00:00Z",
                    "createdAt": "2024-01-01T00:00:00Z",
                }
            }
        }
        
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await adapter.get_issue("test-id")
            
            assert isinstance(result, CoreArtifact)
            assert result.source_id == "test-id"
            assert result.human_ref == "LIN-123"
            assert result.title == "Test Issue"

    @pytest.mark.asyncio
    async def test_update_issue_dry_run(self):
        """Test update in dry run mode."""
        with patch("src.adapters.egress.linear_egress.settings") as mock_settings:
            mock_settings.dry_run = True
            mock_settings.linear_api_key = "test-key"
            mock_settings.linear_team_id = "test-team-id"
            mock_settings.mode = "autonomous"
            mock_settings.require_approval_label = ""
            
            adapter = LinearEgressAdapter()
            artifact = CoreArtifact(
                source_system="linear",
                source_id="test-id",
                human_ref="LIN-123",
                url="https://test.com",
                title="Test",
                description="Test",
                type="Story",
                status=WorkItemStatus.TODO,
                priority=NormalizedPriority.MEDIUM,
            )
            
            result = await adapter.update_issue("test-id", artifact)
            assert result is True

    @pytest.mark.asyncio
    async def test_update_issue_comment_only_mode(self):
        """Test update in comment-only mode."""
        with patch("src.adapters.egress.linear_egress.settings") as mock_settings:
            mock_settings.dry_run = False
            mock_settings.mode = "comment_only"
            mock_settings.linear_api_key = "test-key"
            mock_settings.linear_team_id = "test-team-id"
            mock_settings.require_approval_label = ""
            
            adapter = LinearEgressAdapter()
            artifact = CoreArtifact(
                source_system="linear",
                source_id="test-id",
                human_ref="LIN-123",
                url="https://test.com",
                title="Test",
                description="Test",
                type="Story",
                status=WorkItemStatus.TODO,
                priority=NormalizedPriority.MEDIUM,
            )
            
            with patch.object(adapter, "post_comment", new_callable=AsyncMock) as mock_comment:
                mock_comment.return_value = True
                result = await adapter.update_issue("test-id", artifact)
                assert result is True
                mock_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_comment(self, adapter):
        """Test posting a comment."""
        mock_response_data = {"data": {"commentCreate": {"success": True}}}
        
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await adapter.post_comment("test-id", "Test comment")
            assert result is True

    def test_map_to_artifact(self, adapter):
        """Test mapping Linear data to CoreArtifact."""
        linear_data = {
            "id": "test-id",
            "identifier": "LIN-123",
            "title": "Test Issue",
            "description": "Test description",
            "priority": 2,
            "state": {"name": "In Progress", "type": "started"},
            "type": "Story",
            "url": "https://linear.app/test",
            "updatedAt": "2024-01-01T00:00:00Z",
            "createdAt": "2024-01-01T00:00:00Z",
        }
        
        artifact = adapter._map_to_artifact(linear_data)
        
        assert isinstance(artifact, CoreArtifact)
        assert artifact.source_id == "test-id"
        assert artifact.human_ref == "LIN-123"
        assert artifact.priority == NormalizedPriority.HIGH
        assert artifact.status == WorkItemStatus.IN_PROGRESS


class TestLinearIngressAdapter:
    """Tests for LinearIngressAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter instance."""
        with patch("src.adapters.ingress.linear_ingress.settings") as mock_settings:
            mock_settings.linear_webhook_secret = "test-secret"
            mock_settings.dry_run = False
            adapter = LinearIngressAdapter()
            return adapter

    def test_handle_webhook_issue_created(self, adapter):
        """Test handling Issue.created event."""
        payload = {
            "type": "Issue.created",
            "data": {"id": "test-id"},
        }
        
        # Mock signature verification
        with patch.object(adapter, "_verify_signature", return_value=True):
            result = adapter.handle_webhook(payload, "test-signature")
            
            assert result is not None
            assert isinstance(result, OptimizationRequest)
            assert result.artifact_id == "test-id"
            assert result.trigger == "webhook"

    def test_handle_webhook_issue_updated_relevant(self, adapter):
        """Test handling Issue.updated with relevant changes."""
        payload = {
            "type": "Issue.updated",
            "data": {
                "id": "test-id",
                "changelog": [{"field": "title", "old": "Old", "new": "New"}],
            },
        }
        
        with patch.object(adapter, "_verify_signature", return_value=True):
            result = adapter.handle_webhook(payload, "test-signature")
            
            assert result is not None
            assert isinstance(result, OptimizationRequest)

    def test_handle_webhook_issue_updated_irrelevant(self, adapter):
        """Test handling Issue.updated with irrelevant changes."""
        payload = {
            "type": "Issue.updated",
            "data": {
                "id": "test-id",
                "changelog": [{"field": "status", "old": "Todo", "new": "In Progress"}],
            },
        }
        
        with patch.object(adapter, "_verify_signature", return_value=True):
            result = adapter.handle_webhook(payload, "test-signature")
            
            assert result is None  # Should ignore status-only changes

    def test_handle_webhook_invalid_event(self, adapter):
        """Test handling invalid event type."""
        payload = {
            "type": "Comment.created",
            "data": {"id": "test-id"},
        }
        
        with patch.object(adapter, "_verify_signature", return_value=True):
            result = adapter.handle_webhook(payload, "test-signature")
            
            assert result is None  # Should ignore irrelevant events

    def test_verify_signature(self, adapter):
        """Test HMAC signature verification."""
        import hmac
        import hashlib
        
        payload = {"test": "data"}
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        expected_sig = hmac.new(
            "test-secret".encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        
        result = adapter._verify_signature(payload, expected_sig)
        assert result is True
        
        # Test invalid signature
        result = adapter._verify_signature(payload, "invalid-signature")
        assert result is False

    def test_verify_signature_no_secret(self):
        """Test signature verification when no secret configured."""
        with patch("src.adapters.ingress.linear_ingress.settings") as mock_settings:
            mock_settings.linear_webhook_secret = ""
            adapter = LinearIngressAdapter()
            
            # Should return True in dev mode (no secret)
            result = adapter._verify_signature({}, "any-signature")
            assert result is True


class TestLiteLLMAdapter:
    """Tests for LiteLLMAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter instance."""
        with patch("src.adapters.llm.litellm_adapter.settings") as mock_settings:
            mock_settings.litellm_model = "gpt-4"
            mock_settings.openai_api_key = "test-key"
            mock_settings.embedding_model = "text-embedding-3-small"
            adapter = LiteLLMAdapter()
            return adapter

    @pytest.mark.asyncio
    async def test_chat_completion(self, adapter):
        """Test chat completion."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        
        # Mock at the run_in_executor level
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = MagicMock()
            mock_executor.run_in_executor = AsyncMock(return_value=mock_response)
            mock_loop.return_value = mock_executor
            
            messages = [{"role": "user", "content": "Test"}]
            result = await adapter.chat_completion(messages)
            
            assert result == "Test response"

    @pytest.mark.asyncio
    async def test_get_embedding(self, adapter):
        """Test embedding generation."""
        mock_response = [{"embedding": [0.1] * 1536}]
        
        # Mock at the run_in_executor level
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = MagicMock()
            mock_executor.run_in_executor = AsyncMock(return_value=mock_response)
            mock_loop.return_value = mock_executor
            
            result = await adapter.get_embedding("test text")
            
            assert isinstance(result, list)
            assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_chat_completion_retry(self, adapter):
        """Test retry logic on failure."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Success"
        
        call_count = 0
        
        async def mock_executor_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return mock_response
        
        # Mock at the run_in_executor level
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = MagicMock()
            mock_executor.run_in_executor = mock_executor_run
            mock_loop.return_value = mock_executor
            
            messages = [{"role": "user", "content": "Test"}]
            result = await adapter.chat_completion(messages)
            
            assert result == "Success"
            assert call_count >= 2  # Should retry


class TestTokenBucket:
    """Tests for TokenBucket rate limiter."""

    @pytest.mark.asyncio
    async def test_acquire_success(self):
        """Test successful token acquisition."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        
        # Should succeed immediately with tokens available
        await bucket.acquire()
        assert bucket.tokens < bucket.capacity

    @pytest.mark.asyncio
    async def test_acquire_wait(self):
        """Test waiting for token refill."""
        bucket = TokenBucket(capacity=1, refill_rate=10.0)  # Fast refill
        
        # Consume all tokens
        await bucket.acquire()
        
        # Next acquire should wait briefly then succeed
        import time
        start = time.time()
        await bucket.acquire()
        elapsed = time.time() - start
        
        # Should have waited for refill (at least 0.05 seconds)
        assert elapsed >= 0.05

    @pytest.mark.asyncio
    async def test_try_acquire_success(self):
        """Test try_acquire when tokens available."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        
        result = await bucket.try_acquire()
        assert result is True

    @pytest.mark.asyncio
    async def test_try_acquire_failure(self):
        """Test try_acquire when no tokens available."""
        bucket = TokenBucket(capacity=1, refill_rate=0.1)  # Slow refill
        
        # Consume token
        await bucket.acquire()
        
        # Should fail immediately
        result = await bucket.try_acquire()
        assert result is False

    def test_refill(self):
        """Test token refill mechanism."""
        import asyncio
        
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        bucket.tokens = 5.0
        
        async def test():
            await bucket._refill()
            # After refill, tokens should increase (or stay at capacity)
            assert bucket.tokens >= 5.0
        
        asyncio.run(test())
