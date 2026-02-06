import React, { useState, useEffect } from "react";

import synapseLogo from "../../synapse-logo.png";

// Animated counter component
function AnimatedCounter({ end, duration = 2000, suffix = "" }) {
  const [count, setCount] = useState(0);
  
  useEffect(() => {
    let startTime;
    const animate = (timestamp) => {
      if (!startTime) startTime = timestamp;
      const progress = Math.min((timestamp - startTime) / duration, 1);
      setCount(Math.floor(progress * end));
      if (progress < 1) requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
  }, [end, duration]);
  
  return <span>{count}{suffix}</span>;
}

// Typing animation component
function TypewriterText({ texts, speed = 100 }) {
  const [displayText, setDisplayText] = useState("");
  const [textIndex, setTextIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);
  
  useEffect(() => {
    const currentText = texts[textIndex];
    
    const timeout = setTimeout(() => {
      if (!isDeleting) {
        setDisplayText(currentText.substring(0, charIndex + 1));
        setCharIndex(charIndex + 1);
        
        if (charIndex + 1 === currentText.length) {
          setTimeout(() => setIsDeleting(true), 2000);
        }
      } else {
        setDisplayText(currentText.substring(0, charIndex - 1));
        setCharIndex(charIndex - 1);
        
        if (charIndex === 0) {
          setIsDeleting(false);
          setTextIndex((textIndex + 1) % texts.length);
        }
      }
    }, isDeleting ? speed / 2 : speed);
    
    return () => clearTimeout(timeout);
  }, [charIndex, isDeleting, textIndex, texts, speed]);
  
  return <span className="typewriter-text">{displayText}<span className="typewriter-cursor">|</span></span>;
}

// FAQ Accordion Item
function FAQItem({ question, answer, isOpen, onToggle }) {
  return (
    <div className={`faq-item ${isOpen ? "open" : ""}`}>
      <button className="faq-question" onClick={onToggle}>
        <span>{question}</span>
        <span className="faq-icon">{isOpen ? "−" : "+"}</span>
      </button>
      {isOpen && <div className="faq-answer">{answer}</div>}
    </div>
  );
}

export function HomeApp({ onStartStory, onViewAdmin }) {
  const [openFAQ, setOpenFAQ] = useState(null);
  const [isVisible, setIsVisible] = useState({});
  
  // Intersection observer for scroll animations
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible((prev) => ({ ...prev, [entry.target.id]: true }));
          }
        });
      },
      { threshold: 0.1 }
    );
    
    document.querySelectorAll(".animate-on-scroll").forEach((el) => {
      observer.observe(el);
    });
    
    return () => observer.disconnect();
  }, []);

  const typingTexts = [
    "User Stories",
    "Acceptance Criteria",
    "Technical Requirements",
    "Test Scenarios",
  ];

  const faqs = [
    {
      question: "How does Synapse integrate with my existing tools?",
      answer: "Synapse connects seamlessly with Linear, Jira, Confluence, GitHub, and Notion. Our API-first architecture means you can integrate with virtually any tool in your delivery stack."
    },
    {
      question: "Is my data secure with Synapse?",
      answer: "Absolutely. Synapse runs in your own infrastructure, ensuring complete data sovereignty. We support air-gapped deployments, and all data processing happens within your security perimeter."
    },
    {
      question: "What AI models does Synapse support?",
      answer: "Synapse is model-agnostic. Use OpenAI, Anthropic Claude, Google Gemini, Azure OpenAI, or run locally with Ollama. Switch models without changing your workflows."
    },
    {
      question: "How long does it take to get started?",
      answer: "Most teams are up and running within a day. Our guided setup helps you configure templates, connect knowledge sources, and start generating quality stories immediately."
    },
    {
      question: "Can Synapse work with my custom templates?",
      answer: "Yes! Synapse is template-driven. Import your existing Definition of Ready, story templates, and acceptance criteria formats. The AI learns and enforces your standards."
    },
  ];

  const testimonials = [
    {
      quote: "Synapse reduced our story refinement time by 60%. The AI catches gaps we'd miss in manual reviews.",
      author: "Sarah Chen",
      role: "Engineering Manager",
      company: "TechCorp"
    },
    {
      quote: "Finally, a tool that understands enterprise constraints. Deployable, secure, and actually useful.",
      author: "Marcus Johnson",
      role: "CTO",
      company: "FinanceFlow"
    },
    {
      quote: "The multi-agent critique system is genius. It's like having three senior engineers review every ticket.",
      author: "Elena Rodriguez",
      role: "Product Owner",
      company: "HealthTech Inc"
    }
  ];

  return (
    <section className="page home-page landing-page">
      {/* Hero Section */}
      <div className="hero-section">
        <div className="hero-gradient-bg"></div>
        <div className="hero-content">
          <div className="hero-badge">
            <span className="badge-dot"></span>
            AI-Powered Story Engineering
          </div>
          <h1 className="hero-title">
            Transform Chaos into<br />
            <span className="hero-gradient-text">Delivery Excellence</span>
          </h1>
          <p className="hero-subtitle">
            Synapse generates INVEST-compliant {" "}
            <TypewriterText texts={typingTexts} speed={80} /><br />
            with multi-agent AI critique and full traceability.
          </p>
          <div className="hero-cta-group">
            <button type="button" className="cta-primary" onClick={onStartStory}>
              <span>Start Building Stories</span>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </button>
            <button type="button" className="cta-secondary" onClick={onViewAdmin}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 15a3 3 0 100-6 3 3 0 000 6z"/>
                <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/>
              </svg>
              Configure System
            </button>
          </div>
          <div className="hero-trust">
            <span className="trust-label">Trusted by teams at</span>
            <div className="trust-logos">
              <span className="trust-logo">Enterprise</span>
              <span className="trust-logo">Fortune 500</span>
            </div>
          </div>
        </div>
        <div className="hero-visual">
          <div className="product-preview">
            <div className="preview-header">
              <div className="preview-dots">
                <span></span><span></span><span></span>
              </div>
              <span className="preview-title">Synapse Accelerator</span>
            </div>
            <div className="preview-content">
              <div className="preview-agent-flow">
                <div className="agent-node orchestrator">
                  <span className="agent-icon">🎯</span>
                  <span>Orchestrator</span>
                </div>
                <div className="agent-connector"></div>
                <div className="agent-group">
                  <div className="agent-node po">
                    <span className="agent-icon">📋</span>
                    <span>PO Agent</span>
                  </div>
                  <div className="agent-node qa">
                    <span className="agent-icon">✓</span>
                    <span>QA Agent</span>
                  </div>
                  <div className="agent-node dev">
                    <span className="agent-icon">⚙</span>
                    <span>Dev Agent</span>
                  </div>
                </div>
                <div className="agent-connector"></div>
                <div className="agent-node output">
                  <span className="agent-icon">✨</span>
                  <span>INVEST Story</span>
                </div>
              </div>
              <div className="preview-output">
                <div className="output-badge">Generated</div>
                <p className="output-text">"As a user, I want to filter search results by date range so that I can find recent content quickly."</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Section */}
      <div className="stats-section animate-on-scroll" id="stats">
        <div className="stat-card">
          <div className="stat-value"><AnimatedCounter end={60} suffix="%" /></div>
          <div className="stat-label">Faster Story Creation</div>
        </div>
        <div className="stat-card">
          <div className="stat-value"><AnimatedCounter end={3} suffix="x" /></div>
          <div className="stat-label">Better Acceptance Criteria</div>
        </div>
        <div className="stat-card">
          <div className="stat-value"><AnimatedCounter end={85} suffix="%" /></div>
          <div className="stat-label">INVEST Compliance</div>
        </div>
        <div className="stat-card">
          <div className="stat-value"><AnimatedCounter end={100} suffix="%" /></div>
          <div className="stat-label">Audit Traceability</div>
        </div>
      </div>

      {/* Problem Section */}
      <div className="problem-section animate-on-scroll" id="problem">
        <div className="section-header">
          <span className="section-badge">The Challenge</span>
          <h2>Poor Stories Create Delivery Chaos</h2>
          <p className="section-subtitle">Every unclear requirement cascades into wasted sprints, frustrated teams, and missed deadlines.</p>
        </div>
        <div className="problem-grid">
          <div className="problem-card">
            <div className="problem-icon">⚠</div>
            <h4>Vague Requirements</h4>
            <p>Stories lack clear acceptance criteria, leading to scope creep and rework.</p>
          </div>
          <div className="problem-card">
            <div className="problem-icon">🔄</div>
            <h4>Endless Refinement</h4>
            <p>Teams spend hours debating what "done" means instead of building.</p>
          </div>
          <div className="problem-card">
            <div className="problem-icon">🔍</div>
            <h4>Missing Context</h4>
            <p>Technical constraints and dependencies surface too late in the process.</p>
          </div>
          <div className="problem-card">
            <div className="problem-icon">📉</div>
            <h4>Quality Inconsistency</h4>
            <p>Story quality varies wildly between writers and teams.</p>
          </div>
        </div>
      </div>

      {/* Solution Section */}
      <div className="solution-section animate-on-scroll" id="solution">
        <div className="section-header">
          <span className="section-badge success">The Solution</span>
          <h2>AI-Powered Multi-Agent Critique</h2>
          <p className="section-subtitle">Three specialized agents debate and refine every story until it meets your standards.</p>
        </div>
        <div className="agents-showcase">
          <div className="agent-card po-card">
            <div className="agent-avatar">📋</div>
            <h4>Product Owner Agent</h4>
            <p>Validates business value, user personas, and problem-solution fit.</p>
            <ul className="agent-tasks">
              <li>Value proposition clarity</li>
              <li>User journey alignment</li>
              <li>Business goal mapping</li>
            </ul>
          </div>
          <div className="agent-card qa-card">
            <div className="agent-avatar">✓</div>
            <h4>QA Agent</h4>
            <p>Enforces INVEST criteria and testability standards.</p>
            <ul className="agent-tasks">
              <li>INVEST validation</li>
              <li>Acceptance criteria review</li>
              <li>Test scenario generation</li>
            </ul>
          </div>
          <div className="agent-card dev-card">
            <div className="agent-avatar">⚙</div>
            <h4>Developer Agent</h4>
            <p>Surfaces technical constraints, dependencies, and NFRs.</p>
            <ul className="agent-tasks">
              <li>Technical feasibility</li>
              <li>Dependency mapping</li>
              <li>Architecture alignment</li>
            </ul>
          </div>
        </div>
      </div>

      {/* How It Works */}
      <div className="workflow-section animate-on-scroll" id="workflow">
        <div className="section-header">
          <span className="section-badge">How It Works</span>
          <h2>From Brief to Done in 5 Steps</h2>
        </div>
        <div className="workflow-steps">
          <div className="workflow-step">
            <div className="step-number">1</div>
            <div className="step-content">
              <h4>Input Your Brief</h4>
              <p>Paste your rough idea, feature request, or user feedback.</p>
            </div>
          </div>
          <div className="workflow-connector"></div>
          <div className="workflow-step">
            <div className="step-number">2</div>
            <div className="step-content">
              <h4>Select Template</h4>
              <p>Choose from your organization's approved story templates.</p>
            </div>
          </div>
          <div className="workflow-connector"></div>
          <div className="workflow-step">
            <div className="step-number">3</div>
            <div className="step-content">
              <h4>AI Generation</h4>
              <p>Multi-agent system creates and critiques the story.</p>
            </div>
          </div>
          <div className="workflow-connector"></div>
          <div className="workflow-step">
            <div className="step-number">4</div>
            <div className="step-content">
              <h4>Review & Refine</h4>
              <p>Human review with AI-suggested improvements.</p>
            </div>
          </div>
          <div className="workflow-connector"></div>
          <div className="workflow-step">
            <div className="step-number">5</div>
            <div className="step-content">
              <h4>Export to Tools</h4>
              <p>Push directly to Linear, Jira, or your preferred tracker.</p>
            </div>
          </div>
        </div>
      </div>

      {/* Features Grid */}
      <div className="features-section animate-on-scroll" id="features">
        <div className="section-header">
          <span className="section-badge">Capabilities</span>
          <h2>Built for Enterprise Delivery</h2>
        </div>
        <div className="features-grid">
          <div className="feature-card featured">
            <div className="feature-icon">🔒</div>
            <h4>Deploy Anywhere</h4>
            <p>Run on-premise, in your cloud, or air-gapped. Your data never leaves your infrastructure.</p>
            <span className="feature-tag">Security First</span>
          </div>
          <div className="feature-card">
            <div className="feature-icon">🤖</div>
            <h4>Model Agnostic</h4>
            <p>OpenAI, Anthropic, Google, Azure, or Ollama. Use any LLM provider.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">📐</div>
            <h4>Template Driven</h4>
            <p>Your DoR, DoD, and story templates. Synapse enforces your standards.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">🔗</div>
            <h4>Deep Integrations</h4>
            <p>Linear, Jira, Confluence, GitHub, Notion. Connect your entire stack.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">📊</div>
            <h4>Full Traceability</h4>
            <p>Every decision audited. Know exactly how and why each story was generated.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">🧠</div>
            <h4>RAG Knowledge Base</h4>
            <p>Ingest your docs, repos, and wikis. AI understands your context.</p>
          </div>
        </div>
      </div>

      {/* Testimonials */}
      <div className="testimonials-section animate-on-scroll" id="testimonials">
        <div className="section-header">
          <span className="section-badge">Testimonials</span>
          <h2>Teams Love Synapse</h2>
        </div>
        <div className="testimonials-grid">
          {testimonials.map((t, i) => (
            <div key={i} className="testimonial-card">
              <div className="testimonial-quote">"{t.quote}"</div>
              <div className="testimonial-author">
                <div className="author-avatar">{t.author[0]}</div>
                <div className="author-info">
                  <strong>{t.author}</strong>
                  <span>{t.role} at {t.company}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* FAQ Section */}
      <div className="faq-section animate-on-scroll" id="faq">
        <div className="section-header">
          <span className="section-badge">FAQ</span>
          <h2>Common Questions</h2>
        </div>
        <div className="faq-list">
          {faqs.map((faq, index) => (
            <FAQItem
              key={index}
              question={faq.question}
              answer={faq.answer}
              isOpen={openFAQ === index}
              onToggle={() => setOpenFAQ(openFAQ === index ? null : index)}
            />
          ))}
        </div>
      </div>

      {/* Final CTA */}
      <div className="final-cta-section">
        <div className="cta-card">
          <img src={synapseLogo} alt="Synapse" className="cta-logo" />
          <h2>Ready to Transform Your Delivery?</h2>
          <p>Start generating INVEST-compliant stories in minutes, not hours.</p>
          <div className="cta-buttons">
            <button type="button" className="cta-primary large" onClick={onStartStory}>
              Get Started Free
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </button>
          </div>
          <p className="cta-note">No credit card required. Deploy in your infrastructure.</p>
        </div>
      </div>
    </section>
  );
}
