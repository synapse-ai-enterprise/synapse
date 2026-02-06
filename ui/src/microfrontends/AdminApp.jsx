import React, { useEffect, useState, useRef } from "react";

import { INTEGRATIONS } from "../shared/data";
import {
  connectIntegration,
  fetchIntegrations,
  fetchModelsConfig,
  updateModelConfig,
  resetModelConfig,
  syncIntegration,
  testIntegration,
  updateIntegrationScopes,
  fetchTemplates,
  fetchTemplate,
  fetchActiveTemplate,
  createTemplate,
  updateTemplate,
  rollbackTemplate,
} from "../shared/api";
import { PromptManagementApp } from "./PromptManagementApp";

const ADMIN_ITEMS = [
  { id: "templates", label: "Templates" },
  { id: "integrations", label: "Integrations" },
  { id: "models", label: "Models & Agents" },
  { id: "audit", label: "Audit & Governance" },
];

// Tooltip descriptions for integration actions
const ACTION_TOOLTIPS = {
  connect: "Connect this integration to enable data sync with Synapse",
  scopes: "Configure which projects or boards this integration can access",
  sync: "Pull the latest data from this service into Synapse",
  test: "Verify the API credentials and connection are working properly",
  spaces: "Configure which Confluence spaces this integration can access",
};

// Get tooltip for footer action
const getFooterActionTooltip = (actionType, integrationName) => {
  if (actionType === "sync") {
    return `Sync data from ${integrationName} into Synapse. This may take a few moments.`;
  }
  if (actionType === "test") {
    return `Test the connection to ${integrationName} to verify credentials are valid.`;
  }
  return "";
};

// Loading spinner component
const LoadingSpinner = ({ size = 14 }) => (
  <span
    className="btn-spinner"
    style={{
      width: size,
      height: size,
      border: "2px solid rgba(255,255,255,0.3)",
      borderTopColor: "#fff",
      borderRadius: "50%",
      display: "inline-block",
      animation: "status-spin 0.8s linear infinite",
    }}
  />
);

// Tooltip wrapper component for better UX
const TooltipButton = ({ children, tooltip, disabled, disabledReason, ...props }) => {
  const finalTooltip = disabled && disabledReason ? disabledReason : tooltip;
  return (
    <button
      {...props}
      disabled={disabled}
      title={finalTooltip}
      style={{ position: "relative", ...props.style }}
    >
      {children}
    </button>
  );
};

