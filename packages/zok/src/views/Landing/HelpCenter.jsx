import { useState } from 'react';
import { Search, Link2, MessageSquare, ArrowRight, Settings, CreditCard, ChevronRight } from 'lucide-react';

const CATEGORIES = [
  {
    id: 'whatsapp',
    title: 'WhatsApp Business API',
    icon: <MessageSquare size={20} style={{ color: '#075e54' }} />,
    articles: [
      { id: 'wa-1', title: 'How to apply for WhatsApp Business API', content: 'Applying for the WhatsApp Business API requires a Meta Business Manager account. You need to verify your business credentials, register your phone number, and pass Meta\'s policy validation checks. Once approved, you can hook the API credentials directly inside Zok\'s integrations portal to launch shared multi-agent messaging sessions.' },
      { id: 'wa-2', title: 'Managing WhatsApp Message Templates', content: 'WhatsApp API templates are structured message layouts required for outbound marketing. Templates must be submitted to Meta for review and approval before sending. You can inject custom variables like {{customer_name}} or {{coupon_code}} to personalize bulk campaign broadcasts.' }
    ]
  },
  {
    id: 'line',
    title: 'LINE Official Account (OA)',
    icon: <Link2 size={20} style={{ color: '#00c300' }} />,
    articles: [
      { id: 'line-1', title: 'Connecting LINE Official Account to Zok', content: 'To connect your LINE OA, navigate to the LINE Developers Console and create a Channel Access Token. Copy this token along with your Channel ID, and paste them inside Zok\'s integrations menu. Zok will establish a Webhook URL that routes customer LINE queries to your unified team inbox.' },
      { id: 'line-2', title: 'Configuring LINE Rich Menus and auto-replies', content: 'LINE Rich Menus allow customers to tap visual blocks in their chat layout. You can integrate Zok\'s Flow Builder to capture rich menu events and trigger custom replies, welcome scripts, or route the chat to an active customer support queue.' }
    ]
  },
  {
    id: 'shopify',
    title: 'Shopify Sync Integration',
    icon: <Settings size={20} style={{ color: '#96bf48' }} />,
    articles: [
      { id: 'shop-1', title: 'Syncing Shopify Customer Records', content: 'Connecting your Shopify store enables live customer profiling. Zok pulls purchase histories, customer tags, and active cart details automatically. Support operators can view order status tags (Processing, Shipped, Delivered) directly in the unified conversation sidebar.' },
      { id: 'shop-2', title: 'Setting up Abandoned Checkout Alerts', content: 'Enable Shopify checkout webhooks to sync abandoned cart events. You can configure Zok\'s visual flow builder to wait for 30 minutes, verify if the cart remains uncompleted, and dispatch a WhatsApp re-engagement coupon template automatically.' }
    ]
  },
  {
    id: 'billing',
    title: 'Billing & Account Setup',
    icon: <CreditCard size={20} style={{ color: 'var(--primary-color)' }} />,
    articles: [
      { id: 'bill-1', title: 'Understanding Zok Subscription Plans', content: 'Zok offers three subscription tiers: Basic ($45/mo), Pro ($97/mo), and Advanced ($249/mo). Annual plans receive a 20% discount. Extra costs apply for raw WhatsApp API messaging units charged directly by Meta based on conversation templates.' }
    ]
  }
];

