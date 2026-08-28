import { 
  MessageSquare, Bot, Network, Send, Activity, Link2, LogOut,
  Terminal, Brain, Building2, TrendingUp, GraduationCap
} from 'lucide-react';

export default function DashboardNav({ activeSubView, onChangeSubView, onExitDashboard }) {
  const navItems = [
    { id: 'inbox', label: 'Unified Inbox', icon: <MessageSquare size={18} /> },
    { id: 'ai-agent', label: 'AI Agent Studio', icon: <Bot size={18} /> },
    { id: 'flow-builder', label: 'Flow Builder', icon: <Network size={18} /> },
    { id: 'broadcasts', label: 'Broadcasts', icon: <Send size={18} /> },
    { id: 'analytics', label: 'Analytics', icon: <Activity size={18} /> },
    { id: 'integrations', label: 'Integrations', icon: <Link2 size={18} /> },
  ];

  const releaseItems = [
    { id: 'developer-portal', label: 'Developer Portal', icon: <Terminal size={18} />, badge: 'NEW' },
    { id: 'ai-intelligence', label: 'AI Intelligence', icon: <Brain size={18} />, badge: 'NEW' },
    { id: 'enterprise', label: 'Enterprise', icon: <Building2 size={18} />, badge: 'NEW' },
    { id: 'marketing-o2o', label: 'Marketing & O2O', icon: <TrendingUp size={18} />, badge: 'NEW' },
    { id: 'education', label: 'Zok Academy', icon: <GraduationCap size={18} />, badge: 'NEW' },
  ];

  return (
    <aside className="dashboard-sidebar">
      {/* Brand header */}
      <div className="dashboard-sidebar-brand">
        <div style={{
          width: '28px',
          height: '28px',
          borderRadius: '6px',
          backgroundColor: 'var(--primary-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontWeight: '900',
          fontSize: '1rem'
        }}>
          Z
        </div>
        <span>zok<span style={{ color: 'var(--primary-color)', fontSize: '0.9rem' }}>.app</span></span>
      </div>

      {/* Nav list */}
      <nav className="dashboard-sidebar-nav">
        {navItems.map(item => (
          <div
            key={item.id}
            onClick={() => onChangeSubView(item.id)}
            className={`dashboard-sidebar-item ${activeSubView === item.id ? 'active' : ''}`}
          >
            {item.icon}
            <span>{item.label}</span>
          </div>
        ))}

        {/* Release Plan Pillars */}
        <div style={{
          fontSize: '0.62rem',
          fontWeight: '700',
          letterSpacing: '0.08em',
          color: '#334155',
          textTransform: 'uppercase',
          padding: '0.75rem 0.5rem 0.25rem',
          marginTop: '0.5rem',
          borderTop: '1px solid rgba(255,255,255,0.04)'
        }}>
          Release Pillars
        </div>

        {releaseItems.map(item => (
          <div
            key={item.id}
            onClick={() => onChangeSubView(item.id)}
            className={`dashboard-sidebar-item ${activeSubView === item.id ? 'active' : ''}`}
            style={{ position: 'relative' }}
          >
            {item.icon}
            <span style={{ flex: 1 }}>{item.label}</span>
            {item.badge && (
              <span style={{
                fontSize: '0.55rem',
                fontWeight: '700',
                color: '#00c28e',
                background: 'rgba(0,194,142,0.12)',
                padding: '0.1rem 0.3rem',
                borderRadius: '3px',
                lineHeight: 1.2
              }}>{item.badge}</span>
            )}
          </div>
        ))}
      </nav>


      {/* Footer exit button */}
      <div style={{
        padding: '1rem 0.75rem',
        borderTop: '1px solid rgba(255, 255, 255, 0.05)'
      }}>
        <div
          onClick={onExitDashboard}
          className="dashboard-sidebar-item"
          style={{ color: '#ef4444' }}
        >
          <LogOut size={18} />
          <span>Exit to Site</span>
        </div>
      </div>
    </aside>
  );
}
