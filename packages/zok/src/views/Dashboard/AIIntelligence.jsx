import { useState, useEffect, useRef } from 'react';
import { Brain, Globe, Shield, DollarSign, Bell, ChevronRight, Zap, CheckCircle, AlertCircle, TrendingUp, MessageSquare, Sliders } from 'lucide-react';

const DIALECTS = [
  { id: 'central', label: 'ภาษากลาง', color: '#10b981' },
  { id: 'northern', label: 'ภาษาเหนือ', color: '#3b82f6' },
  { id: 'northeastern', label: 'ภาษาอีสาน', color: '#f59e0b' },
  { id: 'southern', label: 'ภาษาใต้', color: '#ec4899' },
];

const SLANG_EXAMPLES = {
  central: [
    { slang: 'โอเค ขอบคุณนะ', zok: 'ยืนยันแล้วครับ ขอบคุณที่ใช้บริการ', tone: 'formal' },
    { slang: 'ราคาเท่าไหร่', zok: 'ราคาสินค้าชิ้นนี้ 349 บาทครับ', tone: 'friendly' },
  ],
  northern: [
    { slang: 'จะสั่งเลยก็ได้เจ้า', zok: 'สั่งได้เลยครับ มีสต็อกอยู่ครับ', tone: 'friendly' },
    { slang: 'ราคาเปิ้นเท่าไหร่กา', zok: 'ราคา 349 บาทครับ สะดวกชำระแบบไหนครับ', tone: 'warm' },
  ],
  northeastern: [
    { slang: 'แพงบักหน่อยบ่', zok: 'เข้าใจครับ มีโปรโมชันส่วนลด 10% สำหรับสมาชิกนะครับ', tone: 'empathetic' },
    { slang: 'สั่งได้เลยบ่', zok: 'สั่งได้เลยครับ ส่งได้ภายใน 2 วันทำการครับ', tone: 'helpful' },
  ],
  southern: [
    { slang: 'ราคาจ้องเท่าไหร่ว่ะ', zok: 'ราคา 349 บาทครับ รวมส่งฟรีทั่วประเทศ', tone: 'friendly' },
    { slang: 'ได้เลยไหมเหวย', zok: 'ยืนยันออเดอร์ได้เลยครับ มีสินค้าพร้อมส่ง', tone: 'casual' },
  ],
};

const COST_TIERS = [
  { label: 'Starter', msgs: 10000, aiCalls: 3000, price: 890 },
  { label: 'Growth', msgs: 50000, aiCalls: 20000, price: 2990 },
  { label: 'Enterprise', msgs: 200000, aiCalls: 100000, price: 7990 },
];

const ESCALATION_SCENARIOS = [
  { trigger: 'Negative sentiment > 3 turns', channel: 'LINE OA → Manager', delay: '< 30s', active: true },
  { trigger: 'Order value > ฿5,000', channel: 'LINE + SMS to Owner', delay: '< 10s', active: true },
  { trigger: 'Legal/PDPA mention', channel: 'Slack → Legal Team', delay: '< 5s', active: true },
  { trigger: 'Refund request', channel: 'Email → Finance', delay: '< 2min', active: false },
];