export default function HelpCenter({ isDark }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [activeCategory, setActiveCategory] = useState(null);

  const textColor = isDark ? '#fff' : '#0f172a';
  const mutedColor = isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)';
  const borderStyle = `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`;

  // Search filter
  const allArticles = CATEGORIES.flatMap(cat => cat.articles.map(art => ({ ...art, categoryTitle: cat.title })));
  const searchResults = searchQuery
    ? allArticles.filter(art => 
        art.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
        art.content.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : [];

  return (
    <div className="container" style={{ padding: '4rem 0', color: textColor, minHeight: '600px' }}>
      {/* Help Hero Banner */}
      <div style={{ textAlign: 'center', marginBottom: '3.5rem' }}>
        <h1 style={{ fontSize: '2.5rem', marginBottom: '1rem', letterSpacing: '-0.02em' }}>
          Zok Help Center
        </h1>
        <p style={{ color: mutedColor, marginBottom: '2rem' }}>
          Search guides, setting up channel APIs, and integrating e-commerce stores.
        </p>

        {/* Support Search Input */}
        <div style={{
          position: 'relative',
          maxWidth: '550px',
          margin: '0 auto'
        }}>
          <Search size={18} style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: mutedColor }} />
          <input
            type="text"
            placeholder="Search for articles (e.g. WhatsApp API, Shopify, Rich Menus)..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setSelectedArticle(null);
            }}
            style={{
              width: '100%',
              padding: '0.85rem 1rem 0.85rem 2.75rem',
              borderRadius: '30px',
              border: borderStyle,
              backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff',
              color: textColor,
              fontSize: '0.9rem',
              outline: 'none',
              boxShadow: '0 4px 20px rgba(0,0,0,0.05)'
            }}
          />
        </div>
      </div>

      {/* Main Reading/Grid Layout */}
      {selectedArticle ? (
        /* Article Reader view */
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
            ← Back to Help Guides
          </button>
          
          <span style={{ fontSize: '0.8rem', color: mutedColor, textTransform: 'uppercase', fontWeight: '700' }}>
            {selectedArticle.categoryTitle || 'Documentation'}
          </span>
          <h2 style={{ fontSize: '2.2rem', margin: '0.5rem 0 1.5rem 0', letterSpacing: '-0.02em' }}>
            {selectedArticle.title}
          </h2>
          
          <div style={{
            lineHeight: '1.7',
            fontSize: '1rem',
            color: isDark ? '#cbd5e1' : '#334155',
            backgroundColor: isDark ? 'rgba(15, 23, 42, 0.2)' : '#f8fafc',
            padding: '2rem',
            borderRadius: '16px',
            border: borderStyle
          }}>
            {selectedArticle.content}
          </div>
        </div>
      ) : searchQuery ? (
        /* Search results view */
        <div style={{ maxWidth: '750px', margin: '0 auto' }}>
          <h3 style={{ marginBottom: '1.5rem', fontSize: '1.1rem' }}>
            Search Results ({searchResults.length})
          </h3>
          {searchResults.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {searchResults.map(art => (
                <div 
                  key={art.id}
                  onClick={() => setSelectedArticle(art)}
                  style={{
                    padding: '1.25rem',
                    borderRadius: '12px',
                    border: borderStyle,
                    backgroundColor: isDark ? 'rgba(255,255,255,0.01)' : '#fff',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    boxShadow: '0 2px 10px rgba(0,0,0,0.02)'
                  }}
                  className="hover-card"
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h4 style={{ margin: 0, fontSize: '1rem', color: 'var(--primary-color)' }}>{art.title}</h4>
                    <ChevronRight size={16} style={{ color: mutedColor }} />
                  </div>
                  <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.8rem', color: mutedColor, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {art.content}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: mutedColor, textAlign: 'center', margin: '3rem 0' }}>
              No help articles found matching "{searchQuery}". Try searching general terms.
            </p>
          )}
        </div>
      ) : activeCategory ? (
        /* Active Category Articles list */
        <div style={{ maxWidth: '750px', margin: '0 auto' }}>
          <button 
            onClick={() => setActiveCategory(null)}
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
            ← Back to Help Hub
          </button>
          
          <h3 style={{ fontSize: '1.5rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            {activeCategory.icon} {activeCategory.title}
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {activeCategory.articles.map(art => (
              <div 
                key={art.id}
                onClick={() => setSelectedArticle({ ...art, categoryTitle: activeCategory.title })}
                style={{
                  padding: '1.25rem',
                  borderRadius: '12px',
                  border: borderStyle,
                  backgroundColor: isDark ? 'rgba(255,255,255,0.01)' : '#fff',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                className="hover-card"
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: '600' }}>{art.title}</h4>
                  <ChevronRight size={16} style={{ color: 'var(--primary-color)' }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        /* Main Category Portal Cards */
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '1.5rem'
        }}>
          {CATEGORIES.map(cat => (
            <div
              key={cat.id}
              onClick={() => setActiveCategory(cat)}
              style={{
                border: borderStyle,
                borderRadius: '16px',
                padding: '2rem',
                backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff',
                cursor: 'pointer',
                transition: 'all 0.2s',
                boxShadow: '0 4px 15px rgba(0, 0, 0, 0.02)'
              }}
              className="hover-card"
            >
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '8px',
                backgroundColor: isDark ? 'rgba(255,255,255,0.03)' : '#f1f5f9',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '1rem'
              }}>
                {cat.icon}
              </div>
              <h3 style={{ fontSize: '1.15rem', marginBottom: '0.5rem', fontWeight: '700' }}>{cat.title}</h3>
              <p style={{ color: mutedColor, fontSize: '0.8rem', lineHeight: '1.4' }}>
                {cat.articles.length} articles available. Learn setup guides and configuration guidelines.
              </p>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.25rem',
                color: 'var(--primary-color)',
                fontSize: '0.8rem',
                fontWeight: '600',
                marginTop: '1.25rem'
              }}>
                View Articles <ArrowRight size={12} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
