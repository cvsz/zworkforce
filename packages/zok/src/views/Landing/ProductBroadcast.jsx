import { ArrowRight, Send, CheckCircle2 } from 'lucide-react';

export default function ProductBroadcast({ onLaunchApp, isDark }) {
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
          Broadcasting Studio
        </span>
        <h1 style={{ fontSize: '3rem', margin: '1rem 0 0.5rem 0', letterSpacing: '-0.03em' }}>
          Bulk Broadcast Campaigns
        </h1>
        <p style={{ color: mutedColor, fontSize: '1.1rem', maxWidth: '650px', margin: '0 auto' }}>
          Launch targeted newsletters, VIP coupon codes, and promo templates directly to your customers on WhatsApp and LINE OA.
        </p>
        <button onClick={onLaunchApp} className="btn-primary" style={{ margin: '1.5rem auto 0 auto' }}>
          Launch Broadcast Simulator <ArrowRight size={16} />
        </button>
      </div>

      {/* Feature Highlight Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3rem', alignItems: 'center', marginBottom: '5rem' }}>
        <div>
          <h2 style={{ fontSize: '2rem', marginBottom: '1rem', letterSpacing: '-0.02em' }}>
            High-Conversion Bulk Messaging
          </h2>
          <p style={{ color: mutedColor, lineHeight: '1.6', marginBottom: '1.5rem' }}>
            Reach your target audience directly on their preferred chat screens. Re-engage buyers who haven't completed checkouts, push seasonal discounts, and monitor click-through conversion statistics.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Segmented Campaign Targeting:</strong> Filter contacts based on tags like "Shopify Buyer", "VIP", "Inactive Lead" to prevent span complaints and optimize cost.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>WhatsApp & LINE Template Library:</strong> Save, preview, and select pre-approved marketing templates with custom variable injection.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Open and Conversion KPIs:</strong> Monitor exact campaign progress logs representing template deliveries, reads, link clicks, and conversion purchases.
              </div>
            </div>
          </div>
        </div>

        {/* Visual Mock Campaign status card */}
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
            <Send size={16} style={{ color: 'var(--primary-color)' }} /> Active Campaign Report
          </span>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.8rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: '600' }}>
              <span>August VIP Discount Promo</span>
              <span style={{ color: 'var(--primary-color)' }}>Completed</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: mutedColor }}>
              <span>Target:</span>
              <span>VIP Customers</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: mutedColor }}>
              <span>Total Recipients:</span>
              <span>1,450 users</span>
            </div>

            <div style={{ borderTop: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, paddingTop: '0.75rem', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem', textAlign: 'center' }}>
              <div>
                <div style={{ color: 'var(--primary-color)', fontSize: '1.1rem', fontWeight: '800' }}>100%</div>
                <div style={{ fontSize: '0.65rem', color: mutedColor }}>Delivered</div>
              </div>
              <div>
                <div style={{ color: '#f59e0b', fontSize: '1.1rem', fontWeight: '800' }}>84.2%</div>
                <div style={{ fontSize: '0.65rem', color: mutedColor }}>Open Rate</div>
              </div>
              <div>
                <div style={{ color: '#10b981', fontSize: '1.1rem', fontWeight: '800' }}>12.8%</div>
                <div style={{ fontSize: '0.65rem', color: mutedColor }}>Conversion</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
