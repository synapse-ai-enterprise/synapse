const STORY_STEPS = [
  {
    id: "template_parser",
    label: "Template Parser",
    detail: "Extract required fields and formatting rules.",
  },
  {
    id: "knowledge_retrieval",
    label: "Knowledge Retrieval",
    detail: "Gather evidence and relevant documentation.",
  },
  {
    id: "story_writer",
    label: "Story Writer",
    detail: "Populate story sections with context.",
  },
  {
    id: "validation",
    label: "Validation",
    detail: "Check INVEST, gaps, and technical risks.",
  },
  {
    id: "critique_loop",
    label: "Critique Loop",
    detail: "QA and Dev feedback with PO synthesis.",
  },
];

const EPIC_STEPS = [
  {
    id: "epic_analysis",
    label: "Epic Analysis",
    detail: "Extract personas, capabilities, and ambiguities.",
  },
  {
    id: "splitting_strategy",
    label: "Splitting Strategy",
    detail: "Recommend decomposition techniques.",
  },
  {
    id: "story_generation",
    label: "Story Generation",
    detail: "Generate candidate stories from the epic.",
  },
  {
    id: "critique_loop",
    label: "Critique Loop",
    detail: "QA and Dev feedback with PO synthesis.",
  },
];

const INITIATIVE_STEPS = [
  {
    id: "initiative_analysis",
    label: "Initiative Analysis",
    detail: "Summarize outcomes, stakeholders, and scope.",
  },
  {
    id: "epic_strategy",
    label: "Epic Strategy",
    detail: "Select decomposition techniques for EPICs.",
  },
  {
    id: "epic_generation",
    label: "Epic Generation",
    detail: "Generate EPIC candidates from the initiative.",
  },
  {
    id: "critique_loop",
    label: "Critique Loop",
    detail: "QA and Dev feedback with PO synthesis.",
  },
];

const KNOWLEDGE_SNIPPETS = [
  {
    source: "Notion",
    title: "Auth onboarding decision log",
    relevance: "0.82",
  },
  {
    source: "GitHub",
    title: "src/infrastructure/messaging/event_bus.py",
    relevance: "0.76",
  },
  {
    source: "Notion",
    title: "Story acceptance criteria checklist",
    relevance: "0.69",
  },
];

const INVEST_CHECKLIST = [
  { label: "I", status: "success" },
  { label: "N", status: "success" },
  { label: "V", status: "warning" },
  { label: "E", status: "success" },
  { label: "S", status: "warning" },
  { label: "T", status: "success" },
];

const CRITIQUE_FEEDBACK = {
  po: [
    "Clarify the user value in the description.",
    "Reduce scope by splitting optional enhancements.",
  ],
  qa: [
    "Acceptance criteria need explicit negative cases.",
    "Make performance expectations measurable.",
  ],
  dev: [
    "Confirm event bus supports new payload shape.",
    "Dependency on integration auth flow still unclear.",
  ],
};

const INTEGRATIONS = [
  {
    name: "Linear",
    status: "Not connected",
    accent: "muted",
    action: "Connect",
    actionType: "connect",
    details: [
      { label: "Workspace", value: "Unlinked" },
      { label: "Allowed projects", value: "All" },
    ],
    footerAction: "Test connection",
  },
  {
    name: "Jira",
    status: "Not connected",
    accent: "muted",
    action: "Connect",
    actionType: "connect",
    details: [
      { label: "Workspace", value: "Unlinked" },
      { label: "Allowed projects", value: "None" },
    ],
    footerAction: "Test connection",
  },
  {
    name: "Confluence",
    status: "Not connected",
    accent: "muted",
    action: "Connect",
    actionType: "connect",
    details: [
      { label: "Workspace", value: "Unlinked" },
      { label: "Allowed spaces", value: "None" },
    ],
    footerAction: "Test connection",
  },
  {
    name: "Notion",
    status: "Connected",
    accent: "success",
    action: "View scopes",
    actionType: "scopes",
    details: [
      { label: "Workspace", value: "Product Ops" },
      { label: "Allowed projects", value: "PRDs, Roadmaps" },
    ],
    footerAction: "Test connection",
  },
];

const TEMPLATE_PAGES = ["1", "2", "3", "4"];

const TEMPLATE_VERSIONS = [
  { version: "2.1", date: "Jan 21, 2026", status: "Active" },
  { version: "2.0", date: "Dec 18, 2025", status: "Archived" },
  { version: "1.8", date: "Oct 02, 2025", status: "Archived" },
];

export const AUDIT_LOGS = [
  {
    date: "Jan 28, 2026",
    user: "PM Alice",
    artifact: "Story Detailing",
    action: "Created",
    destination: "Linear",
    ticket: "SYN-4421",
  },
  {
    date: "Jan 26, 2026",
    user: "QA Sam",
    artifact: "Epic Breakdown",
    action: "Reviewed",
    destination: "Jira",
    ticket: "EPIC-912",
  },
  {
    date: "Jan 24, 2026",
    user: "Dev Priya",
    artifact: "Story Detailing",
    action: "Refined",
    destination: "Notion",
    ticket: "STORY-204",
  },
];

export {
  STORY_STEPS,
  EPIC_STEPS,
  INITIATIVE_STEPS,
  KNOWLEDGE_SNIPPETS,
  INVEST_CHECKLIST,
  CRITIQUE_FEEDBACK,
  INTEGRATIONS,
  TEMPLATE_PAGES,
  TEMPLATE_VERSIONS,
};
