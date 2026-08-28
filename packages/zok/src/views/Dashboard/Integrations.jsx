import { useState, useEffect } from 'react';
import { 
  Check, RefreshCw, Link2 
} from 'lucide-react';
import { apiFetch } from '../../lib/api';

const INITIAL_INTEGRATIONS = [
  {
    id: 'shopify',
    name: 'Shopify Store Sync',
    description: 'Pull order history, client tags, and catalog details inside unified chat sidebar.',
    status: 'disconnected',
    category: 'E-commerce',
    logo: 'S'
  },
  {
    id: 'tiktok',
    name: 'TikTok Shop DM Integration',
    description: 'Consolidate TikTok seller chats and order statuses into Zok helpdesk.',
    status: 'disconnected',
    category: 'Social Commerce',
    logo: 'T'
  },
  {
    id: 'lazada',
    name: 'Lazada Messaging',
    description: 'Sync customer chats from Lazada Seller Center directly to your agents.',
    status: 'disconnected',
    category: 'Marketplace',
    logo: 'L'
  },
  {
    id: 'shopee',
    name: 'Shopee Seller Chat',
    description: 'Automate customer support for Shopee inquiries using Zok AI bot flow.',
    status: 'disconnected',
    category: 'Marketplace',
    logo: 'Sh'
  },
  {
    id: 'hubspot',
    name: 'HubSpot CRM Sync',
    description: 'Export customer details, active tickets, and chat history into HubSpot CRM leads.',
    status: 'disconnected',
    category: 'CRM',
    logo: 'H'
  }
];

export default function Integrations() {
  const [integrations, setIntegrations] = useState(INITIAL_INTEGRATIONS);
  const [logs, setLogs] = useState([]);

  // Load integrations and sync logs on mount
  useEffect(() => {
    apiFetch('/api/integrations')
      .then(res => res.json())
      .then(data => {
        if (data.integrations) setIntegrations(data.integrations);
        if (data.syncLogs) setLogs(data.syncLogs);
      })
      .catch(err => console.error('Error fetching integrations:', err));
  }, []);

  const handleToggle = async (id) => {
    try {
      const res = await apiFetch(`/api/integrations/${id}/toggle`, { method: 'POST' });
      const data = await res.json();
      if (data.integrations) setIntegrations(data.integrations);
      if (data.syncLogs) setLogs(data.syncLogs);
    } catch (err) {
      console.error('Error toggling integration:', err);
    }
  };

  return (
    <div style={{ padding: '2rem', height: '100%', overflowY: 'auto' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Link2 size={28} style={{ color: 'var(--primary-color)' }} />
            App & Channels Integration
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Link your e-commerce channels, social platforms, and CRM databases to build a unified operations dashboard.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '2rem' }}>
        {/* Left Side: Cards list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
            {integrations.map(item => {
              const isConnected = item.status === 'connected';
              return (
                <div
                  key={item.id}
                  style={{
                    backgroundColor: '#0f172a',
                    border: '1px solid rgba(255, 255, 255, 0.05)',
                    borderRadius: '12px',
                    padding: '1.25rem',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '1.25rem',
                    transition: 'border-color 0.2s',
                    position: 'relative'
                  }}
                >
                  {/* Category badge */}
                  <span style={{
                    position: 'absolute',
                    right: '12px',
                    top: '12px',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    color: '#94a3b8',
                    fontSize: '0.65rem',
                    fontWeight: '600',
                    padding: '0.15rem 0.4rem',
                    borderRadius: '4px'
                  }}>
                    {item.category}
                  </span>

                  {/* Header info */}
                  <div style={{ display: 'flex', gap: '0.75rem' }}>
                    <div style={{
                      width: '45px',
                      height: '45px',
                      borderRadius: '8px',
                      backgroundColor: isConnected ? 'rgba(0, 194, 142, 0.1)' : '#1e293b',
                      color: isConnected ? 'var(--primary-color)' : '#94a3b8',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: '800',
                      fontSize: '1.1rem',
                      flexShrink: 0
                    }}>
                      {item.logo}
                    </div>
                    <div>
                      <h4 style={{ fontSize: '0.9rem', fontWeight: '700', color: '#fff' }}>{item.name}</h4>
                      <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem', lineHeight: '1.4' }}>
                        {item.description}
                      </p>
                    </div>
                  </div>

                  {/* Footer status control */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    borderTop: '1px solid rgba(255, 255, 255, 0.03)',
                    paddingTop: '0.75rem',
                    marginTop: '0.5rem'
                  }}>
                    <span style={{
                      fontSize: '0.75rem',
                      color: isConnected ? '#10b981' : '#64748b',
                      fontWeight: '600',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.25rem'
                    }}>
                      {isConnected ? (
                        <>
                          <Check size={12} />
                          Connected
                        </>
                      ) : (
                        'Not Connected'
                      )}
                    </span>

                    <label className="switch">
                      <input
                        type="checkbox"
                        checked={isConnected}
                        onChange={() => handleToggle(item.id)}
                      />
                      <span className="slider" />
                    </label>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Side: Sync status log console */}
        <div style={{
          backgroundColor: '#0a101f',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          borderRadius: '12px',
          padding: '1.25rem',
          height: 'fit-content'
        }}>
          <h3 style={{ fontSize: '1rem', color: '#fff', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: '0.5rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <RefreshCw size={16} style={{ color: 'var(--primary-color)' }} />
            Sync Logs & Webhooks
          </h3>

          <div style={{
            backgroundColor: '#070b19',
            borderRadius: '6px',
            padding: '0.75rem',
            fontFamily: 'monospace',
            fontSize: '0.7rem',
            lineHeight: '1.5',
            color: '#10b981',
            height: '280px',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.5rem'
          }}>
            {logs.map((log, i) => (
              <div key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)', paddingBottom: '0.25rem' }}>
                {log}
              </div>
            ))}
          </div>
          
          <div style={{ display: 'flex', gap: '0.35rem', color: '#64748b', fontSize: '0.7rem', marginTop: '0.75rem' }}>
            <span>Console auto-updates when integrations are toggled.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
