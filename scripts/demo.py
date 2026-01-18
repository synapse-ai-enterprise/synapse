"""Demo script for showcasing the Agentic AI PoC workflow.

This script demonstrates the multi-agent debate pattern without requiring
external API keys or services. It uses mock data to show the workflow.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.domain.schema import (
    CoreArtifact,
    NormalizedPriority,
    OptimizationRequest,
    WorkItemStatus,
)
from src.infrastructure.di import get_container
from src.utils.logger import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def safe_get(obj, key, default=None):
    """Safely get value from dict or Pydantic model."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    elif hasattr(obj, key):
        return getattr(obj, key, default)
    return default


def safe_get_nested(obj, *keys, default=None):
    """Safely get nested value from dict or Pydantic model."""
    current = obj
    for key in keys:
        if current is None:
            return default
        current = safe_get(current, key)
        if current is None:
            return default
    return current if current is not None else default


async def run_demo():
    """Run a demo of the optimization workflow with mock data."""
    print("=" * 80)
    print("Agentic AI PoC - Demo Workflow")
    print("=" * 80)
    print()

    # Create a mock optimization request
    print("📋 Creating optimization request...")
    request = OptimizationRequest(
        artifact_id="demo-issue-123",
        artifact_type="issue",
        source_system="linear",
        trigger="manual",
        dry_run=True,  # Always dry-run for demo
    )
    print(f"   ✓ Request created: {request.artifact_id}")
    print()

    # Create mock artifact
    print("📝 Creating mock Linear issue...")
    mock_artifact = CoreArtifact(
        source_system="linear",
        source_id="demo-123",
        human_ref="LIN-123",
        url="https://linear.app/demo/LIN-123",
        title="Implement user authentication",
        description="""
        As a user, I want to be able to log in to the application so that I can access my personal data.

        Acceptance Criteria:
        - User can register with email and password
        - User can log in with credentials
        - User can log out
        - Session persists across page refreshes
        """,
        type="Story",
        status=WorkItemStatus.TODO,
        priority=NormalizedPriority.HIGH,
    )
    print(f"   ✓ Mock artifact created: {mock_artifact.human_ref}")
    print(f"   Title: {mock_artifact.title}")
    print(f"   Priority: {mock_artifact.priority.value}")
    print()

    # Get dependencies from DI container
    print("🔧 Initializing dependencies...")
    container = get_container()
    
    try:
        llm_provider = container.get_llm_provider()
        print("   ✓ LLM provider initialized")
    except Exception as e:
        print(f"   ⚠️  LLM provider initialization failed: {e}")
        print("   Note: This is expected if OPENAI_API_KEY is not set")
        print("   The demo will show the workflow structure but cannot execute LLM calls")
        return

    # Create embedding function wrapper
    # LanceDBAdapter expects a sync function but runs it in executor
    # We need to create a sync wrapper that can call the async LLM provider
    # Since the executor will run in a thread, we can create a new event loop there
    def sync_embedding_fn(text: str) -> list[float]:
        """Synchronous wrapper for embedding function.
        
        This is called from a thread executor, so we can safely create a new event loop.
        """
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(llm_provider.get_embedding(text))
            # Validate result
            if not result or len(result) == 0:
                raise ValueError(f"Embedding function returned empty result for text: {text[:100]}")
            return result
        except Exception as e:
            # Log error for debugging
            print(f"   ⚠️  Embedding error: {e}")
            raise
        finally:
            loop.close()

    try:
        knowledge_base = container.get_knowledge_base(sync_embedding_fn)
        # Initialize database asynchronously
        await knowledge_base.initialize_db()
        print("   ✓ Knowledge base initialized")
    except Exception as e:
        print(f"   ⚠️  Knowledge base initialization failed: {e}")
        print("   Note: This may fail if vector store is not initialized")
        knowledge_base = None

    # Use mock issue tracker for demo to avoid Linear API calls
    from src.adapters.egress.mock_issue_tracker import MockIssueTracker
    
    issue_tracker = MockIssueTracker(mock_artifact=mock_artifact)
    print("   ✓ Issue tracker initialized (mock mode for demo)")

    print()

    # Show workflow steps
    print("🔄 Multi-Agent Debate Workflow:")
    print("   1. Ingress: Load artifact from Linear")
    print("   2. Context Assembly: Retrieve relevant knowledge from RAG")
    print("   3. Drafting: Product Owner Agent drafts optimized artifact")
    print("   4. QA Critique: QA Agent validates against INVEST criteria")
    print("   5. Developer Critique: Developer Agent assesses technical feasibility")
    print("   6. Synthesis: Product Owner Agent synthesizes feedback")
    print("   7. Validation: Check confidence and INVEST violations")
    print("   8. Execution: Update Linear issue (if confidence high)")
    print()

    # Check if we can actually run the workflow
    if not settings.openai_api_key:
        print("⚠️  OPENAI_API_KEY not set. Cannot execute full workflow.")
        print()
        print("To run the full demo:")
        print("1. Set OPENAI_API_KEY in your .env file")
        print("2. Optionally set LINEAR_API_KEY for real Linear integration")
        print("3. Run: python scripts/demo.py")
        print()
        print("For now, showing workflow structure only...")
        return

    # Execute use case
    print("🚀 Executing optimization workflow...")
    print()

    from src.domain.use_cases import OptimizeArtifactUseCase

    use_case = OptimizeArtifactUseCase(
        issue_tracker=issue_tracker,
        knowledge_base=knowledge_base,
        llm_provider=llm_provider,
    )

    try:
        result = await use_case.execute(request)

        if result["success"]:
            final_state = result.get("final_state", {})
            
            # Display initial artifact
            print("\n" + "=" * 80)
            print("📋 INITIAL ARTIFACT")
            print("=" * 80)
            artifact = final_state.get("current_artifact")
            if artifact:
                # Handle both dict and Pydantic model
                title = safe_get(artifact, "title", "N/A")
                artifact_type = safe_get(artifact, "type", "N/A")
                priority = safe_get(artifact, "priority")
                if priority:
                    # Handle NormalizedPriority enum
                    if isinstance(priority, NormalizedPriority):
                        priority_str = priority.value
                    elif isinstance(priority, dict):
                        priority_str = priority.get("value", str(priority))
                    else:
                        priority_str = str(priority)
                else:
                    priority_str = "N/A"
                
                print(f"\nTitle: {title}")
                print(f"Type: {artifact_type}")
                print(f"Priority: {priority_str}")
                print(f"\nDescription:")
                desc = safe_get(artifact, "description", "")
                if desc:
                    for line in str(desc).split("\n"):
                        print(f"  {line}")
                acceptance_criteria = safe_get(artifact, "acceptance_criteria", [])
                if acceptance_criteria:
                    print(f"\nAcceptance Criteria:")
                    for ac in acceptance_criteria:
                        print(f"  • {ac}")
            
            # Display retrieved context
            print("\n" + "=" * 80)
            print("🔍 RETRIEVED CONTEXT (RAG)")
            print("=" * 80)
            context = final_state.get("retrieved_context", [])
            if context:
                print(f"\nFound {len(context)} relevant knowledge units:")
                for i, unit in enumerate(context[:5], 1):  # Show first 5
                    source = safe_get(unit, "source", "unknown")
                    location = safe_get(unit, "location", "N/A")
                    summary = safe_get(unit, "summary", "")
                    print(f"\n  {i}. Source: {source}")
                    print(f"     Location: {location}")
                    if summary:
                        print(f"     Summary: {str(summary)[:200]}...")
            else:
                print("\n  No context retrieved from knowledge base.")
            
            # Display debate iterations
            debate_history = final_state.get("debate_history", [])
            if debate_history:
                print("\n" + "=" * 80)
                print("💬 MULTI-AGENT DEBATE ITERATIONS")
                print("=" * 80)
                
                for idx, entry in enumerate(debate_history, 1):
                    print(f"\n{'─' * 80}")
                    print(f"ITERATION {entry.get('iteration', idx)}")
                    print(f"{'─' * 80}")
                    
                    # Draft artifact
                    draft = entry.get("draft", {})
                    print(f"\n📝 PO Agent Draft:")
                    draft_title = safe_get(draft, "title", "N/A")
                    print(f"   Title: {draft_title}")
                    desc = safe_get(draft, "description", "")
                    if desc:
                        print(f"   Description: {str(desc)[:300]}...")
                    draft_ac = safe_get(draft, "acceptance_criteria", [])
                    if draft_ac:
                        print(f"   Acceptance Criteria:")
                        for ac in draft_ac[:3]:
                            print(f"     • {ac}")
                    
                    # QA Critique
                    qa_critique = entry.get("qa_critique", "")
                    if qa_critique:
                        print(f"\n🔍 QA Agent Critique:")
                        # Show first 400 chars of critique
                        critique_lines = qa_critique.split("\n")
                        for line in critique_lines[:15]:  # Show first 15 lines
                            print(f"   {line}")
                        if len(critique_lines) > 15:
                            print(f"   ... ({len(critique_lines) - 15} more lines)")
                    
                    # INVEST Violations
                    violations = entry.get("invest_violations", [])
                    if violations:
                        print(f"\n⚠️  INVEST Violations ({len(violations)}):")
                        for violation in violations[:5]:  # Show first 5
                            print(f"   • {violation}")
                    
                    # Developer Critique
                    dev_critique = entry.get("developer_critique", "")
                    if dev_critique:
                        print(f"\n👨‍💻 Developer Agent Critique:")
                        critique_lines = dev_critique.split("\n")
                        for line in critique_lines[:15]:  # Show first 15 lines
                            print(f"   {line}")
                        if len(critique_lines) > 15:
                            print(f"   ... ({len(critique_lines) - 15} more lines)")
                    
                    # Refined artifact
                    refined = entry.get("refined", {})
                    if refined:
                        print(f"\n✨ PO Agent Refinement:")
                        refined_title = safe_get(refined, "title", "N/A")
                        print(f"   Title: {refined_title}")
                        desc = safe_get(refined, "description", "")
                        if desc:
                            print(f"   Description: {str(desc)[:300]}...")
                        refined_ac = safe_get(refined, "acceptance_criteria", [])
                        if refined_ac:
                            print(f"   Acceptance Criteria:")
                            for ac in refined_ac[:3]:
                                print(f"     • {ac}")
                    
                    # Confidence score
                    confidence = entry.get("confidence_score", 0.0)
                    print(f"\n📊 Confidence Score: {confidence:.2f}")
            
            # Final summary
            print("\n" + "=" * 80)
            print("✅ FINAL SUMMARY")
            print("=" * 80)
            print(f"\n   - Total Iterations: {final_state.get('iteration_count', 0)}")
            print(f"   - Final Confidence: {final_state.get('confidence_score', 0.0):.2f}")
            violations = final_state.get("invest_violations", [])
            if violations:
                print(f"   - Final INVEST Violations: {len(violations)}")
                for violation in violations:
                    print(f"     • {violation}")
            else:
                print("   - Final INVEST Violations: None ✓")
            
            # Show final artifact
            refined_artifact = final_state.get("refined_artifact") or final_state.get("draft_artifact")
            if refined_artifact:
                final_title = safe_get(refined_artifact, "title", "N/A")
                print(f"\n   Final Artifact Title: {final_title}")
        else:
            error_msg = result.get('error', 'Unknown error')
            print(f"❌ Optimization failed: {error_msg}")
            if 'traceback' in result:
                print("\nFull traceback:")
                print(result['traceback'])

    except Exception as e:
        print(f"❌ Error during execution: {e}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()

    print()
    print("=" * 80)
    print("Demo complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_demo())
