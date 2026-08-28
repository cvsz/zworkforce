import { useState, useEffect } from 'react';
import LandingPage from './views/LandingPage';
import DashboardNav from './views/Dashboard/DashboardNav';
import UnifiedInbox from './views/Dashboard/UnifiedInbox';
import AIAgent from './views/Dashboard/AIAgent';
import FlowBuilder from './views/Dashboard/FlowBuilder';
import Broadcasts from './views/Dashboard/Broadcasts';
import Analytics from './views/Dashboard/Analytics';
import Integrations from './views/Dashboard/Integrations';
import DeveloperPortal from './views/Dashboard/DeveloperPortal';
import AIIntelligence from './views/Dashboard/AIIntelligence';
import EnterpriseGovernance from './views/Dashboard/EnterpriseGovernance';
import MarketingO2O from './views/Dashboard/MarketingO2O';
import EducationEcosystem from './views/Dashboard/EducationEcosystem';
import { apiFetch } from './lib/api';

export default function App() {
  const [currentView, setCurrentView] = useState('landing');
  const [dashboardView, setDashboardView] = useState('inbox');
  const [darkMode, setDarkMode] = useState(true);

  // Sync dark mode class on document body
  useEffect(() => {
    if (darkMode) {
      document.body.classList.add('dark-mode');
    } else {
      document.body.classList.remove('dark-mode');
    }
  }, [darkMode]);

  useEffect(() => {
    const handleUnauthorized = () => setCurrentView('landing');
    window.addEventListener('zok:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('zok:unauthorized', handleUnauthorized);
  }, []);

  const handleLogout = async () => {
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' });
    } finally {
      setCurrentView('landing');
    }
  };

  const handleLaunchApp = async () => {
    try {
      const response = await apiFetch('/api/auth/me');
      if (response.ok) {
        setCurrentView('dashboard');
        return;
      }
    } catch {
      // Keep unauthenticated navigation fail-closed when the API is unavailable.
    }
    window.dispatchEvent(new CustomEvent('zok:login-required'));
  };

  if (currentView === 'landing') {
    return (
      <LandingPage
        onLaunchApp={handleLaunchApp}
        isDark={darkMode}
        onToggleTheme={() => setDarkMode(!darkMode)}
      />
    );
  }

  // Active dashboard view component
  const renderDashboardView = () => {
    switch (dashboardView) {
      case 'inbox':
        return <UnifiedInbox />;
      case 'ai-agent':
        return <AIAgent />;
      case 'flow-builder':
        return <FlowBuilder />;
      case 'broadcasts':
        return <Broadcasts />;
      case 'analytics':
        return <Analytics />;
      case 'integrations':
        return <Integrations />;
      case 'developer-portal':
        return <DeveloperPortal />;
      case 'ai-intelligence':
        return <AIIntelligence />;
      case 'enterprise':
        return <EnterpriseGovernance />;
      case 'marketing-o2o':
        return <MarketingO2O />;
      case 'education':
        return <EducationEcosystem />;
      default:
        return <UnifiedInbox />;
    }
  };

  return (
    <div className="dashboard-container">
      {/* Left Sidebar Nav */}
      <DashboardNav
        activeSubView={dashboardView}
        onChangeSubView={setDashboardView}
        onExitDashboard={handleLogout}
      />

      {/* Main Dashboard Content Area */}
      <div className="dashboard-content-area">
        {/* Header toolbar */}
        <header className="dashboard-header">
          <div style={{ fontSize: '0.9rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>Workspace:</span>
            <strong style={{ color: '#fff', textTransform: 'uppercase' }}>Zok Store Demo</strong>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{
              fontSize: '0.75rem',
              color: 'var(--primary-color)',
              backgroundColor: 'rgba(0, 194, 142, 0.1)',
              padding: '0.25rem 0.5rem',
              borderRadius: '4px',
              fontWeight: '600'
            }}>
              Free Developer Sandbox
            </span>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 'bold',
              fontSize: '0.85rem'
            }}>
              AG
            </div>
          </div>
        </header>

        {/* Dynamic sub-view */}
        <main className="dashboard-main-view">
          {renderDashboardView()}
        </main>
      </div>
    </div>
  );
}
