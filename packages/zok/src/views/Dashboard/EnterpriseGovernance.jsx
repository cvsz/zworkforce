import { useState } from 'react';
import { Building2, Users, Shield, FileText, CheckCircle, Lock, Eye, ChevronDown, ChevronRight, Plus, Search } from 'lucide-react';

const ROLES = [
  {
    id: 'owner', name: 'Owner', color: '#f59e0b',
    permissions: { inbox: true, ai_config: true, broadcasts: true, analytics: true, billing: true, user_mgmt: true, audit: true, delete: true }
  },
  {
    id: 'manager', name: 'Manager', color: '#3b82f6',
    permissions: { inbox: true, ai_config: true, broadcasts: true, analytics: true, billing: false, user_mgmt: true, audit: true, delete: false }
  },
  {
    id: 'agent', name: 'Support Agent', color: '#10b981',
    permissions: { inbox: true, ai_config: false, broadcasts: false, analytics: true, billing: false, user_mgmt: false, audit: false, delete: false }
  },
  {
    id: 'readonly', name: 'Read-Only', color: '#64748b',
    permissions: { inbox: false, ai_config: false, broadcasts: false, analytics: true, billing: false, user_mgmt: false, audit: false, delete: false }
  },
];

const PERMISSION_LABELS = {
  inbox: 'Unified Inbox', ai_config: 'AI Configuration', broadcasts: 'Broadcasts',
  analytics: 'Analytics', billing: 'Billing & Plans', user_mgmt: 'User Management',
  audit: 'Audit Logs', delete: 'Delete Records'
};

const ORGS = [
  { id: 1, name: 'Fashion House BKK', agents: 12, msgs: '24.5K', revenue: '฿1.2M', status: 'active', logo: 'F' },
  { id: 2, name: 'Phuket Beach Resort', agents: 6, msgs: '8.3K', revenue: '฿445K', status: 'active', logo: 'P' },
  { id: 3, name: 'Organic Herbs TH', agents: 4, msgs: '3.1K', revenue: '฿89K', status: 'trial', logo: 'O' },
  { id: 4, name: 'AutoParts Central', agents: 9, msgs: '15.2K', revenue: '฿678K', status: 'active', logo: 'A' },
];

const AUDIT_LOGS = [
  { time: '11:09:34', user: 'Arisa K.', action: 'Updated AI response tone', target: 'AI Agent Config', severity: 'info' },
  { time: '11:04:12', user: 'Thanachai P.', action: 'Exported 2,400 contact records', target: 'CRM Export', severity: 'warning' },
  { time: '10:58:47', user: 'Wanida S.', action: 'Deleted broadcast campaign', target: 'Campaign #88', severity: 'critical' },
  { time: '10:45:22', user: 'Arisa K.', action: 'Invited new agent', target: 'john@partner.co', severity: 'info' },
  { time: '10:33:01', user: 'Owner', action: 'Changed billing plan', target: 'Enterprise → Growth', severity: 'warning' },
  { time: '10:21:15', user: 'Thanachai P.', action: 'Enabled WhatsApp integration', target: 'Integrations', severity: 'info' },
  { time: '09:55:30', user: 'System', action: 'Automated data backup completed', target: 'Database', severity: 'info' },
];

