import { ArrowRight, CheckCircle2, Award, Clock } from 'lucide-react';

export default function UseCaseSupport({ onLaunchApp, isDark }) {
  const textColor = isDark ? '#fff' : '#0f172a';
  const mutedColor = isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)';
  
  return (
    <div className="container" style={{ padding: '4rem 0', color: textColor }}>
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
          Use Case
        </span>
        <h1 style={{ fontSize: '3rem', margin: '1rem 0 0.5rem 0', letterSpacing: '-0.03em' }}>
          Zok for Customer Support
        </h1>
        <p style={{ color: mutedColor, fontSize: '1.1rem', maxWidth: '650px', margin: '0 auto' }}>
          Empower support teams with shared queues, automatic routing rules, SLA monitors, and AI response assistance to resolve tickets 10x faster.
        </p>
        <button onClick={onLaunchApp} className="btn-primary" style={{ margin: '1.5rem auto 0 auto' }}>
          Open Support Dashboard <ArrowRight size={16} />
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3rem', alignItems: 'center', marginBottom: '5rem' }}>
        <div>
          <h2 style={{ fontSize: '2rem', marginBottom: '1rem', letterSpacing: '-0.02em' }}>
            Unify and Coordinate Support Operations
          </h2>
          <p style={{ color: mutedColor, lineHeight: '1.6', marginBottom: '1.5rem' }}>
            Provide immediate help to your users on their favorite messaging channels. Never miss an SLA target or duplicate efforts when multiple agents are replying to customer questions.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Shared Team Queues:</strong> Automatically allocate cases to online support operators or trigger chatbot welcome messages.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>SLA Breach Warnings:</strong> Highlight conversations that have been pending without operator answers for over 15 minutes.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>AI Assist Suggestions:</strong> Generate answer drafts inside the chat toolbar based on your training document knowledge.
              </div>
            </div>
          </div>
        </div>

        {/* Support Stats Card Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div style={{ backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, borderRadius: '12px', padding: '1.25rem' }}>
            <Clock size={20} style={{ color: 'var(--primary-color)', marginBottom: '0.5rem' }} />
            <div style={{ fontSize: '1.5rem', fontWeight: '800' }}>3.4m</div>
            <div style={{ fontSize: '0.75rem', color: mutedColor }}>Average Resolution Time</div>
          </div>

          <div style={{ backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, borderRadius: '12px', padding: '1.25rem' }}>
            <Award size={20} style={{ color: 'var(--primary-color)', marginBottom: '0.5rem' }} />
            <div style={{ fontSize: '1.5rem', fontWeight: '800' }}>94.8%</div>
            <div style={{ fontSize: '0.75rem', color: mutedColor }}>SLA Achievement Rate</div>
          </div>

          <div style={{ backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, borderRadius: '12px', padding: '1.25rem', gridColumn: 'span 2' }}>
            <div style={{ fontSize: '0.8rem', fontWeight: '700', marginBottom: '0.5rem' }}>Active Operator Load</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.75rem' }}>
              <div style={{ display: 'flex', justifyBetween: 'space-between', alignItems: 'center' }}>
                <span style={{ width: '100px' }}>Sarah Connor:</span>
                <div style={{ flex: 1, height: '6px', backgroundColor: isDark ? 'rgba(255,255,255,0.05)' : '#e2e8f0', borderRadius: '3px', overflow: 'hidden', margin: '0 0.5rem' }}>
                  <div style={{ width: '85%', height: '100%', backgroundColor: 'var(--primary-color)' }}></div>
                </div>
                <span>12 Open Cases</span>
              </div>
              <div style={{ display: 'flex', justifyBetween: 'space-between', alignItems: 'center' }}>
                <span style={{ width: '100px' }}>Alex Rivera:</span>
                <div style={{ flex: 1, height: '6px', backgroundColor: isDark ? 'rgba(255,255,255,0.05)' : '#e2e8f0', borderRadius: '3px', overflow: 'hidden', margin: '0 0.5rem' }}>
                  <div style={{ width: '50%', height: '100%', backgroundColor: 'var(--primary-color)' }}></div>
                </div>
                <span>7 Open Cases</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
