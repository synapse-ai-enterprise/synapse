"""Demo script for showcasing the Agentic AI PoC workflow.

This script demonstrates the multi-agent debate pattern without requiring
external API keys or services. It uses mock data to show the workflow.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.domain.interfaces import IProgressCallback
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


class DualOutputWriter:
    """Writer that outputs to both console and file."""
    
    def __init__(self, log_file_path: Path):
        """Initialize dual output writer.
        
        Args:
            log_file_path: Path to log file.
        """
        self.log_file_path = log_file_path
        self.log_file = open(log_file_path, "w", encoding="utf-8")
        self.write(f"Demo Log File - Started at {datetime.now().isoformat()}\n")
        self.write("=" * 100 + "\n\n")
    
    def write(self, text: str, to_console: bool = True):
        """Write text to both file and optionally console.
        
        Args:
            text: Text to write.
            to_console: Whether to also print to console.
        """
        if to_console:
            print(text, end="", flush=True)
        self.log_file.write(text)
        self.log_file.flush()
    
    def writeln(self, text: str = "", to_console: bool = True):
        """Write line to both file and optionally console.
        
        Args:
            text: Text to write.
            to_console: Whether to also print to console.
        """
        self.write(text + "\n", to_console)
    
    def write_section(self, title: str, to_console: bool = True):
        """Write a section header.
        
        Args:
            title: Section title.
            to_console: Whether to also print to console.
        """
        self.writeln("", to_console)
        self.writeln("=" * 100, to_console)
        self.writeln(title, to_console)
        self.writeln("=" * 100, to_console)
        self.writeln("", to_console)
    
    def write_state_dump(self, state: Dict, title: str = "State Dump", to_console: bool = False):
        """Write full state dump to file.
        
        Args:
            state: State dictionary to dump.
            title: Title for the dump section.
            to_console: Whether to also print to console.
        """
        self.write_section(title, to_console)
        try:
            # Convert state to JSON-serializable format
            serializable_state = {}
            for key, value in state.items():
                try:
                    # Try to serialize
                    json.dumps(value)
                    serializable_state[key] = value
                except (TypeError, ValueError):
                    # If not serializable, convert to string
                    serializable_state[key] = str(value)
            
            self.writeln(json.dumps(serializable_state, indent=2, default=str), to_console)
        except Exception as e:
            self.writeln(f"Error serializing state: {e}", to_console)
            self.writeln(str(state), to_console)
        self.writeln("", to_console)
    
    def close(self):
        """Close the log file."""
        self.writeln("", False)
        self.writeln("=" * 100, False)
        self.writeln(f"Demo Log File - Completed at {datetime.now().isoformat()}", False)
        self.log_file.close()


class DemoProgressCallback:
    """Progress callback implementation for demo visualization."""

    def __init__(self, log_writer: Optional[DualOutputWriter] = None):
        """Initialize progress callback.
        
        Args:
            log_writer: Optional dual output writer for file logging.
        """
        self.current_iteration = 0
        self.seen_iterations = set()
        self.log_writer = log_writer
        self.node_descriptions = {
            "ingress": "📥 Loading artifact from issue tracker",
            "context_assembly": "🔍 Retrieving relevant knowledge from RAG",
            "drafting": "📝 Product Owner Agent drafting optimized artifact",
            "qa_critique": "🔍 QA Agent validating against INVEST criteria",
            "developer_critique": "👨‍💻 Developer Agent assessing technical feasibility",
            "synthesis": "✨ Product Owner Agent synthesizing feedback",
            "validation": "✅ Validating confidence and INVEST violations",
            "execution": "🚀 Updating issue tracker",
        }

    async def on_node_start(self, node_name: str, state: Dict) -> None:
        """Called when a node starts execution."""
        description = self.node_descriptions.get(node_name, f"⚙️  Executing {node_name}")
        text = f"\n{description}..."
        if self.log_writer:
            self.log_writer.write(text)
            self.log_writer.write_section(f"Node: {node_name} - START", to_console=False)
            self.log_writer.write_state_dump(state, f"State at {node_name} start", to_console=False)
        else:
            print(text, end="", flush=True)

    async def on_node_complete(self, node_name: str, state: Dict) -> None:
        """Called when a node completes execution."""
        text = " ✓"
        if self.log_writer:
            self.log_writer.write(text)
        else:
            print(text, flush=True)
        
        # Show special updates for key nodes
        if node_name == "context_assembly":
            context = state.get("retrieved_context", [])
            if context:
                text = f"   → Found {len(context)} relevant knowledge units"
                if self.log_writer:
                    self.log_writer.writeln(text)
                    # Log full context details to file
                    self.log_writer.write_section(f"Retrieved Context Details ({len(context)} units)", to_console=False)
                    for i, unit in enumerate(context, 1):
                        self.log_writer.writeln(f"\nUnit {i}:", to_console=False)
                        self.log_writer.writeln(json.dumps(unit.model_dump() if hasattr(unit, 'model_dump') else unit, indent=2, default=str), to_console=False)
                else:
                    print(text)
        
        elif node_name == "drafting":
            draft = state.get("draft_artifact")
            if draft:
                title = safe_get(draft, "title", "N/A")
                ac_count = len(safe_get(draft, "acceptance_criteria", []))
                text = f"   → Draft: {title[:60]}... ({ac_count} ACs)"
                if self.log_writer:
                    self.log_writer.writeln(text)
                    # Log full draft to file
                    self.log_writer.write_section("Draft Artifact (Full Details)", to_console=False)
                    if hasattr(draft, 'model_dump'):
                        self.log_writer.writeln(json.dumps(draft.model_dump(), indent=2, default=str), to_console=False)
                    else:
                        self.log_writer.writeln(json.dumps(draft, indent=2, default=str), to_console=False)
                else:
                    print(text)
        
        elif node_name == "qa_critique":
            violations = state.get("invest_violations", [])
            structured_violations = state.get("structured_qa_violations", [])
            violation_count = len(violations)
            if violation_count > 0:
                text = f"   → Found {violation_count} INVEST violation(s)"
            else:
                text = f"   → No INVEST violations ✓"
            if self.log_writer:
                self.log_writer.writeln(text)
                # Log full QA critique to file
                self.log_writer.write_section("QA Critique (Full Details)", to_console=False)
                qa_critique = state.get("qa_critique", "")
                if qa_critique:
                    self.log_writer.writeln("Critique Text:", to_console=False)
                    self.log_writer.writeln(qa_critique, to_console=False)
                self.log_writer.writeln(f"\nQA Confidence: {state.get('qa_confidence', 'N/A')}", to_console=False)
                self.log_writer.writeln(f"QA Assessment: {state.get('qa_overall_assessment', 'N/A')}", to_console=False)
                self.log_writer.writeln(f"\nViolations (String): {len(violations)}", to_console=False)
                for v in violations:
                    self.log_writer.writeln(f"  - {v}", to_console=False)
                self.log_writer.writeln(f"\nStructured Violations: {len(structured_violations)}", to_console=False)
                for sv in structured_violations:
                    if hasattr(sv, 'model_dump'):
                        self.log_writer.writeln(json.dumps(sv.model_dump(), indent=2, default=str), to_console=False)
                    else:
                        self.log_writer.writeln(json.dumps(sv, indent=2, default=str), to_console=False)
            else:
                print(text)
        
        elif node_name == "developer_critique":
            critique = state.get("developer_critique", "")
            if critique:
                # Extract key point from critique
                lines = critique.split("\n")
                key_line = next((line for line in lines if line.strip() and len(line.strip()) > 20), "")
                if key_line:
                    text = f"   → {key_line[:70]}..."
                    if self.log_writer:
                        self.log_writer.writeln(text)
                        # Log full developer critique to file
                        self.log_writer.write_section("Developer Critique (Full Details)", to_console=False)
                        self.log_writer.writeln(critique, to_console=False)
                        self.log_writer.writeln(f"\nDeveloper Confidence: {state.get('developer_confidence', 'N/A')}", to_console=False)
                        self.log_writer.writeln(f"Developer Feasibility: {state.get('developer_feasibility', 'N/A')}", to_console=False)
                    else:
                        print(text)
        
        elif node_name == "synthesis":
            refined = state.get("refined_artifact")
            if refined:
                title = safe_get(refined, "title", "N/A")
                text = f"   → Synthesized: {title[:60]}..."
                if self.log_writer:
                    self.log_writer.writeln(text)
                    # Log full refined artifact to file
                    self.log_writer.write_section("Refined Artifact (Full Details)", to_console=False)
                    if hasattr(refined, 'model_dump'):
                        self.log_writer.writeln(json.dumps(refined.model_dump(), indent=2, default=str), to_console=False)
                    else:
                        self.log_writer.writeln(json.dumps(refined, indent=2, default=str), to_console=False)
                else:
                    print(text)
        
        elif node_name == "validation":
            confidence = state.get("confidence_score", 0.0)
            iteration = state.get("iteration_count", 0)
            violations = state.get("invest_violations", [])
            violation_count = len(violations)
            
            # Visual confidence bar
            confidence_bar = "█" * int(confidence * 20) + "░" * (20 - int(confidence * 20))
            status = "✅" if confidence >= 0.8 and violation_count == 0 else "⚠️" if confidence >= 0.6 else "❌"
            text = f"   → Iteration {iteration}: {status} Confidence {confidence:.2f} [{confidence_bar}] | Violations: {violation_count}"
            if self.log_writer:
                self.log_writer.writeln(text)
                # Log validation details to file
                self.log_writer.write_section(f"Validation Details - Iteration {iteration}", to_console=False)
                self.log_writer.writeln(f"Confidence Score: {confidence:.4f}", to_console=False)
                self.log_writer.writeln(f"QA Confidence: {state.get('qa_confidence', 'N/A')}", to_console=False)
                self.log_writer.writeln(f"Developer Confidence: {state.get('developer_confidence', 'N/A')}", to_console=False)
                self.log_writer.writeln(f"Violations Count: {violation_count}", to_console=False)
            else:
                print(text)
        
        # Always log full state after node completion to file
        if self.log_writer:
            self.log_writer.write_state_dump(state, f"State at {node_name} completion", to_console=False)

    async def on_iteration_update(self, iteration: int, state: Dict) -> None:
        """Called when debate iteration updates."""
        # Only show if this is a new iteration
        if iteration not in self.seen_iterations and iteration > 0:
            self.seen_iterations.add(iteration)
            debate_history = state.get("debate_history", [])
            
            if debate_history and len(debate_history) >= iteration:
                # Get the entry for this iteration
                entry = debate_history[iteration - 1] if iteration <= len(debate_history) else debate_history[-1]
                
                header = f"\n{'═' * 80}\n💬 DEBATE ITERATION {iteration}\n{'═' * 80}"
                if self.log_writer:
                    self.log_writer.writeln(header)
                    self.log_writer.write_section(f"DEBATE ITERATION {iteration} - FULL DETAILS", to_console=False)
                else:
                    print(header)
                
                # Show draft
                draft = entry.get("draft", {})
                if draft:
                    title = safe_get(draft, "title", "N/A")
                    ac_count = len(safe_get(draft, "acceptance_criteria", []))
                    print(f"\n📝 Draft Artifact:")
                    print(f"   Title: {title}")
                    print(f"   Acceptance Criteria: {ac_count} defined")
                
                # Show critiques (full text, not truncated)
                qa_critique = entry.get("qa_critique", "")
                if qa_critique:
                    text = f"\n🔍 QA Agent Critique:"
                    if self.log_writer:
                        self.log_writer.writeln(text)
                    else:
                        print(text)
                    critique_lines = qa_critique.split("\n")
                    for line in critique_lines:
                        if line.strip():
                            if self.log_writer:
                                self.log_writer.writeln(f"   {line}")
                            else:
                                print(f"   {line}")
                    # Always write full critique to file
                    if self.log_writer:
                        self.log_writer.write_section("QA Agent Critique (Full Text)", to_console=False)
                        self.log_writer.writeln(qa_critique, to_console=False)
                
                dev_critique = entry.get("developer_critique", "")
                if dev_critique:
                    text = f"\n👨‍💻 Developer Agent Critique:"
                    if self.log_writer:
                        self.log_writer.writeln(text)
                    else:
                        print(text)
                    critique_lines = dev_critique.split("\n")
                    for line in critique_lines:
                        if line.strip():
                            if self.log_writer:
                                self.log_writer.writeln(f"   {line}")
                            else:
                                print(f"   {line}")
                    # Always write full critique to file
                    if self.log_writer:
                        self.log_writer.write_section("Developer Agent Critique (Full Text)", to_console=False)
                        self.log_writer.writeln(dev_critique, to_console=False)
                
                # Show violations - check both string and structured violations
                violations = entry.get("invest_violations", [])
                structured_violations = entry.get("structured_violations", [])
                
                # Combine both types for display
                all_violations = violations.copy()
                if structured_violations:
                    # Add structured violations that might not be in string format
                    for sv in structured_violations:
                        if isinstance(sv, dict):
                            violation_str = f"{sv.get('criterion', '?')}: {sv.get('description', '')}"
                            if sv.get('severity'):
                                violation_str += f" [{sv.get('severity')}]"
                            if violation_str not in all_violations:
                                all_violations.append(violation_str)
                
                if all_violations:
                    print(f"\n⚠️  INVEST Violations ({len(all_violations)} total):")
                    print(f"   String violations: {len(violations)}, Structured violations: {len(structured_violations)}")
                    for i, violation in enumerate(all_violations, 1):
                        print(f"   {i}. {violation}")
                else:
                    print(f"\n✅ No INVEST Violations")
                    # Debug: show why no violations
                    print(f"   (Debug: invest_violations={len(violations)}, structured_violations={len(structured_violations)})")
                
                # Show refined
                refined = entry.get("refined", {})
                if refined:
                    title = safe_get(refined, "title", "N/A")
                    ac_count = len(safe_get(refined, "acceptance_criteria", []))
                    print(f"\n✨ Refined Artifact:")
                    print(f"   Title: {title}")
                    print(f"   Acceptance Criteria: {ac_count} defined")
                
                # Show metrics with detailed breakdown
                confidence = entry.get("confidence_score", 0.0)
                qa_conf = entry.get("qa_confidence")
                dev_conf = entry.get("developer_confidence")
                qa_assessment = entry.get("qa_overall_assessment", "N/A")
                violation_count = len(all_violations) if 'all_violations' in locals() else len(violations)
                confidence_bar = "█" * int(confidence * 20) + "░" * (20 - int(confidence * 20))
                status = "✅" if confidence >= 0.8 and violation_count == 0 else "⚠️" if confidence >= 0.6 else "❌"
                print(f"\n📊 Quality Metrics:")
                print(f"   {status} Overall Confidence: {confidence:.2f} [{confidence_bar}]")
                if qa_conf is not None:
                    print(f"   QA Agent Confidence: {qa_conf:.2f}")
                if dev_conf is not None:
                    print(f"   Developer Agent Confidence: {dev_conf:.2f}")
                print(f"   QA Overall Assessment: {qa_assessment}")
                print(f"   Total Violations: {violation_count}")
                
                # Show trend if not first iteration
                if iteration > 1 and len(debate_history) >= 2:
                    prev_entry = debate_history[iteration - 2] if iteration > 1 else None
                    if prev_entry:
                        prev_confidence = prev_entry.get("confidence_score", 0.0)
                        prev_violations = len(prev_entry.get("invest_violations", []))
                        conf_change = confidence - prev_confidence
                        viol_change = violation_count - prev_violations
                        
                        trend = []
                        if conf_change > 0:
                            trend.append(f"Confidence ↑ +{conf_change:.2f}")
                        elif conf_change < 0:
                            trend.append(f"Confidence ↓ {conf_change:.2f}")
                        
                        if viol_change < 0:
                            trend.append(f"Violations ↓ {viol_change}")
                        elif viol_change > 0:
                            trend.append(f"Violations ↑ +{viol_change}")
                        
                        if trend:
                            trend_text = f"   Trend: {', '.join(trend)}"
                            if self.log_writer:
                                self.log_writer.writeln(trend_text)
                            else:
                                print(trend_text)
                
                # Write full iteration entry to file
                if self.log_writer:
                    self.log_writer.write_section(f"Iteration {iteration} - Complete Entry", to_console=False)
                    self.log_writer.writeln(json.dumps(entry, indent=2, default=str), to_console=False)
                
                if not self.log_writer:
                    print()  # Extra line for readability


async def run_demo():
    """Run a demo of the optimization workflow with mock data."""
    # Create log file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file_path = log_dir / f"demo_{timestamp}.log"
    
    # Create dual output writer
    log_writer = DualOutputWriter(log_file_path)
    
    log_writer.writeln("=" * 80)
    log_writer.writeln("Agentic AI PoC - Demo Workflow")
    log_writer.writeln("=" * 80)
    log_writer.writeln()
    log_writer.writeln(f"Log file: {log_file_path}")
    log_writer.writeln()

    # Create a mock optimization request
    log_writer.writeln("📋 Creating optimization request...")
    request = OptimizationRequest(
        artifact_id="demo-issue-123",
        artifact_type="issue",
        source_system="linear",
        trigger="manual",
        dry_run=True,  # Always dry-run for demo
    )
    log_writer.writeln(f"   ✓ Request created: {request.artifact_id}")
    log_writer.writeln()
    
    # Log request details to file
    log_writer.write_section("Optimization Request Details", to_console=False)
    log_writer.writeln(json.dumps(request.model_dump(), indent=2, default=str), to_console=False)

    # Create mock artifact
    log_writer.writeln("📝 Creating mock Linear issue...")
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
    log_writer.writeln(f"   ✓ Mock artifact created: {mock_artifact.human_ref}")
    log_writer.writeln(f"   Title: {mock_artifact.title}")
    log_writer.writeln(f"   Priority: {mock_artifact.priority.value}")
    log_writer.writeln()
    
    # Log mock artifact details to file
    log_writer.write_section("Mock Artifact Details", to_console=False)
    log_writer.writeln(json.dumps(mock_artifact.model_dump(), indent=2, default=str), to_console=False)

    # Get dependencies from DI container
    log_writer.writeln("🔧 Initializing dependencies...")
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
            log_writer.writeln(f"   ⚠️  Embedding error: {e}")
            raise
        finally:
            loop.close()

    try:
        knowledge_base = container.get_knowledge_base(sync_embedding_fn)
        # Initialize database asynchronously
        await knowledge_base.initialize_db()
        log_writer.writeln("   ✓ Knowledge base initialized")
    except Exception as e:
        log_writer.writeln(f"   ⚠️  Knowledge base initialization failed: {e}")
        log_writer.writeln("   Note: This may fail if vector store is not initialized")
        knowledge_base = None

    # Use mock issue tracker for demo to avoid Linear API calls
    from src.adapters.egress.mock_issue_tracker import MockIssueTracker
    
    issue_tracker = MockIssueTracker(mock_artifact=mock_artifact)
    log_writer.writeln("   ✓ Issue tracker initialized (mock mode for demo)")

    log_writer.writeln()

    # Show workflow steps
    log_writer.writeln("🔄 Multi-Agent Debate Workflow:")
    log_writer.writeln("   1. Ingress: Load artifact from Linear")
    log_writer.writeln("   2. Context Assembly: Retrieve relevant knowledge from RAG")
    log_writer.writeln("   3. Drafting: Product Owner Agent drafts optimized artifact")
    log_writer.writeln("   4. QA Critique: QA Agent validates against INVEST criteria")
    log_writer.writeln("   5. Developer Critique: Developer Agent assesses technical feasibility")
    log_writer.writeln("   6. Synthesis: Product Owner Agent synthesizes feedback")
    log_writer.writeln("   7. Validation: Check confidence and INVEST violations")
    log_writer.writeln("   8. Execution: Update Linear issue (if confidence high)")
    log_writer.writeln()

    # Check if we can actually run the workflow
    if not settings.openai_api_key:
        log_writer.writeln("⚠️  OPENAI_API_KEY not set. Cannot execute full workflow.")
        log_writer.writeln()
        log_writer.writeln("To run the full demo:")
        log_writer.writeln("1. Set OPENAI_API_KEY in your .env file")
        log_writer.writeln("2. Optionally set LINEAR_API_KEY for real Linear integration")
        log_writer.writeln("3. Run: python scripts/demo.py")
        log_writer.writeln()
        log_writer.writeln("For now, showing workflow structure only...")
        log_writer.close()
        return

    # Execute use case
    log_writer.writeln("🚀 Executing optimization workflow...")
    log_writer.writeln()

    from src.domain.use_cases import OptimizeArtifactUseCase

    # Create progress callback for real-time visualization with log writer
    progress_callback = DemoProgressCallback(log_writer=log_writer)

    use_case = OptimizeArtifactUseCase(
        issue_tracker=issue_tracker,
        knowledge_base=knowledge_base,
        llm_provider=llm_provider,
        progress_callback=progress_callback,
    )

    try:
        result = await use_case.execute(request)

        if result["success"]:
            final_state = result.get("final_state", {})
            
            # Log complete final state to file
            log_writer.write_section("FINAL STATE - COMPLETE DUMP", to_console=False)
            log_writer.write_state_dump(final_state, "Complete Final State", to_console=False)
            
            # Display initial artifact
            log_writer.writeln("\n" + "=" * 80)
            log_writer.writeln("📋 INITIAL ARTIFACT")
            log_writer.writeln("=" * 80)
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
                
                log_writer.writeln(f"\nTitle: {title}")
                log_writer.writeln(f"Type: {artifact_type}")
                log_writer.writeln(f"Priority: {priority_str}")
                log_writer.writeln(f"\nDescription:")
                desc = safe_get(artifact, "description", "")
                if desc:
                    for line in str(desc).split("\n"):
                        log_writer.writeln(f"  {line}")
                acceptance_criteria = safe_get(artifact, "acceptance_criteria", [])
                if acceptance_criteria:
                    log_writer.writeln(f"\nAcceptance Criteria:")
                    for ac in acceptance_criteria:
                        log_writer.writeln(f"  • {ac}")
            
            # Display retrieved context
            log_writer.writeln("\n" + "=" * 80)
            log_writer.writeln("🔍 RETRIEVED CONTEXT (RAG)")
            log_writer.writeln("=" * 80)
            context = final_state.get("retrieved_context", [])
            if context:
                log_writer.writeln(f"\nFound {len(context)} relevant knowledge units:")
                for i, unit in enumerate(context, 1):  # Show all in file
                    source = safe_get(unit, "source", "unknown")
                    location = safe_get(unit, "location", "N/A")
                    summary = safe_get(unit, "summary", "")
                    log_writer.writeln(f"\n  {i}. Source: {source}")
                    log_writer.writeln(f"     Location: {location}")
                    if summary:
                        log_writer.writeln(f"     Summary: {str(summary)}")
                    # Log full unit to file
                    if hasattr(unit, 'model_dump'):
                        log_writer.writeln(f"     Full Unit: {json.dumps(unit.model_dump(), indent=6, default=str)}", to_console=False)
            else:
                log_writer.writeln("\n  No context retrieved from knowledge base.")
            
            # Display debate iterations with progress tracking
            debate_history = final_state.get("debate_history", [])
            if debate_history:
                log_writer.writeln("\n" + "=" * 80)
                log_writer.writeln("💬 MULTI-AGENT DEBATE ITERATIONS")
                log_writer.writeln("=" * 80)
                
                # Track progress metrics
                prev_violation_count = None
                prev_confidence = None
                
                for idx, entry in enumerate(debate_history, 1):
                    log_writer.writeln(f"\n{'─' * 80}")
                    log_writer.writeln(f"ITERATION {entry.get('iteration', idx)}")
                    log_writer.writeln(f"{'─' * 80}")
                    
                    # Draft artifact (show full content)
                    draft = entry.get("draft", {})
                    log_writer.writeln(f"\n📝 PO Agent Draft:")
                    draft_title = safe_get(draft, "title", "N/A")
                    log_writer.writeln(f"   Title: {draft_title}")
                    desc = safe_get(draft, "description", "")
                    if desc:
                        log_writer.writeln(f"   Description:")
                        desc_lines = str(desc).split("\n")
                        for line in desc_lines:
                            log_writer.writeln(f"     {line}")
                    draft_ac = safe_get(draft, "acceptance_criteria", [])
                    if draft_ac:
                        log_writer.writeln(f"   Acceptance Criteria ({len(draft_ac)}):")
                        for ac in draft_ac:
                            log_writer.writeln(f"     • {ac}")
                    
                    # QA Critique (show full text)
                    qa_critique = entry.get("qa_critique", "")
                    if qa_critique:
                        log_writer.writeln(f"\n🔍 QA Agent Critique:")
                        critique_lines = qa_critique.split("\n")
                        for line in critique_lines:
                            if line.strip():
                                log_writer.writeln(f"   {line}")
                    
                    # INVEST Violations with progress indicator (check both types)
                    violations = entry.get("invest_violations", [])
                    structured_violations = entry.get("structured_violations", [])
                    
                    # Combine both types
                    all_violations = violations.copy()
                    if structured_violations:
                        for sv in structured_violations:
                            if isinstance(sv, dict):
                                violation_str = f"{sv.get('criterion', '?')}: {sv.get('description', '')}"
                                if sv.get('severity'):
                                    violation_str += f" [{sv.get('severity')}]"
                                if violation_str not in all_violations:
                                    all_violations.append(violation_str)
                    
                    violation_count = len(all_violations)
                    progress_indicator = ""
                    if prev_violation_count is not None:
                        if violation_count < prev_violation_count:
                            progress_indicator = f" ⬇️  ({prev_violation_count - violation_count} resolved)"
                        elif violation_count > prev_violation_count:
                            progress_indicator = f" ⬆️  ({violation_count - prev_violation_count} new)"
                        else:
                            progress_indicator = " ➡️  (no change)"
                    
                    if all_violations:
                        log_writer.writeln(f"\n⚠️  INVEST Violations ({violation_count} total){progress_indicator}:")
                        log_writer.writeln(f"   (String: {len(violations)}, Structured: {len(structured_violations)})")
                        # Group violations by criterion
                        violations_by_criterion = {}
                        for violation in all_violations:
                            # Extract criterion from violation string (format: "I: description" or "S: description")
                            criterion = "Other"
                            if ":" in violation:
                                criterion = violation.split(":")[0].strip()
                            if criterion not in violations_by_criterion:
                                violations_by_criterion[criterion] = []
                            violations_by_criterion[criterion].append(violation)
                        
                        for criterion, vios in violations_by_criterion.items():
                            log_writer.writeln(f"   [{criterion}] {len(vios)} violation(s):")
                            for violation in vios:
                                log_writer.writeln(f"     • {violation}")
                    else:
                        log_writer.writeln(f"\n✅ INVEST Violations: None ✓")
                        # Debug output
                        log_writer.writeln(f"   (Debug: invest_violations={len(violations)}, structured_violations={len(structured_violations)})")
                    
                    prev_violation_count = violation_count
                    
                    # Developer Critique (show full text)
                    dev_critique = entry.get("developer_critique", "")
                    if dev_critique:
                        log_writer.writeln(f"\n👨‍💻 Developer Agent Critique:")
                        critique_lines = dev_critique.split("\n")
                        for line in critique_lines:
                            if line.strip():
                                log_writer.writeln(f"   {line}")
                    
                    # Refined artifact (show full content)
                    refined = entry.get("refined", {})
                    if refined:
                        log_writer.writeln(f"\n✨ PO Agent Refinement:")
                        refined_title = safe_get(refined, "title", "N/A")
                        log_writer.writeln(f"   Title: {refined_title}")
                        desc = safe_get(refined, "description", "")
                        if desc:
                            log_writer.writeln(f"   Description:")
                            desc_lines = str(desc).split("\n")
                            for line in desc_lines:
                                log_writer.writeln(f"     {line}")
                        refined_ac = safe_get(refined, "acceptance_criteria", [])
                        if refined_ac:
                            log_writer.writeln(f"   Acceptance Criteria ({len(refined_ac)}):")
                            for ac in refined_ac:
                                log_writer.writeln(f"     • {ac}")
                    
                    # Confidence score with trend
                    confidence = entry.get("confidence_score", 0.0)
                    confidence_indicator = ""
                    if prev_confidence is not None:
                        if confidence > prev_confidence:
                            confidence_indicator = f" ⬆️  (+{confidence - prev_confidence:.2f})"
                        elif confidence < prev_confidence:
                            confidence_indicator = f" ⬇️  ({confidence - prev_confidence:.2f})"
                        else:
                            confidence_indicator = " ➡️  (no change)"
                    
                    # Visual confidence bar
                    confidence_bar = "█" * int(confidence * 20) + "░" * (20 - int(confidence * 20))
                    log_writer.writeln(f"\n📊 Confidence Score: {confidence:.2f}{confidence_indicator}")
                    log_writer.writeln(f"   [{confidence_bar}]")
                    
                    prev_confidence = confidence
            
            # Final summary with progress metrics
            log_writer.writeln("\n" + "=" * 80)
            log_writer.writeln("✅ FINAL SUMMARY")
            log_writer.writeln("=" * 80)
            
            iteration_count = final_state.get('iteration_count', 0)
            final_confidence = final_state.get('confidence_score', 0.0)
            violations = final_state.get("invest_violations", [])
            structured_violations = final_state.get("structured_qa_violations", [])
            
            # Combine both violation types for final count
            all_final_violations = violations.copy()
            if structured_violations:
                for sv in structured_violations:
                    if isinstance(sv, dict):
                        violation_str = f"{sv.get('criterion', '?')}: {sv.get('description', '')}"
                        if sv.get('severity'):
                            violation_str += f" [{sv.get('severity')}]"
                        if violation_str not in all_final_violations:
                            all_final_violations.append(violation_str)
                    elif hasattr(sv, 'criterion'):
                        violation_str = f"{sv.criterion}: {sv.description}"
                        if hasattr(sv, 'severity') and sv.severity:
                            violation_str += f" [{sv.severity}]"
                        if violation_str not in all_final_violations:
                            all_final_violations.append(violation_str)
            
            # Calculate progress metrics - check both types in initial state too
            initial_entry = debate_history[0] if debate_history else {}
            initial_violations_list = initial_entry.get("invest_violations", [])
            initial_structured = initial_entry.get("structured_violations", [])
            initial_all_violations = initial_violations_list.copy()
            if initial_structured:
                for sv in initial_structured:
                    if isinstance(sv, dict):
                        violation_str = f"{sv.get('criterion', '?')}: {sv.get('description', '')}"
                        if sv.get('severity'):
                            violation_str += f" [{sv.get('severity')}]"
                        if violation_str not in initial_all_violations:
                            initial_all_violations.append(violation_str)
            
            initial_violations = len(initial_all_violations)
            final_violation_count = len(all_final_violations)
            violations_resolved = initial_violations - final_violation_count
            violation_resolution_rate = (violations_resolved / initial_violations * 100) if initial_violations > 0 else 0
            
            initial_confidence = debate_history[0].get("confidence_score", 0.0) if debate_history else 0.0
            confidence_improvement = final_confidence - initial_confidence
            
            violations_resolved = initial_violations - final_violation_count
            violation_resolution_rate = (violations_resolved / initial_violations * 100) if initial_violations > 0 else 0
            
            log_writer.writeln(f"\n📈 Progress Metrics:")
            log_writer.writeln(f"   • Total Iterations: {iteration_count}")
            log_writer.writeln(f"   • Initial Violations: {initial_violations} (String: {len(initial_violations_list)}, Structured: {len(initial_structured)})")
            log_writer.writeln(f"   • Final Violations: {final_violation_count} (String: {len(violations)}, Structured: {len(structured_violations)})")
            if violations_resolved > 0:
                log_writer.writeln(f"   • Violations Resolved: {violations_resolved} ({violation_resolution_rate:.1f}%) ✓")
            elif violations_resolved < 0:
                log_writer.writeln(f"   • New Violations Introduced: {abs(violations_resolved)} ⚠️")
            else:
                log_writer.writeln(f"   • Violations: No change")
            
            log_writer.writeln(f"\n📊 Quality Metrics:")
            log_writer.writeln(f"   • Initial Confidence: {initial_confidence:.2f}")
            log_writer.writeln(f"   • Final Confidence: {final_confidence:.2f}")
            qa_conf = final_state.get("qa_confidence")
            dev_conf = final_state.get("developer_confidence")
            if qa_conf is not None:
                log_writer.writeln(f"   • QA Agent Confidence: {qa_conf:.2f}")
            if dev_conf is not None:
                log_writer.writeln(f"   • Developer Agent Confidence: {dev_conf:.2f}")
            qa_assessment = final_state.get("qa_overall_assessment")
            if qa_assessment:
                log_writer.writeln(f"   • QA Overall Assessment: {qa_assessment}")
            if confidence_improvement > 0:
                log_writer.writeln(f"   • Confidence Improvement: +{confidence_improvement:.2f} ✓")
            elif confidence_improvement < 0:
                log_writer.writeln(f"   • Confidence Change: {confidence_improvement:.2f} ⚠️")
            else:
                log_writer.writeln(f"   • Confidence: No change")
            
            # Final violations breakdown (show both types)
            if all_final_violations:
                log_writer.writeln(f"\n⚠️  Remaining INVEST Violations ({final_violation_count} total):")
                log_writer.writeln(f"   (String violations: {len(violations)}, Structured violations: {len(structured_violations)})")
                violations_by_criterion = {}
                for violation in all_final_violations:
                    criterion = "Other"
                    if ":" in violation:
                        criterion = violation.split(":")[0].strip()
                    if criterion not in violations_by_criterion:
                        violations_by_criterion[criterion] = []
                    violations_by_criterion[criterion].append(violation)
                
                for criterion, vios in violations_by_criterion.items():
                    log_writer.writeln(f"   [{criterion}] {len(vios)} violation(s):")
                    for violation in vios:
                        log_writer.writeln(f"     • {violation}")
            else:
                log_writer.writeln(f"\n✅ INVEST Violations: None ✓")
                # Debug output to explain why no violations
                log_writer.writeln(f"\n   Debug Information:")
                log_writer.writeln(f"   • invest_violations (strings): {len(violations)} items")
                log_writer.writeln(f"   • structured_qa_violations (objects): {len(structured_violations)} items")
                if structured_violations:
                    log_writer.writeln(f"   • Structured violations details:")
                    for sv in structured_violations:
                        if isinstance(sv, dict):
                            log_writer.writeln(f"     - {sv.get('criterion', '?')}: {sv.get('description', '')} [{sv.get('severity', 'unknown')}]")
                        elif hasattr(sv, 'criterion'):
                            log_writer.writeln(f"     - {sv.criterion}: {sv.description} [{getattr(sv, 'severity', 'unknown')}]")
                log_writer.writeln(f"   • Final confidence: {final_confidence:.2f}")
                log_writer.writeln(f"   • QA confidence: {qa_conf if qa_conf is not None else 'N/A'}")
                log_writer.writeln(f"   • Developer confidence: {dev_conf if dev_conf is not None else 'N/A'}")
            
            # Show final artifact (show full content)
            refined_artifact = final_state.get("refined_artifact") or final_state.get("draft_artifact")
            if refined_artifact:
                log_writer.writeln(f"\n📋 Final Artifact:")
                final_title = safe_get(refined_artifact, "title", "N/A")
                log_writer.writeln(f"   Title: {final_title}")
                final_desc = safe_get(refined_artifact, "description", "")
                if final_desc:
                    log_writer.writeln(f"   Description:")
                    desc_lines = str(final_desc).split("\n")
                    for line in desc_lines:
                        log_writer.writeln(f"     {line}")
                final_ac = safe_get(refined_artifact, "acceptance_criteria", [])
                if final_ac:
                    log_writer.writeln(f"   Acceptance Criteria ({len(final_ac)}):")
                    for ac in final_ac:
                        log_writer.writeln(f"     • {ac}")
                # Log full final artifact to file
                if hasattr(refined_artifact, 'model_dump'):
                    log_writer.write_section("Final Artifact (Complete JSON)", to_console=False)
                    log_writer.writeln(json.dumps(refined_artifact.model_dump(), indent=2, default=str), to_console=False)
            
            # Overall assessment with explanation
            log_writer.writeln(f"\n🎯 Overall Assessment:")
            if final_confidence >= 0.8 and final_violation_count == 0:
                log_writer.writeln("   ✅ Excellent: High confidence and no violations")
                log_writer.writeln(f"      Confidence breakdown: {final_confidence:.2f} (threshold: 0.80)")
                log_writer.writeln(f"      Violations: {final_violation_count} (all resolved)")
            elif final_confidence >= 0.7 and final_violation_count <= 2:
                log_writer.writeln("   ✅ Good: Acceptable quality with minor issues")
                log_writer.writeln(f"      Confidence: {final_confidence:.2f}, Violations: {final_violation_count}")
            elif final_confidence >= 0.6:
                log_writer.writeln("   ⚠️  Needs Improvement: Moderate quality, some violations remain")
                log_writer.writeln(f"      Confidence: {final_confidence:.2f}, Violations: {final_violation_count}")
            else:
                log_writer.writeln("   ⚠️  Poor: Low confidence, significant violations remain")
                log_writer.writeln(f"      Confidence: {final_confidence:.2f}, Violations: {final_violation_count}")
        else:
            error_msg = result.get('error', 'Unknown error')
            log_writer.writeln(f"❌ Optimization failed: {error_msg}")
            if 'traceback' in result:
                log_writer.writeln("\nFull traceback:")
                log_writer.writeln(result['traceback'])

    except Exception as e:
        log_writer.writeln(f"❌ Error during execution: {e}")
        import traceback
        log_writer.writeln("\nFull traceback:")
        log_writer.writeln(traceback.format_exc())

    finally:
        log_writer.writeln()
        log_writer.writeln("=" * 80)
        log_writer.writeln("Demo complete!")
        log_writer.writeln("=" * 80)
        log_writer.writeln(f"\n📄 Complete log saved to: {log_file_path}")
        log_writer.close()
        print(f"\n📄 Complete log saved to: {log_file_path}")


if __name__ == "__main__":
    asyncio.run(run_demo())
