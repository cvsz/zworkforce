import { ArrowRight, Bot, CheckCircle2 } from 'lucide-react';

export default function ProductAIAgent({ onLaunchApp, isDark }) {
  const textColor = isDark ? '#fff' : '#0f172a';
  const mutedColor = isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)';
  
  return (
    <div className="container" style={{ padding: '4rem 0', color: textColor }}>
      {/* Hero Header */}
      <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
        <span style={{
          fontSize: '0.85rem',
          color: 'var(--primary-color)',
          backgroundColor: 'rgba(0, 194, 142, 0.1)',
          padding: '0.4rem 0.8rem',
          borderRadius: '20px',
          fontWeight: '700',
          textTransform: 'uppercase',
          letterSpacing: '0.05em'
        }}>
          AI Platform
        </span>
        <h1 style={{ fontSize: '3rem', margin: '1rem 0 0.5rem 0', letterSpacing: '-0.03em' }}>
          Conversational AI Agent
        </h1>
        <p style={{ color: mutedColor, fontSize: '1.1rem', maxWidth: '650px', margin: '0 auto' }}>
          Train a custom e-commerce bot using your website URLs, PDF catalogs, or QA spreadsheets to capture leads and close orders 24/7.
        </p>
        <button onClick={onLaunchApp} className="btn-primary" style={{ margin: '1.5rem auto 0 auto' }}>
          Train AI Sandbox <ArrowRight size={16} />
        </button>
      </div>

      {/* Feature Highlight Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3rem', alignItems: 'center', marginBottom: '5rem' }}>
        {/* Simulator Preview Card */}
        <div style={{
          backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff',
          border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`,
          borderRadius: '16px',
          padding: '1.5rem',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.1)',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem'
        }}>
          <span style={{ fontWeight: '700', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <Bot size={16} style={{ color: 'var(--primary-color)' }} /> AI Agent Conversational Simulator
          </span>

          <div style={{ border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, borderRadius: '8px', padding: '1rem', backgroundColor: isDark ? 'rgba(255,255,255,0.01)' : '#f8fafc', fontSize: '0.8rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ alignSelf: 'flex-start', backgroundColor: isDark ? 'rgba(255,255,255,0.05)' : '#e2e8f0', padding: '0.5rem 0.75rem', borderRadius: '8px 8px 8px 0', maxWidth: '80%' }}>
                Hi, do you offer free shipping to Thailand?
              </div>
              <div style={{ alignSelf: 'flex-end', backgroundColor: 'var(--primary-color)', color: '#fff', padding: '0.5rem 0.75rem', borderRadius: '8px 8px 0 8px', maxWidth: '80%' }}>
                ✨ Yes, we offer free shipping to Thailand on all orders exceeding $100! Delivery takes 3-5 business days.
              </div>
            </div>
          </div>
        </div>

        <div>
          <h2 style={{ fontSize: '2rem', marginBottom: '1rem', letterSpacing: '-0.02em' }}>
            Instant Customer Service, Zero Setup Fees
          </h2>
          <p style={{ color: mutedColor, lineHeight: '1.6', marginBottom: '1.5rem' }}>
            Train your custom AI bot directly by uploading files or inserting answers. Define response personas (Friendly Sales Rep, Structured Support Guide) and set up triggers to transition to live agents when custom criteria are met.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Context-Aware Knowledge Bases:</strong> Upload documents or paste store policies. The AI learns context rules instantly.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Smart Human Handoff:</strong> Detect keywords like "human", "talk to support", or custom escalation parameters, routing directly to the Unified Inbox.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Multi-Language Competency:</strong> Support languages like Thai, English, Vietnamese, and Bahasa fluently inside the chatbot.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
