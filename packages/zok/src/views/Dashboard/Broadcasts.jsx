import { useState, useEffect } from 'react';
import { Send, BarChart2, Plus, AlertCircle } from 'lucide-react';
import { apiFetch } from '../../lib/api';

const INITIAL_CAMPAIGNS = [
  {
    id: 1,
    name: 'August VIP Discount Promo',
    status: 'completed',
    channel: 'whatsapp',
    target: 'VIP Customers',
    recipients: 1450,
    delivered: '100%',
    opened: '84.2%',
    converted: '12.8%',
    date: '2026-08-05'
  },
  {
    id: 2,
    name: 'LINE OA Welcome Voucher Push',
    status: 'completed',
    channel: 'line',
    target: 'New Leads',
    recipients: 890,
    delivered: '98.5%',
    opened: '92.1%',
    converted: '15.4%',
    date: '2026-08-01'
  },
  {
    id: 3,
    name: 'Abandon Cart Recovery Followup',
    status: 'scheduled',
    channel: 'whatsapp',
    target: 'Shopify Buyer',
    recipients: 320,
    delivered: '--',
    opened: '--',
    converted: '--',
    date: '2026-08-15 (10:00 AM)'
  }
];

export default function Broadcasts() {
  const [campaigns, setCampaigns] = useState(INITIAL_CAMPAIGNS);
  const [newCampaignName, setNewCampaignName] = useState('');
  const [selectedChannel, setSelectedChannel] = useState('whatsapp');
  const [targetTag, setTargetTag] = useState('VIP');
  const [template, setTemplate] = useState('VIP Promo Coupon');
  const [templateText, setTemplateText] = useState('Hello {{customer_name}}, here is your exclusive 15% discount for this month! Use code: VIP15 at checkout. Valid till Aug 31.');
  const [isSending, setIsSending] = useState(false);
  const [sendProgress, setSendProgress] = useState(0);

  // Load campaigns on mount
  useEffect(() => {
    apiFetch('/api/campaigns')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setCampaigns(data);
        }
      })
      .catch(err => console.error('Error fetching campaigns:', err));
  }, []);

  const handleCreateBroadcast = (e) => {
    e.preventDefault();
    if (!newCampaignName.trim()) return;

    // Simulate sending now
    setIsSending(true);
    setSendProgress(0);

    const interval = setInterval(() => {
      setSendProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setIsSending(false);
          
          // Post new completed campaign to server
          apiFetch('/api/campaigns', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              name: newCampaignName.trim(),
              channel: selectedChannel,
              target: targetTag
            })
          })
            .then(res => res.json())
            .then(newCamp => {
              setCampaigns(prev => [newCamp, ...prev]);
              setNewCampaignName('');
              alert(`Broadcast "${newCamp.name}" sent successfully to ${newCamp.recipients} users!`);
            })
            .catch(err => console.error('Error creating campaign:', err));

          return 0;
        }
        return prev + 10;
      });
    }, 200);
  };

  const handleTemplateChange = (val) => {
    setTemplate(val);
    if (val === 'VIP Promo Coupon') {
      setTemplateText('Hello {{customer_name}}, here is your exclusive 15% discount for this month! Use code: VIP15 at checkout. Valid till Aug 31.');
    } else if (val === 'Product Launch Intro') {
      setTemplateText('Hi {{customer_name}}! Check out our newest arrival accessories launch. Click the link to view the lookbook: zok.zeaz.dev/new-arrivals');
    } else if (val === 'Feedback Survey') {
      setTemplateText('Hello {{customer_name}}, we value your feedback! Complete this quick 2-minute survey and get $5 shopping credits: survey.zok.zeaz.dev');
    }
  };

  return (
    <div style={{ padding: '2rem', height: '100%', overflowY: 'auto' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Send size={26} style={{ color: 'var(--primary-color)' }} />
            Smart Broadcast Campaigns
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Send bulk marketing and recovery messages via WhatsApp and LINE OA to targeted segments.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '2rem' }}>
        {/* Left Side: Campaign logs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{
            backgroundColor: '#0f172a',
            border: '1px solid rgba(255, 255, 255, 0.05)',
            borderRadius: '12px',
            padding: '1.5rem'
          }}>
            <h3 style={{ fontSize: '1.1rem', color: '#fff', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <BarChart2 size={18} style={{ color: 'var(--primary-color)' }} />
              Campaign Performance History
            </h3>

            {/* Campaign Table container */}
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', color: '#64748b' }}>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Campaign Name</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Channel</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Target Aud</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Sent To</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Open Rate</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Conv. Rate</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map(camp => (
                    <tr key={camp.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.02)', color: '#e2e8f0' }}>
                      <td style={{ padding: '0.75rem 0.5rem', fontWeight: '500' }}>
                        <div>{camp.name}</div>
                        <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '0.15rem' }}>Sent: {camp.date}</div>
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem' }}>
                        <span className={`channel-pill channel-${camp.channel}`} style={{ fontSize: '0.65rem' }}>
                          {camp.channel}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem', color: '#94a3b8' }}>{camp.target}</td>
                      <td style={{ padding: '0.75rem 0.5rem', fontWeight: '600' }}>{camp.recipients}</td>
                      <td style={{ padding: '0.75rem 0.5rem', color: '#10b981' }}>{camp.opened}</td>
                      <td style={{ padding: '0.75rem 0.5rem', color: 'var(--primary-color)', fontWeight: '600' }}>{camp.converted}</td>
                      <td style={{ padding: '0.75rem 0.5rem' }}>
                        <span style={{
                          fontSize: '0.7rem',
                          fontWeight: '600',
                          padding: '0.2rem 0.4rem',
                          borderRadius: '4px',
                          backgroundColor: camp.status === 'completed' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                          color: camp.status === 'completed' ? '#10b981' : '#f59e0b',
                          textTransform: 'uppercase'
                        }}>
                          {camp.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right Side: Setup new Campaign */}
        <div style={{
          backgroundColor: '#0a101f',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          borderRadius: '12px',
          padding: '1.5rem',
          height: 'fit-content'
        }}>
          <h3 style={{ fontSize: '1rem', color: '#fff', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: '0.5rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Plus size={16} style={{ color: 'var(--primary-color)' }} />
            New Broadcast Campaign
          </h3>

          <form onSubmit={handleCreateBroadcast} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' }}>Campaign Name</label>
              <input
                type="text"
                placeholder="e.g. Back-to-school Promotion"
                required
                value={newCampaignName}
                onChange={(e) => setNewCampaignName(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  backgroundColor: '#11192e',
                  color: '#fff',
                  fontSize: '0.8rem',
                  outline: 'none'
                }}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' }}>Channel</label>
                <select
                  value={selectedChannel}
                  onChange={(e) => setSelectedChannel(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    borderRadius: '6px',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    backgroundColor: '#11192e',
                    color: '#fff',
                    fontSize: '0.8rem',
                    outline: 'none',
                    cursor: 'pointer'
                  }}
                >
                  <option value="whatsapp">WhatsApp</option>
                  <option value="line">LINE OA</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' }}>Target Tag Segment</label>
                <select
                  value={targetTag}
                  onChange={(e) => setTargetTag(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    borderRadius: '6px',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    backgroundColor: '#11192e',
                    color: '#fff',
                    fontSize: '0.8rem',
                    outline: 'none',
                    cursor: 'pointer'
                  }}
                >
                  <option value="VIP">VIP Customers</option>
                  <option value="Shopify Buyer">Shopify Buyers</option>
                  <option value="New Lead">New Leads</option>
                </select>
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' }}>Template Shortcut</label>
              <select
                value={template}
                onChange={(e) => handleTemplateChange(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  borderRadius: '6px',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  backgroundColor: '#11192e',
                  color: '#fff',
                  fontSize: '0.8rem',
                  outline: 'none',
                  cursor: 'pointer'
                }}
              >
                <option value="VIP Promo Coupon">August 15% VIP Coupon</option>
                <option value="Product Launch Intro">Brand Accessories Lookbook</option>
                <option value="Feedback Survey">Customer Feedback credits Campaign</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' }}>Template Text Preview</label>
              <div style={{
                backgroundColor: '#11192e',
                border: '1px solid rgba(255, 255, 255, 0.05)',
                borderRadius: '6px',
                padding: '0.75rem',
                fontSize: '0.75rem',
                color: '#94a3b8',
                lineHeight: '1.4'
              }}>
                {templateText}
              </div>
            </div>

            {isSending ? (
              <div style={{ marginTop: '0.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#fff', marginBottom: '0.25rem' }}>
                  <span>Sending broadcast messages...</span>
                  <span>{sendProgress}%</span>
                </div>
                <div style={{ width: '100%', height: '6px', backgroundColor: '#11192e', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ width: `${sendProgress}%`, height: '100%', backgroundColor: 'var(--primary-color)', transition: 'width 0.2s' }}></div>
                </div>
              </div>
            ) : (
              <button
                type="submit"
                style={{
                  marginTop: '0.5rem',
                  backgroundColor: 'var(--primary-color)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '0.65rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.35rem',
                  boxShadow: '0 4px 12px var(--primary-glow)'
                }}
              >
                <Send size={14} />
                Send Broadcast Now
              </button>
            )}

            <div style={{ display: 'flex', gap: '0.35rem', color: '#64748b', fontSize: '0.7rem', marginTop: '0.25rem' }}>
              <AlertCircle size={12} style={{ flexShrink: 0 }} />
              <span>Broadcast requests adhere strictly to Meta & LINE Official API guidelines.</span>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