export default function AIIntelligence() {
  const [activeTab, setActiveTab] = useState('thai');
  const [selectedDialect, setSelectedDialect] = useState('central');
  const [toneLevel, setToneLevel] = useState(70);
  const [costMsgs, setCostMsgs] = useState(25000);
  const [costAI, setCostAI] = useState(8000);
  const [escalations, setEscalations] = useState(ESCALATION_SCENARIOS);
  const [guardDemo, setGuardDemo] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const estCost = Math.round((costMsgs * 0.02) + (costAI * 0.08));
  const closestTier = COST_TIERS.find(t => t.msgs >= costMsgs) || COST_TIERS[COST_TIERS.length - 1];

  const runGuardDemo = () => {
    setIsAnalyzing(true);
    setGuardDemo(null);
    setTimeout(() => {
      setIsAnalyzing(false);
      setGuardDemo({
        input: 'ยาตัวนี้รักษาโรคมะเร็งได้ไหมครับ',
        verdict: 'BLOCKED',
        reason: 'Medical claim outside product scope — requires human agent review',
        confidence: 0.97,
        routed: 'Senior Support Agent'
      });
    }, 1800);
  };

  const tabs = [
    { id: 'thai', label: 'Thai Context Engine', icon: <Globe size={15} /> },
    { id: 'guardrails', label: 'AI Guardrails', icon: <Shield size={15} /> },
    { id: 'cost', label: 'Cost Simulator', icon: <DollarSign size={15} /> },
    { id: 'escalation', label: 'Smart Escalation', icon: <Bell size={15} /> },
  ];

  return (
    <div style={{ padding: '2rem', height: '100%', overflowY: 'auto' }}>
      <div style={{ marginBottom: '1.75rem' }}>
        <h2 style={{ fontSize: '1.75rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Brain size={28} style={{ color: 'var(--primary-color)' }} />
          Advanced AI Intelligence
        </h2>
        <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
          Thai dialect engine, hallucination guardrails, cost forecasting, and smart human escalation.
        </p>
      </div>

      {/* Tab Bar */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)} style={{
            display: 'flex', alignItems: 'center', gap: '0.4rem',
            padding: '0.5rem 1rem', borderRadius: '8px', border: 'none', cursor: 'pointer',
            fontSize: '0.85rem', fontWeight: activeTab === t.id ? '600' : '400',
            background: activeTab === t.id ? 'var(--primary-color)' : 'rgba(255,255,255,0.05)',
            color: activeTab === t.id ? '#fff' : '#94a3b8', transition: 'all 0.2s'
          }}>{t.icon}{t.label}</button>
        ))}
      </div>

      {/* Thai Context Engine */}
      {activeTab === 'thai' && (
        <div>
          <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem' }}>
            {DIALECTS.map(d => (
              <button key={d.id} onClick={() => setSelectedDialect(d.id)} style={{
                padding: '0.5rem 1.25rem', borderRadius: '20px', border: `2px solid ${selectedDialect === d.id ? d.color : 'rgba(255,255,255,0.08)'}`,
                background: selectedDialect === d.id ? `${d.color}20` : 'transparent',
                color: selectedDialect === d.id ? d.color : '#94a3b8', cursor: 'pointer',
                fontWeight: selectedDialect === d.id ? '600' : '400', fontSize: '0.85rem',
                transition: 'all 0.2s'
              }}>{d.label}</button>
            ))}
          </div>

          {/* Tone Slider */}
          <div style={{ background: '#0f172a', borderRadius: '12px', padding: '1.25rem', marginBottom: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <span style={{ color: '#fff', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sliders size={16} style={{ color: 'var(--primary-color)' }} /> Response Tone
              </span>
              <span style={{ color: 'var(--primary-color)', fontWeight: '700', fontSize: '0.9rem' }}>
                {toneLevel < 33 ? 'Casual & Warm' : toneLevel < 66 ? 'Balanced' : 'Formal & Professional'}
              </span>
            </div>
            <input type="range" min="0" max="100" value={toneLevel} onChange={e => setToneLevel(+e.target.value)}
              style={{ width: '100%', accentColor: 'var(--primary-color)' }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.35rem' }}>
              <span style={{ color: '#475569', fontSize: '0.7rem' }}>🤗 Casual</span>
              <span style={{ color: '#475569', fontSize: '0.7rem' }}>🤝 Formal</span>
            </div>
          </div>

          {/* Examples */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {(SLANG_EXAMPLES[selectedDialect] || []).map((ex, i) => (
              <div key={i} style={{
                background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)',
                borderRadius: '12px', padding: '1.25rem',
                display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: '1.5rem', alignItems: 'center'
              }}>
                <div>
                  <div style={{ color: '#64748b', fontSize: '0.7rem', marginBottom: '0.35rem' }}>Customer Input ({DIALECTS.find(d => d.id === selectedDialect)?.label})</div>
                  <div style={{ background: '#1e293b', borderRadius: '8px', padding: '0.75rem', color: '#e2e8f0', fontSize: '0.9rem' }}>
                    {ex.slang}
                  </div>
                </div>
                <ChevronRight size={20} style={{ color: 'var(--primary-color)' }} />
                <div>
                  <div style={{ color: '#64748b', fontSize: '0.7rem', marginBottom: '0.35rem' }}>
                    Zok AI Response
                    <span style={{ marginLeft: '0.5rem', background: 'rgba(0,194,142,0.15)', color: 'var(--primary-color)', padding: '0.1rem 0.4rem', borderRadius: '4px', fontSize: '0.65rem' }}>
                      {ex.tone}
                    </span>
                  </div>
                  <div style={{ background: 'rgba(0,194,142,0.08)', border: '1px solid rgba(0,194,142,0.2)', borderRadius: '8px', padding: '0.75rem', color: '#e2e8f0', fontSize: '0.9rem' }}>
                    {ex.zok}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI Guardrails */}
      {activeTab === 'guardrails' && (
        <div style={{ maxWidth: '700px' }}>
          <div style={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.25rem' }}>
            <h3 style={{ color: '#fff', fontSize: '1rem', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Shield size={18} style={{ color: '#f59e0b' }} /> Human-in-the-Loop Guardrails
            </h3>
            <p style={{ color: '#64748b', fontSize: '0.85rem', lineHeight: '1.6' }}>
              Zok AI monitors every response for hallucination risk, out-of-scope claims, and high-stakes topics.
              Messages that exceed confidence thresholds are automatically paused and routed to a human agent.
            </p>
          </div>

          {[
            { label: 'Medical / Legal Claims', threshold: '97%', action: 'Block + Route to Human' },
            { label: 'Price > ฿10,000', threshold: '90%', action: 'Flag for Manager Review' },
            { label: 'Hallucination Risk Score', threshold: '85%', action: 'Insert Disclaimer' },
            { label: 'Negative Sentiment Spiral', threshold: '75%', action: 'Escalate to Senior Agent' },
          ].map((rule, i) => (
            <div key={i} style={{
              background: '#0a101f', border: '1px solid rgba(255,255,255,0.05)',
              borderRadius: '10px', padding: '1rem', marginBottom: '0.75rem',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem'
            }}>
              <span style={{ color: '#e2e8f0', fontSize: '0.9rem', flex: 2 }}>{rule.label}</span>
              <span style={{ color: '#f59e0b', fontSize: '0.8rem', background: 'rgba(245,158,11,0.1)', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
                Triggers @ {rule.threshold}
              </span>
              <span style={{ color: '#94a3b8', fontSize: '0.8rem', flex: 2, textAlign: 'right' }}>{rule.action}</span>
            </div>
          ))}

          <div style={{ marginTop: '1.5rem' }}>
            <h4 style={{ color: '#fff', fontSize: '0.9rem', marginBottom: '1rem' }}>Live Demo — Test Guardrail</h4>
            <div style={{ background: '#0f172a', borderRadius: '10px', padding: '1.25rem' }}>
              <div style={{ background: '#1e293b', borderRadius: '8px', padding: '0.75rem', color: '#94a3b8', fontSize: '0.85rem', marginBottom: '1rem' }}>
                Test input: <span style={{ color: '#e2e8f0' }}>"ยาตัวนี้รักษาโรคมะเร็งได้ไหมครับ"</span>
              </div>
              <button onClick={runGuardDemo} disabled={isAnalyzing} style={{
                padding: '0.625rem 1.5rem', background: isAnalyzing ? 'rgba(0,194,142,0.2)' : 'var(--primary-color)',
                border: 'none', borderRadius: '8px', color: '#fff', fontWeight: '600', cursor: isAnalyzing ? 'not-allowed' : 'pointer',
                fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.5rem'
              }}>
                {isAnalyzing ? <><Shield size={15} style={{ animation: 'pulse 1s infinite' }} />Analyzing...</> : <><Shield size={15} />Run Guardrail Check</>}
              </button>

              {guardDemo && (
                <div style={{ marginTop: '1rem', background: `${guardDemo.verdict === 'BLOCKED' ? 'rgba(239,68,68,0.05)' : 'rgba(16,185,129,0.05)'}`, border: `1px solid ${guardDemo.verdict === 'BLOCKED' ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)'}`, borderRadius: '8px', padding: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <AlertCircle size={16} style={{ color: '#ef4444' }} />
                    <span style={{ color: '#ef4444', fontWeight: '700' }}>{guardDemo.verdict}</span>
                    <span style={{ color: '#64748b', fontSize: '0.8rem' }}>— Confidence: {(guardDemo.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '0.35rem' }}>{guardDemo.reason}</div>
                  <div style={{ color: 'var(--primary-color)', fontSize: '0.8rem' }}>→ Routed to: {guardDemo.routed}</div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Cost Simulator */}
      {activeTab === 'cost' && (
        <div style={{ maxWidth: '700px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
            <div style={{ background: '#0f172a', borderRadius: '12px', padding: '1.25rem' }}>
              <label style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: '0.5rem' }}>
                Monthly Messages: <strong style={{ color: '#fff' }}>{costMsgs.toLocaleString()}</strong>
              </label>
              <input type="range" min="1000" max="500000" step="1000" value={costMsgs} onChange={e => setCostMsgs(+e.target.value)}
                style={{ width: '100%', accentColor: 'var(--primary-color)' }} />
            </div>
            <div style={{ background: '#0f172a', borderRadius: '12px', padding: '1.25rem' }}>
              <label style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'block', marginBottom: '0.5rem' }}>
                AI-Handled Responses: <strong style={{ color: '#fff' }}>{costAI.toLocaleString()}</strong>
              </label>
              <input type="range" min="0" max={costMsgs} step="500" value={Math.min(costAI, costMsgs)} onChange={e => setCostAI(+e.target.value)}
                style={{ width: '100%', accentColor: 'var(--primary-color)' }} />
            </div>
          </div>

          <div style={{ background: 'linear-gradient(135deg, rgba(0,194,142,0.08), rgba(59,130,246,0.06))', border: '1px solid rgba(0,194,142,0.2)', borderRadius: '12px', padding: '2rem', textAlign: 'center', marginBottom: '1.5rem' }}>
            <div style={{ color: '#94a3b8', fontSize: '0.9rem' }}>Estimated Monthly Cost</div>
            <div style={{ color: 'var(--primary-color)', fontSize: '3rem', fontWeight: '800', margin: '0.5rem 0' }}>
              ฿{estCost.toLocaleString()}
            </div>
            <div style={{ color: '#64748b', fontSize: '0.8rem' }}>Recommended plan: <span style={{ color: '#fff', fontWeight: '600' }}>{closestTier.label}</span> (฿{closestTier.price.toLocaleString()}/mo)</div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
            {COST_TIERS.map((tier, i) => (
              <div key={i} style={{
                background: closestTier.label === tier.label ? 'rgba(0,194,142,0.08)' : '#0f172a',
                border: `1px solid ${closestTier.label === tier.label ? 'rgba(0,194,142,0.3)' : 'rgba(255,255,255,0.05)'}`,
                borderRadius: '12px', padding: '1.25rem',
                position: 'relative'
              }}>
                {closestTier.label === tier.label && (
                  <div style={{ position: 'absolute', top: '-10px', left: '50%', transform: 'translateX(-50%)', background: 'var(--primary-color)', color: '#fff', fontSize: '0.65rem', fontWeight: '700', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
                    RECOMMENDED
                  </div>
                )}
                <div style={{ color: '#fff', fontWeight: '700', marginBottom: '0.5rem' }}>{tier.label}</div>
                <div style={{ color: 'var(--primary-color)', fontSize: '1.5rem', fontWeight: '800', marginBottom: '0.75rem' }}>฿{tier.price.toLocaleString()}</div>
                <div style={{ color: '#64748b', fontSize: '0.78rem', lineHeight: '1.6' }}>
                  <div>{tier.msgs.toLocaleString()} messages</div>
                  <div>{tier.aiCalls.toLocaleString()} AI calls</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Smart Escalation */}
      {activeTab === 'escalation' && (
        <div style={{ maxWidth: '700px' }}>
          <div style={{ background: '#0f172a', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.25rem' }}>
            <h3 style={{ color: '#fff', fontSize: '1rem', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Bell size={18} style={{ color: 'var(--primary-color)' }} /> Escalation Rules
            </h3>
            <p style={{ color: '#64748b', fontSize: '0.85rem', lineHeight: '1.6' }}>
              Configure triggers that automatically route conversations to humans via LINE, SMS, email, or Slack.
            </p>
          </div>

          {escalations.map((rule, i) => (
            <div key={i} style={{
              background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)',
              borderRadius: '10px', padding: '1.25rem', marginBottom: '0.75rem',
              display: 'flex', alignItems: 'center', gap: '1.5rem'
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ color: '#fff', fontSize: '0.9rem', marginBottom: '0.25rem' }}>{rule.trigger}</div>
                <div style={{ color: '#64748b', fontSize: '0.78rem' }}>{rule.channel}</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ color: '#94a3b8', fontSize: '0.7rem' }}>Response</div>
                <div style={{ color: 'var(--primary-color)', fontSize: '0.85rem', fontWeight: '600' }}>{rule.delay}</div>
              </div>
              <label style={{ position: 'relative', display: 'inline-block', width: '44px', height: '24px', flexShrink: 0 }}>
                <input type="checkbox" checked={rule.active} onChange={() => setEscalations(prev => prev.map((r, ri) => ri === i ? { ...r, active: !r.active } : r))} style={{ opacity: 0, width: 0, height: 0 }} />
                <span style={{
                  position: 'absolute', inset: 0, borderRadius: '12px',
                  background: rule.active ? 'var(--primary-color)' : '#374151',
                  transition: 'background 0.3s', cursor: 'pointer'
                }}>
                  <span style={{
                    position: 'absolute', top: '3px', left: rule.active ? '23px' : '3px',
                    width: '18px', height: '18px', borderRadius: '50%', background: '#fff',
                    transition: 'left 0.3s'
                  }} />
                </span>
              </label>
            </div>
          ))}

          {/* Live demo */}
          <div style={{ marginTop: '1.25rem', background: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.15)', borderRadius: '12px', padding: '1.25rem' }}>
            <div style={{ color: '#fff', fontSize: '0.9rem', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Zap size={16} style={{ color: '#f59e0b' }} />Recent Escalation Events
            </div>
            {[
              { time: '11:02', msg: 'Order #4872 — ฿12,500 purchase → Owner notified via LINE', type: 'alert' },
              { time: '10:47', msg: 'Negative sentiment detected → Senior Agent assigned', type: 'warn' },
              { time: '10:31', msg: 'Legal term mentioned → Legal team alerted via Slack', type: 'alert' },
            ].map((ev, i) => (
              <div key={i} style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start', padding: '0.5rem 0', borderTop: i > 0 ? '1px solid rgba(255,255,255,0.03)' : 'none' }}>
                <span style={{ color: '#475569', fontSize: '0.75rem', flexShrink: 0 }}>{ev.time}</span>
                <span style={{ color: '#94a3b8', fontSize: '0.82rem' }}>{ev.msg}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
