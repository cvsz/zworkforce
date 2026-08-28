import { ArrowRight, CheckCircle2, Award, Users } from 'lucide-react';

export default function UseCaseMarketing({ onLaunchApp, isDark }) {
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
          Zok for Marketing & Broadcasts
        </h1>
        <p style={{ color: mutedColor, fontSize: '1.1rem', maxWidth: '650px', margin: '0 auto' }}>
          Launch targeted newsletters, VIP discount coupon codes, and promo templates directly to customer lists on WhatsApp and LINE OA.
        </p>
        <button onClick={onLaunchApp} className="btn-primary" style={{ margin: '1.5rem auto 0 auto' }}>
          Open Campaign Manager <ArrowRight size={16} />
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3rem', alignItems: 'center', marginBottom: '5rem' }}>
        <div>
          <h2 style={{ fontSize: '2rem', marginBottom: '1rem', letterSpacing: '-0.02em' }}>
            Drive High Open-Rate Campaigns
          </h2>
          <p style={{ color: mutedColor, lineHeight: '1.6', marginBottom: '1.5rem' }}>
            Traditional email marketing yields only 15-20% open rates. WhatsApp and LINE OA campaigns through Zok command over **85%+ open rates**, helping online merchants drive immediate conversions.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Smart Audience Tag Segmenting:</strong> Filter recipients by customer behaviors, orders history, or custom tags to optimize message limits.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>WhatsApp Approved Marketing Templates:</strong> Draft template coordinates and variables, track approval logs, and send bulk updates.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>A/B Click Tracking:</strong> Analyze exact click metrics and conversion performance figures across different template drafts.
              </div>
            </div>
          </div>
        </div>

        {/* Marketing KPI Card Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div style={{ backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, borderRadius: '12px', padding: '1.25rem' }}>
            <Users size={20} style={{ color: 'var(--primary-color)', marginBottom: '0.5rem' }} />
            <div style={{ fontSize: '1.5rem', fontWeight: '800' }}>88.4%</div>
            <div style={{ fontSize: '0.75rem', color: mutedColor }}>Average Broadcast Read Rate</div>
          </div>

          <div style={{ backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, borderRadius: '12px', padding: '1.25rem' }}>
            <Award size={20} style={{ color: 'var(--primary-color)', marginBottom: '0.5rem' }} />
            <div style={{ fontSize: '1.5rem', fontWeight: '800' }}>14.2%</div>
            <div style={{ fontSize: '0.75rem', color: mutedColor }}>Conversion Purchase Rate</div>
          </div>

          <div style={{ backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, borderRadius: '12px', padding: '1.25rem', gridColumn: 'span 2' }}>
            <div style={{ fontSize: '0.8rem', fontWeight: '700', marginBottom: '0.5rem' }}>Latest Campaign Metrics</div>
            <div style={{ display: 'flex', justifyBetween: 'space-between', fontSize: '0.75rem', marginBottom: '0.25rem' }}>
              <span>LINE Voucher Blast:</span>
              <strong style={{ color: 'var(--primary-color)' }}>92.1% Opened</strong>
            </div>
            <div style={{ display: 'flex', justifyBetween: 'space-between', fontSize: '0.75rem' }}>
              <span>August VIP Discount Code:</span>
              <strong style={{ color: 'var(--primary-color)' }}>84.2% Opened</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
