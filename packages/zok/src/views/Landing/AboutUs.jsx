import { CheckCircle2, Heart, Users, Globe } from 'lucide-react';

export default function AboutUs({ isDark }) {
  const textColor = isDark ? '#fff' : '#0f172a';
  const mutedColor = isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)';
  
  return (
    <div className="container" style={{ padding: '4rem 0', color: textColor }}>
      {/* Vision Hero Banner */}
      <div style={{ textAlign: 'center', marginBottom: '5rem' }}>
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
          Our Story
        </span>
        <h1 style={{ fontSize: '3rem', margin: '1rem 0 0.5rem 0', letterSpacing: '-0.03em' }}>
          Empowering Social Commerce
        </h1>
        <p style={{ color: mutedColor, fontSize: '1.1rem', maxWidth: '650px', margin: '0 auto' }}>
          We build conversational AI software to help e-commerce brands, sellers, and teams in Southeast Asia manage customer support, campaigns, and order syncs.
        </p>
      </div>

      {/* Metrics Counter Dashboard */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '2rem',
        marginBottom: '6rem',
        textAlign: 'center'
      }}>
        <div style={{ padding: '1.5rem', borderRadius: '16px', backgroundColor: isDark ? 'rgba(255,255,255,0.01)' : '#f8fafc', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}` }}>
          <Users size={28} style={{ color: 'var(--primary-color)', margin: '0 auto 0.75rem auto' }} />
          <div style={{ fontSize: '2rem', fontWeight: '800' }}>20,000+</div>
          <div style={{ fontSize: '0.8rem', color: mutedColor }}>Connected E-Commerce Brands</div>
        </div>

        <div style={{ padding: '1.5rem', borderRadius: '16px', backgroundColor: isDark ? 'rgba(255,255,255,0.01)' : '#f8fafc', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}` }}>
          <Globe size={28} style={{ color: 'var(--primary-color)', margin: '0 auto 0.75rem auto' }} />
          <div style={{ fontSize: '2rem', fontWeight: '800' }}>5+ Countries</div>
          <div style={{ fontSize: '0.8rem', color: mutedColor }}>Southeast Asia Focus</div>
        </div>

        <div style={{ padding: '1.5rem', borderRadius: '16px', backgroundColor: isDark ? 'rgba(255,255,255,0.01)' : '#f8fafc', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}` }}>
          <Heart size={28} style={{ color: 'var(--primary-color)', margin: '0 auto 0.75rem auto' }} />
          <div style={{ fontSize: '2rem', fontWeight: '800' }}>1.5M+ Chats</div>
          <div style={{ fontSize: '0.8rem', color: mutedColor }}>Automated and Synced Weekly</div>
        </div>
      </div>

      {/* Core Values / Team Mission */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3rem', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '2rem', marginBottom: '1.25rem', letterSpacing: '-0.02em' }}>
            Why We Build Zok
          </h2>
          <p style={{ color: mutedColor, lineHeight: '1.6', marginBottom: '1.5rem' }}>
            Social selling is the standard in Southeast Asia. Customers do not check out from links; they check out after a conversation. We believe that empowering businesses with conversational AI tools bridges the gap between customer engagement and order conversions.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Chat-First DNA:</strong> We prioritize messaging workflows (WhatsApp, LINE OA) before email or traditional websites.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Customer Centricity:</strong> We simplify multi-agent assignment so that clients always receive fast answers.
              </div>
            </div>
          </div>
        </div>

        <div style={{
          backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff',
          border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`,
          borderRadius: '16px',
          padding: '2rem',
          boxShadow: '0 10px 30px rgba(0, 0, 0, 0.05)'
        }}>
          <h3 style={{ fontSize: '1.25rem', marginBottom: '1rem', fontWeight: '700' }}>Our Leadership Philosophy</h3>
          <p style={{ color: mutedColor, fontSize: '0.85rem', lineHeight: '1.6', marginBottom: '1rem' }}>
            "We believe conversational commerce is the future of online sales in Southeast Asia. Our platform removes the complexity of managing multiple messaging channels, enabling merchant brands to scale operations with intelligent automations and shared-agent workspaces."
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '50%', backgroundColor: 'rgba(0,194,142,0.1)', color: 'var(--primary-color)', display: 'flex', alignItems: 'center', justify: 'center', fontWeight: 'bold' }}>
              ZK
            </div>
            <div>
              <div style={{ fontSize: '0.85rem', fontWeight: '700' }}>Arm Patinyasakdikul</div>
              <div style={{ fontSize: '0.75rem', color: mutedColor }}>Founder & CEO, Zok</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
