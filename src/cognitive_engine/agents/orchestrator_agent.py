"""Orchestrator Agent for Product Story Writing AI."""

from typing import Dict

from src.domain.schema import OrchestratorDecision, StoryWritingRequest


class OrchestratorAgent:
    """Central coordinator for module routing and flow control."""

    def decide_next_action(self, state: Dict) -> OrchestratorDecision:
        """Decide next action based on request and state.

        Args:
            state: Current story writing state dictionary.

        Returns:
            OrchestratorDecision indicating the next action.
        """
        request = StoryWritingRequest(**state["request"])

        if request.flow == "epic_to_stories":
            if not request.epic_text:
                return OrchestratorDecision(
                    next_action="end",
                    reasoning="Epic text missing; cannot generate stories.",
                )
            if not state.get("epic_analysis"):
                return OrchestratorDecision(
                    next_action="epic_analysis",
                    reasoning="Run epic analysis before applying splitting strategies.",
                )
            if not state.get("splitting_recommendations"):
                return OrchestratorDecision(
                    next_action="splitting_strategy",
                    reasoning="Generate splitting strategy recommendations after epic analysis.",
                )
            if not state.get("generated_stories"):
                if state.get("metadata", {}).get("story_generation_complete"):
                    return OrchestratorDecision(
                        next_action="end",
                        reasoning="Story generation completed with no results.",
                    )
                return OrchestratorDecision(
                    next_action="story_generation",
                    reasoning="Generate candidate stories from selected techniques.",
                )
            return OrchestratorDecision(
                next_action="end",
                reasoning="Module 1 complete with generated stories.",
            )

        if request.flow == "story_to_detail":
            if not request.story_text:
                return OrchestratorDecision(
                    next_action="end",
                    reasoning="Story text missing; cannot detail story.",
                )
            if not state.get("template_schema"):
                return OrchestratorDecision(
                    next_action="template_parser",
                    reasoning="Parse story template before detailing.",
                )
            if not state.get("retrieved_context"):
                if state.get("metadata", {}).get("knowledge_retrieval_skipped"):
                    return OrchestratorDecision(
                        next_action="end",
                        reasoning="Knowledge retrieval skipped due to missing story text.",
                    )
                return OrchestratorDecision(
                    next_action="knowledge_retrieval",
                    reasoning="Gather context before writing story details.",
                )
            if not state.get("populated_story"):
                return OrchestratorDecision(
                    next_action="story_writer",
                    reasoning="Populate story template using retrieved knowledge.",
                )
            if not state.get("validation_results"):
                return OrchestratorDecision(
                    next_action="validation",
                    reasoning="Validate story quality and detect gaps.",
                )
            critique_complete = state.get("metadata", {}).get("critique_completed")
            if not critique_complete and not state.get("critique_history"):
                return OrchestratorDecision(
                    next_action="critique_loop",
                    reasoning="Run critique loop after validation to refine story quality.",
                )

            # Always generate split proposals after critique to provide splitting options
            split_completed = state.get("metadata", {}).get("split_completed")
            if critique_complete and not split_completed:
                return OrchestratorDecision(
                    next_action="split_proposal",
                    reasoning="Generate split proposals for story after critique loop.",
                )

            return OrchestratorDecision(
                next_action="end",
                reasoning="Module 2 complete with validated story and split proposals.",
            )

        return OrchestratorDecision(
            next_action="end",
            reasoning="Unsupported flow or insufficient context provided.",
        )
