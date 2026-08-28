import { useEffect, useState } from 'react';
import { 
  Bot, ArrowRight, ShieldCheck, CheckCircle2, UserCheck, RefreshCw, Sun, Moon 
} from 'lucide-react';
import ProductInbox from './Landing/ProductInbox';
import ProductAutomations from './Landing/ProductAutomations';
import ProductAnalytics from './Landing/ProductAnalytics';
import ProductAIAgent from './Landing/ProductAIAgent';
import ProductBroadcast from './Landing/ProductBroadcast';
import UseCaseSupport from './Landing/UseCaseSupport';
import UseCaseSales from './Landing/UseCaseSales';
import UseCaseMarketing from './Landing/UseCaseMarketing';
import HelpCenter from './Landing/HelpCenter';
import Blog from './Landing/Blog';
import AboutUs from './Landing/AboutUs';
import Register from './Landing/Register';
import Login from './Landing/Login';

const CHANNELS = [
  { name: 'WhatsApp', color: '#25d366' },
  { name: 'LINE Official Account', color: '#06c15f' },
  { name: 'Facebook Messenger', color: '#0084ff' },
  { name: 'Instagram Direct', color: '#e1306c' },
  { name: 'TikTok Shop', color: '#ffffff' },
  { name: 'Shopify Checkout', color: '#95be31' },
  { name: 'Shopee CRM', color: '#ff5722' },
  { name: 'Lazada Inbox', color: '#000080' }
];