export default function EnterpriseGovernance() {
  const [activeTab, setActiveTab] = useState('rbac');
  const [selectedRole, setSelectedRole] = useState('manager');
  const [expandedOrg, setExpandedOrg] = useState(null);
  const [auditSearch, setAuditSearch] = useState('');

  const currentRole = ROLES.find(r => r.id === selectedRole);
  const filteredLogs = AUDIT_LOGS.filter(l =>
    auditSearch === '' || l.action.toLowerCase().includes(auditSearch.toLowerCase()) || l.user.toLowerCase().includes(auditSearch.toLowerCase())
  );

  const severityColor = { info: '#3b82f6', warning: '#f59e0b', critical: '#ef4444' };

  const tabs = [
    { id: 'rbac', label: 'Granular RBAC', icon: <Shield size={15} /> },
    { id: 'agency', label: 'Agency Hub', icon: <Building2 size={15} /> },
    { id: 'audit', label: 'Audit Logs', icon: <FileText size={15} /> },
  ];

  return (
    <div style={{ padding: '2rem', height: '100%', overflowY: 'auto' }}>
      <div style={{ marginBottom: '1.75rem' }}>
        <h2 style={{ fontSize: '1.75rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Building2 size={28} style={{ color: 'var(--primary-color)' }} />
          Enterprise Governance
        </h2>
        <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
          Role-based access control, multi-org agency hub, and full audit trail for enterprise compliance.
        </p>
      </div>

      {/* Tab Bar */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)} style={{
            display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 1rem',
            borderRadius: '8px', border: 'none', cursor: 'pointer', fontSize: '0.85rem',
            fontWeight: activeTab === t.id ? '600' : '400',
            background: activeTab === t.id ? 'var(--primary-color)' : 'rgba(255,255,255,0.05)',
            color: activeTab === t.id ? '#fff' : '#94a3b8', transition: 'all 0.2s'
          }}>{t.icon}{t.label}</button>
        ))}
      </div>

      {/* Granular RBAC */}
      {activeTab === 'rbac' && (
        <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: '1.5rem' }}>
          {/* Role selector */}
          <div>
            <div style={{ color: '#94a3b8', fontSize: '0.78rem', marginBottom: '0.75rem', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Roles</div>
            {ROLES.map(role => (
              <div key={role.id} onClick={() => setSelectedRole(role.id)} style={{
                padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer', marginBottom: '0.35rem',
                background: selectedRole === role.id ? `${role.color}15` : 'transparent',
                border: `1px solid ${selectedRole === role.id ? role.color + '40' : 'transparent'}`,
                display: 'flex', alignItems: 'center', gap: '0.75rem', transition: 'all 0.2s'
              }}>
                <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: role.color }} />
                <span style={{ color: selectedRole === role.id ? '#fff' : '#94a3b8', fontSize: '0.875rem', fontWeight: selectedRole === role.id ? '600' : '400' }}>
                  {role.name}
                </span>
              </div>
            ))}
            <button style={{
              width: '100%', marginTop: '0.5rem', padding: '0.625rem',
              background: 'rgba(255,255,255,0.04)', border: '1px dashed rgba(255,255,255,0.1)',
              borderRadius: '8px', color: '#64748b', cursor: 'pointer', fontSize: '0.8rem',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem'
            }}>
              <Plus size={14} />Create Custom Role
            </button>
          </div>

          {/* Permissions grid */}
          <div style={{ background: '#0f172a', borderRadius: '12px', padding: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: currentRole?.color }} />
              <span style={{ color: '#fff', fontWeight: '700', fontSize: '1rem' }}>{currentRole?.name}</span>
              <span style={{ color: '#64748b', fontSize: '0.8rem' }}>— Field-level permission matrix</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              {Object.entries(PERMISSION_LABELS).map(([key, label]) => {
                const hasAccess = currentRole?.permissions[key];
                return (
                  <div key={key} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '0.875rem 1rem', borderRadius: '8px',
                    background: hasAccess ? 'rgba(16,185,129,0.06)' : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${hasAccess ? 'rgba(16,185,129,0.15)' : 'rgba(255,255,255,0.04)'}`
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      {hasAccess ? <Eye size={14} style={{ color: '#10b981' }} /> : <Lock size={14} style={{ color: '#475569' }} />}
                      <span style={{ color: hasAccess ? '#e2e8f0' : '#475569', fontSize: '0.85rem' }}>{label}</span>
                    </div>
                    {hasAccess
                      ? <CheckCircle size={16} style={{ color: '#10b981' }} />
                      : <div style={{ width: '16px', height: '16px', borderRadius: '50%', border: '2px solid #374151' }} />}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Agency Hub */}
      {activeTab === 'agency' && (
        <div>
          {/* Summary stats */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
            {[
              { label: 'Managed Orgs', value: '4', sub: '+1 this month' },
              { label: 'Total Agents', value: '31', sub: 'across all orgs' },
              { label: 'Combined Revenue', value: '฿2.4M', sub: 'this month' },
              { label: 'White-label Clients', value: '2', sub: 'custom branding' },
            ].map((s, i) => (
              <div key={i} style={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px', padding: '1.25rem' }}>
                <div style={{ color: '#94a3b8', fontSize: '0.78rem', marginBottom: '0.35rem' }}>{s.label}</div>
                <div style={{ color: '#fff', fontSize: '1.5rem', fontWeight: '800' }}>{s.value}</div>
                <div style={{ color: '#475569', fontSize: '0.72rem', marginTop: '0.25rem' }}>{s.sub}</div>
              </div>
            ))}
          </div>

          {/* Org list */}
          {ORGS.map(org => (
            <div key={org.id} style={{
              background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px',
              marginBottom: '0.75rem', overflow: 'hidden'
            }}>
              <div
                onClick={() => setExpandedOrg(expandedOrg === org.id ? null : org.id)}
                style={{
                  padding: '1rem 1.25rem', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '1rem'
                }}
              >
                <div style={{
                  width: '40px', height: '40px', borderRadius: '10px',
                  background: 'rgba(0,194,142,0.1)', color: 'var(--primary-color)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: '800', fontSize: '1rem', flexShrink: 0
                }}>{org.logo}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#fff', fontWeight: '600', fontSize: '0.9rem' }}>{org.name}</div>
                  <div style={{ color: '#64748b', fontSize: '0.75rem' }}>{org.agents} agents · {org.msgs} messages/mo</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ color: 'var(--primary-color)', fontWeight: '700' }}>{org.revenue}</div>
                  <span style={{
                    fontSize: '0.65rem', padding: '0.15rem 0.4rem', borderRadius: '4px',
                    background: org.status === 'active' ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)',
                    color: org.status === 'active' ? '#10b981' : '#f59e0b', fontWeight: '600'
                  }}>{org.status.toUpperCase()}</span>
                </div>
                {expandedOrg === org.id ? <ChevronDown size={16} style={{ color: '#64748b' }} /> : <ChevronRight size={16} style={{ color: '#64748b' }} />}
              </div>
              {expandedOrg === org.id && (
                <div style={{ borderTop: '1px solid rgba(255,255,255,0.03)', padding: '1rem 1.25rem', display: 'flex', gap: '1.5rem' }}>
                  <button style={{ padding: '0.4rem 1rem', background: 'var(--primary-color)', border: 'none', borderRadius: '6px', color: '#fff', fontSize: '0.8rem', cursor: 'pointer' }}>
                    View Dashboard
                  </button>
                  <button style={{ padding: '0.4rem 1rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '6px', color: '#94a3b8', fontSize: '0.8rem', cursor: 'pointer' }}>
                    White-label Setup
                  </button>
                  <button style={{ padding: '0.4rem 1rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '6px', color: '#94a3b8', fontSize: '0.8rem', cursor: 'pointer' }}>
                    Generate Report
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Audit Logs */}
      {activeTab === 'audit' && (
        <div>
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.25rem', alignItems: 'center' }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <Search size={15} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#475569' }} />
              <input
                placeholder="Search by user or action..."
                value={auditSearch}
                onChange={e => setAuditSearch(e.target.value)}
                style={{
                  width: '100%', paddingLeft: '36px', paddingRight: '1rem',
                  padding: '0.625rem 1rem 0.625rem 36px',
                  background: '#0f172a', border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '8px', color: '#e2e8f0', fontSize: '0.875rem', outline: 'none'
                }}
              />
            </div>
            <span style={{ color: '#64748b', fontSize: '0.8rem', whiteSpace: 'nowrap' }}>{filteredLogs.length} events</span>
            <button style={{
              padding: '0.5rem 1rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '8px', color: '#94a3b8', fontSize: '0.8rem', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '0.4rem'
            }}>
              <FileText size={13} />Export CSV
            </button>
          </div>

          <div style={{ background: '#0f172a', borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.05)' }}>
            <div style={{
              display: 'grid', gridTemplateColumns: '80px 120px 1fr 160px 80px',
              padding: '0.75rem 1.25rem',
              borderBottom: '1px solid rgba(255,255,255,0.04)',
              color: '#475569', fontSize: '0.72rem', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em'
            }}>
              <span>Time</span><span>User</span><span>Action</span><span>Target</span><span>Level</span>
            </div>
            {filteredLogs.map((log, i) => (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '80px 120px 1fr 160px 80px',
                padding: '0.875rem 1.25rem',
                borderBottom: '1px solid rgba(255,255,255,0.02)',
                transition: 'background 0.15s'
              }}>
                <span style={{ color: '#475569', fontSize: '0.78rem', fontFamily: 'monospace' }}>{log.time}</span>
                <span style={{ color: '#94a3b8', fontSize: '0.82rem' }}>{log.user}</span>
                <span style={{ color: '#e2e8f0', fontSize: '0.82rem' }}>{log.action}</span>
                <span style={{ color: '#64748b', fontSize: '0.78rem' }}>{log.target}</span>
                <span style={{
                  fontSize: '0.65rem', fontWeight: '700', padding: '0.15rem 0.4rem', borderRadius: '4px',
                  background: `${severityColor[log.severity]}20`, color: severityColor[log.severity],
                  alignSelf: 'center', justifySelf: 'start'
                }}>{log.severity.toUpperCase()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
