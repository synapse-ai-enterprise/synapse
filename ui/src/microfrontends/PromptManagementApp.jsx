import React, { useEffect, useState, useCallback } from "react";
import {
  fetchPrompts,
  fetchPrompt,
  savePrompt,
  addPromptVersion,
  rollbackPromptVersion,
  fetchPromptSummary,
  fetchPromptMetrics,
  fetchPromptCalls,
  fetchPromptAlerts,
  updateAlertThresholds,
} from "../shared/api";

// Default metrics when no data available
const DEFAULT_METRICS = {
  total_calls: 0,
  successful_calls: 0,
  failed_calls: 0,
  total_tokens: 0,
  total_cost_usd: 0,
  avg_latency_ms: 0,
  p95_latency_ms: 0,
  calls_by_model: {},
  calls_by_agent: {},
};

const PROMPT_CATEGORIES = [
  { id: "agent_system", label: "Agent System" },
  { id: "agent_task", label: "Agent Task" },
  { id: "critique", label: "Critique" },
  { id: "extraction", label: "Extraction" },
  { id: "generation", label: "Generation" },
  { id: "synthesis", label: "Synthesis" },
  { id: "routing", label: "Routing" },
];

// Agent Groups based on Synapse Agentic Workflow Architecture
const AGENT_GROUPS = [
  {
    id: "orchestrator",
    label: "Orchestrator Hub",
    color: "#4A90D9",
    description: "Routes steps based on state",
    agents: [
      { id: "supervisor", label: "Supervisor" },
    ],
  },
  {
    id: "task_based",
    label: "Task-based (Story Detailing)",
    color: "#5CB85C",
    description: "Specialized story processing agents",
    agents: [
      { id: "epic_analysis_agent", label: "Epic Analysis" },
      { id: "splitting_strategy_agent", label: "Splitting Strategy" },
      { id: "story_generation_agent", label: "Story Generation" },
      { id: "knowledge_retrieval_agent", label: "Knowledge Retrieval" },
      { id: "story_writer_agent", label: "Story Writer" },
      { id: "validation_gap_agent", label: "Validation" },
      { id: "template_parser_agent", label: "Template Parser" },
    ],
  },
  {
    id: "domain_based",
    label: "Domain-based (User-facing)",
    color: "#9B59B6",
    description: "Multi-agent debate participants",
    agents: [
      { id: "po_agent", label: "Product Owner" },
      { id: "qa_agent", label: "QA Agent" },
      { id: "developer_agent", label: "Developer Agent" },
    ],
  },
];

// Flat list of agent types (for compatibility)
const AGENT_TYPES = AGENT_GROUPS.flatMap((group) => 
  group.agents.map((agent) => ({ ...agent, group: group.id, groupLabel: group.label }))
);

// Sub-navigation for Audit & Governance
const PROMPT_TABS = [
  { id: "library", label: "Prompt Library" },
  { id: "metrics", label: "Performance" },
  { id: "alerts", label: "Alerts" },
  { id: "audit-logs", label: "Audit Logs" },
];

// Format number with K/M suffix
const formatNumber = (num) => {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toString();
};

// Format currency
const formatCurrency = (amount) => `$${amount.toFixed(2)}`;

