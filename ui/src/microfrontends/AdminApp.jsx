import React, { useEffect, useState } from "react";

import { INTEGRATIONS, TEMPLATE_PAGES, TEMPLATE_VERSIONS } from "../shared/data";
import {
  connectIntegration,
  fetchIntegrations,
  testIntegration,
  updateIntegrationScopes,
} from "../shared/api";

const ADMIN_ITEMS = [
  { id: "templates", label: "Templates" },
  { id: "integrations", label: "Integrations" },
  { id: "models", label: "Models & Agents" },
  { id: "audit", label: "Audit & Governance" },
];

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
  const isAuditComingSoon = activeAdmin === "audit";
  const mvpIntegrations = ["Jira", "Confluence"];

  useEffect(() => {
    if (adminTab && adminTab !== activeAdmin) {
      setActiveAdmin(adminTab);
    }
  }, [adminTab, activeAdmin]);

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

  const normalizeIntegration = (integration) => {
    const statusMap = {
      connected: { label: "Connected", accent: "success" },
      not_connected: { label: "Not connected", accent: "muted" },
      error: { label: "Error", accent: "warning" },
    };
    const statusMeta = statusMap[integration.status] || statusMap.not_connected;
    return {
      name: integration.name,
      status: statusMeta.label,
      accent: statusMeta.accent,
      action: integration.action,
      actionType: integration.action_type || "connect",
      details: integration.details || [],
      footerAction: integration.footer_action || null,
    };
  };

  const updateIntegration = (updatedIntegration) => {
    setIntegrations((prev) =>
      prev.map((integration) =>
        integration.name === updatedIntegration.name ? updatedIntegration : integration
      )
    );
  };

  const handleIntegrationAction = async (integration) => {
    try {
      if (integration.actionType === "connect") {
        const result = await connectIntegration(integration.name);
        updateIntegration(normalizeIntegration(result));
        return;
      }
      if (integration.actionType === "scopes") {
        const scopes =
          integration.details.find((detail) => detail.label === "Allowed projects")?.value || "";
        const scopeList = scopes
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean);
        const result = await updateIntegrationScopes(integration.name, scopeList);
        updateIntegration(normalizeIntegration(result));
        return;
      }
      await testIntegration(integration.name);
    } catch (error) {
      console.warn("Integration action failed", error);
    }
  };

  const handleIntegrationTest = async (integration) => {
    try {
      await testIntegration(integration.name);
    } catch (error) {
      console.warn("Integration test failed", error);
    }
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
                <select id="artifactType">
                  <option>User Story</option>
                </select>
              </div>
              <button type="button" className="primary">
                Upload template
              </button>
            </div>
            <div className="card">
              <div className="card-header">
                <div>
                  <h3>Template document</h3>
                  <p className="muted">Read-only preview of active user story template</p>
                </div>
                <button type="button" className="ghost" onClick={() => setTemplateEditMode(true)}>
                  Edit
                </button>
              </div>
              <div className="template-preview">
                <div className="page-list">
                  {TEMPLATE_PAGES.map((page) => (
                    <div key={page} className={`page-thumb ${page === "1" ? "active" : ""}`}>
                      {page}
                    </div>
                  ))}
                </div>
                <div className="document">
                  <h4>User Story Template Specification</h4>
                  <p className="muted">Version 2.1 · Last updated Jan 21, 2026</p>
                  <div className="doc-section">
                    <h5>1. Field Mappings</h5>
                    <ul>
                      <li>Title → title (required)</li>
                      <li>Description → description (required)</li>
                      <li>Acceptance criteria → acceptance_criteria (required)</li>
                      <li>Dependencies → linked_issues (optional)</li>
                      <li>NFRs → custom_field_10042 (optional)</li>
                    </ul>
                  </div>
                  <div className="doc-section">
                    <h5>2. Output Structure</h5>
                    <pre className="code-block">
title: "As a shopper, I can retry payment"
description: "### Business value\n..."
acceptance_criteria:
  - [x] When a retriable payment error occurs...
  - [ ] Retry attempts are logged...
  - [ ] After 2 failed attempts...
linked_issues: ["SYN-INIT-1423"]
                    </pre>
                  </div>
                </div>
              </div>
            </div>
            <div className="card">
              <div className="section">
                <h3>Version history</h3>
                <ul className="summary-list">
                  {TEMPLATE_VERSIONS.map((item) => (
                    <li key={item.version}>
                      v{item.version} · {item.date} · {item.status}
                    </li>
                  ))}
                </ul>
                <div className="actions align-left">
                  <button type="button" className="ghost">
                    Roll back
                  </button>
                  <button type="button" className="ghost">
                    Test parse
                  </button>
                </div>
              </div>
            </div>
          </>
          )}

          {activeAdmin === "templates" && templateEditMode && (
          <>
            <div className="page-header">
              <h1>Templates</h1>
              <p>Customize output structure and field mappings for each artifact type.</p>
              <button type="button" className="text-link" onClick={() => setTemplateEditMode(false)}>
                ← Back to preview
              </button>
            </div>
            <div className="card">
              <div className="card-header">
                <div>
                  <h3>Edit template</h3>
                  <p className="muted">Modify the epic template document</p>
                </div>
              </div>
              <div className="section">
                <label htmlFor="templateContent">Template content</label>
                <textarea
                  id="templateContent"
                  rows={12}
                  value={templateText}
                  onChange={(event) => setTemplateText(event.target.value)}
                />
              </div>
              <div className="actions align-left">
                <button type="button" className="primary">
                  Save
                </button>
                <button type="button" className="ghost">
                  Cancel
                </button>
                <button type="button" className="ghost">
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
              {integrations.map((integration) => (
                <div
                  key={integration.name}
                  className={`integration-card ${integration.accent} ${
                    mvpIntegrations.includes(integration.name) ? "" : "coming-soon"
                  }`}
                >
                  <div className="card-header">
                    <div>
                      <h3>{integration.name}</h3>
                      <p className={`status ${integration.accent}`}>{integration.status}</p>
                    </div>
                    <button
                      type="button"
                      className="ghost"
                      disabled={!mvpIntegrations.includes(integration.name)}
                      onClick={() => handleIntegrationAction(integration)}
                    >
                      {integration.action}
                    </button>
                  </div>
                  <div className="card-body">
                    {integration.details.map((detail) => (
                      <div key={detail.label} className="detail-row">
                        <span>{detail.label}</span>
                        <span className="muted">{detail.value}</span>
                      </div>
                    ))}
                  </div>
                  {integration.footerAction && (
                    <div className="card-footer">
                      <button
                        type="button"
                        className="ghost"
                        disabled={!mvpIntegrations.includes(integration.name)}
                        onClick={() => handleIntegrationTest(integration)}
                      >
                        {integration.footerAction}
                      </button>
                    </div>
                  )}
                  {!mvpIntegrations.includes(integration.name) && (
                    <div className="integration-overlay">
                      <span>Coming Soon</span>
                    </div>
                  )}
                </div>
              ))}
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
                </div>
                <div className="section">
                  <label htmlFor="modelSelect">AI Model</label>
                  <select id="modelSelect">
                    <option>OpenAI GPT-4</option>
                    <option>Azure OpenAI GPT-4</option>
                    <option>Claude 3.5 Sonnet</option>
                  </select>
                </div>
                <div className="section">
                  <label htmlFor="temperature">Temperature: 0.7</label>
                  <input id="temperature" type="range" min="0" max="1" step="0.1" defaultValue="0.7" />
                  <p className="muted">Lower = more focused, Higher = more creative</p>
                </div>
                <div className="section">
                  <label htmlFor="retention">Data retention</label>
                  <select id="retention">
                    <option>30 days</option>
                    <option>90 days</option>
                    <option>180 days</option>
                  </select>
                </div>
              </div>

              <div className="card">
                <div className="card-header">
                  <div>
                    <h3>Agent configuration</h3>
                    <p className="muted">Enable and configure specialized agents</p>
                  </div>
                </div>
                <div className="toggle-row">
                  <div>
                    <h4>Orchestrator agent</h4>
                    <p className="muted">Coordinates Story Detailing and Epic → Stories workflows</p>
                    <div className="pill-row">
                      <span>Story Detailing</span>
                      <span>Epic → Stories</span>
                    </div>
                    <div className="section">
                      <label htmlFor="conflictPolicy">Conflict resolution policy</label>
                      <select id="conflictPolicy">
                        <option>Ask user (recommended)</option>
                        <option>Majority vote</option>
                        <option>Orchestrator decides</option>
                      </select>
                    </div>
                  </div>
                  <label className="switch">
                    <input type="checkbox" checked readOnly />
                    <span />
                  </label>
                </div>
                <div className="toggle-row">
                  <div>
                    <h4>Technical agent</h4>
                    <p className="muted">Technical review for Story Detailing + critique loop</p>
                    <div className="pill-row">
                      <span>Story Detailing</span>
                      <span>Critique</span>
                    </div>
                    <div className="pill-row">
                      <span>QA critique</span>
                      <span>Developer critique</span>
                    </div>
                    <div className="subtoggle-row">
                      <span className="muted">QA critique</span>
                      <label className="switch">
                        <input type="checkbox" checked={qaEnabled} onChange={(event) => setQaEnabled(event.target.checked)} />
                        <span />
                      </label>
                    </div>
                    <div className="subtoggle-row">
                      <span className="muted">Developer critique</span>
                      <label className="switch">
                        <input
                          type="checkbox"
                          checked={devEnabled}
                          onChange={(event) => setDevEnabled(event.target.checked)}
                        />
                        <span />
                      </label>
                    </div>
                  </div>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={technicalEnabled}
                      onChange={(event) => setTechnicalEnabled(event.target.checked)}
                    />
                    <span />
                  </label>
                </div>
                <div className="toggle-row">
                  <div>
                    <h4>Business agent</h4>
                    <p className="muted">Business review for Epic → Stories and Story Detailing critique</p>
                    <div className="pill-row">
                      <span>Epic → Stories</span>
                      <span>Critique</span>
                    </div>
                    <div className="pill-row">
                      <span>Product Owner critique</span>
                    </div>
                    <div className="subtoggle-row">
                      <span className="muted">Product Owner critique</span>
                      <label className="switch">
                        <input type="checkbox" checked={poEnabled} onChange={(event) => setPoEnabled(event.target.checked)} />
                        <span />
                      </label>
                    </div>
                  </div>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={businessEnabled}
                      onChange={(event) => setBusinessEnabled(event.target.checked)}
                    />
                    <span />
                  </label>
                </div>
              </div>
            </div>
          </>
          )}

        {activeAdmin === "audit" && (
          <>
            <div className="page-header">
              <h1>Audit & Governance</h1>
              <p className="muted">Planned for future releases.</p>
            </div>
            <div className="card">
              <div className="section">
                <h3>Coming soon</h3>
                <p className="muted">
                  Audit logs, export workflows, and governance reporting will be delivered after MVP.
                </p>
              </div>
            </div>
          </>
        )}
          {isAuditComingSoon && (
            <div className="coming-soon-overlay">
              <span>Coming Soon</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
