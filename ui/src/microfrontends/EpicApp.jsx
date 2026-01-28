import React, { useMemo, useState } from "react";

import { CRITIQUE_FEEDBACK, EPIC_STEPS } from "../shared/data";
import { buildCandidatesFromTechniques, buildEpicRun } from "../shared/flows";

export function EpicApp({ activeModes, critiqueEnabled }) {
  const [startFromSource, setStartFromSource] = useState(false);
  const [epicDraft, setEpicDraft] = useState("");
  const [epicRun, setEpicRun] = useState(null);
  const [epicTechniques, setEpicTechniques] = useState([]);

  const canGenerateEpic = useMemo(() => epicDraft.trim().length > 0, [epicDraft]);

  const handleGenerateEpic = () => {
    const run = buildEpicRun(epicDraft, activeModes);
    setEpicRun(run);
    setEpicTechniques(run.selectedTechniques);
  };

  const handleToggleTechnique = (technique) => {
    if (epicTechniques.includes(technique)) {
      setEpicTechniques(epicTechniques.filter((item) => item !== technique));
      return;
    }
    setEpicTechniques([...epicTechniques, technique]);
  };

  const handleRegenerateEpicStories = () => {
    if (!epicRun) return;
    setEpicRun({
      ...epicRun,
      selectedTechniques: epicTechniques,
      generatedStories: buildCandidatesFromTechniques(
        epicRun.analysis.persona,
        epicRun.analysis.capability,
        epicTechniques,
        "STORY"
      ),
    });
  };

  return (
    <section className="page">
      <div className="page-header">
        <h1>Create an EPIC</h1>
        <p>Draft an EPIC from an existing Initiative or from scratch.</p>
      </div>
      <div className="card">
        <div className="section">
          <h3>Start source</h3>
          <p className="muted">Start from an existing Initiative?</p>
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
        </div>
      </div>
      <div className="card">
        <div className="section">
          <h3>Describe your feature</h3>
          <p className="muted">Required to generate a draft.</p>
          <textarea
            rows={6}
            value={epicDraft}
            onChange={(event) => setEpicDraft(event.target.value)}
            placeholder="Describe the feature, context, target users, expected value, constraints..."
          />
          <p className="muted">Required to generate a draft.</p>
        </div>
      </div>
      <div className="actions">
        <button
          type="button"
          className="primary"
          disabled={!canGenerateEpic}
          onClick={handleGenerateEpic}
        >
          Generate draft
        </button>
      </div>
      <div className="card">
        <div className="section">
          <h3>Agent timeline</h3>
          <div className="stepper">
            {EPIC_STEPS.map((step) => (
              <div key={step.id} className="step">
                <div className={`status-pill ${epicRun ? "success" : "muted"}`}>
                  {epicRun ? "Complete" : "Pending"}
                </div>
                <div>
                  <strong>{step.label}</strong>
                  <p className="muted">{step.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      {epicRun && (
        <>
          <div className="card">
            <div className="section">
              <h3>Epic analysis</h3>
              <p className="muted">
                Persona: {epicRun.analysis.persona} · Capability: {epicRun.analysis.capability}
              </p>
              <p className="muted">
                Benefit: {epicRun.analysis.benefit} · Complexity: {epicRun.analysis.complexityScore.toFixed(2)}
              </p>
              {epicRun.analysis.ambiguities.length > 0 && (
                <ul className="summary-list">
                  {epicRun.analysis.ambiguities.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          <div className="card">
            <div className="section">
              <h3>Technique selection</h3>
              <p className="muted">Select techniques before generating stories.</p>
              <div className="checkbox-grid">
                {epicRun.recommendations.map((item) => (
                  <label key={item.technique} className="checkbox-item">
                    <input
                      type="checkbox"
                      checked={epicTechniques.includes(item.technique)}
                      onChange={() => handleToggleTechnique(item.technique)}
                    />
                    <span>
                      {item.technique} · <span className="muted">{item.rationale}</span>
                    </span>
                  </label>
                ))}
              </div>
              <div className="actions align-left">
                <button type="button" className="ghost" onClick={handleRegenerateEpicStories}>
                  Regenerate stories
                </button>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="section">
              <h3>Generated stories</h3>
              <ul className="summary-list">
                {epicRun.generatedStories.map((story) => (
                  <li key={story.id}>{story.title}</li>
                ))}
              </ul>
              <div className="actions align-left">
                <button type="button" className="primary">
                  Detail selected stories
                </button>
                <button type="button" className="ghost">
                  Export to Jira
                </button>
                <button type="button" className="ghost">
                  Export to Linear
                </button>
              </div>
            </div>
          </div>
          {(critiqueEnabled.poEnabled || critiqueEnabled.qaEnabled || critiqueEnabled.devEnabled) && (
            <div className="card">
              <div className="section">
                <h3>Critique loop</h3>
                <div className="grid-3">
                  {critiqueEnabled.poEnabled && (
                    <div className="critique-panel">
                      <h4>Product Owner</h4>
                      <ul className="summary-list">
                        {CRITIQUE_FEEDBACK.po.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {critiqueEnabled.qaEnabled && (
                    <div className="critique-panel">
                      <h4>QA</h4>
                      <ul className="summary-list">
                        {CRITIQUE_FEEDBACK.qa.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {critiqueEnabled.devEnabled && (
                    <div className="critique-panel">
                      <h4>Developer</h4>
                      <ul className="summary-list">
                        {CRITIQUE_FEEDBACK.dev.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
                <div className="actions align-left">
                  <button type="button" className="primary">
                    Apply suggestions
                  </button>
                  <button type="button" className="ghost">
                    Rerun critique
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
