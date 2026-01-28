import React, { useMemo, useState } from "react";

import { CRITIQUE_FEEDBACK, INITIATIVE_STEPS } from "../shared/data";
import { buildCandidatesFromTechniques, buildInitiativeRun } from "../shared/flows";

export function InitiativeApp({ activeModes, critiqueEnabled }) {
  const [startFromSource, setStartFromSource] = useState(false);
  const [initiativeTitle, setInitiativeTitle] = useState("");
  const [initiativeDraft, setInitiativeDraft] = useState("");
  const [initiativeOutcome, setInitiativeOutcome] = useState("");
  const [initiativeConstraints, setInitiativeConstraints] = useState("");
  const [initiativeRun, setInitiativeRun] = useState(null);
  const [initiativeTechniques, setInitiativeTechniques] = useState([]);

  const canGenerateInitiative = useMemo(
    () => initiativeTitle.trim().length > 0 && initiativeDraft.trim().length > 0,
    [initiativeTitle, initiativeDraft]
  );

  const handleGenerateInitiative = () => {
    const run = buildInitiativeRun(initiativeDraft, activeModes);
    setInitiativeRun(run);
    setInitiativeTechniques(run.selectedTechniques);
  };

  const handleToggleTechnique = (technique) => {
    if (initiativeTechniques.includes(technique)) {
      setInitiativeTechniques(initiativeTechniques.filter((item) => item !== technique));
      return;
    }
    setInitiativeTechniques([...initiativeTechniques, technique]);
  };

  const handleRegenerateInitiativeEpics = () => {
    if (!initiativeRun) return;
    setInitiativeRun({
      ...initiativeRun,
      selectedTechniques: initiativeTechniques,
      generatedEpics: buildCandidatesFromTechniques(
        initiativeRun.analysis.persona,
        initiativeRun.analysis.capability,
        initiativeTechniques,
        "EPIC"
      ),
    });
  };

  return (
    <section className="page">
      <div className="page-header">
        <h1>Create an Initiative</h1>
        <p>Define strategic goals and generate aligned EPIC candidates.</p>
      </div>
      <div className="card">
        <div className="section">
          <h3>Start source</h3>
          <p className="muted">Start from an existing portfolio initiative?</p>
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
          <h3>Initiative details</h3>
          <label htmlFor="initiativeTitle">Initiative title</label>
          <input
            id="initiativeTitle"
            type="text"
            value={initiativeTitle}
            onChange={(event) => setInitiativeTitle(event.target.value)}
            placeholder="Expand payments adoption in LATAM"
          />
          <label htmlFor="initiativeDescription">Description</label>
          <textarea
            id="initiativeDescription"
            rows={6}
            value={initiativeDraft}
            onChange={(event) => setInitiativeDraft(event.target.value)}
            placeholder="Describe the initiative, scope, stakeholders, and constraints..."
          />
          <label htmlFor="initiativeOutcome">Business outcome / KPI</label>
          <input
            id="initiativeOutcome"
            type="text"
            value={initiativeOutcome}
            onChange={(event) => setInitiativeOutcome(event.target.value)}
            placeholder="Increase recurring revenue by 12% within 6 months"
          />
          <label htmlFor="initiativeConstraints">Constraints</label>
          <input
            id="initiativeConstraints"
            type="text"
            value={initiativeConstraints}
            onChange={(event) => setInitiativeConstraints(event.target.value)}
            placeholder="Regulatory approvals, partner timelines, funding"
          />
        </div>
      </div>
      <div className="actions">
        <button
          type="button"
          className="primary"
          disabled={!canGenerateInitiative}
          onClick={handleGenerateInitiative}
        >
          Generate EPICs
        </button>
      </div>
      <div className="card">
        <div className="section">
          <h3>Agent timeline</h3>
          <div className="stepper">
            {INITIATIVE_STEPS.map((step) => (
              <div key={step.id} className="step">
                <div className={`status-pill ${initiativeRun ? "success" : "muted"}`}>
                  {initiativeRun ? "Complete" : "Pending"}
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
      {initiativeRun && (
        <>
          <div className="card">
            <div className="section">
              <h3>Initiative analysis</h3>
              <p className="muted">
                Persona: {initiativeRun.analysis.persona} · Capability: {initiativeRun.analysis.capability}
              </p>
              <p className="muted">
                Benefit: {initiativeRun.analysis.benefit} · Complexity:{" "}
                {initiativeRun.analysis.complexityScore.toFixed(2)}
              </p>
              {initiativeRun.analysis.ambiguities.length > 0 && (
                <ul className="summary-list">
                  {initiativeRun.analysis.ambiguities.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          <div className="card">
            <div className="section">
              <h3>Technique selection</h3>
              <p className="muted">Select how to decompose the initiative into EPICs.</p>
              <div className="checkbox-grid">
                {initiativeRun.recommendations.map((item) => (
                  <label key={item.technique} className="checkbox-item">
                    <input
                      type="checkbox"
                      checked={initiativeTechniques.includes(item.technique)}
                      onChange={() => handleToggleTechnique(item.technique)}
                    />
                    <span>
                      {item.technique} · <span className="muted">{item.rationale}</span>
                    </span>
                  </label>
                ))}
              </div>
              <div className="actions align-left">
                <button type="button" className="ghost" onClick={handleRegenerateInitiativeEpics}>
                  Regenerate EPICs
                </button>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="section">
              <h3>Generated EPICs</h3>
              <ul className="summary-list">
                {initiativeRun.generatedEpics.map((epic) => (
                  <li key={epic.id}>{epic.title}</li>
                ))}
              </ul>
              <div className="actions align-left">
                <button type="button" className="primary">
                  Open in EPIC workflow
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
