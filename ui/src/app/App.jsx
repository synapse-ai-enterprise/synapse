import React, { Suspense, lazy, useMemo, useState } from "react";

const NAV_ITEMS = [
  { id: "home", label: "Home" },
  { id: "initiative", label: "Initiative" },
  { id: "epic", label: "EPIC" },
  { id: "story", label: "User Story" },
  { id: "admin", label: "Admin Console" },
  { id: "history", label: "History" },
];

const MICRO_FRONTENDS = {
  home: lazy(() => import("../microfrontends/HomeApp").then((module) => ({ default: module.HomeApp }))),
  initiative: lazy(() =>
    import("../microfrontends/InitiativeApp").then((module) => ({ default: module.InitiativeApp }))
  ),
  epic: lazy(() => import("../microfrontends/EpicApp").then((module) => ({ default: module.EpicApp }))),
  story: lazy(() => import("../microfrontends/StoryApp").then((module) => ({ default: module.StoryApp }))),
  admin: lazy(() => import("../microfrontends/AdminApp").then((module) => ({ default: module.AdminApp }))),
  history: lazy(() =>
    import("../microfrontends/HistoryApp").then((module) => ({ default: module.HistoryApp }))
  ),
};

const MicroFrontendHost = ({ activeId, sharedProps }) => {
  const Component = MICRO_FRONTENDS[activeId];
  if (!Component) return null;
  return (
    <Suspense
      fallback={
        <section className="page">
          <div className="card">
            <div className="section">
              <h3>Loading workspace…</h3>
              <p className="muted">Bringing the micro frontend online.</p>
            </div>
          </div>
        </section>
      }
    >
      <Component {...sharedProps} />
    </Suspense>
  );
};

export default function App() {
  const [activeNav, setActiveNav] = useState("home");
  const [adminTab, setAdminTab] = useState("templates");
  const [technicalEnabled, setTechnicalEnabled] = useState(true);
  const [businessEnabled, setBusinessEnabled] = useState(true);
  const [poEnabled, setPoEnabled] = useState(true);
  const [qaEnabled, setQaEnabled] = useState(true);
  const [devEnabled, setDevEnabled] = useState(true);
  const [templateText, setTemplateText] = useState(
    "# User Story Template Specification\nVersion 1.0 · Last updated Jan 28, 2026\n\n## 1. Field Mappings\nTitle → title (required)\nDescription → description (required)\nAcceptance criteria → acceptance_criteria (required)\nDependencies → dependencies (optional)\nNFRs → nfrs (optional)\nOut of scope → out_of_scope (optional)\nAssumptions → assumptions (optional)\nOpen questions → open_questions (optional)\n\n## 2. Output Structure\ntitle: \"As a user, I want ... so that ...\"\ndescription: \"### Context\\n...\"\nacceptance_criteria:\n  - [ ] Given ... When ... Then ...\n  - [ ] Given ... When ... Then ...\n\ndependencies: [\"STORY-123\"]\nnfrs: [\"Response < 2s\"]\n"
  );

  const activeModes = useMemo(() => ({ technicalEnabled, businessEnabled }), [technicalEnabled, businessEnabled]);
  const critiqueEnabled = useMemo(
    () => ({ poEnabled, qaEnabled, devEnabled }),
    [poEnabled, qaEnabled, devEnabled]
  );

  const sharedProps = {
    activeModes,
    critiqueEnabled,
    templateText,
    setTemplateText,
    adminTab,
    setAdminTab,
    onStartStory: () => {
      setActiveNav("story");
    },
    onViewAdmin: () => {
      setActiveNav("admin");
      setAdminTab("templates");
    },
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
  };

  const isPreviewOnly = useMemo(
    () => ["initiative", "epic", "history"].includes(activeNav),
    [activeNav]
  );

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">Synapse</div>
        <nav className="topnav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`tab ${activeNav === item.id ? "active" : ""}`}
              onClick={() => setActiveNav(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="profile">
          <span className="avatar">A</span>
          <span>Admin</span>
          <span className="caret">▾</span>
        </div>
      </header>

      <main className="content">
        <div className={`preview-wrapper ${isPreviewOnly ? "preview-only" : ""}`}>
          <MicroFrontendHost
            activeId={activeNav}
            sharedProps={{
              ...sharedProps,
              onManageTemplate: () => {
                setActiveNav("admin");
                setAdminTab("templates");
              },
              onManageKnowledgeSources: () => {
                setActiveNav("admin");
                setAdminTab("integrations");
              },
            }}
          />
          {isPreviewOnly && (
            <div className="preview-overlay">
              <span>Coming Soon</span>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
