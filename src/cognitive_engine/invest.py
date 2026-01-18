"""INVEST criteria validation logic."""

from typing import List

from src.domain.schema import CoreArtifact


class InvestValidator:
    """INVEST criteria validator for artifacts."""

    def validate(self, artifact: CoreArtifact) -> List[str]:
        """Validate artifact against INVEST criteria.

        Args:
            artifact: Artifact to validate.

        Returns:
            List of violation strings.
        """
        violations = []

        # Independent: Check if artifact has dependencies
        if artifact.parent_ref:
            # Having a parent is OK, but check if it's blocking
            pass  # This would need more context to determine

        # Negotiable: Check if description is too prescriptive
        if "must" in artifact.description.lower() or "shall" in artifact.description.lower():
            # Too prescriptive - but this is a heuristic
            pass

        # Valuable: Check if "so that" clause exists (for user stories)
        if artifact.type.lower() == "story":
            if "so that" not in artifact.description.lower():
                violations.append("Valuable: Missing 'so that' clause indicating user value")

        # Estimable: Check if description is too vague
        vague_terms = ["fast", "better", "improve", "enhance", "user-friendly"]
        description_lower = artifact.description.lower()
        vague_found = [term for term in vague_terms if term in description_lower]
        if vague_found:
            violations.append(f"Estimable: Contains vague terms: {', '.join(vague_found)}")

        # Small: Check description length as proxy for size
        if len(artifact.description) > 2000:
            violations.append("Small: Description is very long, may indicate story is too large")

        # Testable: Check acceptance criteria
        if not artifact.acceptance_criteria:
            violations.append("Testable: Missing acceptance criteria")
        else:
            # Check if ACs are binary (pass/fail)
            for ac in artifact.acceptance_criteria:
                ac_lower = ac.lower()
                if any(term in ac_lower for term in ["should", "could", "might", "better"]):
                    violations.append(f"Testable: Acceptance criteria '{ac[:50]}...' is not binary (pass/fail)")

        return violations
