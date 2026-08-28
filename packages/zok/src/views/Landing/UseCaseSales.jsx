import { ArrowRight, ShoppingBag, CheckCircle2, TrendingUp, DollarSign } from 'lucide-react';

export default function UseCaseSales({ onLaunchApp, isDark }) {
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
          Zok for Conversational Sales
        </h1>
        <p style={{ color: mutedColor, fontSize: '1.1rem', maxWidth: '650px', margin: '0 auto' }}>
          Drive conversions directly on chat apps. Sync with Shopify to share custom product catalog cards and capture orders instantly inside the chat screen.
        </p>
        <button onClick={onLaunchApp} className="btn-primary" style={{ margin: '1.5rem auto 0 auto' }}>
          Open Sales CRM Sandbox <ArrowRight size={16} />
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3rem', alignItems: 'center', marginBottom: '5rem' }}>
        {/* Sales Stats Box */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div style={{ backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, borderRadius: '12px', padding: '1.5rem', gridColumn: 'span 2', display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: '50%', backgroundColor: 'rgba(0,194,142,0.1)', color: 'var(--primary-color)', display: 'flex', alignItems: 'center', justify: 'center', flexShrink: 0 }}>
              <DollarSign size={24} />
            </div>
            <div>
              <div style={{ fontSize: '1.6rem', fontWeight: '800' }}>$4,890.00</div>
              <div style={{ fontSize: '0.8rem', color: mutedColor }}>Conversational Sales Revenue (Today)</div>
            </div>
          </div>

          <div style={{ backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, borderRadius: '12px', padding: '1.25rem' }}>
            <TrendingUp size={20} style={{ color: 'var(--primary-color)', marginBottom: '0.5rem' }} />
            <div style={{ fontSize: '1.5rem', fontWeight: '800' }}>28.5%</div>
            <div style={{ fontSize: '0.75rem', color: mutedColor }}>Abandoned Cart Recovery Rate</div>
          </div>

          <div style={{ backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, borderRadius: '12px', padding: '1.25rem' }}>
            <ShoppingBag size={20} style={{ color: 'var(--primary-color)', marginBottom: '0.5rem' }} />
            <div style={{ fontSize: '1.5rem', fontWeight: '800' }}>4,120</div>
            <div style={{ fontSize: '0.75rem', color: mutedColor }}>Shopify orders synced this month</div>
          </div>
        </div>

        <div>
          <h2 style={{ fontSize: '2rem', marginBottom: '1rem', letterSpacing: '-0.02em' }}>
            Convert Social Chat Leads to Completed Orders
          </h2>
          <p style={{ color: mutedColor, lineHeight: '1.6', marginBottom: '1.5rem' }}>
            Social commerce buyers expect instant answers. With Zok's e-commerce integrations, your sales reps can generate direct cart links, process loyalty points, and recovery abandoned carts without making customers open another app.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Shopify Inventory Catalog Sync:</strong> Search for store items and share rich image-card snippets directly inside LINE or WhatsApp threads.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>One-Click Checkout Links:</strong> Pre-fill cart coordinates for buyers so they only need to tap once to complete credit card payments.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Abandoned Cart Followups:</strong> Automatically queue messages on WhatsApp when a user exits checkout before completing their purchase.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
