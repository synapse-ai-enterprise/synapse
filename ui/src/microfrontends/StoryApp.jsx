import React, { useEffect, useMemo, useState } from "react";
import { marked } from "marked";

import { INTEGRATIONS } from "../shared/data";
import { fetchIntegrations, runStoryWriting, streamStoryWriting, splitStorySimple, fetchActiveTemplate, fetchTemplates } from "../shared/api";

export function StoryApp({
  activeModes,
  critiqueEnabled,
  templateText,
  onManageTemplate,
  onManageKnowledgeSources,
}) {
  // Tab state
  const [activeTab, setActiveTab] = useState("detailing"); // "detailing" or "splitting"
  
  // Shared state
  const [startFromSource, setStartFromSource] = useState(false);
  const [epicId, setEpicId] = useState("");
  const [epicDescription, setEpicDescription] = useState("");
  const [storyDraft, setStoryDraft] = useState("");
  const [storyRun, setStoryRun] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingSeconds, setLoadingSeconds] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");
  const [hasRun, setHasRun] = useState(false);
  const [runStatus, setRunStatus] = useState("idle");
  const [selectedFlowStep, setSelectedFlowStep] = useState("template_parser");
  const [flowStatus, setFlowStatus] = useState(buildInitialFlowStatus());
  const [retrievalSources, setRetrievalSources] = useState(["github", "notion"]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState(null);
  const [showSplitPanel, setShowSplitPanel] = useState(false);
  const [isSplitting, setIsSplitting] = useState(false);
  const [manualSplits, setManualSplits] = useState([]);
  
  // Splitting-only tab state
  const [splitOnlyDraft, setSplitOnlyDraft] = useState("");
  const [splitOnlyResults, setSplitOnlyResults] = useState(null);
  const [splitOnlySplits, setSplitOnlySplits] = useState([]); // Editable splits array
  const [splitOnlyLoading, setSplitOnlyLoading] = useState(false);
  const [splitOnlyError, setSplitOnlyError] = useState("");
  const [splitFlowStatus, setSplitFlowStatus] = useState(buildInitialSplitFlowStatus());
  const [splitCurrentStep, setSplitCurrentStep] = useState("drafting");
  const [splitLoadingSeconds, setSplitLoadingSeconds] = useState(0);

  // Template state - loaded from backend
  const [activeTemplate, setActiveTemplate] = useState(null);
  const [templateLoadError, setTemplateLoadError] = useState("");

  // Load active template from backend on mount
  useEffect(() => {
    let isMounted = true;
    const loadActiveTemplate = async () => {
      try {
        const result = await fetchActiveTemplate("user_story");
        if (!isMounted) return;
        
        if (result?.content) {
          setActiveTemplate(result);
          // If parent doesn't have template set, use the backend one
          if (!templateText) {
            // Template text is managed by parent, so we'll use our local activeTemplate
          }
        }
      } catch (error) {
        console.warn("Failed to load active template", error);
        if (isMounted) {
          setTemplateLoadError("Could not load template from server. Using default.");
        }
      }
    };

    loadActiveTemplate();
    return () => {
      isMounted = false;
    };
  }, []);

  // Use either passed templateText or loaded template
  const effectiveTemplateText = templateText || activeTemplate?.content || "";

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
    let isMounted = true;
    const loadIntegrations = async () => {
      try {
        const integrations = await fetchIntegrations();
        if (!isMounted || !Array.isArray(integrations)) return;
        const connectedSources = integrations
          .filter((integration) => integration.status === "connected")
          .map((integration) => mapIntegrationToSource(integration.name))
          .filter(Boolean);
        if (connectedSources.length) {
          setRetrievalSources(connectedSources);
        }
      } catch (error) {
        console.warn("Failed to load integrations for retrieval", error);
      }
    };
    loadIntegrations();
    return () => {
      isMounted = false;
    };
  }, []);

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

  // Timer for split loading
  useEffect(() => {
    if (!splitOnlyLoading) {
      setSplitLoadingSeconds(0);
      return;
    }
    const startTime = Date.now();
    setSplitLoadingSeconds(0);
    const timer = setInterval(() => {
      setSplitLoadingSeconds(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [splitOnlyLoading]);

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
    setHasRun(true);
    setRunStatus("loading");
    setStoryRun(null);
    setShowSplitPanel(false);
    setIsSplitting(false);
    setManualSplits([]);
    resetFlowStatus();
    try {
      const payload = {
        flow: "story_to_detail",
        story_text: storyDraft,
        template_text: effectiveTemplateText || null,
        epic_text: startFromSource && epicDescription.trim() ? epicDescription.trim() : null,
        epic_id: startFromSource && epicId.trim() ? epicId.trim() : null,
        retrieval_sources: retrievalSources,
        direct_sources: [],
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
          const finalState = event.result?.final_state || null;
          setStoryRun(finalState);
          setFlowStatus({
            template_parser: "complete",
            knowledge_retrieval: "complete",
            story_writer: "complete",
            validation: "complete",
            critique_loop: "complete",
          });
          if (!finalState?.populated_story) {
            const warningText = Array.isArray(finalState?.warnings)
              ? finalState.warnings.filter(Boolean).join(" ")
              : "";
            setRunStatus("error");
            setErrorMessage(
              warningText || "Draft completed without story output. Please retry."
            );
          } else {
            setRunStatus("generated");
          }
          setIsLoading(false);
        }
        if (event.event === "error") {
          setErrorMessage(event.message || "Failed to run story writing workflow.");
          setRunStatus("error");
          setIsLoading(false);
        }
      });
    } catch (error) {
      setErrorMessage(error?.message || "Failed to run story writing workflow.");
      setStoryRun(null);
      setRunStatus("error");
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

  const evidenceItems = buildEvidenceItems(retrievedContext, storyRun?.evidence_items);
  const referencesBySection = storyRun?.field_references || {};
  const evidenceLookup = buildEvidenceLookup(storyRun?.evidence_items);
  const evidenceDetails = storyRun?.evidence_items || [];
  const contextGraphSummary = buildContextGraphSummary(storyRun?.context_graph);
  const contextGraphDetails = buildContextGraphDetails(
    storyRun?.context_graph,
    selectedEvidenceId,
    evidenceLookup
  );
  const groupedContextNodes = useMemo(() => {
    if (!contextGraphDetails) return null;
    return contextGraphDetails.nodes.reduce((acc, node) => {
      const key = node.type || "unknown";
      acc[key] = acc[key] || [];
      acc[key].push(node);
      return acc;
    }, {});
  }, [contextGraphDetails]);
  const groupedContextEdges = useMemo(() => {
    if (!contextGraphDetails) return null;
    return contextGraphDetails.edges.reduce((acc, edge) => {
      const key = edge.type || "LINK";
      acc[key] = acc[key] || [];
      acc[key].push(edge);
      return acc;
    }, {});
  }, [contextGraphDetails]);
  
  // User-friendly evidence traceability view
  const evidenceTraceability = useMemo(
    () => buildEvidenceTraceability(storyRun?.evidence_items, referencesBySection),
    [storyRun?.evidence_items, referencesBySection]
  );
  
  const investChecklist = buildInvestChecklist(validation?.invest_score);
  const validationGaps = (validation?.gaps || []).map((gap) => gap.gap || gap.message || String(gap));
  const validationIssues = (validation?.issues || []).map((issue) => issue.message || String(issue));
  const ungroundedClaims = (validation?.ungrounded_claims || []).map((claim) => String(claim));

  const acceptanceCriteria = (populatedStory?.acceptance_criteria || [])
    .map((item) => formatAcceptanceCriteria(item))
    .filter(Boolean);
  const citationIssues = useMemo(
    () => buildCitationIssues(populatedStory),
    [populatedStory]
  );
  const timelineLabels = ["Analyze Requirements", "Draft Story", "Validate Output"];
  const flowSteps = [
    { id: "template_parser", label: "Template Parser", detail: "Extract required fields and schema." },
    { id: "knowledge_retrieval", label: "Knowledge Retrieval", detail: "Retrieve evidence from connected sources." },
    { id: "story_writer", label: "Story Writer", detail: "Populate story sections with context." },
    { id: "validation", label: "Validation", detail: "Check INVEST, gaps, and technical risks." },
    { id: "critique_loop", label: "Critique Loop", detail: "QA and Dev feedback with PO synthesis." },
  ];
  
  // Splitting flow steps (matches migush-repo multi-agent debate)
  const splitFlowSteps = [
    { id: "drafting", label: "PO Draft", detail: "Product Owner creates initial artifact from story text." },
    { id: "qa_critique", label: "QA Critique", detail: "QA Agent validates against INVEST criteria." },
    { id: "dev_critique", label: "Dev Critique", detail: "Developer Agent assesses technical feasibility." },
    { id: "synthesis", label: "Synthesis", detail: "PO Agent synthesizes all feedback into refined artifact." },
    { id: "validation", label: "Validation", detail: "Check confidence scores and INVEST violations." },
    { id: "split_proposal", label: "Split Proposal", detail: "Generate domain-specific story splits." },
  ];
  const selectedFlow = flowSteps.find((step) => step.id === selectedFlowStep) || flowSteps[0];
  const mvpIntegrations = ["Jira", "Confluence"];
  const integrationSources = INTEGRATIONS.map((integration) => ({
    name: integration.name,
    enabled: mvpIntegrations.includes(integration.name),
  }));
  const templatePreviewHtml = useMemo(() => {
    if (!effectiveTemplateText) {
      return "";
    }
    return marked.parse(effectiveTemplateText);
  }, [effectiveTemplateText]);

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
  const draftStatusDescription = (() => {
    if (runStatus === "loading") return "Draft generation in progress";
    if (runStatus === "error") return "Draft failed to generate";
    if (runStatus === "generated") return "Draft generated successfully";
    return "Ready to generate a draft";
  })();

  const handleSplitStory = async () => {
    setShowSplitPanel(true);
    setIsSplitting(true);
    
    // Simulate split analysis (in real implementation, call backend)
    try {
      // If we already have proposed artifacts from backend, use those
      if (storyRun?.proposed_artifacts && storyRun.proposed_artifacts.length > 0) {
        setManualSplits(storyRun.proposed_artifacts);
        setIsSplitting(false);
        return;
      }
      
      // Generate suggested splits based on acceptance criteria
      const story = populatedStory;
      if (!story) {
        setIsSplitting(false);
        return;
      }
      
      // Simple heuristic: split by acceptance criteria groups
      const acList = story.acceptance_criteria || [];
      const suggestedSplits = [];
      
      if (acList.length >= 2) {
        // Split into multiple stories based on AC
        const midpoint = Math.ceil(acList.length / 2);
        suggestedSplits.push({
          title: `${story.title || "Story"} - Part 1`,
          description: story.description || "",
          acceptance_criteria: acList.slice(0, midpoint).map((ac) => formatAcceptanceCriteria(ac)),
          suggested_ref_suffix: "A",
        });
        suggestedSplits.push({
          title: `${story.title || "Story"} - Part 2`,
          description: story.description || "",
          acceptance_criteria: acList.slice(midpoint).map((ac) => formatAcceptanceCriteria(ac)),
          suggested_ref_suffix: "B",
        });
      } else {
        // Single story, suggest creating sub-tasks
        suggestedSplits.push({
          title: story.title || "Main Story",
          description: story.description || "",
          acceptance_criteria: acList.map((ac) => formatAcceptanceCriteria(ac)),
          suggested_ref_suffix: "MAIN",
        });
      }
      
      setManualSplits(suggestedSplits);
    } catch (error) {
      console.error("Failed to analyze story for splitting:", error);
    } finally {
      setIsSplitting(false);
    }
  };

  const handleAddSplit = () => {
    setManualSplits((prev) => [
      ...prev,
      {
        title: `New Story Part ${prev.length + 1}`,
        description: "",
        acceptance_criteria: [],
        suggested_ref_suffix: String.fromCharCode(65 + prev.length), // A, B, C...
      },
    ]);
  };

  const handleRemoveSplit = (index) => {
    setManualSplits((prev) => prev.filter((_, i) => i !== index));
  };

  const handleCloseSplitPanel = () => {
    setShowSplitPanel(false);
    setManualSplits([]);
  };

  // Handlers for Story Splitting tab editable splits
  const handleSplitOnlyAdd = () => {
    setSplitOnlySplits((prev) => [
      ...prev,
      {
        title: `New Story Part ${prev.length + 1}`,
        description: "",
        acceptance_criteria: [],
        suggested_ref_suffix: String.fromCharCode(65 + prev.length), // A, B, C...
      },
    ]);
  };

  const handleSplitOnlyRemove = (index) => {
    setSplitOnlySplits((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSplitOnlyUpdate = (index, field, value) => {
    setSplitOnlySplits((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const handleSplitOnlyACUpdate = (splitIndex, acIndex, value) => {
    setSplitOnlySplits((prev) => {
      const updated = [...prev];
      const ac = [...(updated[splitIndex].acceptance_criteria || [])];
      ac[acIndex] = value;
      updated[splitIndex] = { ...updated[splitIndex], acceptance_criteria: ac };
      return updated;
    });
  };

  const handleSplitOnlyACAdd = (splitIndex) => {
    setSplitOnlySplits((prev) => {
      const updated = [...prev];
      const ac = [...(updated[splitIndex].acceptance_criteria || []), ""];
      updated[splitIndex] = { ...updated[splitIndex], acceptance_criteria: ac };
      return updated;
    });
  };

  const handleSplitOnlyACRemove = (splitIndex, acIndex) => {
    setSplitOnlySplits((prev) => {
      const updated = [...prev];
      const ac = [...(updated[splitIndex].acceptance_criteria || [])];
      ac.splice(acIndex, 1);
      updated[splitIndex] = { ...updated[splitIndex], acceptance_criteria: ac };
      return updated;
    });
  };

  // Handler for split-only flow (Splitting tab) - uses full multi-agent debate API
  const handleSplitOnly = async () => {
    if (!splitOnlyDraft.trim()) return;
    
    setSplitOnlyLoading(true);
    setSplitOnlyError("");
    setSplitOnlyResults(null);
    setSplitFlowStatus(buildInitialSplitFlowStatus());
    setSplitCurrentStep("drafting");
    
    // Simulate flow progress updates while API runs
    const flowSteps = ["drafting", "qa_critique", "dev_critique", "synthesis", "validation", "split_proposal"];
    let stepIndex = 0;
    
    const progressInterval = setInterval(() => {
      if (stepIndex < flowSteps.length) {
        const currentStep = flowSteps[stepIndex];
        setSplitCurrentStep(currentStep);
        setSplitFlowStatus(prev => {
          const next = { ...prev };
          // Mark previous steps as complete
          flowSteps.slice(0, stepIndex).forEach(step => {
            next[step] = "complete";
          });
          // Mark current step as running
          next[currentStep] = "running";
          return next;
        });
        stepIndex++;
      }
    }, 2500); // Advance step every 2.5 seconds
    
    try {
      const result = await splitStorySimple({
        story_text: splitOnlyDraft,
        title: null,
      });
      
      clearInterval(progressInterval);
      
      // Mark all steps complete
      setSplitFlowStatus({
        drafting: "complete",
        qa_critique: "complete",
        dev_critique: "complete",
        synthesis: "complete",
        validation: "complete",
        split_proposal: "complete",
      });
      setSplitCurrentStep("split_proposal");
      
      if (result.success) {
        setSplitOnlyResults({
          proposed_artifacts: result.proposed_artifacts,
          rationale: result.rationale,
        });
        // Copy to editable splits array
        setSplitOnlySplits(result.proposed_artifacts.map(art => ({...art})));
      } else {
        setSplitOnlyError(result.error || "Failed to split story.");
      }
    } catch (error) {
      clearInterval(progressInterval);
      setSplitOnlyError(error?.message || "Failed to split story.");
    } finally {
      setSplitOnlyLoading(false);
    }
  };

  const showResults = hasRun || isLoading || storyRun;

  return (
    <section className="page story-page">
      <div className="page-header">
        <h1>User Story Workshop</h1>
        <p>Detail and split user stories with AI-powered assistance.</p>
      </div>
      
      {/* Tab Navigation */}
      <div className="tab-navigation">
        <button
          type="button"
          className={`tab-btn ${activeTab === "detailing" ? "active" : ""}`}
          onClick={() => setActiveTab("detailing")}
        >
          Story Detailing
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "splitting" ? "active" : ""}`}
          onClick={() => setActiveTab("splitting")}
        >
          Story Splitting
        </button>
      </div>

      {/* Story Detailing Tab */}
      {activeTab === "detailing" && (
        <>
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
      {showResults && (
        <>
          <div className="card">
            <div className="section">
              <h3>Workflow</h3>
              <div className="flow-diagram">
                {flowSteps.map((step, index) => (
                  <React.Fragment key={step.id}>
                    <button
                      type="button"
                      className={`flow-node ${flowStatus[step.id]} ${
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
              <p className="muted">{selectedFlow?.detail}</p>
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
              <span
                className={`status-pill ${
                  runStatus === "loading" ? "loading" : runStatus === "error" ? "warn" : "success"
                }`}
              >
                {runStatus === "loading" && <span className="status-spinner" />}
                {runStatus === "loading" ? loadingLabel : runStatus === "error" ? "Draft Error" : "Draft Generated"}
              </span>
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
                  <>
                    <p className="muted">{populatedStory?.description || "No description provided."}</p>
                    {renderReferenceChips(
                      "description",
                      referencesBySection,
                      evidenceLookup,
                      setSelectedEvidenceId
                    )}
                  </>
                )}
                {citationIssues.length > 0 && (
                  <div className="story-panel-row">
                    <span className="status-pill warn">Citation check</span>
                    <div className="muted">
                      {citationIssues.join(" · ")}
                    </div>
                  </div>
                )}
                {acceptanceCriteria.length > 0 && (
                  <ul className="story-criteria-list">
                    {acceptanceCriteria.map((item, index) => (
                      <li key={item}>
                        <span>{index + 1}. {item}</span>
                        <span className={`status-pill ${validationGaps.length > 0 && index === 1 ? "warn" : "success"}`}>
                          {validationGaps.length > 0 && index === 1 ? "Gap Detected" : "Validated"}
                        </span>
                        {renderReferenceChips(
                          "acceptance_criteria",
                          referencesBySection,
                          evidenceLookup,
                          setSelectedEvidenceId
                        )}
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
                      <button
                        key={item.key}
                        type="button"
                        className={`story-evidence-chip ${
                          selectedEvidenceId === item.key ? "active" : ""
                        }`}
                        onClick={() => setSelectedEvidenceId(item.key)}
                      >
                        {item.label}
                      </button>
                    ))
                  ) : (
                    <p className="muted">No evidence retrieved yet.</p>
                  )}
                </div>
                {evidenceDetails.length > 0 && (
                  <div className="evidence-detail-list">
                    {evidenceDetails.map((item) => (
                      <div
                        key={item.id}
                        className={`evidence-detail-card ${
                          selectedEvidenceId === item.id ? "active" : ""
                        }`}
                        onClick={() => setSelectedEvidenceId(item.id)}
                        role="button"
                        tabIndex={0}
                      >
                        <div className="evidence-detail-header">
                          <strong>{item.title || "Evidence"}</strong>
                          <span className="muted">{item.source || "source"}</span>
                        </div>
                        {item.excerpt && <p className="muted">{item.excerpt}</p>}
                        {item.url && (
                          <a className="text-link" href={item.url} target="_blank" rel="noreferrer">
                            View source
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="story-panel">
                <h4>Evidence Traceability</h4>
                <p className="muted" style={{ marginTop: 0, marginBottom: "12px", fontSize: "13px" }}>
                  How your story is supported by source documents
                </p>
                {isLoading ? (
                  <div className="loading-row">
                    <span className="status-spinner" />
                    <span className="muted">Analyzing evidence sources...</span>
                  </div>
                ) : evidenceTraceability ? (
                  <div className="evidence-traceability">
                    {/* Coverage Summary */}
                    <div className="traceability-summary">
                      <div className="traceability-stat">
                        <span className="traceability-stat-value">{evidenceTraceability.totalEvidence}</span>
                        <span className="traceability-stat-label">Evidence Items</span>
                      </div>
                      <div className="traceability-stat">
                        <span className="traceability-stat-value">{evidenceTraceability.totalSources}</span>
                        <span className="traceability-stat-label">Sources</span>
                      </div>
                      <div className="traceability-stat">
                        <span className="traceability-stat-value">{evidenceTraceability.coveragePercent}%</span>
                        <span className="traceability-stat-label">Coverage</span>
                      </div>
                    </div>

                    {/* Visual Flow: Sources → Sections */}
                    <div className="traceability-flow">
                      {/* Sources Column */}
                      <div className="traceability-column">
                        <div className="traceability-column-header">
                          <span className="traceability-column-icon">📥</span>
                          <span>Sources</span>
                        </div>
                        <div className="traceability-items">
                          {evidenceTraceability.sources.map((source) => (
                            <div
                              key={source.name}
                              className={`traceability-item source-item ${
                                selectedEvidenceId &&
                                source.evidence.some((e) => e.id === selectedEvidenceId)
                                  ? "active"
                                  : ""
                              }`}
                            >
                              <span className="traceability-item-icon">{source.icon}</span>
                              <span className="traceability-item-name">{source.displayName}</span>
                              <span className="traceability-item-badge">{source.evidence.length}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Arrow */}
                      <div className="traceability-arrow">
                        <span>→</span>
                        <span className="traceability-arrow-label">supports</span>
                      </div>

                      {/* Sections Column */}
                      <div className="traceability-column">
                        <div className="traceability-column-header">
                          <span className="traceability-column-icon">📋</span>
                          <span>Story Sections</span>
                        </div>
                        <div className="traceability-items">
                          {evidenceTraceability.sections.map((section) => (
                            <div
                              key={section.name}
                              className={`traceability-item section-item ${
                                section.evidenceCount > 0 ? "supported" : "unsupported"
                              }`}
                            >
                              <span className="traceability-item-name">{section.displayName}</span>
                              <span
                                className={`traceability-item-status ${
                                  section.evidenceCount > 0 ? "success" : "warning"
                                }`}
                              >
                                {section.evidenceCount > 0
                                  ? `${section.evidenceCount} evidence`
                                  : "No evidence"}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Selected Evidence Detail */}
                    {selectedEvidenceId && evidenceLookup[selectedEvidenceId] && (
                      <div className="traceability-detail">
                        <div className="traceability-detail-header">
                          <span className="muted">Selected Evidence Trail</span>
                        </div>
                        <div className="traceability-trail">
                          <span className="trail-step">
                            {getSourceIcon(evidenceLookup[selectedEvidenceId].source)}{" "}
                            {formatSourceName(evidenceLookup[selectedEvidenceId].source)}
                          </span>
                          <span className="trail-arrow">→</span>
                          <span className="trail-step">
                            📄 {evidenceLookup[selectedEvidenceId].title || "Document"}
                          </span>
                          <span className="trail-arrow">→</span>
                          <span className="trail-step">
                            📋 {formatSectionName(evidenceLookup[selectedEvidenceId].section)}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="muted">No evidence traceability data yet.</p>
                )}
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

          {/* Split Story Section - Always visible after story generation */}
          {runStatus === "generated" && populatedStory && (
            <div className="card">
              <div className="section">
                <div className="split-story-header">
                  <div>
                    <h3>Story Splitting</h3>
                    <p className="muted">
                      {storyRun?.proposed_artifacts?.length > 0
                        ? "System recommends splitting this story based on INVEST analysis."
                        : "Split this story into smaller, more manageable pieces."}
                    </p>
                  </div>
                  {!showSplitPanel && (
                    <button
                      type="button"
                      className="primary"
                      onClick={handleSplitStory}
                      disabled={isSplitting}
                    >
                      {isSplitting ? "Analyzing..." : "Split Story"}
                    </button>
                  )}
                </div>

                {/* Auto-recommended splits badge */}
                {storyRun?.proposed_artifacts?.length > 0 && !showSplitPanel && (
                  <div className="split-recommendation-badge">
                    <span className="status-pill warn">
                      Split Recommended: {storyRun.proposed_artifacts.length} parts suggested
                    </span>
                  </div>
                )}

                {/* Split Panel - Shows when triggered */}
                {showSplitPanel && (
                  <div className="split-panel-content">
                    {isSplitting ? (
                      <div className="loading-row" style={{ padding: "20px", justifyContent: "center" }}>
                        <span className="status-spinner" />
                        <span className="muted">Analyzing story for optimal splits...</span>
                      </div>
                    ) : (
                      <>
                        <div className="split-cards-grid">
                          {(manualSplits.length > 0 ? manualSplits : storyRun?.proposed_artifacts || []).map((artifact, idx) => (
                            <div key={idx} className="split-card">
                              <div className="split-card-header">
                                <span className="split-badge">
                                  {artifact.suggested_ref_suffix || artifact.human_ref || `Part ${idx + 1}`}
                                </span>
                                <button
                                  type="button"
                                  className="split-remove-btn"
                                  onClick={() => handleRemoveSplit(idx)}
                                  title="Remove this split"
                                >
                                  ×
                                </button>
                              </div>
                              <h4 className="split-card-title">{artifact.title}</h4>
                              {artifact.description && (
                                <p className="muted">{artifact.description}</p>
                              )}
                              {artifact.acceptance_criteria && artifact.acceptance_criteria.length > 0 && (
                                <div className="split-card-ac">
                                  <strong>Acceptance Criteria:</strong>
                                  <ul>
                                    {artifact.acceptance_criteria.map((ac, i) => (
                                      <li key={i}>{typeof ac === "string" ? ac : formatAcceptanceCriteria(ac)}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          ))}
                          
                          {/* Add new split card */}
                          <button
                            type="button"
                            className="split-card split-card-add"
                            onClick={handleAddSplit}
                          >
                            <span className="split-add-icon">+</span>
                            <span>Add Another Split</span>
                          </button>
                        </div>

                        <div className="actions align-left" style={{ marginTop: "16px" }}>
                          <button
                            type="button"
                            className="ghost"
                            onClick={handleCloseSplitPanel}
                          >
                            Cancel
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="card" style={{ position: 'relative' }}>
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
            <div className="coming-soon-overlay">
              <span>Coming Soon</span>
            </div>
          </div>
        </>
      )}
        </>
      )}

      {/* Story Splitting Tab */}
      {activeTab === "splitting" && (
        <>
          <div className="card">
            <div className="section">
              <h3>Story to Split</h3>
              <p className="muted">
                Enter a user story that may be too large or covers multiple features.
                The AI will analyze it and propose optimal splits following INVEST principles.
              </p>
              <textarea
                rows={8}
                value={splitOnlyDraft}
                onChange={(event) => setSplitOnlyDraft(event.target.value)}
                placeholder={`Example:
As a user, I want to see the currency of stored monetary values so that I can distinguish between historical BGN data and new EUR data.

Acceptance Criteria:
- Order model can store payment currency (BGN or EUR)
- Frame model can store the price currency (BGN or EUR)
- Glasses model can store the price currency (BGN or EUR)
- All existing records are marked as BGN
- Database migration completes successfully on production`}
              />
              <div className="actions" style={{ marginTop: "16px" }}>
                <button
                  type="button"
                  className="primary"
                  disabled={!splitOnlyDraft.trim() || splitOnlyLoading}
                  onClick={handleSplitOnly}
                >
                  {splitOnlyLoading ? "Analyzing & Splitting..." : "Analyze & Split Story"}
                </button>
              </div>
            </div>
          </div>

          {splitOnlyError && (
            <div className="card">
              <div className="section">
                <p className="error-text">{splitOnlyError}</p>
              </div>
            </div>
          )}

          {/* Workflow Status Indicator */}
          {splitOnlyLoading && (
            <div className="card">
              <div className="section">
                <div className="split-workflow-header">
                  <h3>Multi-Agent Debate in Progress</h3>
                  <span className="status-pill loading">
                    <span className="status-spinner" />
                    Running · {splitLoadingSeconds}s
                  </span>
                </div>
                <p className="muted" style={{ marginBottom: "16px" }}>
                  Running full debate cycle with PO, QA, and Developer agents...
                </p>
                <div className="flow-diagram split-flow-diagram">
                  {splitFlowSteps.map((step, index) => (
                    <React.Fragment key={step.id}>
                      <button
                        type="button"
                        className={`flow-node ${splitFlowStatus[step.id]} ${
                          splitCurrentStep === step.id ? "active" : ""
                        }`}
                        onClick={() => setSplitCurrentStep(step.id)}
                      >
                        {step.label}
                      </button>
                      {index < splitFlowSteps.length - 1 && <span className="flow-connector" />}
                    </React.Fragment>
                  ))}
                </div>
                <p className="muted" style={{ marginTop: "12px", textAlign: "center" }}>
                  {splitFlowSteps.find(s => s.id === splitCurrentStep)?.detail}
                </p>
              </div>
            </div>
          )}

          {splitOnlySplits.length > 0 && (
            <div className="card">
              <div className="section">
                <div className="split-story-header">
                  <div>
                    <h3>Proposed Story Splits</h3>
                    <p className="muted">
                      {splitOnlySplits.length} stories generated following INVEST principles.
                      Each story is Independent, Small, and Testable. You can edit, add, or remove splits below.
                    </p>
                  </div>
                </div>

                <div className="split-cards-grid">
                  {splitOnlySplits.map((artifact, idx) => (
                    <div key={idx} className="split-card split-card-editable">
                      <div className="split-card-header">
                        <input
                          type="text"
                          className="split-badge-input"
                          value={artifact.suggested_ref_suffix || artifact.human_ref || `Part ${idx + 1}`}
                          onChange={(e) => handleSplitOnlyUpdate(idx, "suggested_ref_suffix", e.target.value)}
                          placeholder="Ref"
                        />
                        <button
                          type="button"
                          className="split-remove-btn"
                          onClick={() => handleSplitOnlyRemove(idx)}
                          title="Remove this split"
                        >
                          ×
                        </button>
                      </div>
                      <input
                        type="text"
                        className="split-card-title-input"
                        value={artifact.title}
                        onChange={(e) => handleSplitOnlyUpdate(idx, "title", e.target.value)}
                        placeholder="Story title..."
                      />
                      <textarea
                        className="split-card-desc-input"
                        value={artifact.description || ""}
                        onChange={(e) => handleSplitOnlyUpdate(idx, "description", e.target.value)}
                        placeholder="Story description..."
                        rows={3}
                      />
                      <div className="split-card-ac">
                        <strong>Acceptance Criteria:</strong>
                        <ul className="split-ac-list">
                          {(artifact.acceptance_criteria || []).map((ac, i) => (
                            <li key={i} className="split-ac-item">
                              <textarea
                                className="split-ac-input"
                                value={typeof ac === "string" ? ac : formatAcceptanceCriteria(ac)}
                                onChange={(e) => handleSplitOnlyACUpdate(idx, i, e.target.value)}
                                placeholder="Acceptance criterion..."
                                rows={2}
                              />
                              <button
                                type="button"
                                className="split-ac-remove"
                                onClick={() => handleSplitOnlyACRemove(idx, i)}
                                title="Remove criterion"
                              >
                                ×
                              </button>
                            </li>
                          ))}
                        </ul>
                        <button
                          type="button"
                          className="split-ac-add"
                          onClick={() => handleSplitOnlyACAdd(idx)}
                        >
                          + Add Criterion
                        </button>
                      </div>
                    </div>
                  ))}
                  
                  {/* Add new split card */}
                  <button
                    type="button"
                    className="split-card split-card-add"
                    onClick={handleSplitOnlyAdd}
                  >
                    <span className="split-add-icon">+</span>
                    <span>Add Another Split</span>
                  </button>
                </div>

                <div className="actions align-left" style={{ marginTop: "24px", position: "relative" }}>
                  <button type="button" className="primary" disabled>
                    Export All to Jira
                  </button>
                  <button type="button" className="ghost" disabled>
                    Export to Linear
                  </button>
                  <div className="coming-soon-overlay" style={{ borderRadius: "8px" }}>
                    <span>Coming Soon</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {splitOnlyResults && splitOnlySplits.length === 0 && !splitOnlyLoading && (
            <div className="card">
              <div className="section">
                <p className="muted">
                  No split proposals generated. The story may already be appropriately sized,
                  or try adding more acceptance criteria to analyze.
                </p>
              </div>
            </div>
          )}
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

const buildInitialSplitFlowStatus = () => ({
  drafting: "pending",
  qa_critique: "pending",
  dev_critique: "pending",
  synthesis: "pending",
  validation: "pending",
  split_proposal: "pending",
});

const buildFlowOrder = () => [
  "template_parser",
  "knowledge_retrieval",
  "story_writer",
  "validation",
  "critique_loop",
];


const buildEvidenceItems = (context, evidenceItems) => {
  if (Array.isArray(evidenceItems) && evidenceItems.length > 0) {
    return evidenceItems.map((item) => ({
      key: item.id,
      label: `${item.source || "Source"} · ${item.title || "Untitled"} · ${
        item.confidence != null ? `Confidence ${item.confidence}` : "Confidence n/a"
      }`,
    }));
  }
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

const mapIntegrationToSource = (name) => {
  const normalized = (name || "").toLowerCase();
  const mapping = {
    jira: "jira",
    confluence: "confluence",
    github: "github",
    notion: "notion",
    linear: "linear",
    sharepoint: "sharepoint",
  };
  return mapping[normalized] || null;
};

const buildReferenceSummary = (fieldReferences) => {
  if (!fieldReferences) {
    return "";
  }
  const entries = Object.entries(fieldReferences);
  if (!entries.length) {
    return "";
  }
  const totalRefs = entries.reduce((count, [, refs]) => count + (refs?.length || 0), 0);
  return `References captured: ${totalRefs}`;
};

const buildEvidenceLookup = (evidenceItems) => {
  if (!Array.isArray(evidenceItems)) {
    return {};
  }
  return evidenceItems.reduce((acc, item) => {
    acc[item.id] = item;
    return acc;
  }, {});
};

const buildContextGraphSummary = (contextGraph) => {
  if (!contextGraph) {
    return null;
  }
  const nodes = Array.isArray(contextGraph.nodes) ? contextGraph.nodes : [];
  const edges = Array.isArray(contextGraph.edges) ? contextGraph.edges : [];
  const nodeTypes = nodes.reduce((acc, node) => {
    const type = node?.type || "unknown";
    acc[type] = (acc[type] || 0) + 1;
    return acc;
  }, {});
  const nodeTypesSummary = Object.entries(nodeTypes)
    .map(([type, count]) => `${type}: ${count}`)
    .join(" · ");
  return {
    nodeCount: nodes.length,
    edgeCount: edges.length,
    nodeTypesSummary,
  };
};

const buildContextGraphDetails = (contextGraph, selectedEvidenceId, evidenceLookup) => {
  if (!contextGraph) {
    return null;
  }
  const nodes = Array.isArray(contextGraph.nodes) ? contextGraph.nodes : [];
  const edges = Array.isArray(contextGraph.edges) ? contextGraph.edges : [];
  const highlightIds = new Set();
  let highlightLabel = "";
  if (selectedEvidenceId) {
    highlightIds.add(`document:${selectedEvidenceId}`);
    highlightIds.add(`chunk:${selectedEvidenceId}`);
    const evidence = evidenceLookup?.[selectedEvidenceId];
    if (evidence?.source) {
      highlightIds.add(`source:${evidence.source}`);
    }
    if (evidence?.section) {
      highlightIds.add(`story_section:${evidence.section}`);
    }
    highlightLabel = evidence
      ? `${evidence.source || "Source"} · ${evidence.title || "Evidence"}`
      : selectedEvidenceId;
  }
  const maxNodes = 12;
  const maxEdges = 12;
  return {
    nodes: nodes.slice(0, maxNodes),
    edges: edges.slice(0, maxEdges),
    totalNodes: nodes.length,
    totalEdges: edges.length,
    hasMoreNodes: nodes.length > maxNodes,
    hasMoreEdges: edges.length > maxEdges,
    highlightIds,
    highlightLabel,
  };
};

/**
 * Build a user-friendly evidence traceability view.
 * Shows: Sources → Evidence → Story Sections in a clear visual flow.
 */
const buildEvidenceTraceability = (evidenceItems, fieldReferences) => {
  if (!evidenceItems || evidenceItems.length === 0) {
    return null;
  }

  // Group evidence by source
  const sourceMap = {};
  evidenceItems.forEach((item) => {
    const source = item.source || "unknown";
    if (!sourceMap[source]) {
      sourceMap[source] = {
        name: source,
        displayName: formatSourceName(source),
        icon: getSourceIcon(source),
        evidence: [],
      };
    }
    sourceMap[source].evidence.push(item);
  });

  // Group evidence by section it supports
  const sectionMap = {};
  evidenceItems.forEach((item) => {
    const section = item.section || "description";
    if (!sectionMap[section]) {
      sectionMap[section] = {
        name: section,
        displayName: formatSectionName(section),
        evidenceCount: 0,
        sources: new Set(),
      };
    }
    sectionMap[section].evidenceCount++;
    sectionMap[section].sources.add(item.source);
  });

  // Convert section sources to array
  Object.values(sectionMap).forEach((section) => {
    section.sources = Array.from(section.sources);
  });

  // Calculate coverage
  const totalSections = Object.keys(sectionMap).length;
  const sectionsWithEvidence = Object.values(sectionMap).filter(
    (s) => s.evidenceCount > 0
  ).length;
  const coveragePercent = totalSections > 0
    ? Math.round((sectionsWithEvidence / totalSections) * 100)
    : 0;

  return {
    sources: Object.values(sourceMap),
    sections: Object.values(sectionMap),
    totalEvidence: evidenceItems.length,
    totalSources: Object.keys(sourceMap).length,
    totalSections,
    sectionsWithEvidence,
    coveragePercent,
  };
};

const formatSourceName = (source) => {
  const names = {
    jira: "Jira",
    confluence: "Confluence",
    github: "GitHub",
    notion: "Notion",
    direct: "Direct Link",
    codebase: "Codebase",
    derived: "AI Derived",
  };
  return names[source?.toLowerCase()] || source || "Unknown";
};

const getSourceIcon = (source) => {
  const icons = {
    jira: "🎫",
    confluence: "📄",
    github: "💻",
    notion: "📝",
    direct: "🔗",
    codebase: "📦",
    derived: "🤖",
  };
  return icons[source?.toLowerCase()] || "📋";
};

const formatSectionName = (section) => {
  const names = {
    description: "Description",
    acceptance_criteria: "Acceptance Criteria",
    assumptions: "Assumptions",
    dependencies: "Dependencies",
    nfrs: "Non-Functional Requirements",
    out_of_scope: "Out of Scope",
    open_questions: "Open Questions",
  };
  return names[section] || section?.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) || "Other";
};

const renderReferenceChips = (
  sectionKey,
  referencesBySection,
  evidenceLookup,
  onSelectEvidence
) => {
  const refs = referencesBySection?.[sectionKey] || [];
  if (!refs.length) {
    return null;
  }
  return (
    <div className="reference-chips">
      {refs.map((refId) => {
        const evidence = evidenceLookup?.[refId];
        const label = evidence
          ? `${evidence.source || "Source"} · ${evidence.title || "Evidence"}`
          : refId;
        return (
          <button
            key={refId}
            type="button"
            className="reference-chip"
            onClick={() => onSelectEvidence?.(refId)}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
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

const buildCitationIssues = (story) => {
  if (!story) {
    return [];
  }
  const issues = [];
  if (!hasCitation(story.description)) {
    issues.push("Description missing citation tags");
  }
  (story.acceptance_criteria || []).forEach((item, index) => {
    const formatted = formatAcceptanceCriteria(item);
    if (formatted && !hasCitation(formatted)) {
      issues.push(`Acceptance criteria ${index + 1} missing citation tags`);
    }
  });
  return issues;
};

const hasCitation = (text) => {
  if (!text || typeof text !== "string") {
    return false;
  }
  return /\[source:\s*[^\]]+\]/i.test(text);
};
