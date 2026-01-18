"""Use cases for domain logic."""

import asyncio
from typing import Any, Dict

from src.cognitive_engine.graph import create_cognitive_graph
from src.cognitive_engine.state import CognitiveState
from src.domain.interfaces import IKnowledgeBase, IIssueTracker, ILLMProvider
from src.domain.schema import OptimizationRequest


class OptimizeArtifactUseCase:
    """Use case for optimizing an artifact using multi-agent debate."""

    def __init__(
        self,
        issue_tracker: IIssueTracker,
        knowledge_base: IKnowledgeBase,
        llm_provider: ILLMProvider,
    ):
        """Initialize use case with dependencies.

        Args:
            issue_tracker: Issue tracker adapter.
            knowledge_base: Knowledge base adapter.
            llm_provider: LLM provider adapter.
        """
        self.issue_tracker = issue_tracker
        self.knowledge_base = knowledge_base
        self.llm_provider = llm_provider

    async def execute(self, request: OptimizationRequest) -> Dict[str, Any]:
        """Execute the optimization workflow.

        Args:
            request: Optimization request.

        Returns:
            Result dictionary with execution status.
        """
        try:
            # Create cognitive graph
            graph = create_cognitive_graph(
                issue_tracker=self.issue_tracker,
                knowledge_base=self.knowledge_base,
                llm_provider=self.llm_provider,
            )

            # Initialize state
            initial_state = CognitiveState(request=request)
            state_dict = initial_state.model_dump()

            # Execute graph
            final_state_dict = await graph.ainvoke(state_dict)

            return {
                "success": True,
                "final_state": final_state_dict,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
