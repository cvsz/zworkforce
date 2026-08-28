import { ArrowRight, CheckCircle2, MessageSquare, Users, Tag, ShoppingBag } from 'lucide-react';

export default function ProductInbox({ onLaunchApp, isDark }) {
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
          Omnichannel Solution
        </span>
        <h1 style={{ fontSize: '3rem', margin: '1rem 0 0.5rem 0', letterSpacing: '-0.03em' }}>
          Unified Customer Inbox
        </h1>
        <p style={{ color: mutedColor, fontSize: '1.1rem', maxWidth: '650px', margin: '0 auto' }}>
          Consolidate LINE OA, WhatsApp API, Instagram DM, Facebook Messenger, Shopee, and Lazada chats into a single collaborative team workspace.
        </p>
        <button onClick={onLaunchApp} className="btn-primary" style={{ margin: '1.5rem auto 0 auto' }}>
          Launch Sandbox Inbox <ArrowRight size={16} />
        </button>
      </div>

      {/* Feature Highlight Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3rem', alignItems: 'center', marginBottom: '5rem' }}>
        <div>
          <h2 style={{ fontSize: '2rem', marginBottom: '1rem', letterSpacing: '-0.02em' }}>
            Never Switch Apps Again
          </h2>
          <p style={{ color: mutedColor, lineHeight: '1.6', marginBottom: '1.5rem' }}>
            Zok's Unified Inbox solves the pain of jumping between different seller hubs and messaging applications. Your support agents can manage Facebook comments, Instagram chats, LINE customer inquiries, and Shopee seller messages in one fluid pipeline.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Shared Agent Assignment:</strong> Distribute incoming chats dynamically among sales and support reps. Prevent double-reply collisions.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Live Shopify Syncing:</strong> Pull customer order status, shipping tracks, and cart contents directly inside the active chat view.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Custom Tags & Segmentations:</strong> Label conversations based on lead temperature, VIP status, or customer support issues.
              </div>
            </div>
          </div>
        </div>

        {/* Visual Mock Card representing Inbox Sidebar */}
        <div style={{
          backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff',
          border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`,
          borderRadius: '16px',
          padding: '1.5rem',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.1)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, paddingBottom: '1rem', marginBottom: '1rem' }}>
            <span style={{ fontWeight: '700', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <MessageSquare size={18} style={{ color: 'var(--primary-color)' }} /> Customer Profile CRM
            </span>
            <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '4px', backgroundColor: 'rgba(0, 194, 142, 0.1)', color: 'var(--primary-color)', fontWeight: '600' }}>Active</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', fontSize: '0.85rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: mutedColor }}>Customer Name:</span>
              <strong>Panacee Medical</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: mutedColor }}>Channel:</span>
              <span style={{ color: '#00c300', fontWeight: 'bold' }}>LINE OA</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: mutedColor }}>Assigned Agent:</span>
              <strong style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}><Users size={12} /> Sarah Connor</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: mutedColor }}>Tags:</span>
              <div style={{ display: 'flex', gap: '0.35rem' }}>
                <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.4rem', borderRadius: '4px', backgroundColor: isDark ? 'rgba(255, 255, 255, 0.05)' : '#f1f5f9' }}><Tag size={10} style={{ marginRight: '0.2rem' }} /> VIP</span>
                <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.4rem', borderRadius: '4px', backgroundColor: 'rgba(0, 194, 142, 0.1)', color: 'var(--primary-color)' }}>LINE OA</span>
              </div>
            </div>
            
            <div style={{ borderTop: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, paddingTop: '1rem', marginTop: '0.5rem' }}>
              <span style={{ fontWeight: '700', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem', marginBottom: '0.75rem' }}>
                <ShoppingBag size={14} style={{ color: 'var(--primary-color)' }} /> Shopify Order History
              </span>
              <div style={{ padding: '0.75rem', borderRadius: '8px', backgroundColor: isDark ? 'rgba(255, 255, 255, 0.02)' : '#f8fafc', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: '600', marginBottom: '0.25rem' }}>
                  <span>ORD-8812</span>
                  <span style={{ color: '#10b981' }}>Delivered</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: mutedColor }}>
                  <span>Aug 01, 2026</span>
                  <span>$149.00</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
