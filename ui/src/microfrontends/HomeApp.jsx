import React from "react";

import synapseLogo from "../../synapse-logo.png";

export function HomeApp({ onStartStory, onViewAdmin }) {
  return (
    <section className="page home-page">
      <div className="home-hero">
        <div className="home-hero-text">
          <div className="home-hero-header" />
          <h1>The AI Accelerator for Precision Delivery</h1>
          <p className="muted">
            Eliminate the chaos of poor ticket quality and accelerate your path from brief to
            "ready-to-review."
          </p>
          <div className="home-actions">
            <button type="button" className="primary home-cta" onClick={onStartStory}>
              Start with User Story
            </button>
            <button type="button" className="ghost" onClick={onViewAdmin}>
              View Admin Console
            </button>
          </div>
        </div>
        <div className="home-hero-card">
          <div className="home-hero-media">
            <img src={synapseLogo} alt="Synapse logo" className="home-logo-large" />
            <p className="muted">Safe, controlled AI for enterprise delivery workflows.</p>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="section">
          <h3>A 5-Step Journey to High-Quality Tickets</h3>
          <div className="workflow-ribbon">
            <span>1. Select</span>
            <span>2. Input</span>
            <span>3. Generate</span>
            <span>4. Export</span>
            <span>5. Review</span>
          </div>
          <div className="infrastructure-diagram">
            <div className="infra-column">
              <strong>Inputs</strong>
              <p className="muted">Briefs · Templates · Knowledge</p>
            </div>
            <div className="infra-center">
              <span>Synapse Accelerator</span>
            </div>
            <div className="infra-column">
              <strong>Outputs</strong>
              <p className="muted">Refined tickets · Exports · Audit</p>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="section">
          <h3>Why Synapse?</h3>
          <div className="home-feature-grid">
            <div className="home-feature">
              <h4>Deployable by Design</h4>
              <p className="muted">Runs in your infrastructure to meet security and governance needs.</p>
            </div>
            <div className="home-feature">
              <h4>Tool & Model Agnostic</h4>
              <p className="muted">Works with preferred AI models and delivery stacks.</p>
            </div>
            <div className="home-feature">
              <h4>Config-Driven</h4>
              <p className="muted">Align with your templates, DoR/DoD rules, and policies.</p>
            </div>
            <div className="home-feature">
              <h4>Human-Centered</h4>
              <p className="muted">Prepares inputs; humans handle estimation and review.</p>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="section">
          <h3>Empowering Every Role</h3>
          <div className="bento-grid">
            <div className="bento-card bento-main">
              <h4>Problem / Solution</h4>
              <p className="muted">
                Poor inputs create downstream chaos. Synapse standardizes quality before delivery.
              </p>
            </div>
            <div className="bento-card">
              <h4>Contextual Role</h4>
              <p className="muted">Templates, DoR/DoD, and organizational context.</p>
            </div>
            <div className="bento-card">
              <h4>Business Role</h4>
              <p className="muted">Problem statement, personas, and value alignment.</p>
            </div>
            <div className="bento-card">
              <h4>Technical Role</h4>
              <p className="muted">Constraints, dependencies, and NFRs surfaced early.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