// Format latency
const formatLatency = (ms) => {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms)}ms`;
};

// Metric Card Component
const MetricCard = ({ label, value, subtext, accent }) => (
  <div className={`metric-card ${accent || ""}`}>
    <div className="metric-value">{value}</div>
    <div className="metric-label">{label}</div>
    {subtext && <div className="metric-subtext">{subtext}</div>}
  </div>
);

// Prompt Card Component
const PromptCard = ({ prompt, onSelect, isSelected }) => {
  const currentVersion = prompt.versions?.find((v) => v.version === prompt.current_version);
  const metrics = currentVersion?.metrics || {};

  return (
    <div
      className={`prompt-card ${isSelected ? "selected" : ""}`}
      onClick={() => onSelect(prompt)}
    >
      <div className="prompt-card-header">
        <div>
          <h4>{prompt.name}</h4>
          <p className="muted">{prompt.description}</p>
        </div>
        <span className={`status-pill ${metrics.success_rate >= 0.9 ? "success" : "warn"}`}>
          {((metrics.success_rate || 0) * 100).toFixed(0)}%
        </span>
      </div>
      <div className="prompt-card-meta">
        <span className="chip">{prompt.category}</span>
        <span className="chip">{prompt.agent_type}</span>
        <span className="chip">v{prompt.current_version}</span>
      </div>
      <div className="prompt-card-stats">
        <span>{formatNumber(metrics.total_uses || 0)} uses</span>
        <span>{formatLatency(metrics.avg_latency_ms || 0)} avg</span>
      </div>
    </div>
  );
};

// Prompt Editor Component
const PromptEditor = ({ prompt, onSave, onClose }) => {
  const [editedPrompt, setEditedPrompt] = useState(prompt);
  const [newVersion, setNewVersion] = useState("");
  const [changelog, setChangelog] = useState("");
  const [template, setTemplate] = useState(
    prompt.versions?.find((v) => v.version === prompt.current_version)?.template || ""
  );

  const handleSave = () => {
    if (newVersion && newVersion !== prompt.current_version) {
      // Adding a new version
      onSave({
        ...editedPrompt,
        newVersion: {
          version: newVersion,
          template,
          changelog,
        },
      });
    } else {
      // Just updating metadata
      onSave(editedPrompt);
    }
  };

  return (
    <div className="prompt-editor">
      <div className="prompt-editor-header">
        <h3>Edit Prompt</h3>
        <button type="button" className="ghost" onClick={onClose}>
          ✕
        </button>
      </div>

      <div className="prompt-editor-body">
        <div className="section">
          <label htmlFor="promptName">Name</label>
          <input
            id="promptName"
            type="text"
            value={editedPrompt.name}
            onChange={(e) => setEditedPrompt({ ...editedPrompt, name: e.target.value })}
          />
        </div>

        <div className="section">
          <label htmlFor="promptDesc">Description</label>
          <textarea
            id="promptDesc"
            rows={2}
            value={editedPrompt.description}
            onChange={(e) => setEditedPrompt({ ...editedPrompt, description: e.target.value })}
          />
        </div>

        <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <div className="section">
            <label htmlFor="promptCategory">Category</label>
            <select
              id="promptCategory"
              value={editedPrompt.category}
              onChange={(e) => setEditedPrompt({ ...editedPrompt, category: e.target.value })}
            >
              {PROMPT_CATEGORIES.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.label}
                </option>
              ))}
            </select>
          </div>

          <div className="section">
            <label htmlFor="promptAgent">Agent Type</label>
            <select
              id="promptAgent"
              value={editedPrompt.agent_type}
              onChange={(e) => setEditedPrompt({ ...editedPrompt, agent_type: e.target.value })}
            >
              {AGENT_TYPES.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="section">
          <label htmlFor="promptTemplate">Prompt Template</label>
          <textarea
            id="promptTemplate"
            rows={12}
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            className="code-input"
          />
          <p className="muted">
            Use {"{variable_name}"} for variable substitution. Variables will be filled at runtime.
          </p>
        </div>

        <div className="version-section">
          <h4>Version Control</h4>
          <div className="form-grid" style={{ gridTemplateColumns: "1fr 2fr" }}>
            <div className="section">
              <label htmlFor="newVersion">New Version</label>
              <input
                id="newVersion"
                type="text"
                placeholder={`Current: ${prompt.current_version}`}
                value={newVersion}
                onChange={(e) => setNewVersion(e.target.value)}
              />
            </div>
            <div className="section">
              <label htmlFor="changelog">Changelog</label>
              <input
                id="changelog"
                type="text"
                placeholder="Description of changes..."
                value={changelog}
                onChange={(e) => setChangelog(e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="version-history">
          <h4>Version History</h4>
          <ul className="version-list">
            {(editedPrompt.versions || []).map((v) => (
              <li key={v.version} className={v.is_active ? "active" : ""}>
                <span className="version-tag">v{v.version}</span>
                <span className="version-stats">
                  {formatNumber(v.metrics?.total_uses || 0)} uses · {((v.metrics?.success_rate || 0) * 100).toFixed(0)}%
                </span>
                {v.is_active && <span className="status-pill success">Active</span>}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="prompt-editor-footer">
        <button type="button" className="ghost" onClick={onClose}>
          Cancel
        </button>
        <button type="button" className="primary" onClick={handleSave}>
          Save Changes
        </button>
      </div>
    </div>
  );
};

// Performance Dashboard Component
const PerformanceDashboard = ({ metrics }) => {
  const successRate = metrics.total_calls > 0
    ? ((metrics.successful_calls / metrics.total_calls) * 100).toFixed(1)
    : 0;

  return (
    <div className="performance-dashboard">
      <div className="metrics-grid">
        <MetricCard
          label="Total Calls"
          value={formatNumber(metrics.total_calls)}
          subtext="Last 24 hours"
        />
        <MetricCard
          label="Success Rate"
          value={`${successRate}%`}
          accent={successRate >= 90 ? "success" : successRate >= 70 ? "warn" : "error"}
        />
        <MetricCard
          label="Avg Latency"
          value={formatLatency(metrics.avg_latency_ms)}
          subtext={`P95: ${formatLatency(metrics.p95_latency_ms)}`}
        />
        <MetricCard
          label="Total Cost"
          value={formatCurrency(metrics.total_cost_usd)}
          subtext={`${formatNumber(metrics.total_tokens)} tokens`}
        />
      </div>

      <div className="dashboard-row">
        <div className="card">
          <h4>Calls by Model</h4>
          <div className="bar-chart">
            {Object.entries(metrics.calls_by_model || {}).map(([model, count]) => {
              const percentage = (count / metrics.total_calls) * 100;
              return (
                <div key={model} className="bar-row">
                  <span className="bar-label">{model}</span>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                  <span className="bar-value">{formatNumber(count)}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card">
          <h4>Calls by Agent</h4>
          <div className="bar-chart">
            {Object.entries(metrics.calls_by_agent || {}).map(([agent, count]) => {
              const percentage = (count / metrics.total_calls) * 100;
              return (
                <div key={agent} className="bar-row">
                  <span className="bar-label">{agent.replace("_", " ")}</span>
                  <div className="bar-track">
                    <div
                      className="bar-fill agent"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                  <span className="bar-value">{formatNumber(count)}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

// Alerts Configuration Component
const AlertsConfig = ({ onSave }) => {
  const [thresholds, setThresholds] = useState({
    latency_warning_ms: 5000,
    latency_critical_ms: 15000,
    error_rate_warning: 0.1,
    error_rate_critical: 0.25,
    quality_warning: 0.6,
    quality_critical: 0.4,
    cost_warning_usd: 10,
    cost_critical_usd: 50,
  });

  const [recentAlerts, setRecentAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(true);

  // Load alerts from API
  useEffect(() => {
    const loadAlerts = async () => {
      try {
        setAlertsLoading(true);
        const data = await fetchPromptAlerts({ limit: 20 });
        setRecentAlerts(data.alerts || []);
      } catch (err) {
        console.error("Failed to load alerts:", err);
        setRecentAlerts([]);
      } finally {
        setAlertsLoading(false);
      }
    };
    loadAlerts();
  }, []);

  return (
    <div className="alerts-config">
      <div className="card">
        <div className="card-header">
          <div>
            <h3>Alert Thresholds</h3>
            <p className="muted">Configure when to trigger alerts based on prompt performance</p>
          </div>
        </div>

        <div className="threshold-grid">
          <div className="threshold-section">
            <h4>Latency</h4>
            <div className="threshold-row">
              <label>Warning (ms)</label>
              <input
                type="number"
                value={thresholds.latency_warning_ms}
                onChange={(e) =>
                  setThresholds({ ...thresholds, latency_warning_ms: parseInt(e.target.value) })
                }
              />
            </div>
            <div className="threshold-row">
              <label>Critical (ms)</label>
              <input
                type="number"
                value={thresholds.latency_critical_ms}
                onChange={(e) =>
                  setThresholds({ ...thresholds, latency_critical_ms: parseInt(e.target.value) })
                }
              />
            </div>
          </div>

          <div className="threshold-section">
            <h4>Error Rate</h4>
            <div className="threshold-row">
              <label>Warning (%)</label>
              <input
                type="number"
                value={thresholds.error_rate_warning * 100}
                onChange={(e) =>
                  setThresholds({ ...thresholds, error_rate_warning: parseFloat(e.target.value) / 100 })
                }
              />
            </div>
            <div className="threshold-row">
              <label>Critical (%)</label>
              <input
                type="number"
                value={thresholds.error_rate_critical * 100}
                onChange={(e) =>
                  setThresholds({ ...thresholds, error_rate_critical: parseFloat(e.target.value) / 100 })
                }
              />
            </div>
          </div>

          <div className="threshold-section">
            <h4>Quality Score</h4>
            <div className="threshold-row">
              <label>Warning (0-1)</label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="1"
                value={thresholds.quality_warning}
                onChange={(e) =>
                  setThresholds({ ...thresholds, quality_warning: parseFloat(e.target.value) })
                }
              />
            </div>
            <div className="threshold-row">
              <label>Critical (0-1)</label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="1"
                value={thresholds.quality_critical}
                onChange={(e) =>
                  setThresholds({ ...thresholds, quality_critical: parseFloat(e.target.value) })
                }
              />
            </div>
          </div>

          <div className="threshold-section">
            <h4>Cost (per hour)</h4>
            <div className="threshold-row">
              <label>Warning ($)</label>
              <input
                type="number"
                value={thresholds.cost_warning_usd}
                onChange={(e) =>
                  setThresholds({ ...thresholds, cost_warning_usd: parseFloat(e.target.value) })
                }
              />
            </div>
            <div className="threshold-row">
              <label>Critical ($)</label>
              <input
                type="number"
                value={thresholds.cost_critical_usd}
                onChange={(e) =>
                  setThresholds({ ...thresholds, cost_critical_usd: parseFloat(e.target.value) })
                }
              />
            </div>
          </div>
        </div>

        <div className="actions align-left">
          <button type="button" className="primary" onClick={() => onSave(thresholds)}>
            Save Thresholds
          </button>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <h3>Recent Alerts</h3>
            <p className="muted">Latest alerts triggered by threshold violations</p>
          </div>
        </div>

        <div className="alerts-list">
          {recentAlerts.length === 0 ? (
            <p className="muted centered-text">No recent alerts</p>
          ) : (
            recentAlerts.map((alert) => (
              <div key={alert.id} className={`alert-item ${alert.severity}`}>
                <div className="alert-icon">
                  {alert.severity === "critical" ? "🔴" : "🟡"}
                </div>
                <div className="alert-content">
                  <div className="alert-message">{alert.message}</div>
                  <div className="alert-meta">
                    <span className={`status-pill ${alert.severity === "critical" ? "error" : "warn"}`}>
                      {alert.severity}
                    </span>
                    <span className="muted">
                      {new Date(alert.timestamp).toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

// Main Prompt Management Component
export function PromptManagementApp() {
  const [activeTab, setActiveTab] = useState("library");
  const [prompts, setPrompts] = useState([]);
  const [metrics, setMetrics] = useState(DEFAULT_METRICS);
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [filterCategory, setFilterCategory] = useState("");
  const [filterAgent, setFilterAgent] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load prompts from API
  const loadPrompts = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchPrompts();
      setPrompts(data.prompts || []);
    } catch (err) {
      console.error("Failed to load prompts:", err);
      setError("Failed to load prompts. Please check if the backend is running.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Load metrics from API
  const loadMetrics = useCallback(async () => {
    try {
      const data = await fetchPromptMetrics();
      setMetrics(data || DEFAULT_METRICS);
    } catch (err) {
      console.error("Failed to load metrics:", err);
      // Keep default metrics on error
    }
  }, []);

  // Initial data load
  useEffect(() => {
    loadPrompts();
    loadMetrics();
  }, [loadPrompts, loadMetrics]);

  // Refresh metrics when switching to metrics tab
  useEffect(() => {
    if (activeTab === "metrics") {
      loadMetrics();
    }
  }, [activeTab, loadMetrics]);

  // Filter prompts
  const filteredPrompts = prompts.filter((p) => {
    if (filterCategory && p.category !== filterCategory) return false;
    if (filterAgent && p.agent_type !== filterAgent) return false;
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        p.name.toLowerCase().includes(query) ||
        p.description.toLowerCase().includes(query) ||
        p.id.toLowerCase().includes(query)
      );
    }
    return true;
  });

  const handleSavePrompt = async (updatedPrompt) => {
    try {
      // If there's a new version, add it first
      if (updatedPrompt.newVersion) {
        await addPromptVersion(updatedPrompt.id, {
          version: updatedPrompt.newVersion.version,
          template: updatedPrompt.newVersion.template,
          changelog: updatedPrompt.newVersion.changelog,
          set_active: true,
        });
      }
      
      // Save the prompt metadata
      await savePrompt({
        id: updatedPrompt.id,
        name: updatedPrompt.name,
        description: updatedPrompt.description,
        category: updatedPrompt.category,
        agent_type: updatedPrompt.agent_type,
        tags: updatedPrompt.tags || [],
      });
      
      // Reload prompts to get fresh data
      await loadPrompts();
      
      setIsEditing(false);
      setSelectedPrompt(null);
    } catch (err) {
      console.error("Failed to save prompt:", err);
      window.alert("Failed to save prompt: " + err.message);
    }
  };

  const handleSaveThresholds = async (thresholds) => {
    try {
      await updateAlertThresholds(thresholds);
      window.alert("Alert thresholds saved successfully!");
    } catch (err) {
      console.error("Failed to save thresholds:", err);
      window.alert("Failed to save thresholds: " + err.message);
    }
  };

  return (
    <div className="prompt-management">
      <div className="page-header">
        <h1>Audit & Governance</h1>
        <p>Manage prompt templates, monitor performance, configure alerts, and review audit logs.</p>
      </div>

      {/* Sub-navigation */}
      <div className="prompt-tabs">
        {PROMPT_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`tab-btn ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Library Tab */}
      {activeTab === "library" && (
        <div className="library-content">
          {/* Filters */}
          <div className="library-toolbar">
            <div className="filter-row">
              <input
                type="text"
                placeholder="Search prompts..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="search-input"
              />
              <select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
              >
                <option value="">All Categories</option>
                {PROMPT_CATEGORIES.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.label}
                  </option>
                ))}
              </select>
              <select
                value={filterAgent}
                onChange={(e) => setFilterAgent(e.target.value)}
              >
                <option value="">All Agents</option>
                {AGENT_GROUPS.map((group) => (
                  <optgroup key={group.id} label={group.label}>
                    {group.agents.map((agent) => (
                      <option key={agent.id} value={agent.id}>
                        {agent.label}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
            <button type="button" className="ghost" onClick={loadPrompts} title="Refresh">
              Refresh
            </button>
          </div>

          {/* Loading/Error States */}
          {loading && (
            <div className="loading-state">
              <p>Loading prompts...</p>
            </div>
          )}
          
          {error && (
            <div className="error-state">
              <p>{error}</p>
              <button type="button" className="ghost" onClick={loadPrompts}>
                Retry
              </button>
            </div>
          )}

          {/* Prompt Grid - Grouped by Agent Type */}
          {!loading && !error && (
            <div className="prompt-groups">
              {filteredPrompts.length === 0 ? (
                <div className="empty-state">
                  <p className="muted">No prompts found. Start by creating a new prompt or adjust your filters.</p>
                </div>
              ) : (
                AGENT_GROUPS.map((group) => {
                  // Get prompts for agents in this group
                  const groupAgentIds = group.agents.map((a) => a.id);
                  const groupPrompts = filteredPrompts.filter((p) =>
                    groupAgentIds.includes(p.agent_type)
                  );

                  // Skip groups with no prompts in current filter
                  if (groupPrompts.length === 0) return null;

                  return (
                    <div key={group.id} className="prompt-group">
                      <div
                        className="prompt-group-header"
                        style={{ borderLeftColor: group.color }}
                      >
                        <div className="prompt-group-title">
                          <span
                            className="group-indicator"
                            style={{ backgroundColor: group.color }}
                          />
                          <h3>{group.label}</h3>
                          <span className="group-count">{groupPrompts.length}</span>
                        </div>
                        <p className="muted">{group.description}</p>
                      </div>
                      <div className="prompt-grid">
                        {groupPrompts.map((prompt) => (
                          <PromptCard
                            key={prompt.id}
                            prompt={prompt}
                            isSelected={selectedPrompt?.id === prompt.id}
                            onSelect={(p) => {
                              setSelectedPrompt(p);
                              setIsEditing(true);
                            }}
                          />
                        ))}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* Editor Modal */}
          {isEditing && selectedPrompt && (
            <div className="modal-overlay">
              <div className="modal-content">
                <PromptEditor
                  prompt={selectedPrompt}
                  onSave={handleSavePrompt}
                  onClose={() => {
                    setIsEditing(false);
                    setSelectedPrompt(null);
                  }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Performance Tab */}
      {activeTab === "metrics" && (
        <PerformanceDashboard metrics={metrics} />
      )}

      {/* Alerts Tab */}
      {activeTab === "alerts" && (
        <AlertsConfig onSave={handleSaveThresholds} />
      )}

      {/* Audit Logs Tab */}
      {activeTab === "audit-logs" && (
        <div className="audit-logs-content">
          <div className="card">
            <div className="card-header">
              <div>
                <h3>Audit Logs</h3>
                <p className="muted">Track all system activities, user actions, and workflow executions</p>
              </div>
            </div>
            <div className="section coming-soon-section">
              <div className="coming-soon-badge">Coming Soon</div>
              <h4>Planned Features</h4>
              <ul className="feature-list">
                <li>User activity tracking and session logs</li>
                <li>Workflow execution history with full traceability</li>
                <li>Agent decision audit trail</li>
                <li>Export and compliance reporting</li>
                <li>Data retention policy management</li>
                <li>Role-based access audit</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default PromptManagementApp;
