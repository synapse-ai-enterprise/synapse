const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? "http://localhost:8000" : "");

const requestJson = async (path, options = {}) => {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return response.json();
};

export const fetchIntegrations = async () => {
  const payload = await requestJson("/api/integrations");
  return payload.integrations || [];
};

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

export const runStoryWriting = async (payload) => requestJson("/api/story-writing", {
  method: "POST",
  body: JSON.stringify(payload),
});

export const streamStoryWriting = async (payload, onEvent) => {
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
      onEvent(JSON.parse(json));
    }
  }
};
