"""Mock issue tracker for demos and testing."""

from typing import Optional

from src.domain.interfaces import IIssueTracker
from src.domain.schema import CoreArtifact


class MockIssueTracker(IIssueTracker):
    """Mock issue tracker that returns predefined artifacts without API calls."""

    def __init__(self, mock_artifact: Optional[CoreArtifact] = None):
        """Initialize mock tracker with optional artifact.

        Args:
            mock_artifact: Artifact to return for get_issue calls.
        """
        self.mock_artifact = mock_artifact
        self._update_calls: list[tuple[str, CoreArtifact]] = []
        self._comment_calls: list[tuple[str, str]] = []

    async def get_issue(self, issue_id: str) -> CoreArtifact:
        """Return mock artifact.

        Args:
            issue_id: Issue ID (ignored, returns mock artifact).

        Returns:
            Mock artifact.
        """
        if self.mock_artifact:
            return self.mock_artifact
        raise ValueError(f"Mock artifact not set for issue {issue_id}")

    async def update_issue(self, issue_id: str, artifact: CoreArtifact) -> bool:
        """Mock update - just records the call.

        Args:
            issue_id: Issue ID.
            artifact: Artifact to update.

        Returns:
            True (always succeeds in mock).
        """
        self._update_calls.append((issue_id, artifact))
        return True

    async def create_issue(self, artifact: CoreArtifact) -> str:
        """Mock create - returns fake URL.

        Args:
            artifact: Artifact to create.

        Returns:
            Fake issue URL.
        """
        return f"mock://issue/{artifact.source_id}"

    async def post_comment(self, issue_id: str, comment: str) -> bool:
        """Mock comment - just records the call.

        Args:
            issue_id: Issue ID.
            comment: Comment text.

        Returns:
            True (always succeeds in mock).
        """
        self._comment_calls.append((issue_id, comment))
        return True