export function AdminApp({
  templateText,
  setTemplateText,
  adminTab,
  setAdminTab,
  technicalEnabled,
  setTechnicalEnabled,
  businessEnabled,
  setBusinessEnabled,
  poEnabled,
  setPoEnabled,
  qaEnabled,
  setQaEnabled,
  devEnabled,
  setDevEnabled,
}) {
  const [activeAdmin, setActiveAdmin] = useState(adminTab || "templates");
  const [templateEditMode, setTemplateEditMode] = useState(false);
  const [integrations, setIntegrations] = useState(INTEGRATIONS);
  const [loadingActions, setLoadingActions] = useState({}); // Track loading state per integration+action
  const mvpIntegrations = ["jira", "confluence"];
  const fileInputRef = useRef(null);
  
  // Template management state
  const [templates, setTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState(null);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [templateArtifactType, setTemplateArtifactType] = useState("user_story");
  const [templateLoading, setTemplateLoading] = useState(false);
  const [editedTemplateContent, setEditedTemplateContent] = useState("");
  const [editedChangelog, setEditedChangelog] = useState("");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadData, setUploadData] = useState({ name: "", content: "", description: "" });
  const [templateSaveLoading, setTemplateSaveLoading] = useState(false);
  
  // Model configuration state
  const [modelsConfig, setModelsConfig] = useState({
    current_model: "",
    current_provider: "",
    available_models: [],
    ollama_models: [],
  });
  const [selectedModel, setSelectedModel] = useState("");
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelSaveLoading, setModelSaveLoading] = useState(false);
  const [temperature, setTemperature] = useState(0.7);
  const [hasModelChanges, setHasModelChanges] = useState(false);
  const [modelSaveMessage, setModelSaveMessage] = useState(null);

  // Helper to set loading state for a specific action
  const setActionLoading = (integrationName, actionType, isLoading) => {
    const key = `${integrationName}-${actionType}`;
    setLoadingActions((prev) => ({ ...prev, [key]: isLoading }));
  };

  // Check if a specific action is loading
  const isActionLoading = (integrationName, actionType) => {
    const key = `${integrationName}-${actionType}`;
    return loadingActions[key] || false;
  };

  useEffect(() => {
    if (adminTab && adminTab !== activeAdmin) {
      setActiveAdmin(adminTab);
    }
  }, [adminTab, activeAdmin]);

  // Load templates when templates tab is active or artifact type changes
  useEffect(() => {
    if (activeAdmin !== "templates") return;
    
    let isMounted = true;
    const loadTemplates = async () => {
      setTemplateLoading(true);
      try {
        const data = await fetchTemplates({ artifact_type: templateArtifactType });
        if (!isMounted) return;
        
        const templateList = data.templates || [];
        setTemplates(templateList);
        
        // Auto-select first template if none selected
        if (templateList.length > 0 && !selectedTemplateId) {
          const firstTemplate = templateList[0];
          setSelectedTemplateId(firstTemplate.id);
          setSelectedTemplate(firstTemplate);
          
          // Set template text for parent component
          const activeVersion = firstTemplate.active_version || firstTemplate.versions?.[0];
          if (activeVersion?.content && setTemplateText) {
            setTemplateText(activeVersion.content);
          }
        }
      } catch (error) {
        console.warn("Failed to load templates", error);
      } finally {
        if (isMounted) {
          setTemplateLoading(false);
        }
      }
    };

    loadTemplates();
    return () => {
      isMounted = false;
    };
  }, [activeAdmin, templateArtifactType, selectedTemplateId, setTemplateText]);

  // Load specific template when selection changes
  useEffect(() => {
    if (!selectedTemplateId) return;
    
    let isMounted = true;
    const loadTemplate = async () => {
      try {
        const template = await fetchTemplate(selectedTemplateId);
        if (!isMounted) return;
        
        setSelectedTemplate(template);
        
        // Find active version
        const activeVersion = template.versions?.find(v => v.is_active) || template.versions?.[0];
        if (activeVersion?.content) {
          setEditedTemplateContent(activeVersion.content);
          if (setTemplateText) {
            setTemplateText(activeVersion.content);
          }
        }
      } catch (error) {
        console.warn("Failed to load template", error);
      }
    };

    loadTemplate();
    return () => {
      isMounted = false;
    };
  }, [selectedTemplateId, setTemplateText]);

  useEffect(() => {
    let isMounted = true;
    const loadIntegrations = async () => {
      try {
        const data = await fetchIntegrations();
        if (!isMounted || !Array.isArray(data) || data.length === 0) return;
        const normalized = data.map(normalizeIntegration);
        setIntegrations(normalized);
      } catch (error) {
        console.warn("Failed to load integrations", error);
      }
    };

    loadIntegrations();
    return () => {
      isMounted = false;
    };
  }, []);

  // Load models configuration
  useEffect(() => {
    let isMounted = true;
    const loadModels = async () => {
      setModelsLoading(true);
      setModelSaveMessage(null);
      try {
        const data = await fetchModelsConfig();
        if (!isMounted) return;
        console.log("Models config loaded:", data); // Debug log
        setModelsConfig(data);
        // Set selected model to current model from backend
        if (data.current_model) {
          setSelectedModel(data.current_model);
        }
        setHasModelChanges(false);
      } catch (error) {
        console.error("Failed to load models configuration", error);
        const isNetworkError =
          error?.message === "Failed to fetch" ||
          error?.name === "TypeError" ||
          (error?.message && error.message.includes("NetworkError"));
        const hint = import.meta.env.DEV
          ? " Start the backend (e.g. ./scripts/start_local_ui_backend.sh or poetry run python -m src.main) so the API runs at http://localhost:8000."
          : " Check that the API is deployed and reachable.";
        setModelSaveMessage({
          type: "error",
          text: isNetworkError
            ? `Cannot reach the API. Is the backend running?${hint}`
            : `Failed to load models: ${error?.message || "Unknown error"}.`,
        });
      } finally {
        if (isMounted) {
          setModelsLoading(false);
        }
      }
    };

    // Load models when the models tab is active
    if (activeAdmin === "models") {
      loadModels();
    }

    return () => {
      isMounted = false;
    };
  }, [activeAdmin]);

  // Handle model selection change
  const handleModelChange = (newModel) => {
    setSelectedModel(newModel);
    setHasModelChanges(newModel !== modelsConfig.current_model);
    setModelSaveMessage(null);
  };

  // Handle temperature change
  const handleTemperatureChange = (newTemp) => {
    setTemperature(newTemp);
    setHasModelChanges(true);
    setModelSaveMessage(null);
  };

  // Save model configuration
  const handleSaveModelConfig = async () => {
    if (!selectedModel) return;
    
    setModelSaveLoading(true);
    setModelSaveMessage(null);
    try {
      const result = await updateModelConfig({
        model: selectedModel,
        temperature: temperature,
      });
      
      if (result.success) {
        setModelsConfig(prev => ({
          ...prev,
          current_model: result.model,
          current_provider: result.provider,
        }));
        setHasModelChanges(false);
        setModelSaveMessage({
          type: "success",
          text: result.message,
        });
      } else {
        setModelSaveMessage({
          type: "error",
          text: "Failed to update model configuration",
        });
      }
    } catch (error) {
      console.error("Failed to save model configuration", error);
      setModelSaveMessage({
        type: "error",
        text: error.message || "Failed to save model configuration",
      });
    } finally {
      setModelSaveLoading(false);
    }
  };

  // Reset to environment defaults
  const handleResetModelConfig = async () => {
    const confirmed = window.confirm(
      "Reset to environment defaults?\n\nThis will revert to the model configured in your .env file."
    );
    if (!confirmed) return;
    
    setModelSaveLoading(true);
    setModelSaveMessage(null);
    try {
      const result = await resetModelConfig();
      
      if (result.success) {
        setModelsConfig(prev => ({
          ...prev,
          current_model: result.model,
          current_provider: result.provider,
        }));
        setSelectedModel(result.model);
        setHasModelChanges(false);
        setModelSaveMessage({
          type: "success",
          text: result.message,
        });
      }
    } catch (error) {
      console.error("Failed to reset model configuration", error);
      setModelSaveMessage({
        type: "error",
        text: error.message || "Failed to reset model configuration",
      });
    } finally {
      setModelSaveLoading(false);
    }
  };

  const normalizeIntegration = (integration) => {
    const statusMap = {
      connected: { label: "Connected", accent: "success" },
      not_connected: { label: "Not connected", accent: "muted" },
      error: { label: "Error", accent: "warning" },
    };
    const statusMeta = statusMap[integration.status] || statusMap.not_connected;
    const footerActions = Array.isArray(integration.footer_actions)
      ? integration.footer_actions.map((action) => ({
          label: action.label,
          actionType: action.action_type,
        }))
      : [];
    return {
      name: integration.name,
      status: statusMeta.label,
      accent: statusMeta.accent,
      action: integration.action,
      actionType: integration.action_type || "connect",
      details: integration.details || [],
      footerAction: integration.footer_action || null,
      footerActions,
    };
  };

  const updateIntegration = (updatedIntegration) => {
    setIntegrations((prev) =>
      prev.map((integration) =>
        integration.name === updatedIntegration.name ? updatedIntegration : integration
      )
    );
  };

  const normalizeIntegrationKey = (name) => (name || "").toLowerCase();

  const handleIntegrationAction = async (integration) => {
    const actionType = integration.actionType || "connect";
    setActionLoading(integration.name, "main", true);
    
    try {
      if (actionType === "connect") {
        const result = await connectIntegration(integration.name);
        updateIntegration(normalizeIntegration(result));
        window.alert(`Successfully connected to ${integration.name}!`);
        return;
      }
      if (actionType === "scopes") {
        const scopes =
          integration.details.find((detail) => detail.label === "Allowed projects")?.value || "";
        const scopeList = scopes
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean);
        const result = await updateIntegrationScopes(integration.name, scopeList);
        updateIntegration(normalizeIntegration(result));
        window.alert(`Scopes updated for ${integration.name}.`);
        return;
      }
      await testIntegration(integration.name);
    } catch (error) {
      console.warn("Integration action failed", error);
      const msg = error?.message && !error.message.startsWith("Request failed")
        ? error.message
        : `Action failed for ${integration.name}. Please check your configuration and try again.`;
      window.alert(msg);
    } finally {
      setActionLoading(integration.name, "main", false);
    }
  };

  const handleIntegrationTest = async (integration) => {
    setActionLoading(integration.name, "test", true);
    
    try {
      const result = await testIntegration(integration.name);
      if (result?.message) {
        window.alert(result.message);
      } else {
        window.alert(`Connection to ${integration.name} is working correctly!`);
      }
    } catch (error) {
      console.warn("Integration test failed", error);
      const msg = error?.message && !error.message.startsWith("Request failed")
        ? error.message
        : `Connection test failed for ${integration.name}. Please check your API credentials and try again.`;
      window.alert(msg);
    } finally {
      setActionLoading(integration.name, "test", false);
    }
  };

  const handleIntegrationFooterAction = async (integration, action) => {
    const actionType = action.actionType || "test";
    
    // Confirmation dialog for sync operations
    if (actionType === "sync") {
      const confirmed = window.confirm(
        `Sync data from ${integration.name}?\n\nThis will pull the latest projects, issues, and metadata from ${integration.name} into Synapse. This may take a few moments depending on the amount of data.`
      );
      if (!confirmed) return;
    }
    
    setActionLoading(integration.name, actionType, true);
    
    try {
      if (actionType === "sync") {
        const result = await syncIntegration(integration.name);
        if (result?.integration) {
          updateIntegration(normalizeIntegration(result.integration));
        }
        window.alert(`Successfully synced data from ${integration.name}!`);
        return;
      }
      if (actionType === "test") {
        const result = await testIntegration(integration.name);
        if (result?.message) {
          window.alert(result.message);
        } else {
          window.alert(`Connection to ${integration.name} is working correctly!`);
        }
      }
    } catch (error) {
      console.warn("Integration footer action failed", error);
      const msg = error?.message && !error.message.startsWith("Request failed")
        ? error.message
        : `${action.label} failed for ${integration.name}. Please check your configuration and try again.`;
      window.alert(msg);
    } finally {
      setActionLoading(integration.name, actionType, false);
    }
  };

  // ============================================
  // Template Management Handlers
  // ============================================

  const handleEditTemplate = () => {
    if (selectedTemplate) {
      const activeVersion = selectedTemplate.versions?.find(v => v.is_active) || selectedTemplate.versions?.[0];
      setEditedTemplateContent(activeVersion?.content || "");
      setEditedChangelog("");
      setTemplateEditMode(true);
    }
  };

  const handleSaveTemplate = async () => {
    if (!selectedTemplateId || !editedTemplateContent.trim()) return;
    
    setTemplateSaveLoading(true);
    try {
      const result = await updateTemplate(selectedTemplateId, {
        content: editedTemplateContent,
        changelog: editedChangelog || "Updated template content",
      });
      
      if (result?.template) {
        setSelectedTemplate(result.template);
        // Update in templates list
        setTemplates(prev => prev.map(t => 
          t.id === result.template.id ? { ...t, ...result.template } : t
        ));
        // Update parent component
        if (setTemplateText) {
          setTemplateText(editedTemplateContent);
        }
        setTemplateEditMode(false);
        window.alert("Template saved successfully!");
      }
    } catch (error) {
      console.warn("Failed to save template", error);
      window.alert("Failed to save template. Please try again.");
    } finally {
      setTemplateSaveLoading(false);
    }
  };

  const handleCancelEdit = () => {
    // Reset to original content
    if (selectedTemplate) {
      const activeVersion = selectedTemplate.versions?.find(v => v.is_active) || selectedTemplate.versions?.[0];
      setEditedTemplateContent(activeVersion?.content || "");
    }
    setEditedChangelog("");
    setTemplateEditMode(false);
  };

  const handleUploadClick = () => {
    setUploadData({ name: "", content: "", description: "" });
    setUploadModalOpen(true);
  };

  const handleFileUpload = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result;
      if (typeof content === "string") {
        setUploadData(prev => ({
          ...prev,
          name: prev.name || file.name.replace(/\.[^/.]+$/, ""),
          content,
        }));
      }
    };
    reader.readAsText(file);
  };

  const handleCreateTemplate = async () => {
    if (!uploadData.name.trim() || !uploadData.content.trim()) {
      window.alert("Please provide a template name and content.");
      return;
    }

    setTemplateSaveLoading(true);
    try {
      const result = await createTemplate({
        name: uploadData.name,
        artifact_type: templateArtifactType,
        description: uploadData.description,
        content: uploadData.content,
      });

      if (result?.template) {
        // Add to templates list
        setTemplates(prev => [result.template, ...prev]);
        // Select the new template
        setSelectedTemplateId(result.template.id);
        setSelectedTemplate(result.template);
        // Close modal
        setUploadModalOpen(false);
        setUploadData({ name: "", content: "", description: "" });
        window.alert("Template created successfully!");
      }
    } catch (error) {
      console.warn("Failed to create template", error);
      window.alert("Failed to create template. Please try again.");
    } finally {
      setTemplateSaveLoading(false);
    }
  };

  const handleRollback = async (version) => {
    if (!selectedTemplateId) return;
    
    const confirmed = window.confirm(
      `Roll back to version ${version}?\n\nThis will make version ${version} the active version.`
    );
    if (!confirmed) return;

    setTemplateSaveLoading(true);
    try {
      const result = await rollbackTemplate(selectedTemplateId, version);
      
      if (result?.template) {
        setSelectedTemplate(result.template);
        // Update in templates list
        setTemplates(prev => prev.map(t => 
          t.id === result.template.id ? { ...t, ...result.template } : t
        ));
        // Update content
        const activeVersion = result.template.versions?.find(v => v.is_active);
        if (activeVersion?.content && setTemplateText) {
          setTemplateText(activeVersion.content);
        }
        window.alert(`Rolled back to version ${version}`);
      }
    } catch (error) {
      console.warn("Failed to rollback template", error);
      window.alert("Failed to rollback template. Please try again.");
    } finally {
      setTemplateSaveLoading(false);
    }
  };

  const handleTestParse = () => {
    // For now, just show a preview of template parsing
    window.alert("Test parse functionality will validate the template structure and show sample output.\n\nThis feature is coming soon!");
  };

  // Get active version from selected template
  const activeVersion = selectedTemplate?.versions?.find(v => v.is_active) || selectedTemplate?.versions?.[0];
  const templateVersions = selectedTemplate?.versions || [];

  // Format version date
  const formatVersionDate = (dateStr) => {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" });
  };

  return (
    <section className="admin-layout">
      <aside className="sidebar">
        {ADMIN_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`side-link ${activeAdmin === item.id ? "active" : ""}`}
            onClick={() => {
              setActiveAdmin(item.id);
              if (setAdminTab) {
                setAdminTab(item.id);
              }
            }}
          >
            {item.label}
          </button>
        ))}
      </aside>

      <div className="admin-content">
        <div className="admin-section">
          {activeAdmin === "templates" && !templateEditMode && (
          <>
            <div className="page-header">
              <h1>Templates</h1>
              <p>Customize output structure and field mappings for each artifact type.</p>
            </div>
            <div className="toolbar">
              <div className="field-group">
                <label htmlFor="artifactType">Artifact type</label>
                <select 
                  id="artifactType"
                  value={templateArtifactType}
                  onChange={(e) => {
                    setTemplateArtifactType(e.target.value);
                    setSelectedTemplateId(null);
                    setSelectedTemplate(null);
                  }}
                >
                  <option value="user_story">User Story</option>
                  <option value="epic">Epic</option>
                  <option value="initiative">Initiative</option>
                </select>
              </div>
              {templates.length > 1 && (
                <div className="field-group">
                  <label htmlFor="templateSelect">Template</label>
                  <select
                    id="templateSelect"
                    value={selectedTemplateId || ""}
                    onChange={(e) => setSelectedTemplateId(e.target.value)}
                  >
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                </div>
              )}
              <button type="button" className="primary" onClick={handleUploadClick}>
                Upload template
              </button>
            </div>
            
            {templateLoading ? (
              <div className="card">
                <div className="section">
                  <div className="loading-row">
                    <LoadingSpinner />
                    <span className="muted">Loading templates...</span>
                  </div>
                </div>
              </div>
            ) : selectedTemplate ? (
              <>
                <div className="card">
                  <div className="card-header">
                    <div>
                      <h3>Template document</h3>
                      <p className="muted">
                        {selectedTemplate.description || `Active ${templateArtifactType.replace("_", " ")} template`}
                      </p>
                    </div>
                    <button type="button" className="ghost" onClick={handleEditTemplate}>
                      Edit
                    </button>
                  </div>
                  <div className="template-preview">
                    <div className="page-list">
                      {templateVersions.slice(0, 4).map((version, index) => (
                        <div 
                          key={version.version} 
                          className={`page-thumb ${version.is_active ? "active" : ""}`}
                          title={`Version ${version.version}`}
                        >
                          {index + 1}
                        </div>
                      ))}
                    </div>
                    <div className="document">
                      <h4>{selectedTemplate.name}</h4>
                      <p className="muted">
                        Version {activeVersion?.version || "1.0"} · Last updated {formatVersionDate(selectedTemplate.updated_at)}
                      </p>
                      {activeVersion?.field_mappings?.length > 0 && (
                        <div className="doc-section">
                          <h5>1. Field Mappings</h5>
                          <ul>
                            {activeVersion.field_mappings.map((fm, idx) => (
                              <li key={idx}>
                                {fm.source_field} → {fm.target_field} ({fm.required ? "required" : "optional"})
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {activeVersion?.output_structure && (
                        <div className="doc-section">
                          <h5>2. Output Structure</h5>
                          <pre className="code-block">{activeVersion.output_structure}</pre>
                        </div>
                      )}
                      {activeVersion?.content && (
                        <div className="doc-section">
                          <h5>Template Content Preview</h5>
                          <div className="template-content-preview">
                            {activeVersion.content.slice(0, 500)}
                            {activeVersion.content.length > 500 && "..."}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                <div className="card">
                  <div className="section">
                    <h3>Version history</h3>
                    <ul className="summary-list">
                      {templateVersions.map((version) => (
                        <li key={version.version} className={version.is_active ? "active-version" : ""}>
                          v{version.version} · {formatVersionDate(version.created_at)} · {version.is_active ? "Active" : "Archived"}
                          {version.changelog && <span className="version-changelog"> - {version.changelog}</span>}
                        </li>
                      ))}
                    </ul>
                    <div className="actions align-left">
                      <div className="field-group inline">
                        <select
                          id="rollbackVersion"
                          defaultValue=""
                          onChange={(e) => {
                            if (e.target.value) {
                              handleRollback(e.target.value);
                              e.target.value = "";
                            }
                          }}
                        >
                          <option value="" disabled>Roll back to...</option>
                          {templateVersions.filter(v => !v.is_active).map((version) => (
                            <option key={version.version} value={version.version}>
                              v{version.version}
                            </option>
                          ))}
                        </select>
                      </div>
                      <button type="button" className="ghost" onClick={handleTestParse}>
                        Test parse
                      </button>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="card">
                <div className="section">
                  <p className="muted">No templates found for this artifact type. Click "Upload template" to create one.</p>
                </div>
              </div>
            )}

            {/* Upload Template Modal */}
            {uploadModalOpen && (
              <div className="modal-overlay" onClick={() => setUploadModalOpen(false)}>
                <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                  <div className="modal-header">
                    <h3>Upload Template</h3>
                    <button 
                      type="button" 
                      className="modal-close"
                      onClick={() => setUploadModalOpen(false)}
                    >
                      ×
                    </button>
                  </div>
                  <div className="modal-body">
                    <div className="field-group">
                      <label htmlFor="uploadName">Template name</label>
                      <input
                        id="uploadName"
                        type="text"
                        value={uploadData.name}
                        onChange={(e) => setUploadData(prev => ({ ...prev, name: e.target.value }))}
                        placeholder="e.g., Custom User Story Template"
                      />
                    </div>
                    <div className="field-group">
                      <label htmlFor="uploadDescription">Description (optional)</label>
                      <input
                        id="uploadDescription"
                        type="text"
                        value={uploadData.description}
                        onChange={(e) => setUploadData(prev => ({ ...prev, description: e.target.value }))}
                        placeholder="Brief description of the template"
                      />
                    </div>
                    <div className="field-group">
                      <label>Upload file or paste content</label>
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".md,.txt,.yaml,.yml"
                        onChange={handleFileUpload}
                        style={{ marginBottom: "8px" }}
                      />
                      <textarea
                        id="uploadContent"
                        rows={12}
                        value={uploadData.content}
                        onChange={(e) => setUploadData(prev => ({ ...prev, content: e.target.value }))}
                        placeholder="Paste template content here or upload a file..."
                      />
                    </div>
                  </div>
                  <div className="modal-footer">
                    <button 
                      type="button" 
                      className="ghost"
                      onClick={() => setUploadModalOpen(false)}
                    >
                      Cancel
                    </button>
                    <button 
                      type="button" 
                      className="primary"
                      onClick={handleCreateTemplate}
                      disabled={templateSaveLoading || !uploadData.name.trim() || !uploadData.content.trim()}
                    >
                      {templateSaveLoading ? "Creating..." : "Create Template"}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
          )}

          {activeAdmin === "templates" && templateEditMode && (
          <>
            <div className="page-header">
              <h1>Templates</h1>
              <p>Customize output structure and field mappings for each artifact type.</p>
              <button type="button" className="text-link" onClick={handleCancelEdit}>
                ← Back to preview
              </button>
            </div>
            <div className="card">
              <div className="card-header">
                <div>
                  <h3>Edit template</h3>
                  <p className="muted">
                    Editing: {selectedTemplate?.name || "Template"} (v{activeVersion?.version || "1.0"})
                  </p>
                </div>
              </div>
              <div className="section">
                <label htmlFor="templateContent">Template content (Markdown)</label>
                <textarea
                  id="templateContent"
                  rows={20}
                  value={editedTemplateContent}
                  onChange={(event) => setEditedTemplateContent(event.target.value)}
                  className="template-editor"
                />
              </div>
              <div className="section">
                <label htmlFor="changelogInput">Changelog (optional)</label>
                <input
                  id="changelogInput"
                  type="text"
                  value={editedChangelog}
                  onChange={(e) => setEditedChangelog(e.target.value)}
                  placeholder="Describe what changed in this version..."
                />
              </div>
              <div className="actions align-left">
                <button 
                  type="button" 
                  className="primary"
                  onClick={handleSaveTemplate}
                  disabled={templateSaveLoading || !editedTemplateContent.trim()}
                >
                  {templateSaveLoading ? "Saving..." : "Save"}
                </button>
                <button type="button" className="ghost" onClick={handleCancelEdit}>
                  Cancel
                </button>
                <button type="button" className="ghost" onClick={handleUploadClick}>
                  Upload new version
                </button>
              </div>
            </div>
          </>
          )}

          {activeAdmin === "integrations" && (
          <>
            <div className="page-header">
              <h1>Integrations</h1>
              <p>Connect Synapse to your project management tools.</p>
            </div>
            <div className="stack">
              {integrations.map((integration) => {
                const isMvp = mvpIntegrations.includes(normalizeIntegrationKey(integration.name));
                const disabledReason = !isMvp
                  ? `${integration.name} integration is coming soon. Only Jira and Confluence are available in this release.`
                  : "";
                const mainLoading = isActionLoading(integration.name, "main");
                
                return (
                  <div
                    key={integration.name}
                    className={`integration-card ${integration.accent} ${!isMvp ? "coming-soon" : ""}`}
                  >
                    <div className="card-header">
                      <div>
                        <h3>{integration.name}</h3>
                        <p className={`status ${integration.accent}`}>{integration.status}</p>
                      </div>
                      <TooltipButton
                        type="button"
                        className="ghost"
                        disabled={!isMvp || mainLoading}
                        disabledReason={disabledReason}
                        tooltip={ACTION_TOOLTIPS[integration.actionType] || "Manage this integration"}
                        onClick={() => handleIntegrationAction(integration)}
                      >
                        {mainLoading ? (
                          <span className="loading-row">
                            <LoadingSpinner size={12} />
                            <span>Working...</span>
                          </span>
                        ) : (
                          integration.action
                        )}
                      </TooltipButton>
                    </div>
                    <div className="card-body">
                      {integration.details.map((detail) => (
                        <div key={detail.label} className="detail-row">
                          <span>{detail.label}</span>
                          <span className="muted">{detail.value}</span>
                        </div>
                      ))}
                    </div>
                    {(integration.footerActions?.length || integration.footerAction) && (
                      <div className="card-footer">
                        {(integration.footerActions?.length
                          ? integration.footerActions
                          : integration.footerAction
                          ? [{ label: integration.footerAction, actionType: "test" }]
                          : []
                        ).map((action) => {
                          const actionLoading = isActionLoading(integration.name, action.actionType);
                          return (
                            <TooltipButton
                              key={`${integration.name}-${action.label}`}
                              type="button"
                              className="ghost"
                              disabled={!isMvp || actionLoading}
                              disabledReason={disabledReason}
                              tooltip={getFooterActionTooltip(action.actionType, integration.name)}
                              onClick={() => handleIntegrationFooterAction(integration, action)}
                            >
                              {actionLoading ? (
                                <span className="loading-row">
                                  <LoadingSpinner size={12} />
                                  <span>{action.actionType === "sync" ? "Syncing..." : "Testing..."}</span>
                                </span>
                              ) : (
                                action.label
                              )}
                            </TooltipButton>
                          );
                        })}
                      </div>
                    )}
                    {!isMvp && (
                      <div className="integration-overlay" title={disabledReason}>
                        <span>Coming Soon</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
          )}

          {activeAdmin === "models" && (
          <>
            <div className="page-header">
              <h1>Models & Agents</h1>
              <p>Configure AI models and agent behavior.</p>
            </div>
            <div className="stack">
              <div className="card">
                <div className="card-header">
                  <div>
                    <h3>Model configuration</h3>
                    <p className="muted">Select the AI model powering Synapse</p>
                  </div>
                  {modelsConfig.current_provider && (
                    <span className={`status-badge ${modelsConfig.current_provider}`}>
                      {modelsConfig.current_provider.toUpperCase()}
                    </span>
                  )}
                </div>
                <div className="section">
                  <label htmlFor="modelSelect">AI Model</label>
                  {modelsLoading ? (
                    <p className="muted">Loading available models...</p>
                  ) : (
                    <select
                      id="modelSelect"
                      value={selectedModel}
                      onChange={(e) => handleModelChange(e.target.value)}
                      disabled={modelSaveLoading}
                    >
                      {/* Group by provider - show Ollama models first */}
                      {modelsConfig.ollama_models && modelsConfig.ollama_models.length > 0 && (
                        <optgroup label="Ollama (Local Models - Running)">
                          {modelsConfig.ollama_models.map((model) => (
                            <option key={model.id} value={model.id}>
                              {model.name} {model.is_current ? "✓" : ""}
                            </option>
                          ))}
                        </optgroup>
                      )}
                      
                      {/* Ollama models from static list (when not detected dynamically) */}
                      {modelsConfig.available_models?.filter(m => m.provider === "ollama").length > 0 && (
                        <optgroup label={modelsConfig.ollama_models?.length > 0 ? "Ollama (Other Models)" : "Ollama (Local Models)"}>
                          {modelsConfig.available_models
                            .filter((m) => m.provider === "ollama")
                            .map((model) => (
                              <option key={model.id} value={model.id}>
                                {model.name} {model.is_current ? "✓" : ""}{!model.available ? " ⚠" : ""}
                              </option>
                            ))}
                        </optgroup>
                      )}
                      
                      {/* OpenAI models - show all, mark unavailable */}
                      {modelsConfig.available_models?.filter(m => m.provider === "openai").length > 0 && (
                        <optgroup label="OpenAI">
                          {modelsConfig.available_models
                            .filter((m) => m.provider === "openai")
                            .map((model) => (
                              <option key={model.id} value={model.id}>
                                {model.name} {model.is_current ? "✓" : ""}{!model.available ? " (needs API key)" : ""}
                              </option>
                            ))}
                        </optgroup>
                      )}
                      
                      {/* Anthropic models - show all, mark unavailable */}
                      {modelsConfig.available_models?.filter(m => m.provider === "anthropic").length > 0 && (
                        <optgroup label="Anthropic (Claude)">
                          {modelsConfig.available_models
                            .filter((m) => m.provider === "anthropic")
                            .map((model) => (
                              <option key={model.id} value={model.id}>
                                {model.name} {model.is_current ? "✓" : ""}{!model.available ? " (needs API key)" : ""}
                              </option>
                            ))}
                        </optgroup>
                      )}
                      
                      {/* Google models - show all, mark unavailable */}
                      {modelsConfig.available_models?.filter(m => m.provider === "google").length > 0 && (
                        <optgroup label="Google (Gemini)">
                          {modelsConfig.available_models
                            .filter((m) => m.provider === "google")
                            .map((model) => (
                              <option key={model.id} value={model.id}>
                                {model.name} {model.is_current ? "✓" : ""}{!model.available ? " (needs API key)" : ""}
                              </option>
                            ))}
                        </optgroup>
                      )}
                      
                      {/* Azure models - show all, mark unavailable */}
                      {modelsConfig.available_models?.filter(m => m.provider === "azure").length > 0 && (
                        <optgroup label="Azure OpenAI">
                          {modelsConfig.available_models
                            .filter((m) => m.provider === "azure")
                            .map((model) => (
                              <option key={model.id} value={model.id}>
                                {model.name} {model.is_current ? "✓" : ""}{!model.available ? " (needs API key)" : ""}
                              </option>
                            ))}
                        </optgroup>
                      )}
                      
                      {/* Fallback: if no models from API, show current model */}
                      {(!modelsConfig.available_models || modelsConfig.available_models.length === 0) && 
                       (!modelsConfig.ollama_models || modelsConfig.ollama_models.length === 0) &&
                       modelsConfig.current_model && (
                        <option value={modelsConfig.current_model}>
                          {modelsConfig.current_model} (current)
                        </option>
                      )}
                    </select>
                  )}
                  
                  {/* Help text about API keys */}
                  {!modelsLoading && modelsConfig.available_models?.some(m => !m.available) && (
                    <p className="muted hint">
                      Models marked with "(needs API key)" require environment configuration. 
                      Set the appropriate API key (e.g., OPENAI_API_KEY, ANTHROPIC_API_KEY) in your .env file.
                    </p>
                  )}
                  {hasModelChanges && (
                    <p className="muted info">
                      You have unsaved changes. Click "Apply Changes" to switch models.
                    </p>
                  )}
                </div>
                <div className="section">
                  <label htmlFor="temperature">Temperature: {temperature}</label>
                  <input
                    id="temperature"
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={temperature}
                    onChange={(e) => handleTemperatureChange(parseFloat(e.target.value))}
                    disabled={modelSaveLoading}
                  />
                  <p className="muted">Lower = more focused, Higher = more creative</p>
                </div>
                
                {/* Save/Reset Actions */}
                <div className="section actions-row">
                  <button
                    type="button"
                    className="primary"
                    onClick={handleSaveModelConfig}
                    disabled={!hasModelChanges || modelSaveLoading}
                  >
                    {modelSaveLoading ? (
                      <span className="loading-row">
                        <LoadingSpinner size={12} />
                        <span>Applying...</span>
                      </span>
                    ) : (
                      "Apply Changes"
                    )}
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    onClick={handleResetModelConfig}
                    disabled={modelSaveLoading}
                    title="Reset to the model configured in your .env file"
                  >
                    Reset to Defaults
                  </button>
                </div>
                
                {/* Status Message */}
                {modelSaveMessage && (
                  <div className={`section message-banner ${modelSaveMessage.type}`}>
                    <span className={modelSaveMessage.type === "success" ? "success-icon" : "error-icon"}>
                      {modelSaveMessage.type === "success" ? "✓" : "⚠"}
                    </span>
                    <p>{modelSaveMessage.text}</p>
                  </div>
                )}
                
                <div className="section">
                  <label htmlFor="retention">Data retention</label>
                  <select id="retention">
                    <option>30 days</option>
                    <option>90 days</option>
                    <option>180 days</option>
                  </select>
                </div>
              </div>

              {/* Agent Configuration - Improved Layout */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <h3>Agent configuration</h3>
                    <p className="muted">Configure how AI agents collaborate to refine your artifacts</p>
                  </div>
                </div>
                
                {/* Workflow Overview */}
                <div className="section agent-workflow-overview">
                  <h4>How agents work together</h4>
                  <div className="workflow-diagram">
                    <div className="workflow-step">
                      <div className="workflow-icon">📝</div>
                      <span>Draft</span>
                    </div>
                    <div className="workflow-arrow">→</div>
                    <div className="workflow-step">
                      <div className="workflow-icon">🔍</div>
                      <span>Review</span>
                    </div>
                    <div className="workflow-arrow">→</div>
                    <div className="workflow-step">
                      <div className="workflow-icon">🔄</div>
                      <span>Refine</span>
                    </div>
                    <div className="workflow-arrow">→</div>
                    <div className="workflow-step">
                      <div className="workflow-icon">✅</div>
                      <span>Validate</span>
                    </div>
                  </div>
                  <p className="muted workflow-description">
                    The Supervisor coordinates multiple specialist agents in a debate loop. Each agent contributes their expertise, 
                    critiques are synthesized, and artifacts are iteratively refined until quality thresholds are met.
                  </p>
                </div>
              </div>

              {/* Supervisor / Orchestrator Settings */}
              <div className="card agent-card orchestrator">
                <div className="agent-card-header">
                  <div className="agent-icon-badge orchestrator">
                    <span>🎯</span>
                  </div>
                  <div className="agent-info">
                    <div className="agent-title-row">
                      <h4>Supervisor & Orchestrator</h4>
                      <span className="agent-badge essential">Essential</span>
                    </div>
                    <p className="muted">Coordinates all agent workflows and makes routing decisions</p>
                  </div>
                  <div className="agent-status-indicator active">
                    <span className="status-dot"></span>
                    <span>Always Active</span>
                  </div>
                </div>
                
                <div className="agent-details">
                  <div className="workflow-tags">
                    <span className="workflow-tag story-detailing">Story Detailing</span>
                    <span className="workflow-tag epic-stories">Epic → Stories</span>
                    <span className="workflow-tag optimization">Artifact Optimization</span>
                  </div>
                  
                  <div className="agent-settings-grid">
                    <div className="field-group">
                      <label htmlFor="conflictPolicy">Conflict resolution</label>
                      <select id="conflictPolicy">
                        <option value="ask_user">Ask user (recommended)</option>
                        <option value="majority">Majority vote</option>
                        <option value="orchestrator">Supervisor decides</option>
                      </select>
                      <p className="field-hint">How to resolve disagreements between agents</p>
                    </div>
                    
                    <div className="field-group">
                      <label htmlFor="maxIterations">Max debate iterations</label>
                      <select id="maxIterations" defaultValue="3">
                        <option value="2">2 iterations (faster)</option>
                        <option value="3">3 iterations (balanced)</option>
                        <option value="5">5 iterations (thorough)</option>
                      </select>
                      <p className="field-hint">Maximum refinement cycles before finalizing</p>
                    </div>
                    
                    <div className="field-group">
                      <label htmlFor="confidenceThreshold">Quality threshold</label>
                      <select id="confidenceThreshold" defaultValue="0.8">
                        <option value="0.7">70% (lenient)</option>
                        <option value="0.8">80% (balanced)</option>
                        <option value="0.9">90% (strict)</option>
                      </select>
                      <p className="field-hint">Minimum confidence score to approve artifacts</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Critique Agents Section */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <h3>Critique agents</h3>
                    <p className="muted">Specialist agents that review and critique artifacts from different perspectives</p>
                  </div>
                </div>
                
                {/* QA Agent */}
                <div className={`agent-card-inline ${!technicalEnabled || !qaEnabled ? 'disabled' : ''}`}>
                  <div className="agent-icon-badge qa">
                    <span>🔍</span>
                  </div>
                  <div className="agent-info">
                    <div className="agent-title-row">
                      <h4>QA Agent</h4>
                      <span className="agent-badge quality">Quality</span>
                    </div>
                    <p className="muted">Validates artifacts against INVEST principles (Independent, Negotiable, Valuable, Estimable, Small, Testable)</p>
                    <div className="workflow-tags small">
                      <span className="workflow-tag story-detailing">Story Detailing</span>
                      <span className="workflow-tag critique">Critique Loop</span>
                    </div>
                  </div>
                  <label className="switch">
                    <input 
                      type="checkbox" 
                      checked={qaEnabled && technicalEnabled} 
                      onChange={(event) => {
                        setQaEnabled(event.target.checked);
                        if (event.target.checked && !technicalEnabled) {
                          setTechnicalEnabled(true);
                        }
                      }} 
                    />
                    <span />
                  </label>
                </div>

                {/* Developer Agent */}
                <div className={`agent-card-inline ${!technicalEnabled || !devEnabled ? 'disabled' : ''}`}>
                  <div className="agent-icon-badge developer">
                    <span>⚙️</span>
                  </div>
                  <div className="agent-info">
                    <div className="agent-title-row">
                      <h4>Developer Agent</h4>
                      <span className="agent-badge technical">Technical</span>
                    </div>
                    <p className="muted">Assesses technical feasibility, identifies implementation risks, and suggests architectural considerations</p>
                    <div className="workflow-tags small">
                      <span className="workflow-tag story-detailing">Story Detailing</span>
                      <span className="workflow-tag critique">Critique Loop</span>
                    </div>
                  </div>
                  <label className="switch">
                    <input 
                      type="checkbox" 
                      checked={devEnabled && technicalEnabled} 
                      onChange={(event) => {
                        setDevEnabled(event.target.checked);
                        if (event.target.checked && !technicalEnabled) {
                          setTechnicalEnabled(true);
                        }
                      }} 
                    />
                    <span />
                  </label>
                </div>

                {/* Product Owner Agent */}
                <div className={`agent-card-inline ${!businessEnabled || !poEnabled ? 'disabled' : ''}`}>
                  <div className="agent-icon-badge po">
                    <span>💼</span>
                  </div>
                  <div className="agent-info">
                    <div className="agent-title-row">
                      <h4>Product Owner Agent</h4>
                      <span className="agent-badge business">Business</span>
                    </div>
                    <p className="muted">Evaluates business value, user impact, and ensures alignment with product goals and stakeholder needs</p>
                    <div className="workflow-tags small">
                      <span className="workflow-tag epic-stories">Epic → Stories</span>
                      <span className="workflow-tag story-detailing">Story Detailing</span>
                      <span className="workflow-tag critique">Critique Loop</span>
                    </div>
                  </div>
                  <label className="switch">
                    <input 
                      type="checkbox" 
                      checked={poEnabled && businessEnabled} 
                      onChange={(event) => {
                        setPoEnabled(event.target.checked);
                        if (event.target.checked && !businessEnabled) {
                          setBusinessEnabled(true);
                        }
                      }} 
                    />
                    <span />
                  </label>
                </div>

                {/* Warning if all critique agents disabled */}
                {(!qaEnabled || !devEnabled || !poEnabled) && (
                  <div className="agent-warning">
                    <span className="warning-icon">⚠️</span>
                    <p>
                      {!qaEnabled && !devEnabled && !poEnabled 
                        ? "All critique agents are disabled. Artifacts will not be reviewed before output."
                        : `Some critique agents are disabled. ${!qaEnabled ? "INVEST validation" : ""} ${!devEnabled ? "Technical review" : ""} ${!poEnabled ? "Business review" : ""} will be skipped.`.replace(/\s+/g, ' ').trim()
                      }
                    </p>
                  </div>
                )}
              </div>

              {/* Pipeline Agents (Read-only info) */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <h3>Pipeline agents</h3>
                    <p className="muted">Automated agents that handle specific workflow steps (always active)</p>
                  </div>
                  <span className="agent-badge muted">Auto-managed</span>
                </div>
                
                <div className="pipeline-agents-grid">
                  <div className="pipeline-agent">
                    <span className="pipeline-icon">📊</span>
                    <div>
                      <strong>Epic Analysis</strong>
                      <p className="muted">Breaks down epics into logical components</p>
                    </div>
                  </div>
                  <div className="pipeline-agent">
                    <span className="pipeline-icon">✂️</span>
                    <div>
                      <strong>Splitting Strategy</strong>
                      <p className="muted">Determines optimal story boundaries</p>
                    </div>
                  </div>
                  <div className="pipeline-agent">
                    <span className="pipeline-icon">✍️</span>
                    <div>
                      <strong>Story Generation</strong>
                      <p className="muted">Creates story drafts from analysis</p>
                    </div>
                  </div>
                  <div className="pipeline-agent">
                    <span className="pipeline-icon">📚</span>
                    <div>
                      <strong>Knowledge Retrieval</strong>
                      <p className="muted">Fetches relevant context from RAG</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </>
          )}

        {activeAdmin === "audit" && (
          <PromptManagementApp />
        )}
        </div>
      </div>
    </section>
  );
}
