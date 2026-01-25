"""Use cases for domain logic."""

from typing import Any, Dict, Optional

from src.cognitive_engine.graph import create_cognitive_graph
from src.cognitive_engine.state import CognitiveState
from src.domain.interfaces import IKnowledgeBase, IIssueTracker, ILLMProvider, IProgressCallback
from src.domain.schema import OptimizationRequest


class OptimizeArtifactUseCase:
    """Use case for optimizing an artifact using multi-agent debate."""

    def __init__(
        self,
        issue_tracker: IIssueTracker,
        knowledge_base: IKnowledgeBase,
        llm_provider: ILLMProvider,
        progress_callback: Optional[IProgressCallback] = None,
    ):
        """Initialize use case with dependencies.

        Args:
            issue_tracker: Issue tracker adapter.
            knowledge_base: Knowledge base adapter.
            llm_provider: LLM provider adapter.
            progress_callback: Optional progress callback for real-time updates.
        """
        self.issue_tracker = issue_tracker
        self.knowledge_base = knowledge_base
        self.llm_provider = llm_provider
        self.progress_callback = progress_callback

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

            # Execute graph with streaming for real-time updates
            if self.progress_callback:
                # Use streaming to get real-time updates
                final_state_dict = None
                async for event in graph.astream(state_dict):
                    # LangGraph streams events as dicts with node names as keys
                    # Each event contains the state after that node executes
                    for node_name, node_state in event.items():
                        if node_name != "__end__":
                            # Notify callback of node start (before execution)
                            # Note: We don't have pre-execution state, so we use current state
                            await self.progress_callback.on_node_start(node_name, node_state)
                            
                            # Notify callback of node completion
                            await self.progress_callback.on_node_complete(node_name, node_state)
                            
                            # Check for iteration updates
                            iteration = node_state.get("iteration_count", 0)
                            debate_history = node_state.get("debate_history", [])
                            if iteration > 0 and debate_history:
                                await self.progress_callback.on_iteration_update(iteration, node_state)
                            
                            # Track final state
                            final_state_dict = node_state
                
                # If no events were streamed, fall back to ainvoke
                if final_state_dict is None:
                    final_state_dict = await graph.ainvoke(state_dict)
            else:
                # No callback, use standard execution
                final_state_dict = await graph.ainvoke(state_dict)

            return {
                "success": True,
                "final_state": final_state_dict,
            }

        except Exception as e:
            import traceback
            error_details = {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
            return error_details