"""Linear API egress adapter implementing IIssueTracker."""

import asyncio
from typing import Optional

import aiohttp

from src.config import settings
from src.domain.interfaces import IIssueTracker
from src.domain.schema import CoreArtifact, NormalizedPriority, WorkItemStatus
from src.adapters.rate_limiter import TokenBucket


class LinearEgressAdapter(IIssueTracker):
    """Linear egress adapter with GraphQL API, optimistic locking, and rate limiting."""

    def __init__(self):
        """Initialize adapter with rate limiter."""
        self.api_key = settings.linear_api_key
        self.team_id = settings.linear_team_id
        self.dry_run = settings.dry_run
        self.mode = settings.mode
        self.require_approval_label = settings.require_approval_label

        # Token Bucket: 1400 requests/hour = ~0.39 requests/second
        # Capacity: 1400 tokens, refill: 0.39 tokens/second
        self.rate_limiter = TokenBucket(capacity=1400, refill_rate=0.39)

        self.base_url = "https://api.linear.app/graphql"
        self.headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

    async def get_issue(self, issue_id: str) -> CoreArtifact:
        """Fetch an issue by ID.

        Args:
            issue_id: Linear issue ID (UUID).

        Returns:
            CoreArtifact representation of the issue.

        Raises:
            ValueError: If API call fails.
        """
        await self.rate_limiter.acquire()

        query = """
        query GetIssue($id: String!) {
            issue(id: $id) {
                id
                identifier
                title
                description
                priority
                state {
                    name
                    type
                }
                type
                url
                updatedAt
                createdAt
                parent {
                    id
                    identifier
                }
            }
        }
        """

        variables = {"id": issue_id}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url,
                json={"query": query, "variables": variables},
                headers=self.headers,
            ) as response:
                if response.status != 200:
                    raise ValueError(f"Linear API error: {response.status}")

                data = await response.json()
                if "errors" in data:
                    raise ValueError(f"GraphQL errors: {data['errors']}")

                issue_data = data["data"]["issue"]
                if not issue_data:
                    raise ValueError(f"Issue {issue_id} not found")

                return self._map_to_artifact(issue_data)

    async def update_issue(self, issue_id: str, artifact: CoreArtifact) -> bool:
        """Update an issue with optimistic locking.

        Args:
            issue_id: Linear issue ID.
            artifact: Updated artifact.

        Returns:
            True if successful.
        """
        if self.dry_run:
            # Shadow mode: log but don't update
            return True

        if self.mode == "comment_only":
            # Comment-only mode: post as comment
            comment = self._format_optimization_comment(artifact)
            return await self.post_comment(issue_id, comment)

        # Fetch current state for optimistic locking
        current = await self.get_issue(issue_id)
        original_updated_at = current.raw_metadata.get("updatedAt")

        # Re-fetch before write to check for conflicts
        current_after = await self.get_issue(issue_id)
        if current_after.raw_metadata.get("updatedAt") != original_updated_at:
            # Conflict detected - post as comment instead
            comment = f"""🤖 AI Optimization Prepared

I prepared an optimization, but the ticket was edited while I was working. Please review my suggestions:

{self._format_optimization_comment(artifact)}
"""
            return await self.post_comment(issue_id, comment)

        # No conflict - proceed with update
        return await self._execute_update(issue_id, artifact)

    async def create_issue(self, artifact: CoreArtifact) -> str:
        """Create a new issue.

        Args:
            artifact: Artifact to create.

        Returns:
            Issue URL.
        """
        if self.dry_run:
            return "dry-run://issue"

        await self.rate_limiter.acquire()

        mutation = """
        mutation CreateIssue($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                    url
                }
            }
        }
        """

        # Map priority
        priority_map = {
            NormalizedPriority.CRITICAL: 1,
            NormalizedPriority.HIGH: 2,
            NormalizedPriority.MEDIUM: 3,
            NormalizedPriority.LOW: 4,
            NormalizedPriority.NONE: 0,
        }

        input_data = {
            "teamId": self.team_id,
            "title": artifact.title,
            "description": artifact.description,
            "priority": priority_map.get(artifact.priority, 0),
        }

        if artifact.parent_ref:
            # Extract parent ID from reference
            parent_id = artifact.parent_ref
            input_data["parentId"] = parent_id

        variables = {"input": input_data}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url,
                json={"query": mutation, "variables": variables},
                headers=self.headers,
            ) as response:
                if response.status != 200:
                    raise ValueError(f"Linear API error: {response.status}")

                data = await response.json()
                if "errors" in data:
                    raise ValueError(f"GraphQL errors: {data['errors']}")

                issue = data["data"]["issueCreate"]["issue"]
                issue_url = issue["url"]

                # Add approval label if required
                if self.require_approval_label and self.mode == "autonomous":
                    await self._add_label(issue["id"], self.require_approval_label)

                return issue_url

    async def post_comment(self, issue_id: str, comment: str) -> bool:
        """Post a comment to an issue.

        Args:
            issue_id: Linear issue ID.
            comment: Comment text.

        Returns:
            True if successful.
        """
        if self.dry_run:
            return True

        await self.rate_limiter.acquire()

        mutation = """
        mutation CreateComment($input: CommentCreateInput!) {
            commentCreate(input: $input) {
                success
            }
        }
        """

        variables = {
            "input": {
                "issueId": issue_id,
                "body": comment,
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url,
                json={"query": mutation, "variables": variables},
                headers=self.headers,
            ) as response:
                if response.status != 200:
                    return False

                data = await response.json()
                return "errors" not in data and data.get("data", {}).get("commentCreate", {}).get("success", False)

    async def _execute_update(self, issue_id: str, artifact: CoreArtifact) -> bool:
        """Execute the actual update mutation.

        Args:
            issue_id: Linear issue ID.
            artifact: Updated artifact.

        Returns:
            True if successful.
        """
        await self.rate_limiter.acquire()

        mutation = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
            }
        }
        """

        priority_map = {
            NormalizedPriority.CRITICAL: 1,
            NormalizedPriority.HIGH: 2,
            NormalizedPriority.MEDIUM: 3,
            NormalizedPriority.LOW: 4,
            NormalizedPriority.NONE: 0,
        }

        input_data = {
            "title": artifact.title,
            "description": artifact.description,
            "priority": priority_map.get(artifact.priority, 0),
        }

        variables = {"id": issue_id, "input": input_data}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url,
                json={"query": mutation, "variables": variables},
                headers=self.headers,
            ) as response:
                if response.status != 200:
                    return False

                data = await response.json()
                success = "errors" not in data and data.get("data", {}).get("issueUpdate", {}).get("success", False)

                # Add approval label if required
                if success and self.require_approval_label and self.mode == "autonomous":
                    await self._add_label(issue_id, self.require_approval_label)

                return success

    async def _add_label(self, issue_id: str, label_name: str) -> None:
        """Add a label to an issue.

        Args:
            issue_id: Linear issue ID.
            label_name: Label name to add.
        """
        # First, get team labels to find label ID
        query = """
        query GetTeamLabels($teamId: String!) {
            team(id: $teamId) {
                labels {
                    nodes {
                        id
                        name
                    }
                }
            }
        }
        """

        variables = {"teamId": self.team_id}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url,
                json={"query": query, "variables": variables},
                headers=self.headers,
            ) as response:
                if response.status != 200:
                    return

                data = await response.json()
                if "errors" in data:
                    return

                labels = data.get("data", {}).get("team", {}).get("labels", {}).get("nodes", [])
                label_id = None
                for label in labels:
                    if label["name"] == label_name:
                        label_id = label["id"]
                        break

                if not label_id:
                    return  # Label doesn't exist

                # Add label to issue
                mutation = """
                mutation AddLabel($issueId: String!, $labelId: String!) {
                    issueUpdate(id: $issueId, input: {labelIds: [$labelId]}) {
                        success
                    }
                }
                """

                variables = {"issueId": issue_id, "labelId": label_id}
                await session.post(
                    self.base_url,
                    json={"query": mutation, "variables": variables},
                    headers=self.headers,
                )

    def _map_to_artifact(self, issue_data: dict) -> CoreArtifact:
        """Map Linear issue data to CoreArtifact.

        Args:
            issue_data: Linear issue data from GraphQL.

        Returns:
            CoreArtifact instance.
        """
        # Map priority
        priority_map = {
            1: NormalizedPriority.CRITICAL,
            2: NormalizedPriority.HIGH,
            3: NormalizedPriority.MEDIUM,
            4: NormalizedPriority.LOW,
            0: NormalizedPriority.NONE,
        }

        # Map status
        state_type = issue_data.get("state", {}).get("type", "").lower()
        status_map = {
            "unstarted": WorkItemStatus.TODO,
            "started": WorkItemStatus.IN_PROGRESS,
            "completed": WorkItemStatus.DONE,
            "canceled": WorkItemStatus.CANCELLED,
        }

        parent_ref = None
        if issue_data.get("parent"):
            parent_ref = issue_data["parent"].get("identifier")

        return CoreArtifact(
            source_system="linear",
            source_id=issue_data["id"],
            human_ref=issue_data.get("identifier", ""),
            url=issue_data.get("url", ""),
            title=issue_data.get("title", ""),
            description=issue_data.get("description") or "",
            acceptance_criteria=[],  # Extract from description if needed
            type=issue_data.get("type", "Story"),
            status=status_map.get(state_type, WorkItemStatus.TODO),
            priority=priority_map.get(issue_data.get("priority", 0), NormalizedPriority.NONE),
            parent_ref=parent_ref,
            raw_metadata={
                "updatedAt": issue_data.get("updatedAt"),
                "createdAt": issue_data.get("createdAt"),
            },
        )

    def _format_optimization_comment(self, artifact: CoreArtifact) -> str:
        """Format artifact as optimization comment.

        Args:
            artifact: Artifact to format.

        Returns:
            Formatted comment string.
        """
        ac_text = "\n".join(f"- {ac}" for ac in artifact.acceptance_criteria) if artifact.acceptance_criteria else "None specified"

        return f"""🤖 AI Optimization Suggestion

**Proposed Title:** {artifact.title}

**Proposed Description:**
{artifact.description}

**Acceptance Criteria:**
{ac_text}

---
*Review and apply manually if approved.*"""
