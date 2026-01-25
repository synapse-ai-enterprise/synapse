"""Linear webhook ingress adapter."""

import hashlib
import hmac
from typing import Dict, Mapping, Optional

from src.config import settings
from src.domain.schema import OptimizationRequest


class LinearIngressAdapter:
    """Linear ingress adapter for webhook handling."""

    def __init__(self):
        """Initialize adapter with webhook secret."""
        self.webhook_secret = settings.linear_webhook_secret
        self.source_system = settings.webhook_provider.strip().lower()

    def handle_webhook(
        self,
        payload: Dict,
        headers: Mapping[str, str],
    ) -> Optional[OptimizationRequest]:
        """Handle Linear webhook with HMAC verification.

        Args:
            payload: Webhook payload dictionary.
            headers: Request headers containing Linear signature.

        Returns:
            OptimizationRequest if event is relevant, None otherwise.

        Raises:
            ValueError: If signature verification fails.
        """
        signature = self._extract_signature(headers)

        # Verify signature
        if not self._verify_signature(payload, signature):
            raise ValueError("Invalid webhook signature")

        # Extract event type
        event_type = payload.get("type")
        if event_type not in ["Issue.created", "Issue.updated"]:
            return None  # Ignore irrelevant events

        # For Issue.updated, check if description/title changed
        if event_type == "Issue.updated":
            changelog = payload.get("data", {}).get("changelog", [])
            relevant_fields = ["title", "description"]
            if not any(c.get("field") in relevant_fields for c in changelog):
                return None  # Skip status-only updates

        # Normalize to OptimizationRequest
        issue_data = payload.get("data", {})
        return OptimizationRequest(
            artifact_id=issue_data.get("id", ""),
            artifact_type="issue",
            source_system=self.source_system,
            trigger="webhook",
            dry_run=settings.dry_run,
        )

    def _extract_signature(self, headers: Mapping[str, str]) -> str:
        """Extract Linear signature from request headers.

        Args:
            headers: Request headers.

        Returns:
            Signature string if present, otherwise empty string.
        """
        for key, value in headers.items():
            if key.lower() == "linear-signature":
                return value
        return ""

    def _verify_signature(self, payload: Dict, signature: str) -> bool:
        """Verify HMAC-SHA256 signature.

        Args:
            payload: Webhook payload.
            signature: Signature from header.

        Returns:
            True if signature is valid.
        """
        if not self.webhook_secret:
            # If no secret configured, skip verification (dev mode)
            return True

        # Convert payload to bytes
        import json
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")

        # Compute expected signature
        expected_signature = hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison
        return hmac.compare_digest(expected_signature, signature)
