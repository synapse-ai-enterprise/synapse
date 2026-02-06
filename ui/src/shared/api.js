const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? "http://localhost:8000" : "");

/**
 * Parse API error body (e.g. FastAPI {"detail": "..."}) for user-facing messages.
 */
const getErrorMessage = async (response) => {
  const text = await response.text();
  try {
    const json = JSON.parse(text);
    if (json.detail) return typeof json.detail === "string" ? json.detail : JSON.stringify(json.detail);
  } catch (_) {}
  return text || `Request failed: ${response.status}`;
};

const requestJson = async (path, options = {}) => {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    const message = await getErrorMessage(response);
    const err = new Error(message);
    err.status = response.status;
    throw err;
  }

  return response.json();
};

export const fetchIntegrations = async () => {
  const payload = await requestJson("/api/integrations");
  return payload.integrations || [];
};

// ============================================
// Model Configuration API Functions
// ============================================

/**
 * Fetch available models based on environment configuration.
 * Returns current model and list of available models by provider.
 */
export const fetchModelsConfig = async () =>
  requestJson("/api/config/models");

/**
 * Get the currently configured model.
 */
export const fetchCurrentModel = async () =>
  requestJson("/api/config/current-model");

/**
 * Update the runtime model configuration.
 * @param {Object} config - { model: string, temperature?: number }
 * @returns {Promise<Object>} - { success, model, provider, temperature, message, previous_model }
 */
export const updateModelConfig = async (config) =>
  requestJson("/api/config/models", {
    method: "POST",
    body: JSON.stringify(config),
  });

/**
 * Reset model configuration to environment defaults.
 * @returns {Promise<Object>} - { success, model, provider, message }
 */
export const resetModelConfig = async () =>
  requestJson("/api/config/models/reset", {
    method: "POST",
  });

export const connectIntegration = async (name) =>
  requestJson(`/api/integrations/${name}/connect`, {
    method: "POST",
    body: JSON.stringify({ token: "demo-token" }),
  });

export const testIntegration = async (name) =>
  requestJson(`/api/integrations/${name}/test`, {
    method: "POST",
  });

export const updateIntegrationScopes = async (name, scopes) =>
  requestJson(`/api/integrations/${name}/scopes`, {
    method: "PUT",
    body: JSON.stringify({ scopes }),
  });

export const syncIntegration = async (name) =>
  requestJson(`/api/integrations/${name}/sync`, {
    method: "POST",
  });

// ============================================
// Template Management API Functions
// ============================================

/**
 * Fetch all templates, optionally filtered by artifact type.
 * @param {Object} filters - { artifact_type? }
 */
export const fetchTemplates = async (filters = {}) => {
  const params = new URLSearchParams();
  if (filters.artifact_type) params.append("artifact_type", filters.artifact_type);
  const query = params.toString() ? `?${params}` : "";
  return requestJson(`/api/templates${query}`);
};

/**
 * Get a specific template by ID.
 * @param {string} templateId - Template ID
 */
export const fetchTemplate = async (templateId) =>
  requestJson(`/api/templates/${templateId}`);

/**
 * Get the active template for an artifact type.
 * @param {string} artifactType - Artifact type (user_story, epic, initiative)
 */
export const fetchActiveTemplate = async (artifactType) =>
  requestJson(`/api/templates/active/${artifactType}`);

/**
 * Create a new template (upload).
 * @param {Object} template - Template data
 */
export const createTemplate = async (template) =>
  requestJson(`/api/templates`, {
    method: "POST",
    body: JSON.stringify(template),
  });

/**
 * Update a template (creates new version).
 * @param {string} templateId - Template ID
 * @param {Object} updateData - { content, field_mappings?, output_structure?, changelog? }
 */
export const updateTemplate = async (templateId, updateData) =>
  requestJson(`/api/templates/${templateId}`, {
    method: "PUT",
    body: JSON.stringify(updateData),
  });

/**
 * Rollback a template to a previous version.
 * @param {string} templateId - Template ID
 * @param {string} version - Version to rollback to
 */
export const rollbackTemplate = async (templateId, version) =>
  requestJson(`/api/templates/${templateId}/rollback?version=${encodeURIComponent(version)}`, {
    method: "POST",
  });

/**
 * Delete a template.
 * @param {string} templateId - Template ID
 */
export const deleteTemplate = async (templateId) =>
  requestJson(`/api/templates/${templateId}`, {
    method: "DELETE",
  });

// ============================================
// Prompt Management API Functions
// ============================================

/**
 * Fetch all prompts from the library with optional filtering.
 * @param {Object} filters - { category?, agent_type?, tags? }
 */
