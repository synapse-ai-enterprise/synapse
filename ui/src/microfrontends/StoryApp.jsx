import React, { useEffect, useMemo, useState } from "react";
import { marked } from "marked";

import { INTEGRATIONS } from "../shared/data";
import { runStoryWriting, streamStoryWriting } from "../shared/api";

export function StoryApp({
  activeModes,
  critiqueEnabled,
  templateText,
  onManageTemplate,
  onManageKnowledgeSources,
}) {
  const [startFromSource, setStartFromSource] = useState(false);
  const [epicId, setEpicId] = useState("");
  const [epicDescription, setEpicDescription] = useState("");
  const [storyDraft, setStoryDraft] = useState("");
  const [storyRun, setStoryRun] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingSeconds, setLoadingSeconds] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");
  const [selectedFlowStep, setSelectedFlowStep] = useState("template_parser");
  const [flowStatus, setFlowStatus] = useState(buildInitialFlowStatus());

  useEffect(() => {
    if (!startFromSource) {
      return;
    }
    const trimmedEpic = epicDescription.trim();
    if (trimmedEpic && !storyDraft.trim()) {
      setStoryDraft(trimmedEpic);
    }
  }, [epicDescription, startFromSource, storyDraft]);

  useEffect(() => {
    if (!isLoading) {
      setLoadingSeconds(0);
      return;
    }
    const startTime = Date.now();
    setLoadingSeconds(0);
    const timer = setInterval(() => {
      setLoadingSeconds(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [isLoading]);

  const canGenerateStory = useMemo(() => {
    if (!storyDraft.trim().length) {
      return false;
    }
    if (startFromSource && !epicId.trim().length) {
      return false;
    }
    return true;
  }, [epicId, startFromSource, storyDraft]);

  const handleGenerateStory = async () => {
    setIsLoading(true);
    setErrorMessage("");
    resetFlowStatus();
    try {
      const payload = {
        flow: "story_to_detail",
        story_text: storyDraft,
        template_text: templateText || null,
        epic_text: startFromSource && epicDescription.trim() ? epicDescription.trim() : null,
        epic_id: startFromSource && epicId.trim() ? epicId.trim() : null,
        selected_techniques: [],
        project_id: null,
        requester_id: null,
      };
      await streamStoryWriting(payload, (event) => {
        if (event.event === "node_start") {
          updateFlowStatus(event.node, "running");
          setSelectedFlowStep(event.node);
        }
        if (event.event === "node_complete") {
          updateFlowStatus(event.node, "complete");
          setSelectedFlowStep(event.node);
        }
        if (event.event === "done") {
          setStoryRun(event.result?.final_state || null);
          setFlowStatus({
            template_parser: "complete",
            knowledge_retrieval: "complete",
            story_writer: "complete",
            validation: "complete",
            critique_loop: "complete",
          });
          setIsLoading(false);
        }
        if (event.event === "error") {
          setErrorMessage(event.message || "Failed to run story writing workflow.");
          setIsLoading(false);
        }
      });
    } catch (error) {
      setErrorMessage(error?.message || "Failed to run story writing workflow.");
      setStoryRun(null);
      setIsLoading(false);
    } finally {
      setIsLoading(false);
    }
  };

  const templateSchema = storyRun?.template_schema;
  const retrievedContext = storyRun?.retrieved_context;
  const populatedStory = storyRun?.populated_story;
  const validation = storyRun?.validation_results;
  const latestCritique = storyRun?.critique_history?.[storyRun.critique_history.length - 1] || null;

  const evidenceItems = buildEvidenceItems(retrievedContext);
  const investChecklist = buildInvestChecklist(validation?.invest_score);
  const validationGaps = (validation?.gaps || []).map((gap) => gap.gap || gap.message || String(gap));
  const validationIssues = (validation?.issues || []).map((issue) => issue.message || String(issue));
  const ungroundedClaims = (validation?.ungrounded_claims || []).map((claim) => String(claim));

  const acceptanceCriteria = (populatedStory?.acceptance_criteria || [])
    .map((item) => formatAcceptanceCriteria(item))
    .filter(Boolean);
  const timelineLabels = ["Gather Context", "Analyze Requirements", "Draft Story", "Validate Output"];
  const flowSteps = [
    { id: "template_parser", label: "Template Parser", detail: "Extract required fields and schema." },
    { id: "knowledge_retrieval", label: "Knowledge Retrieval", detail: "Retrieve evidence from connected sources." },
    { id: "story_writer", label: "Story Writer", detail: "Populate story sections with context." },
    { id: "validation", label: "Validation", detail: "Check INVEST, gaps, and technical risks." },
    { id: "critique_loop", label: "Critique Loop", detail: "QA and Dev feedback with PO synthesis." },
  ];
  const mvpIntegrations = ["Jira", "Confluence"];
  const integrationSources = INTEGRATIONS.map((integration) => ({
    name: integration.name,
    enabled: mvpIntegrations.includes(integration.name),
  }));
  const templatePreviewHtml = useMemo(() => {
    if (!templateText) {
      return "";
    }
    return marked.parse(templateText);
  }, [templateText]);

  const resetFlowStatus = () => {
    setFlowStatus(buildInitialFlowStatus());
  };

  const updateFlowStatus = (node, status) => {
    const order = buildFlowOrder();
    const nodeIndex = order.indexOf(node);
    setFlowStatus((prev) => {
      const next = { ...prev, [node]: status };
      if (status === "running" && nodeIndex > 0) {
        order.slice(0, nodeIndex).forEach((key) => {
          if (next[key] !== "complete") {
            next[key] = "complete";
          }
        });
      }
      return next;
    });
  };

  const loadingLabel = isLoading ? `Draft Loading · ${loadingSeconds}s` : "Draft Generated";
  const draftStatusDescription = isLoading ? "Draft generation in progress" : "Draft generated successfully";

  return (
    <section className="page story-page">
      <div className="page-header">
        <h1>Create a User Story</h1>
        <p>Draft a user story from an existing EPIC or from scratch.</p>
      </div>
      <div className="story-intake">
        <div className="card">
          <div className="section">
            <h3>Start source</h3>
            <p className="muted">Start from an existing EPIC?</p>
            <div className="pill-toggle">
              <button
                type="button"
                className={!startFromSource ? "active" : ""}
                onClick={() => setStartFromSource(false)}
              >
                No
              </button>
              <button
                type="button"
                className={startFromSource ? "active" : ""}
                onClick={() => setStartFromSource(true)}
              >
                Yes
              </button>
            </div>
            {startFromSource && (
              <div className="form-grid">
                <label className="stacked-field">
                  <span className="muted">Epic ID (required)</span>
                  <input
                    type="text"
                    value={epicId}
                    onChange={(event) => setEpicId(event.target.value)}
                    placeholder="EPIC-123"
                  />
                </label>
                <label className="stacked-field">
                  <span className="muted">Epic description (optional)</span>
                  <textarea
                    rows={4}
                    value={epicDescription}
                    onChange={(event) => setEpicDescription(event.target.value)}
                    placeholder="Provide epic context to guide story detailing..."
                  />
                </label>
              </div>
            )}
          </div>
        </div>
        <div className="card">
          <div className="section">
            <h3>Describe your feature</h3>
            <p className="muted">Required to generate a draft.</p>
            <textarea
              rows={6}
              value={storyDraft}
              onChange={(event) => setStoryDraft(event.target.value)}
              placeholder="Describe the feature, context, target users, expected value, constraints..."
            />
          </div>
          <div className="actions">
            <button
              type="button"
              className="primary"
              disabled={!canGenerateStory || isLoading}
              onClick={handleGenerateStory}
            >
              {isLoading ? "Running..." : "Generate draft"}
            </button>
          </div>
        </div>
      </div>
      {errorMessage && (
        <div className="card">
          <div className="section">
            <p className="muted">{errorMessage}</p>
          </div>
        </div>
      )}
      {(storyRun || isLoading) && (
        <>
          <div className="card">
            <div className="section">
              <h3>Workflow</h3>
              <div className="flow-diagram">
                {flowSteps.map((step, index) => (
                  <React.Fragment key={step.id}>
                    <button
                      type="button"
                      className={`flow-node ${flowStatus[step.id] || ""} ${
                        selectedFlowStep === step.id ? "active" : ""
                      }`}
                      onClick={() => setSelectedFlowStep(step.id)}
                    >
                      {step.label}
                    </button>
                    {index < flowSteps.length - 1 && <span className="flow-connector" />}
                  </React.Fragment>
                ))}
              </div>
              <p className="muted">
                {flowSteps.find((step) => step.id === selectedFlowStep)?.detail}
              </p>
            </div>
          </div>
          <div className="card story-detailing-card">
            <div className="story-detailing-header">
              <div>
                <h3 className="story-detailing-title">
                  Story Detailing: {isLoading ? "Draft Loading" : populatedStory?.title || "Draft Generated Successfully"}
                </h3>
                <p className="muted">{draftStatusDescription}</p>
              </div>
              <span className={`status-pill ${isLoading ? "loading" : "success"}`}>
                {isLoading && <span className="status-spinner" />}
                {loadingLabel}
              </span>
            </div>
            <div className="story-detailing-timeline">
              {timelineLabels.map((label) => (
                <div key={label} className="timeline-step">
                  <span className="timeline-dot" />
                  <span className="muted">{label}</span>
                </div>
              ))}
            </div>
            <div className="story-detailing-grid">
              <div className="story-panel">
                <h4>Template Schema Details</h4>
                <div className="story-panel-row">
                  <span className="muted">Summary</span>
                  <div className="story-panel-chip">{storyDraft || "No summary provided"}</div>
                </div>
                <div className="story-panel-row">
                  <span className="muted">Priority</span>
                  <div className="story-panel-chip">High</div>
                </div>
                <div className="story-panel-row">
                  <span className="muted">Epic</span>
                  <div className="story-panel-chip">{epicId || "User Account Management"}</div>
                </div>
                {templateSchema && (
                  <div className="story-panel-meta">
                    <span className="muted">Fields: {templateSchema.required_fields?.join(", ") || "Standard"}</span>
                  </div>
                )}
              </div>
              <div className="story-panel">
                <h4>Story Writer Output</h4>
                {isLoading ? (
                  <div className="loading-row">
                    <span className="status-spinner" />
                    <span className="muted">Generating story output...</span>
                  </div>
                ) : (
                  <p className="muted">{populatedStory?.description || "No description provided."}</p>
                )}
                {acceptanceCriteria.length > 0 && (
                  <ul className="story-criteria-list">
                    {acceptanceCriteria.map((item, index) => (
                      <li key={item}>
                        <span>{index + 1}. {item}</span>
                        <span className={`status-pill ${validationGaps.length > 0 && index === 1 ? "warn" : "success"}`}>
                          {validationGaps.length > 0 && index === 1 ? "Gap Detected" : "Validated"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="story-panel">
                <h4>Evidence List</h4>
                <div className="story-evidence-list">
                  {isLoading ? (
                    <div className="loading-row">
                      <span className="status-spinner" />
                      <span className="muted">Retrieving evidence...</span>
                    </div>
                  ) : evidenceItems.length > 0 ? (
                    evidenceItems.map((item) => (
                      <div key={item.key} className="story-evidence-chip">
                        {item.label}
                      </div>
                    ))
                  ) : (
                    <p className="muted">No evidence retrieved yet.</p>
                  )}
                </div>
              </div>
            </div>
            {(critiqueEnabled.poEnabled || critiqueEnabled.qaEnabled || critiqueEnabled.devEnabled) && (
              <div className="story-critique-section">
                <h4>Critique Panels</h4>
                <div className="story-critique-grid">
                  {critiqueEnabled.qaEnabled && (
                    <div className="story-critique-card">
                      <h5>QA Notes</h5>
                      {isLoading ? (
                        <div className="loading-row">
                          <span className="status-spinner" />
                          <span className="muted">Running QA critique...</span>
                        </div>
                      ) : (
                        <p className="muted">
                          {latestCritique?.qa_critique || storyRun?.qa_critique || "No QA critique available."}
                        </p>
                      )}
                    </div>
                  )}
                  {critiqueEnabled.devEnabled && (
                    <div className="story-critique-card">
                      <h5>Developer Notes</h5>
                      {isLoading ? (
                        <div className="loading-row">
                          <span className="status-spinner" />
                          <span className="muted">Running developer critique...</span>
                        </div>
                      ) : (
                        <p className="muted">
                          {latestCritique?.developer_critique || storyRun?.developer_critique || "No developer critique available."}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
          <div className="card">
            <div className="section">
              <h3>Export detailed story</h3>
              <div className="actions align-left">
                <button type="button" className="primary">
                  Export to Jira
                </button>
                <button type="button" className="ghost">
                  Export to Linear
                </button>
                <button type="button" className="ghost">
                  Export to Notion
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

const buildInitialFlowStatus = () => ({
  template_parser: "pending",
  knowledge_retrieval: "pending",
  story_writer: "pending",
  validation: "pending",
  critique_loop: "pending",
});

const buildFlowOrder = () => [
  "template_parser",
  "knowledge_retrieval",
  "story_writer",
  "validation",
  "critique_loop",
];


const buildEvidenceItems = (context) => {
  if (!context) {
    return [];
  }
  const items = [];
  (context.decisions || []).forEach((decision, index) => {
    items.push({
      key: `decision-${index}`,
      label: `Decision · ${decision.text || "Decision"} · ${decision.source || "source"}`,
    });
  });
  (context.constraints || []).forEach((constraint, index) => {
    items.push({
      key: `constraint-${index}`,
      label: `Constraint · ${constraint.text || "Constraint"} · ${constraint.source || "source"}`,
    });
  });
  (context.relevant_docs || []).forEach((doc, index) => {
    items.push({
      key: `doc-${index}`,
      label: `${doc.source || "Doc"} · ${doc.title || "Untitled"} · Relevance ${doc.relevance ?? "n/a"}`,
    });
  });
  (context.code_context || []).forEach((snippet, index) => {
    items.push({
      key: `code-${index}`,
      label: `Code · ${snippet.file || "Unknown file"} · ${snippet.note || "Referenced"}`,
    });
  });
  return items;
};

const buildInvestChecklist = (investScore) => {
  if (!investScore) {
    return [
      { label: "I", status: "muted" },
      { label: "N", status: "muted" },
      { label: "V", status: "muted" },
      { label: "E", status: "muted" },
      { label: "S", status: "muted" },
      { label: "T", status: "muted" },
    ];
  }
  return [
    { label: "I", status: investScore.independent ? "success" : "warning" },
    { label: "N", status: investScore.negotiable ? "success" : "warning" },
    { label: "V", status: investScore.valuable ? "success" : "warning" },
    { label: "E", status: investScore.estimable ? "success" : "warning" },
    { label: "S", status: investScore.small ? "success" : "warning" },
    { label: "T", status: investScore.testable ? "success" : "warning" },
  ];
};

const formatAcceptanceCriteria = (item) => {
  if (!item) {
    return "";
  }
  if (item.type === "gherkin") {
    const parts = [];
    if (item.scenario) {
      parts.push(`Scenario: ${item.scenario}`);
    }
    if (item.given) {
      parts.push(`Given ${item.given}`);
    }
    if (item.when) {
      parts.push(`When ${item.when}`);
    }
    if (item.then) {
      parts.push(`Then ${item.then}`);
    }
    return parts.join(" ");
  }
  return item.text || "";
};
