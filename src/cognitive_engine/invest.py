"""INVEST criteria validation logic."""

import re
from typing import List

from src.domain.schema import CoreArtifact


class InvestValidator:
    """INVEST criteria validator for artifacts."""

    # Keywords that indicate multiple features/concerns
    MULTI_FEATURE_INDICATORS = [
        "and also", "additionally", "as well as", "along with",
        "furthermore", "moreover", "plus", "in addition",
        "this includes", "this should include", "includes:",
    ]
    
    # Domain terms that often indicate separate models/entities
    MODEL_INDICATORS = [
        "order", "frame", "glasses", "lens", "prescription",
        "payment", "checkout", "cart", "inventory", "shipping",
        "user", "admin", "customer", "product", "catalog",
        "authentication", "authorization", "notification", "email",
    ]

    def validate(self, artifact: CoreArtifact) -> List[str]:
        """Validate artifact against INVEST criteria.

        Args:
            artifact: Artifact to validate.

        Returns:
            List of violation strings.
        """
        violations = []
        description_lower = artifact.description.lower()

        # Independent: Check if artifact has dependencies
        if artifact.parent_ref:
            # Having a parent is OK, but check if it's blocking
            pass  # This would need more context to determine

        # Negotiable: Check if description is too prescriptive
        if "must" in description_lower or "shall" in description_lower:
            # Too prescriptive - but this is a heuristic
            pass

        # Valuable: Check if "so that" clause exists (for user stories)
        if artifact.type.lower() == "story":
            if "so that" not in description_lower:
                violations.append("Valuable: Missing 'so that' clause indicating user value")

        # Estimable: Check if description is too vague
        vague_terms = ["fast", "better", "improve", "enhance", "user-friendly"]
        vague_found = [term for term in vague_terms if term in description_lower]
        if vague_found:
            violations.append(f"Estimable: Contains vague terms: {', '.join(vague_found)}")

        # ============================================================
        # Small: ENHANCED detection for large/multi-feature stories
        # ============================================================
        small_violations = []
        
        # Check 1: Description length (lowered threshold)
        if len(artifact.description) > 800:
            small_violations.append("description exceeds 800 chars")
        
        # Check 2: Too many acceptance criteria (more than 5 = too large)
        ac_count = len(artifact.acceptance_criteria) if artifact.acceptance_criteria else 0
        if ac_count > 5:
            small_violations.append(f"has {ac_count} acceptance criteria (max 5 recommended)")
        
        # Check 3: Multiple feature indicators in description
        multi_feature_found = [
            indicator for indicator in self.MULTI_FEATURE_INDICATORS 
            if indicator in description_lower
        ]
        if multi_feature_found:
            small_violations.append(f"contains multi-feature phrases: {', '.join(multi_feature_found[:3])}")
        
        # Check 4: Multiple distinct models/entities mentioned
        models_found = [
            model for model in self.MODEL_INDICATORS 
            if re.search(rf'\b{model}\b', description_lower)
        ]
        if len(models_found) >= 3:
            small_violations.append(f"covers {len(models_found)} distinct entities: {', '.join(models_found[:5])}")
        
        # Check 5: Bullet points or numbered lists (often indicate multiple features)
        bullet_count = len(re.findall(r'(?:^|\n)\s*[-•*]\s', artifact.description))
        numbered_count = len(re.findall(r'(?:^|\n)\s*\d+[.)]\s', artifact.description))
        list_items = bullet_count + numbered_count
        if list_items >= 4:
            small_violations.append(f"contains {list_items} list items (suggests multiple features)")
        
        # If any Small violations found, add them
        if small_violations:
            violations.append(f"S: Story too large - {'; '.join(small_violations)}")

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
