"""Workflow registry for versioned orchestration."""

from typing import Dict


class WorkflowRegistry:
    """Registry of workflow versions."""

    def __init__(self) -> None:
        self._versions: Dict[str, str] = {
            "optimization": "v1",
            "story_writing": "v1",
        }

    def get_version(self, workflow_name: str) -> str:
        """Get the active version for a workflow."""
        return self._versions.get(workflow_name, "v1")

    def register(self, workflow_name: str, version: str) -> None:
        """Register or update a workflow version."""
        self._versions[workflow_name] = version
