const ORCHESTRATOR_AGENT = "Orchestrator";
const TECHNICAL_AGENTS = ["Knowledge Retrieval", "Story Writer", "Validation"];
const BUSINESS_AGENTS = ["Epic Analysis", "Splitting Strategy", "Story Generation"];

const toWords = (text) => (text || "").trim().split(/\s+/).filter(Boolean);

const extractPersona = (text) => {
  const match = text.match(/as a[n]?\s+([^,.\n]+?)(?:,|\.|\s+i\s+want|\s+i\s+can)/i);
  return match ? match[1].trim() : "user";
};

const extractCapability = (text) => {
  const match = text.match(/\bi can\s+([^.\n]+)|\bi want to\s+([^.\n]+)/i);
  const capability = match ? match[1] || match[2] : "";
  return capability ? capability.trim() : "achieve the goal";
};

const extractBenefit = (text) => {
  const match = text.match(/\bso that\s+([^.\n]+)/i);
  return match ? match[1].trim() : "deliver measurable value";
};

const getActiveAgents = ({ technicalEnabled, businessEnabled }) => {
  const agents = [ORCHESTRATOR_AGENT];
  if (businessEnabled) {
    agents.push(...BUSINESS_AGENTS);
  }
  if (technicalEnabled) {
    agents.push(...TECHNICAL_AGENTS);
  }
  return Array.from(new Set(agents));
};

const buildCandidatesFromTechniques = (persona, capability, techniques, label) =>
  techniques.map((technique, index) => ({
    id: `${label}-${index + 1}`,
    title: `As a ${persona}, I can ${capability} (${technique})`,
    technique,
  }));

const buildEpicRun = (draft, modes) => {
  const words = toWords(draft);
  const persona = extractPersona(draft);
  const capability = extractCapability(draft);
  const benefit = extractBenefit(draft);
  const complexityScore = Math.min(0.95, Math.max(0.2, words.length / 120));
  const ambiguities = [];
  if (!/so that/i.test(draft)) {
    ambiguities.push("Business value is not explicitly stated.");
  }
  if (words.length < 40) {
    ambiguities.push("More detail recommended to refine scope and constraints.");
  }

  const recommendations = [];
  if (/flow|journey|path|checkout/i.test(draft)) {
    recommendations.push({ technique: "Path", rationale: "Multiple user flows detected." });
  }
  if (/integration|api|third[- ]party/i.test(draft)) {
    recommendations.push({ technique: "Interface", rationale: "External integration surfaces are implied." });
  }
  if (/data|schema|migration|reporting/i.test(draft)) {
    recommendations.push({ technique: "Data", rationale: "Data considerations are present." });
  }
  if (!recommendations.length) {
    recommendations.push({ technique: "Simple/Complex", rationale: "Start with the simplest valuable slice." });
  }

  const selectedTechniques = recommendations.slice(0, 2).map((item) => item.technique);
  const generatedStories = buildCandidatesFromTechniques(persona, capability, selectedTechniques, "STORY");

  return {
    agents: getActiveAgents(modes),
    analysis: { persona, capability, benefit, complexityScore, ambiguities },
    recommendations,
    selectedTechniques,
    generatedStories,
  };
};

const buildInitiativeRun = (draft, modes) => {
  const words = toWords(draft);
  const persona = extractPersona(draft);
  const capability = extractCapability(draft);
  const benefit = extractBenefit(draft);
  const complexityScore = Math.min(0.95, Math.max(0.2, words.length / 150));
  const ambiguities = [];
  if (!/so that/i.test(draft)) {
    ambiguities.push("Business outcome is not explicitly stated.");
  }
  if (words.length < 60) {
    ambiguities.push("More detail recommended to align stakeholders.");
  }

  const recommendations = [];
  if (/platform|migration|architecture/i.test(draft)) {
    recommendations.push({ technique: "Interface", rationale: "Multiple surfaces or channels implied." });
  }
  if (/regional|market|segment/i.test(draft)) {
    recommendations.push({ technique: "Path", rationale: "Multiple user segments detected." });
  }
  if (!recommendations.length) {
    recommendations.push({ technique: "Simple/Complex", rationale: "Start with the simplest valuable slice." });
  }

  const selectedTechniques = recommendations.slice(0, 2).map((item) => item.technique);
  const generatedEpics = buildCandidatesFromTechniques(persona, capability, selectedTechniques, "EPIC");

  return {
    agents: getActiveAgents(modes),
    analysis: { persona, capability, benefit, complexityScore, ambiguities },
    recommendations,
    selectedTechniques,
    generatedEpics,
  };
};

const buildStoryRun = (draft, modes, templateText) => {
  const words = toWords(draft);
  const formatStyle = /given|when|then/i.test(templateText || "") ? "gherkin" : "free_form";
  const requiredFields = ["title", "description", "acceptance_criteria"];
  const optionalFields = ["dependencies", "nfrs", "out_of_scope", "assumptions", "open_questions"];
  const persona = extractPersona(draft);
  const capability = extractCapability(draft);

  const contextSummary = {
    decisions: modes.businessEnabled ? 2 : 0,
    constraints: modes.businessEnabled ? 1 : 0,
    relevantDocs: modes.businessEnabled ? 3 : 1,
    codeContext: modes.technicalEnabled ? 4 : 0,
  };

  const gaps = [];
  if (words.length < 35) {
    gaps.push("Add more user/context detail to improve estimations.");
  }
  if (!/acceptance|criteria/i.test(draft)) {
    gaps.push("Acceptance criteria should be explicitly stated.");
  }

  return {
    agents: getActiveAgents(modes),
    templateSchema: { requiredFields, optionalFields, formatStyle },
    contextSummary,
    populatedStory: {
      title: `As a ${persona}, I can ${capability}`,
      description: "Draft prepared using available context and selected expertise.",
    },
    validation: {
      overall: gaps.length ? "warning" : "pass",
      gaps,
      refineActions: [
        "Expand acceptance criteria with edge cases",
        "Clarify dependencies and constraints",
      ],
    },
  };
};

export {
  ORCHESTRATOR_AGENT,
  TECHNICAL_AGENTS,
  BUSINESS_AGENTS,
  getActiveAgents,
  buildCandidatesFromTechniques,
  buildEpicRun,
  buildInitiativeRun,
  buildStoryRun,
};