export default function LandingPage({ onLaunchApp, isDark, onToggleTheme }) {
  const [activeTab, setActiveTab] = useState('inbox');
  const [billingPeriod, setBillingPeriod] = useState('annual');
  const [landingSubView, setLandingSubView] = useState('home');
  const [productDropdownOpen, setProductDropdownOpen] = useState(false);
  const [useCaseDropdownOpen, setUseCaseDropdownOpen] = useState(false);

  useEffect(() => {
    const handleLoginRequired = () => setLandingSubView('login');
    window.addEventListener('zok:login-required', handleLoginRequired);
    return () => window.removeEventListener('zok:login-required', handleLoginRequired);
  }, []);

  const renderLandingSubView = () => {
    switch (landingSubView) {
      case 'product-inbox':
        return <ProductInbox onLaunchApp={onLaunchApp} isDark={isDark} />;
      case 'product-automations':
        return <ProductAutomations onLaunchApp={onLaunchApp} isDark={isDark} />;
      case 'product-analytics':
        return <ProductAnalytics onLaunchApp={onLaunchApp} isDark={isDark} />;
      case 'product-ai-agent':
        return <ProductAIAgent onLaunchApp={onLaunchApp} isDark={isDark} />;
      case 'product-broadcast':
        return <ProductBroadcast onLaunchApp={onLaunchApp} isDark={isDark} />;
      case 'usecase-support':
        return <UseCaseSupport onLaunchApp={onLaunchApp} isDark={isDark} />;
      case 'usecase-sales':
        return <UseCaseSales onLaunchApp={onLaunchApp} isDark={isDark} />;
      case 'usecase-marketing':
        return <UseCaseMarketing onLaunchApp={onLaunchApp} isDark={isDark} />;
      case 'help-center':
        return <HelpCenter isDark={isDark} />;
      case 'blog':
        return <Blog isDark={isDark} />;
      case 'about-us':
        return <AboutUs isDark={isDark} />;
      case 'register':
        return <Register onSwitchToLogin={() => setLandingSubView('login')} isDark={isDark} />;
      case 'login':
        return <Login onSwitchToRegister={() => setLandingSubView('register')} onLaunchApp={onLaunchApp} isDark={isDark} />;
      default:
        return null;
    }
  };

  const tabContent = {
    inbox: {
      tag: 'HELPDESK',
      title: 'One inbox, all your customer conversations',
      desc: 'Centralize conversations from WhatsApp, Facebook, Instagram, LINE OA, TikTok Shop, Shopee, Lazada, and email into one powerful, collaborative inbox dashboard. Assign chats to operators and tag customers based on behavior.',
      visual: (
        <div style={{
          backgroundColor: '#070b19',
          border: '1px solid rgba(255,255,255,0.05)',
          borderRadius: '12px',
          padding: '1.25rem',
          color: '#e2e8f0',
          fontFamily: 'sans-serif'
        }}>
          {/* Mock Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '0.75rem', marginBottom: '0.75rem' }}>
            <span style={{ fontWeight: '600', fontSize: '0.85rem' }}>Unified Inbox • Zok</span>
            <span style={{ fontSize: '0.7rem', color: '#10b981' }}>● Live Channel Sync</span>
          </div>
          {/* Mock chats */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ backgroundColor: 'rgba(0, 194, 142, 0.1)', padding: '0.5rem', borderRadius: '6px', fontSize: '0.8rem', borderLeft: '3px solid var(--primary-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: '600' }}>
                <span>Panacee Medical Centre</span>
                <span style={{ color: '#06c15f', fontSize: '0.7rem' }}>LINE OA</span>
              </div>
              <div style={{ color: '#94a3b8', fontSize: '0.75rem', marginTop: '0.2rem' }}>Hi, is there a doctor available tomorrow?</div>
            </div>
            <div style={{ backgroundColor: '#0f172a', padding: '0.5rem', borderRadius: '6px', fontSize: '0.8rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: '600' }}>
                <span>Karmart Customer Care</span>
                <span style={{ color: '#25d366', fontSize: '0.7rem' }}>WhatsApp</span>
              </div>
              <div style={{ color: '#94a3b8', fontSize: '0.75rem', marginTop: '0.2rem' }}>Sure, I will dispatch the tracking code #9811.</div>
            </div>
          </div>
        </div>
      )
    },
    agent: {
      tag: 'AUTOMATION',
      title: 'AI Sales Agents, Active 24/7',
      desc: 'Set up an AI-powered conversational sales assistant trained on your custom store data. Automatically reply to common FAQ questions, route leads, and secure Shopify cart orders even while your staff is offline.',
      visual: (
        <div style={{
          backgroundColor: '#070b19',
          border: '1px solid rgba(255,255,255,0.05)',
          borderRadius: '12px',
          padding: '1.25rem',
          color: '#e2e8f0',
          fontFamily: 'sans-serif'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <Bot size={16} style={{ color: 'var(--primary-color)' }} />
            <span style={{ fontWeight: '600', fontSize: '0.85rem' }}>AI Agent Sandbox Simulator</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.75rem' }}>
            <div style={{ alignSelf: 'flex-start', backgroundColor: '#1e293b', padding: '0.4rem 0.6rem', borderRadius: '8px' }}>
              Do you offer free delivery?
            </div>
            <div style={{ alignSelf: 'flex-end', backgroundColor: 'var(--primary-color)', padding: '0.4rem 0.6rem', borderRadius: '8px' }}>
              ✨ [Sales Bot] Yes! We offer free shipping on all orders over $100. Let us know if you have other questions!
            </div>
          </div>
        </div>
      )
    },
    flow: {
      tag: 'CHATBOTS',
      title: 'No-Code Visual Chat Flow Builder',
      desc: 'Create highly engaging customized responses and branching customer logic using our drag-and-drop flow builder. Auto-trigger steps when keywords are matched, or query Shopify to verify customer orders.',
      visual: (
        <div style={{
          backgroundColor: '#070b19',
          border: '1px solid rgba(255,255,255,0.05)',
          borderRadius: '12px',
          padding: '1.25rem',
          color: '#e2e8f0',
          fontFamily: 'sans-serif',
          position: 'relative'
        }}>
          <div style={{ fontSize: '0.85rem', fontWeight: '600', marginBottom: '0.75rem' }}>Flow Builder Canvas</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', justifyContent: 'center' }}>
            <div style={{ border: '1px solid #eab308', padding: '0.35rem 0.5rem', borderRadius: '6px', fontSize: '0.7rem', backgroundColor: 'rgba(234,179,8,0.1)' }}>
              Keyword Match
            </div>
            <ArrowRight size={14} style={{ color: '#64748b' }} />
            <div style={{ border: '1px solid #3b82f6', padding: '0.35rem 0.5rem', borderRadius: '6px', fontSize: '0.7rem', backgroundColor: 'rgba(59,130,246,0.1)' }}>
              Send Coupon Code
            </div>
          </div>
        </div>
      )
    },
    campaign: {
      tag: 'MARKETING',
      title: 'Target smarter, sell more with Broadcasts',
      desc: 'Send targeted broadcast templates to specific customer cohorts matching tags like "Abandon Cart" or "VIP Buyer" on WhatsApp and LINE OA. Analyze delivery rates, read rates, and checkout conversion rates.',
      visual: (
        <div style={{
          backgroundColor: '#070b19',
          border: '1px solid rgba(255,255,255,0.05)',
          borderRadius: '12px',
          padding: '1.25rem',
          color: '#e2e8f0',
          fontFamily: 'sans-serif'
        }}>
          <div style={{ fontSize: '0.85rem', fontWeight: '600', marginBottom: '0.5rem' }}>VIP Promo Broadcast Campaign</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '0.25rem', color: '#94a3b8' }}>
            <span>Delivered count</span>
            <span style={{ color: '#fff', fontWeight: '600' }}>1,450 users (100%)</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '0.25rem', color: '#94a3b8' }}>
            <span>Open rate</span>
            <span style={{ color: '#10b981', fontWeight: '600' }}>84.2%</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#94a3b8' }}>
            <span>Conversions</span>
            <span style={{ color: 'var(--primary-color)', fontWeight: '600' }}>12.8%</span>
          </div>
        </div>
      )
    }
  };

  return (
    <div className="gradient-bg" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      
      {/* Landing Navbar */}
      <header style={{
        height: '75px',
        borderBottom: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 2rem',
        position: 'sticky',
        top: 0,
        backdropFilter: 'blur(12px)',
        backgroundColor: isDark ? 'rgba(7, 11, 25, 0.8)' : 'rgba(248, 250, 252, 0.8)',
        zIndex: 100,
        transition: 'all var(--transition-normal)'
      }}>
        <div 
          onClick={() => { setLandingSubView('home'); setProductDropdownOpen(false); setUseCaseDropdownOpen(false); }}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}
        >
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '6px',
            backgroundColor: 'var(--primary-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: '900',
            fontSize: '1.2rem'
          }}>
            Z
          </div>
          <span style={{ fontFamily: 'var(--font-heading)', fontWeight: '800', fontSize: '1.3rem', letterSpacing: '-0.03em' }}>
            zok<span style={{ color: 'var(--primary-color)' }}>.clone</span>
          </span>
        </div>

        <nav style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', fontSize: '0.9rem', fontWeight: '500', position: 'relative' }}>
          {/* Products Dropdown */}
          <div style={{ position: 'relative' }}>
            <button 
              onClick={() => { setProductDropdownOpen(!productDropdownOpen); setUseCaseDropdownOpen(false); }}
              style={{ background: 'transparent', border: 'none', color: 'inherit', fontSize: '0.9rem', fontWeight: '500', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
            >
              Products {productDropdownOpen ? '▴' : '▾'}
            </button>
            {productDropdownOpen && (
              <div style={{
                position: 'absolute',
                top: '100%',
                left: '50%',
                transform: 'translateX(-50%)',
                marginTop: '0.75rem',
                backgroundColor: isDark ? '#1e293b' : '#fff',
                border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`,
                borderRadius: '12px',
                padding: '0.5rem',
                width: '180px',
                zIndex: 100,
                display: 'flex',
                flexDirection: 'column',
                gap: '0.25rem',
                boxShadow: '0 10px 25px rgba(0,0,0,0.1)'
              }}>
                <button onClick={() => { setLandingSubView('product-inbox'); setProductDropdownOpen(false); }} className="dropdown-item">Unified Inbox</button>
                <button onClick={() => { setLandingSubView('product-automations'); setProductDropdownOpen(false); }} className="dropdown-item">Flow Builder</button>
                <button onClick={() => { setLandingSubView('product-ai-agent'); setProductDropdownOpen(false); }} className="dropdown-item">AI Agent</button>
                <button onClick={() => { setLandingSubView('product-broadcast'); setProductDropdownOpen(false); }} className="dropdown-item">Broadcasts</button>
                <button onClick={() => { setLandingSubView('product-analytics'); setProductDropdownOpen(false); }} className="dropdown-item">Analytics</button>
              </div>
            )}
          </div>

          {/* Use Cases Dropdown */}
          <div style={{ position: 'relative' }}>
            <button 
              onClick={() => { setUseCaseDropdownOpen(!useCaseDropdownOpen); setProductDropdownOpen(false); }}
              style={{ background: 'transparent', border: 'none', color: 'inherit', fontSize: '0.9rem', fontWeight: '500', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
            >
              Use Cases {useCaseDropdownOpen ? '▴' : '▾'}
            </button>
            {useCaseDropdownOpen && (
              <div style={{
                position: 'absolute',
                top: '100%',
                left: '50%',
                transform: 'translateX(-50%)',
                marginTop: '0.75rem',
                backgroundColor: isDark ? '#1e293b' : '#fff',
                border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`,
                borderRadius: '12px',
                padding: '0.5rem',
                width: '180px',
                zIndex: 100,
                display: 'flex',
                flexDirection: 'column',
                gap: '0.25rem',
                boxShadow: '0 10px 25px rgba(0,0,0,0.1)'
              }}>
                <button onClick={() => { setLandingSubView('usecase-support'); setUseCaseDropdownOpen(false); }} className="dropdown-item">Customer Support</button>
                <button onClick={() => { setLandingSubView('usecase-sales'); setUseCaseDropdownOpen(false); }} className="dropdown-item">Sales & Conversion</button>
                <button onClick={() => { setLandingSubView('usecase-marketing'); setUseCaseDropdownOpen(false); }} className="dropdown-item">Marketing campaigns</button>
              </div>
            )}
          </div>

          <button 
            onClick={() => { setLandingSubView('help-center'); setProductDropdownOpen(false); setUseCaseDropdownOpen(false); }}
            style={{ background: 'transparent', border: 'none', color: 'inherit', fontSize: '0.9rem', fontWeight: '500', cursor: 'pointer' }}
          >
            Help Center
          </button>

          <button 
            onClick={() => { setLandingSubView('blog'); setProductDropdownOpen(false); setUseCaseDropdownOpen(false); }}
            style={{ background: 'transparent', border: 'none', color: 'inherit', fontSize: '0.9rem', fontWeight: '500', cursor: 'pointer' }}
          >
            Blog
          </button>

          <button 
            onClick={() => { setLandingSubView('about-us'); setProductDropdownOpen(false); setUseCaseDropdownOpen(false); }}
            style={{ background: 'transparent', border: 'none', color: 'inherit', fontSize: '0.9rem', fontWeight: '500', cursor: 'pointer' }}
          >
            About Us
          </button>

          <button 
            onClick={onToggleTheme}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'inherit',
              display: 'flex',
              alignItems: 'center',
              padding: '0.2rem'
            }}
          >
            {isDark ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <button 
            onClick={() => { setLandingSubView('login'); setProductDropdownOpen(false); setUseCaseDropdownOpen(false); }}
            style={{ background: 'transparent', border: 'none', color: 'inherit', fontSize: '0.9rem', fontWeight: '600', cursor: 'pointer' }}
          >
            Login
          </button>
          
          <button 
            onClick={() => { setLandingSubView('register'); setProductDropdownOpen(false); setUseCaseDropdownOpen(false); }}
            style={{
              backgroundColor: 'rgba(0, 194, 142, 0.1)',
              color: 'var(--primary-color)',
              border: '1px solid var(--primary-color)',
              borderRadius: '8px',
              padding: '0.5rem 1rem',
              fontWeight: '600',
              cursor: 'pointer',
              fontSize: '0.85rem'
            }}
          >
            Register
          </button>

          <button 
            onClick={onLaunchApp}
            className="btn-primary"
            style={{ padding: '0.5rem 1.25rem', fontSize: '0.85rem' }}
          >
            Sandbox Web App
            <ArrowRight size={14} />
          </button>
        </nav>
      </header>

      {/* Hero Section */}
      <section style={{ padding: '5rem 0 3rem 0', textAlign: 'center' }}>
        <div className="container" style={{ maxWidth: '800px' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            backgroundColor: 'rgba(0, 194, 142, 0.1)',
            color: 'var(--primary-hover)',
            padding: '0.35rem 0.85rem',
            borderRadius: '20px',
            fontSize: '0.8rem',
            fontWeight: '600',
            marginBottom: '1.5rem',
            fontFamily: 'var(--font-heading)'
          }}>
            <Bot size={14} />
            ALL-IN-ONE CONVERSATIONAL AI FOR COMMERCE
          </div>

          <h1 style={{
            fontSize: '3.5rem',
            lineHeight: '1.15',
            fontWeight: '800',
            marginBottom: '1.5rem',
            fontFamily: 'var(--font-heading)',
            letterSpacing: '-0.04em'
          }}>
            Redefine Your Customer Experience With <span className="gradient-text">AI Agents</span>
          </h1>

          <p style={{
            fontSize: '1.15rem',
            color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)',
            lineHeight: '1.6',
            marginBottom: '2.5rem',
            maxWidth: '640px',
            marginRight: 'auto',
            marginLeft: 'auto'
          }}>
            Automate customer service with an intelligent AI agent, qualify leads automatically, and manage every conversation from one powerful inbox.
          </p>

          <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem' }}>
            <button onClick={onLaunchApp} className="btn-primary" style={{ padding: '0.9rem 2rem', fontSize: '1rem' }}>
              Get Started Free
              <ArrowRight size={16} />
            </button>
            <a href="#features" className="btn-secondary" style={{ padding: '0.9rem 2rem', fontSize: '1rem' }}>
              Explore Features
            </a>
          </div>
        </div>
      </section>

      {/* Infinite Horizontal Channel Marquee */}
      <section style={{ margin: '2rem 0' }}>
        <div className="marquee-wrapper">
          <div className="marquee-content">
            {CHANNELS.concat(CHANNELS).map((chan, index) => (
              <span key={index} className="marquee-item">
                <span style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: chan.color,
                  display: 'inline-block'
                }}></span>
                {chan.name}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Interactive Tabs Section */}
      <section id="features" style={{ padding: '5rem 0' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <h2 style={{ fontSize: '2.2rem', marginBottom: '0.5rem', letterSpacing: '-0.03em' }}>
              Streamlined Tools Built For Scale
            </h2>
            <p style={{ color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', fontSize: '0.95rem' }}>
              Manage chats, trigger automation templates, and sync e-commerce databases.
            </p>
          </div>

          {/* Navigation Tabs */}
          <div className="feature-tabs-nav">
            <button
              onClick={() => setActiveTab('inbox')}
              className={`feature-tab-btn ${activeTab === 'inbox' ? 'active' : ''}`}
            >
              Unified Inbox
            </button>
            <button
              onClick={() => setActiveTab('agent')}
              className={`feature-tab-btn ${activeTab === 'agent' ? 'active' : ''}`}
            >
              AI Agents Studio
            </button>
            <button
              onClick={() => setActiveTab('flow')}
              className={`feature-tab-btn ${activeTab === 'flow' ? 'active' : ''}`}
            >
              Visual Flow Builder
            </button>
            <button
              onClick={() => setActiveTab('campaign')}
              className={`feature-tab-btn ${activeTab === 'campaign' ? 'active' : ''}`}
            >
              Broadcast Campaigns
            </button>
          </div>

          {/* Tab active content card */}
          <div className="glass-card" style={{
            maxWidth: '900px',
            margin: '0 auto',
            padding: '2.5rem',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '3rem',
            alignItems: 'center'
          }}>
            <div>
              <span style={{
                color: 'var(--primary-color)',
                fontSize: '0.75rem',
                fontWeight: '700',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                display: 'block',
                marginBottom: '0.75rem'
              }}>
                {tabContent[activeTab].tag}
              </span>
              <h3 style={{ fontSize: '1.6rem', marginBottom: '1rem', lineHeight: '1.25' }}>
                {tabContent[activeTab].title}
              </h3>
              <p style={{
                fontSize: '0.95rem',
                color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)',
                lineHeight: '1.6',
                marginBottom: '1.5rem'
              }}>
                {tabContent[activeTab].desc}
              </p>
              <button onClick={onLaunchApp} style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--primary-color)',
                fontWeight: '600',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.25rem',
                fontSize: '0.9rem'
              }}>
                Launch interactive App View
                <ArrowRight size={14} />
              </button>
            </div>
            <div>
              {tabContent[activeTab].visual}
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Plans Section */}
      <section id="pricing" style={{ padding: '5rem 0' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <h2 style={{ fontSize: '2.2rem', marginBottom: '0.5rem', letterSpacing: '-0.03em' }}>
              Simple, Transparent Pricing
            </h2>
            <p style={{ color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', fontSize: '0.95rem', marginBottom: '1.5rem' }}>
              Choose a plan that fits your business scale. All plans include a 7-day free trial.
            </p>
            
            {/* Billing Period Selector */}
            <div style={{ display: 'inline-flex', backgroundColor: isDark ? 'rgba(255, 255, 255, 0.05)' : '#e2e8f0', padding: '0.25rem', borderRadius: '30px' }}>
              <button
                onClick={() => setBillingPeriod('monthly')}
                style={{
                  border: 'none',
                  borderRadius: '20px',
                  padding: '0.5rem 1.25rem',
                  fontSize: '0.85rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                  backgroundColor: billingPeriod === 'monthly' ? 'var(--primary-color)' : 'transparent',
                  color: billingPeriod === 'monthly' ? '#fff' : (isDark ? '#94a3b8' : '#64748b'),
                  transition: 'all var(--transition-fast)'
                }}
              >
                Monthly
              </button>
              <button
                onClick={() => setBillingPeriod('annual')}
                style={{
                  border: 'none',
                  borderRadius: '20px',
                  padding: '0.5rem 1.25rem',
                  fontSize: '0.85rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                  backgroundColor: billingPeriod === 'annual' ? 'var(--primary-color)' : 'transparent',
                  color: billingPeriod === 'annual' ? '#fff' : (isDark ? '#94a3b8' : '#64748b'),
                  transition: 'all var(--transition-fast)'
                }}
              >
                Annually (Save 20%)
              </button>
            </div>
          </div>

          {/* Pricing Cards Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '2rem', maxWidth: '1000px', margin: '0 auto' }}>
            {/* Basic Card */}
            <div className="glass-card" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '1.5rem' }}>
              <div>
                <h4 style={{ fontSize: '1.25rem', fontWeight: '700', color: isDark ? '#fff' : 'var(--light-text)' }}>Basic</h4>
                <p style={{ fontSize: '0.8rem', color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', marginTop: '0.25rem' }}>For growing stores getting started</p>
                <div style={{ display: 'flex', alignItems: 'baseline', marginTop: '1.5rem' }}>
                  <span style={{ fontSize: '2rem', fontWeight: '800', color: 'var(--primary-color)' }}>
                    ${billingPeriod === 'annual' ? '45' : '55'}
                  </span>
                  <span style={{ fontSize: '0.85rem', color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', marginLeft: '0.25rem' }}>/month</span>
                </div>
                {billingPeriod === 'annual' && <span style={{ fontSize: '0.7rem', color: '#10b981', fontWeight: '600' }}>Billed annually ($540/yr)</span>}
                <ul style={{ listStyleType: 'none', fontSize: '0.85rem', marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> 3 Team Operator Seats</li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> Unlimited Support Chats</li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> WhatsApp & LINE Integrations</li>
                </ul>
              </div>
              <button onClick={onLaunchApp} className="btn-secondary" style={{ width: '100%', justifyContent: 'center' }}>Start Free Trial</button>
            </div>

            {/* Pro Card (Recommended) */}
            <div className="glass-card" style={{
              padding: '2rem',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              gap: '1.5rem',
              border: '2px solid var(--primary-color)',
              boxShadow: '0 8px 30px rgba(0, 194, 142, 0.15)',
              position: 'relative'
            }}>
              <span style={{
                position: 'absolute',
                top: '-12px',
                right: '24px',
                backgroundColor: 'var(--primary-color)',
                color: '#fff',
                fontSize: '0.7rem',
                fontWeight: '700',
                padding: '0.25rem 0.75rem',
                borderRadius: '20px'
              }}>
                MOST POPULAR
              </span>
              <div>
                <h4 style={{ fontSize: '1.25rem', fontWeight: '700', color: isDark ? '#fff' : 'var(--light-text)' }}>Pro</h4>
                <p style={{ fontSize: '0.8rem', color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', marginTop: '0.25rem' }}>For scale omnichannel operations</p>
                <div style={{ display: 'flex', alignItems: 'baseline', marginTop: '1.5rem' }}>
                  <span style={{ fontSize: '2rem', fontWeight: '800', color: 'var(--primary-color)' }}>
                    ${billingPeriod === 'annual' ? '97' : '119'}
                  </span>
                  <span style={{ fontSize: '0.85rem', color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', marginLeft: '0.25rem' }}>/month</span>
                </div>
                {billingPeriod === 'annual' && <span style={{ fontSize: '0.7rem', color: '#10b981', fontWeight: '600' }}>Billed annually ($1,164/yr)</span>}
                <ul style={{ listStyleType: 'none', fontSize: '0.85rem', marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> 5 Team Operator Seats</li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> Advanced Visual Flow Builder</li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> Shopify & Lazada Order Sync</li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> Auto-Tag CRM Engine</li>
                </ul>
              </div>
              <button onClick={onLaunchApp} className="btn-primary" style={{ width: '100%', justifyContent: 'center' }}>Start Free Trial</button>
            </div>

            {/* Advanced Card */}
            <div className="glass-card" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '1.5rem' }}>
              <div>
                <h4 style={{ fontSize: '1.25rem', fontWeight: '700', color: isDark ? '#fff' : 'var(--light-text)' }}>Advanced</h4>
                <p style={{ fontSize: '0.8rem', color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', marginTop: '0.25rem' }}>For automated AI sales systems</p>
                <div style={{ display: 'flex', alignItems: 'baseline', marginTop: '1.5rem' }}>
                  <span style={{ fontSize: '2rem', fontWeight: '800', color: 'var(--primary-color)' }}>
                    ${billingPeriod === 'annual' ? '145' : '179'}
                  </span>
                  <span style={{ fontSize: '0.85rem', color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', marginLeft: '0.25rem' }}>/month</span>
                </div>
                {billingPeriod === 'annual' && <span style={{ fontSize: '0.7rem', color: '#10b981', fontWeight: '600' }}>Billed annually ($1,740/yr)</span>}
                <ul style={{ listStyleType: 'none', fontSize: '0.85rem', marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> 10 Team Operator Seats</li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> 24/7 AI Sales Agent Studio</li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> Unlimited Broadcast Campaigns</li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> Custom Webhooks & API Access</li>
                </ul>
              </div>
              <button onClick={onLaunchApp} className="btn-secondary" style={{ width: '100%', justifyContent: 'center' }}>Start Free Trial</button>
            </div>
          </div>
        </div>
      </section>

      {landingSubView === 'home' ? (
        <>
          {/* Hero Section */}
          <section style={{ padding: '5rem 0 3rem 0', textAlign: 'center' }}>
            <div className="container" style={{ maxWidth: '800px' }}>
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                backgroundColor: 'rgba(0, 194, 142, 0.1)',
                color: 'var(--primary-hover)',
                padding: '0.35rem 0.85rem',
                borderRadius: '20px',
                fontSize: '0.8rem',
                fontWeight: '600',
                marginBottom: '1.5rem',
                fontFamily: 'var(--font-heading)'
              }}>
                <Bot size={14} />
                ALL-IN-ONE CONVERSATIONAL AI FOR COMMERCE
              </div>

              <h1 style={{
                fontSize: '3.5rem',
                lineHeight: '1.15',
                fontWeight: '800',
                marginBottom: '1.5rem',
                fontFamily: 'var(--font-heading)',
                letterSpacing: '-0.04em'
              }}>
                Redefine Your Customer Experience With <span className="gradient-text">AI Agents</span>
              </h1>

              <p style={{
                fontSize: '1.15rem',
                color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)',
                lineHeight: '1.6',
                marginBottom: '2.5rem',
                maxWidth: '640px',
                marginRight: 'auto',
                marginLeft: 'auto'
              }}>
                Automate customer service with an intelligent AI agent, qualify leads automatically, and manage every conversation from one powerful inbox.
              </p>

              <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
                <button onClick={onLaunchApp} className="btn-primary">
                  Get Started Free
                  <ArrowRight size={18} />
                </button>
                <a href="#features" className="btn-secondary">Explore Features</a>
              </div>
            </div>
          </section>

          {/* Continuous Marquee Banner */}
          <div className="marquee-wrapper" style={{ borderTop: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, borderBottom: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`, backgroundColor: isDark ? 'rgba(255,255,255,0.01)' : 'rgba(0,0,0,0.01)' }}>
            <div className="marquee-content">
              {CHANNELS.concat(CHANNELS).map((chan, idx) => (
                <span key={idx} className="marquee-item">
                  <Bot />
                  {chan.name}
                </span>
              ))}
            </div>
          </div>

          {/* Interactive Feature Slider */}
          <section id="features" style={{ padding: '6rem 0' }}>
            <div className="container">
              <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
                <h2 style={{ fontSize: '2.5rem', marginBottom: '0.75rem', letterSpacing: '-0.03em' }}>
                  All Key Channels, Unified In One Tool
                </h2>
                <p style={{ color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', fontSize: '1rem', maxWidth: '600px', margin: '0 auto' }}>
                  Choose from our core platforms to experience how Zok organizes, schedules, and automates high-volume chat operations.
                </p>
              </div>

              {/* Navigation Tabs */}
              <div className="feature-tabs-nav">
                {Object.keys(tabContent).map(key => (
                  <button
                    key={key}
                    onClick={() => setActiveTab(key)}
                    className={`feature-tab-btn ${activeTab === key ? 'active' : ''}`}
                  >
                    {key.toUpperCase().replace('-', ' ')}
                  </button>
                ))}
              </div>

              {/* Tab Display Panel */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '4rem',
                alignItems: 'center',
                marginTop: '2rem'
              }}>
                <div style={{ textAlign: 'left' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--primary-color)', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    {tabContent[activeTab].tag}
                  </span>
                  <h3 style={{ fontSize: '2rem', margin: '0.5rem 0 1rem 0', letterSpacing: '-0.02em', lineHeight: '1.2' }}>
                    {tabContent[activeTab].title}
                  </h3>
                  <p style={{ color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', lineHeight: '1.6', marginBottom: '2rem' }}>
                    {tabContent[activeTab].desc}
                  </p>
                  <button onClick={onLaunchApp} className="btn-primary">
                    Try {activeTab.toUpperCase().replace('-', ' ')} Now
                    <ArrowRight size={16} />
                  </button>
                </div>

                <div className="glass-card" style={{
                  padding: '2rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  minHeight: '260px',
                  position: 'relative',
                  overflow: 'hidden'
                }}>
                  {tabContent[activeTab].illustration}
                </div>
              </div>
            </div>
          </section>

          {/* Pricing Plans Section */}
          <section id="pricing" style={{ padding: '5rem 0' }}>
            <div className="container">
              <div style={{ textAlign: 'center', marginBottom: '3.5rem' }}>
                <h2 style={{ fontSize: '2.5rem', marginBottom: '0.5rem', letterSpacing: '-0.03em' }}>
                  Transparent, Simple Pricing
                </h2>
                <p style={{ color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', fontSize: '0.95rem' }}>
                  Start for free, then scale as your business grows. No hidden integration fees.
                </p>

                {/* Monthly/Annual Toggle Slider */}
                <div style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  marginTop: '2rem',
                  backgroundColor: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)',
                  padding: '0.35rem',
                  borderRadius: '30px',
                  border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`
                }}>
                  <button
                    onClick={() => setBillingPeriod('monthly')}
                    style={{
                      background: billingPeriod === 'monthly' ? (isDark ? '#1e293b' : '#fff') : 'transparent',
                      color: billingPeriod === 'monthly' ? 'var(--primary-color)' : 'inherit',
                      border: 'none',
                      padding: '0.5rem 1.25rem',
                      borderRadius: '20px',
                      cursor: 'pointer',
                      fontWeight: '600',
                      fontSize: '0.85rem'
                    }}
                  >
                    Monthly
                  </button>
                  <button
                    onClick={() => setBillingPeriod('annual')}
                    style={{
                      background: billingPeriod === 'annual' ? (isDark ? '#1e293b' : '#fff') : 'transparent',
                      color: billingPeriod === 'annual' ? 'var(--primary-color)' : 'inherit',
                      border: 'none',
                      padding: '0.5rem 1.25rem',
                      borderRadius: '20px',
                      cursor: 'pointer',
                      fontWeight: '600',
                      fontSize: '0.85rem',
                      position: 'relative'
                    }}
                  >
                    Annual (Save 20%)
                  </button>
                </div>
              </div>

              {/* Pricing Cards Grid */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: '2rem',
                maxWidth: '1000px',
                margin: '0 auto'
              }}>
                {/* Basic Card */}
                <div className="glass-card" style={{ padding: '2.5rem 2rem', display: 'flex', flexDirection: 'column', textAlign: 'left', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}` }}>
                  <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem', fontWeight: '700' }}>Basic</h3>
                  <p style={{ fontSize: '0.85rem', color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', marginBottom: '1.5rem' }}>Best for small stores starting with automation.</p>
                  <div style={{ marginBottom: '1.5rem' }}>
                    <span style={{ fontSize: '2.5rem', fontWeight: '800' }}>${billingPeriod === 'annual' ? '36' : '45'}</span>
                    <span style={{ color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', fontSize: '0.85rem' }}> / month</span>
                  </div>
                  <ul style={{ padding: 0, margin: '0 0 2rem 0', listStyle: 'none', fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', flex: 1 }}>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> 3 Team Operator Seats</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> 1 LINE OA Connection</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> 1 WhatsApp API Connection</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> Basic Bot Auto-replies</li>
                  </ul>
                  <button onClick={onLaunchApp} className="btn-secondary" style={{ width: '100%', justifyContent: 'center' }}>Choose Basic</button>
                </div>

                {/* Pro Card */}
                <div className="glass-card glow-active" style={{ padding: '2.5rem 2rem', display: 'flex', flexDirection: 'column', textAlign: 'left', border: '2px solid var(--primary-color)', position: 'relative' }}>
                  <span style={{ position: 'absolute', top: '1rem', right: '1rem', backgroundColor: 'var(--primary-color)', color: '#fff', fontSize: '0.7rem', fontWeight: '700', padding: '0.25rem 0.5rem', borderRadius: '4px', textTransform: 'uppercase' }}>Popular</span>
                  <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem', fontWeight: '700' }}>Pro</h3>
                  <p style={{ fontSize: '0.85rem', color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', marginBottom: '1.5rem' }}>Ideal for growing shops seeking CRM integrations.</p>
                  <div style={{ marginBottom: '1.5rem' }}>
                    <span style={{ fontSize: '2.5rem', fontWeight: '800' }}>${billingPeriod === 'annual' ? '77' : '97'}</span>
                    <span style={{ color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', fontSize: '0.85rem' }}> / month</span>
                  </div>
                  <ul style={{ padding: 0, margin: '0 0 2rem 0', listStyle: 'none', fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', flex: 1 }}>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> 10 Team Operator Seats</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> 3 LINE OA Connections</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> 2 WhatsApp API Connections</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> Visual Flow Builder Access</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> Shopify Sync CRM Sidebar</li>
                  </ul>
                  <button onClick={onLaunchApp} className="btn-primary" style={{ width: '100%', justifyContent: 'center' }}>Choose Pro</button>
                </div>

                {/* Advanced Card */}
                <div className="glass-card" style={{ padding: '2.5rem 2rem', display: 'flex', flexDirection: 'column', textAlign: 'left', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}` }}>
                  <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem', fontWeight: '700' }}>Advanced</h3>
                  <p style={{ fontSize: '0.85rem', color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', marginBottom: '1.5rem' }}>Designed for high-scale multi-channel sellers.</p>
                  <div style={{ marginBottom: '1.5rem' }}>
                    <span style={{ fontSize: '2.5rem', fontWeight: '800' }}>${billingPeriod === 'annual' ? '199' : '249'}</span>
                    <span style={{ color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', fontSize: '0.85rem' }}> / month</span>
                  </div>
                  <ul style={{ padding: 0, margin: '0 0 2rem 0', listStyle: 'none', fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', flex: 1 }}>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> Unlimited Operator Seats</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> Unlimited LINE Connections</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> 5 WhatsApp API Connections</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> Custom AI Sales Agent Training</li>
                    <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} style={{ color: 'var(--primary-color)' }} /> Custom Webhooks & API Access</li>
                  </ul>
                  <button onClick={onLaunchApp} className="btn-secondary" style={{ width: '100%', justifyContent: 'center' }}>Choose Advanced</button>
                </div>
              </div>
            </div>
          </section>

          {/* Platform Comparison Section */}
          <section id="comparison" style={{ padding: '5rem 0' }}>
            <div className="container">
              <div style={{ textAlign: 'center', marginBottom: '3.5rem' }}>
                <h2 style={{ fontSize: '2.2rem', marginBottom: '0.5rem', letterSpacing: '-0.03em' }}>
                  Why Choose Zok?
                </h2>
                <p style={{ color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', fontSize: '0.95rem' }}>
                  See how Zok compares to general-purpose enterprise helpdesks and standalone messaging platforms.
                </p>
              </div>

              <div style={{
                maxWidth: '900px',
                margin: '0 auto',
                overflowX: 'auto',
                border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`,
                borderRadius: '16px',
                backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff',
                boxShadow: '0 4px 30px rgba(0, 0, 0, 0.05)'
              }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{
                      borderBottom: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`,
                      backgroundColor: isDark ? 'rgba(255, 255, 255, 0.02)' : '#f8fafc',
                      color: isDark ? '#fff' : '#0f172a',
                      fontWeight: '700'
                    }}>
                      <th style={{ padding: '1.25rem' }}>Core Capability</th>
                      <th style={{ padding: '1.25rem', color: 'var(--primary-color)' }}>Zok</th>
                      <th style={{ padding: '1.25rem', color: '#64748b' }}>HubSpot / Zendesk</th>
                      <th style={{ padding: '1.25rem', color: '#64748b' }}>LINE/WhatsApp Apps</th>
                    </tr>
                  </thead>
                  <tbody style={{ color: isDark ? 'var(--dark-text)' : 'var(--light-text)' }}>
                    <tr style={{ borderBottom: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}` }}>
                      <td style={{ padding: '1.25rem', fontWeight: '600' }}>WhatsApp & LINE OA API</td>
                      <td style={{ padding: '1.25rem', color: '#10b981' }}>✅ Shared Multi-Agent Access</td>
                      <td style={{ padding: '1.25rem', color: '#f59e0b' }}>⚠️ High Setup Overhead</td>
                      <td style={{ padding: '1.25rem', color: '#ef4444' }}>❌ Single Device Only</td>
                    </tr>
                    <tr style={{ borderBottom: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}` }}>
                      <td style={{ padding: '1.25rem', fontWeight: '600' }}>E-Commerce Sync (Shopify)</td>
                      <td style={{ padding: '1.25rem', color: '#10b981' }}>✅ Order Sync in Chat View</td>
                      <td style={{ padding: '1.25rem', color: '#f59e0b' }}>⚠️ Requires Expensive Add-on</td>
                      <td style={{ padding: '1.25rem', color: '#ef4444' }}>❌ Manual Copy-Paste</td>
                    </tr>
                    <tr style={{ borderBottom: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}` }}>
                      <td style={{ padding: '1.25rem', fontWeight: '600' }}>Shopee & Lazada Chats</td>
                      <td style={{ padding: '1.25rem', color: '#10b981' }}>✅ Direct Consolidated Inbox</td>
                      <td style={{ padding: '1.25rem', color: '#ef4444' }}>❌ No Direct Integration</td>
                      <td style={{ padding: '1.25rem', color: '#ef4444' }}>❌ Switch seller apps</td>
                    </tr>
                    <tr style={{ borderBottom: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}` }}>
                      <td style={{ padding: '1.25rem', fontWeight: '600' }}>Interactive Flow Builders</td>
                      <td style={{ padding: '1.25rem', color: '#10b981' }}>✅ Visual & E-Commerce Focused</td>
                      <td style={{ padding: '1.25rem', color: '#f59e0b' }}>⚠️ Technical Setup Required</td>
                      <td style={{ padding: '1.25rem', color: '#ef4444' }}>❌ Basic Auto-Replies Only</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '1.25rem', fontWeight: '600' }}>Primary Use Case</td>
                      <td style={{ padding: '1.25rem', fontWeight: '600', color: 'var(--primary-color)' }}>Social Commerce & Chat Selling</td>
                      <td style={{ padding: '1.25rem', color: '#94a3b8' }}>B2B Pipelines & Ticket Desk</td>
                      <td style={{ padding: '1.25rem', color: '#94a3b8' }}>Basic P2P Dialogs</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          {/* Security Showcase */}
          <section id="security" style={{ padding: '5rem 0', backgroundColor: isDark ? 'rgba(15, 23, 42, 0.3)' : 'rgba(241, 245, 249, 0.5)' }}>
            <div className="container">
              <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
                <h2 style={{ fontSize: '2.2rem', marginBottom: '0.5rem', letterSpacing: '-0.03em' }}>
                  Built For Enterprise Security
                </h2>
                <p style={{ color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', fontSize: '0.95rem' }}>
                  Your store details and customer records are locked down with safety-first infrastructure.
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '2rem' }}>
                <div className="glass-card" style={{ padding: '2rem', textAlign: 'left' }}>
                  <ShieldCheck size={32} style={{ color: 'var(--primary-color)', marginBottom: '1rem' }} />
                  <h4 style={{ fontSize: '1.1rem', marginBottom: '0.75rem' }}>Absolute Data Ownership</h4>
                  <p style={{ fontSize: '0.85rem', color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', lineHeight: '1.5' }}>
                    We do not sell, share, or use store datasets or catalog archives to train external open models.
                  </p>
                </div>

                <div className="glass-card" style={{ padding: '2rem', textAlign: 'left' }}>
                  <UserCheck size={32} style={{ color: 'var(--primary-color)', marginBottom: '1rem' }} />
                  <h4 style={{ fontSize: '1.1rem', marginBottom: '0.75rem' }}>Compliance & API Partnerships</h4>
                  <p style={{ fontSize: '0.85rem', color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', lineHeight: '1.5' }}>
                    Partnered directly with Meta APIs & LINE official channel nodes to ensure delivery rates and compliance guidelines.
                  </p>
                </div>

                <div className="glass-card" style={{ padding: '2rem', textAlign: 'left' }}>
                  <RefreshCw size={32} style={{ color: 'var(--primary-color)', marginBottom: '1rem' }} />
                  <h4 style={{ fontSize: '1.1rem', marginBottom: '0.75rem' }}>Secure Shopify Sync</h4>
                  <p style={{ fontSize: '0.85rem', color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', lineHeight: '1.5' }}>
                    Encrypted sync structures import client items safely. Access tokens stay isolated inside secure databases.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Conversion / Call To Action Footer */}
          <section style={{ padding: '6rem 0', textAlign: 'center' }}>
            <div className="container" style={{ maxWidth: '600px' }}>
              <h2 style={{ fontSize: '2.5rem', marginBottom: '1rem', letterSpacing: '-0.03em' }}>
                Try Zok Clone Today
              </h2>
              <p style={{ color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)', marginBottom: '2rem', lineHeight: '1.6' }}>
                Automate customer chats, boost resolution rates, and grow store sales without expanding support overhead. No credit card required.
              </p>
              <button onClick={onLaunchApp} className="btn-primary" style={{ padding: '0.9rem 2.2rem', fontSize: '1rem' }}>
                Launch Interactive Dashboard
                <ArrowRight size={16} />
              </button>
            </div>
          </section>
        </>
      ) : (
        renderLandingSubView()
      )}

      {/* Footer */}
      <footer style={{
        marginTop: 'auto',
        padding: '2.5rem 0',
        borderTop: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`,
        fontSize: '0.85rem',
        color: isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)',
        textAlign: 'center'
      }}>
        <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            © 2026 Zok Clone. Built for demonstration and execution planning validation.
          </div>
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            <button onClick={() => { setLandingSubView('home'); setProductDropdownOpen(false); setUseCaseDropdownOpen(false); }} style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '0.85rem' }}>Home</button>
            <button onClick={() => { setLandingSubView('about-us'); setProductDropdownOpen(false); setUseCaseDropdownOpen(false); }} style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '0.85rem' }}>About Us</button>
            <button onClick={() => { setLandingSubView('blog'); setProductDropdownOpen(false); setUseCaseDropdownOpen(false); }} style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '0.85rem' }}>Blog</button>
            <button onClick={() => { setLandingSubView('help-center'); setProductDropdownOpen(false); setUseCaseDropdownOpen(false); }} style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '0.85rem' }}>Help Center</button>
          </div>
        </div>
      </footer>

    </div>
  );
}
