import { useState } from 'react';
import { Calendar, Clock, ArrowRight, User } from 'lucide-react';

const ARTICLES = [
  {
    id: 'blog-1',
    title: 'How to Sell More on LINE OA using AI Chatbots',
    category: 'Guides',
    date: 'Aug 05, 2026',
    readTime: '5 min read',
    author: 'Arm Patinyasakdikul',
    imageText: 'AI & LINE OA',
    summary: 'Discover how online sellers use visual flows to automate responses, handle customer frequently asked questions, sync catalogs, and drive higher checkouts on LINE OA.',
    content: 'LINE Official Account (OA) has become the backbone of social commerce in Thailand and broader Southeast Asia. However, scaling human support to handle thousands of daily chat queries is impossible without automation. By connecting your LINE OA with Zok\'s Conversational AI chatbot, you can handle 80% of routine customer questions (such as shipping details, product returns, and clinic hours) instantly. Furthermore, syncing Shopify product catalog coordinates inside LINE threads allows customers to select accessories and checkout without leaving the chat app, leading to a 3x increase in checkout rates.'
  },
  {
    id: 'blog-2',
    title: '5 Shopify Marketing Tips for Southeast Asia in 2026',
    category: 'Marketing',
    date: 'Jul 28, 2026',
    readTime: '7 min read',
    author: 'Sarah Connor',
    imageText: 'Shopify Sales',
    summary: 'Increase your store conversions using target broadcasts, abandoned cart recovery alerts, and unified CRM databases.',
    content: 'E-commerce in Southeast Asia is highly conversational. Unlike Western markets where customers checkout silently via web links, Asian buyers prefer chat validation before purchasing. To scale your Shopify store conversions, implement these 5 tips: 1. Launch high open-rate WhatsApp broadcasts for seasonal promos. 2. Automate re-engagement checkouts on WhatsApp for abandoned carts. 3. Tag users by lead interest. 4. Allow multi-agent login to distribute incoming inquiries. 5. Sync your stock inventory list dynamically to prevent double-booking.'
  },
  {
    id: 'blog-3',
    title: 'Introducing Zok AI Agent 2.0: Knowledge Training',
    category: 'Product News',
    date: 'Jul 15, 2026',
    readTime: '4 min read',
    author: 'Wilfried Buiron',
    imageText: 'AI Agent 2.0',
    summary: 'Train your chatbot assistant using custom PDF documents, webpage links, or spreadsheets. Empower bots to handle CRM order queries.',
    content: 'Today we are excited to roll out Zok AI Agent 2.0. This release makes chatbot training simpler than ever. Instead of writing complex regex keyword templates, developers can now drag and drop PDF store guidelines, enter help center documentation links, or upload QA Excel grids. The AI Agent parses text structures, builds context matrices, and responds to customer chat requests in friendly, context-rich prose. AI Agent 2.0 is fully available for connection across LINE OA, WhatsApp Business API, and website live chat widgets.'
  }
];

export default function Blog({ isDark }) {
  const [selectedArticle, setSelectedArticle] = useState(null);

  const textColor = isDark ? '#fff' : '#0f172a';
  const mutedColor = isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)';
  const borderStyle = `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`;

  return (
    <div className="container" style={{ padding: '4rem 0', color: textColor, minHeight: '600px' }}>
      {selectedArticle ? (
        /* Blog Article Reader Screen */
        <div style={{ maxWidth: '750px', margin: '0 auto' }}>
          <button 
            onClick={() => setSelectedArticle(null)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--primary-color)',
              fontWeight: '600',
              cursor: 'pointer',
              marginBottom: '1.5rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem',
              fontSize: '0.9rem'
            }}
          >
            ← Back to Blog Articles
          </button>
          
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', fontSize: '0.8rem', color: mutedColor, marginBottom: '0.5rem' }}>
            <span style={{ color: 'var(--primary-color)', fontWeight: '700', textTransform: 'uppercase' }}>{selectedArticle.category}</span>
            <span>•</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}><Calendar size={12} /> {selectedArticle.date}</span>
            <span>•</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}><Clock size={12} /> {selectedArticle.readTime}</span>
          </div>

          <h2 style={{ fontSize: '2.5rem', margin: '0.5rem 0 1.5rem 0', letterSpacing: '-0.02em', lineHeight: '1.2' }}>
            {selectedArticle.title}
          </h2>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '2rem' }}>
            <div style={{ width: '28px', height: '28px', borderRadius: '50%', backgroundColor: 'rgba(0,194,142,0.1)', color: 'var(--primary-color)', display: 'flex', alignItems: 'center', justify: 'center' }}>
              <User size={14} />
            </div>
            <span style={{ fontSize: '0.85rem', fontWeight: '600' }}>By {selectedArticle.author}</span>
          </div>

          <div style={{
            lineHeight: '1.8',
            fontSize: '1.05rem',
            color: isDark ? '#cbd5e1' : '#334155'
          }}>
            <p style={{ whiteSpace: 'pre-wrap' }}>
              {selectedArticle.content}
            </p>
          </div>
        </div>
      ) : (
        /* Blog grid listing view */
        <div>
          <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
            <h1 style={{ fontSize: '2.5rem', marginBottom: '1rem', letterSpacing: '-0.02em' }}>
              The Zok Blog
            </h1>
            <p style={{ color: mutedColor }}>
              Insights, tutorials, and strategy guides to optimize social selling and conversational AI.
            </p>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '2rem'
          }}>
            {ARTICLES.map(art => (
              <div
                key={art.id}
                onClick={() => setSelectedArticle(art)}
                style={{
                  border: borderStyle,
                  borderRadius: '16px',
                  overflow: 'hidden',
                  backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  display: 'flex',
                  flexDirection: 'column',
                  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.02)'
                }}
                className="hover-card"
              >
                {/* Visual placeholder graphic block */}
                <div style={{
                  height: '160px',
                  backgroundColor: isDark ? 'rgba(255,255,255,0.02)' : '#f1f5f9',
                  borderBottom: borderStyle,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: '800',
                  color: 'var(--primary-color)',
                  fontSize: '1.25rem'
                }}>
                  {art.imageText}
                </div>

                <div style={{ padding: '1.5rem', flex: 1, display: 'flex', flexDirection: 'column' }}>
                  <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', fontSize: '0.75rem', color: mutedColor, marginBottom: '0.5rem' }}>
                    <span style={{ color: 'var(--primary-color)', fontWeight: '700' }}>{art.category}</span>
                    <span>•</span>
                    <span>{art.readTime}</span>
                  </div>
                  
                  <h3 style={{ fontSize: '1.15rem', marginBottom: '0.75rem', fontWeight: '700', lineHeight: '1.3' }}>
                    {art.title}
                  </h3>
                  
                  <p style={{ color: mutedColor, fontSize: '0.8rem', lineHeight: '1.5', marginBottom: '1.25rem' }}>
                    {art.summary}
                  </p>

                  <div style={{
                    marginTop: 'auto',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.25rem',
                    color: 'var(--primary-color)',
                    fontSize: '0.8rem',
                    fontWeight: '600'
                  }}>
                    Read Article <ArrowRight size={12} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