export const fetchPrompts = async (filters = {}) => {
  const params = new URLSearchParams();
  if (filters.category) params.append("category", filters.category);
  if (filters.agent_type) params.append("agent_type", filters.agent_type);
  if (filters.tags) params.append("tags", filters.tags.join(","));
  const query = params.toString() ? `?${params}` : "";
  return requestJson(`/api/prompts${query}`);
};

/**
 * Get a specific prompt by ID.
 * @param {string} promptId - Prompt ID
 */
export const fetchPrompt = async (promptId) =>
  requestJson(`/api/prompts/${promptId}`);

/**
 * Save or update a prompt.
 * @param {Object} prompt - Prompt template object
 */
export const savePrompt = async (prompt) =>
  requestJson(`/api/prompts`, {
    method: "POST",
    body: JSON.stringify(prompt),
  });

/**
 * Delete a prompt.
 * @param {string} promptId - Prompt ID
 */
export const deletePrompt = async (promptId) =>
  requestJson(`/api/prompts/${promptId}`, {
    method: "DELETE",
  });

/**
 * Add a new version to a prompt.
 * @param {string} promptId - Prompt ID
 * @param {Object} versionData - { version, template, changelog, set_active }
 */
export const addPromptVersion = async (promptId, versionData) =>
  requestJson(`/api/prompts/${promptId}/versions`, {
    method: "POST",
    body: JSON.stringify(versionData),
  });

/**
 * Rollback to a previous version.
 * @param {string} promptId - Prompt ID
 * @param {string} version - Version to rollback to
 */
export const rollbackPromptVersion = async (promptId, version) =>
  requestJson(`/api/prompts/${promptId}/rollback?version=${encodeURIComponent(version)}`, {
    method: "POST",
  });

/**
 * Fetch prompt library summary/metrics.
 */
export const fetchPromptSummary = async () =>
  requestJson("/api/prompts/summary");

/**
 * Fetch prompt monitoring metrics.
 */
export const fetchPromptMetrics = async () =>
  requestJson("/api/prompts/metrics");

/**
 * Fetch recent prompt calls from observability endpoint.
 * @param {Object} filters - { limit? }
 */
export const fetchPromptCalls = async (filters = {}) => {
  const params = new URLSearchParams();
  if (filters.limit) params.append("limit", filters.limit);
  const query = params.toString() ? `?${params}` : "";
  return requestJson(`/api/observability/prompts/history${query}`);
};

/**
 * Update alert thresholds.
 * @param {Object} thresholds - Alert threshold configuration
 */
export const updateAlertThresholds = async (thresholds) =>
  requestJson("/api/prompts/alerts/thresholds", {
    method: "PUT",
    body: JSON.stringify(thresholds),
  });

/**
 * Fetch recent alerts.
 * @param {Object} filters - { severity?, alert_type?, limit? }
 */
export const fetchPromptAlerts = async (filters = {}) => {
  const params = new URLSearchParams();
  if (filters.severity) params.append("severity", filters.severity);
  if (filters.alert_type) params.append("alert_type", filters.alert_type);
  if (filters.limit) params.append("limit", filters.limit);
  const query = params.toString() ? `?${params}` : "";
  return requestJson(`/api/prompts/alerts${query}`);
};

export const runStoryWriting = async (payload) => requestJson("/api/story-writing", {
  method: "POST",
  body: JSON.stringify(payload),
});

/**
 * Simplified story splitting - directly splits without full workflow.
 * @param {Object} payload - { story_text: string, title?: string }
 * @returns {Promise<Object>} - { success, proposed_artifacts, rationale, error }
 */
export const splitStorySimple = async (payload) => requestJson("/api/story-split", {
  method: "POST",
  body: JSON.stringify(payload),
});

/**
 * Stream story writing workflow with SSE.
 * @param {Object} payload - The request payload
 * @param {Function} onEvent - Callback for workflow events (node_start, node_complete, done, error)
 * @param {Object} options - Optional configuration
 * @param {Function} options.onHeartbeat - Optional callback for heartbeat events (connection health)
 */
export const streamStoryWriting = async (payload, onEvent, options = {}) => {
  const { onHeartbeat } = options;

  const response = await fetch(`${API_BASE}/api/story-writing/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const json = line.replace("data:", "").trim();
      if (!json) continue;
      const event = JSON.parse(json);
      
      // Handle heartbeat events separately (don't pass to main handler)
      if (event.event === "heartbeat") {
        if (onHeartbeat) {
          onHeartbeat(event);
        }
        continue;
      }
      
      onEvent(event);
    }
  }
};
