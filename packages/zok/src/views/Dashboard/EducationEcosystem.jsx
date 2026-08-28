import { useState } from 'react';
import { GraduationCap, ShoppingBag, Zap, Star, Clock, Users, Award, BookOpen, Play, ChevronRight, CheckCircle, Lock, Search, Tag } from 'lucide-react';

const COURSES = [
  {
    id: 1, title: 'Zok AI Agent Masterclass', level: 'Beginner', duration: '3h 20m',
    modules: 8, enrolled: 1240, rating: 4.8, certified: true,
    topics: ['Setting up AI Agent', 'Flow Builder basics', 'Thai language tuning'],
    progress: 100
  },
  {
    id: 2, title: 'Broadcast Automation Playbook', level: 'Intermediate', duration: '2h 10m',
    modules: 6, enrolled: 890, rating: 4.7, certified: true,
    topics: ['Behavioral triggers', 'Segmentation', 'A/B testing messages'],
    progress: 60
  },
  {
    id: 3, title: 'Enterprise CRM Integration', level: 'Advanced', duration: '4h 45m',
    modules: 12, enrolled: 420, rating: 4.9, certified: true,
    topics: ['API webhooks', 'HubSpot sync', 'Data migration best practices'],
    progress: 0
  },
  {
    id: 4, title: 'Multi-Channel O2O Commerce', level: 'Intermediate', duration: '2h 55m',
    modules: 7, enrolled: 650, rating: 4.6, certified: false,
    topics: ['POS sync setup', 'Attribution models', 'Offline-online bridge'],
    progress: 0
  },
];

const TEMPLATES = [
  { id: 1, name: 'Abandoned Cart Recovery', category: 'E-commerce', rating: 4.9, sales: 340, price: 290, preview: '📦', tags: ['automation', 'conversion'] },
  { id: 2, name: 'VIP Customer Welcome Flow', category: 'Loyalty', rating: 4.8, sales: 210, price: 190, preview: '⭐', tags: ['welcome', 'retention'] },
  { id: 3, name: 'Post-Purchase Review Request', category: 'Reviews', rating: 4.7, sales: 480, price: 0, preview: '✍️', tags: ['reviews', 'free'] },
  { id: 4, name: 'Flash Sale Countdown Broadcast', category: 'Marketing', rating: 4.9, sales: 620, price: 390, preview: '⚡', tags: ['broadcast', 'urgency'] },
  { id: 5, name: 'Lead Qualification Bot', category: 'Sales', rating: 4.6, sales: 155, price: 490, preview: '🤖', tags: ['leads', 'automation'] },
  { id: 6, name: 'Product FAQ Autoresponder', category: 'Support', rating: 4.5, sales: 720, price: 0, preview: '❓', tags: ['support', 'free'] },
];

const WIZARD_STEPS = [
  { id: 'business', label: 'Business Type', icon: '🏪', question: 'What type of business do you run?', options: ['E-commerce Store', 'F&B / Restaurant', 'Service Business', 'B2B Company'] },
  { id: 'channels', label: 'Channels', icon: '📡', question: 'Which channels do your customers use?', options: ['LINE OA', 'Facebook Messenger', 'WhatsApp', 'Instagram DM'] },
  { id: 'goals', label: 'Goals', icon: '🎯', question: 'What is your primary goal with Zok?', options: ['Increase Sales', 'Reduce Support Tickets', 'Improve Response Time', 'Customer Retention'] },
  { id: 'setup', label: 'Auto-Setup', icon: '⚙️', question: 'Zok will configure your workspace automatically based on your answers.' },
];

export default function EducationEcosystem() {
  const [activeTab, setActiveTab] = useState('academy');
  const [wizardStep, setWizardStep] = useState(0);
  const [wizardAnswers, setWizardAnswers] = useState({});
  const [wizardComplete, setWizardComplete] = useState(false);
  const [setupProgress, setSetupProgress] = useState(0);
  const [templateSearch, setTemplateSearch] = useState('');
  const [cartTemplate, setCartTemplate] = useState(null);
  const [selectedFilter, setSelectedFilter] = useState('All');

  const tabs = [
    { id: 'academy', label: 'Zok Academy', icon: <GraduationCap size={15} /> },
    { id: 'marketplace', label: 'Template Marketplace', icon: <ShoppingBag size={15} /> },
    { id: 'wizard', label: 'Interactive Wizard', icon: <Zap size={15} /> },
  ];

  const categories = ['All', 'E-commerce', 'Loyalty', 'Marketing', 'Sales', 'Support', 'Reviews'];
  const filteredTemplates = TEMPLATES.filter(t =>
    (selectedFilter === 'All' || t.category === selectedFilter) &&
    (templateSearch === '' || t.name.toLowerCase().includes(templateSearch.toLowerCase()))
  );

  const levelColor = { Beginner: '#10b981', Intermediate: '#f59e0b', Advanced: '#ef4444' };

  const handleWizardSelect = (answer) => {
    setWizardAnswers(prev => ({ ...prev, [WIZARD_STEPS[wizardStep]?.id]: answer }));
    if (wizardStep < WIZARD_STEPS.length - 1) {
      setWizardStep(s => s + 1);
    } else {
      // Final setup step
      setSetupProgress(0);
      const interval = setInterval(() => {
        setSetupProgress(p => {
          if (p >= 100) { clearInterval(interval); setWizardComplete(true); return 100; }
          return p + 4;
        });
      }, 80);
    }
  };

  const handleAddToCart = (t) => {
    setCartTemplate(t.name);
    setTimeout(() => setCartTemplate(null), 2000);
  };

  return (
    <div style={{ padding: '2rem', height: '100%', overflowY: 'auto' }}>
      <div style={{ marginBottom: '1.75rem' }}>
        <h2 style={{ fontSize: '1.75rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <GraduationCap size={28} style={{ color: 'var(--primary-color)' }} />
          Education Ecosystem
        </h2>
        <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
          Zok Academy courses with certificates, template marketplace, and AI-powered setup wizard.
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

      {/* Zok Academy */}
      {activeTab === 'academy' && (
        <div>
          {/* Stats bar */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
            {[
              { label: 'Courses Available', value: '12', icon: <BookOpen size={16} /> },
              { label: 'Students Enrolled', value: '3,200+', icon: <Users size={16} /> },
              { label: 'Certificates Issued', value: '847', icon: <Award size={16} /> },
              { label: 'Avg. Rating', value: '4.8★', icon: <Star size={16} /> },
            ].map((s, i) => (
              <div key={i} style={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px', padding: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{ color: 'var(--primary-color)' }}>{s.icon}</div>
                <div>
                  <div style={{ color: '#fff', fontWeight: '800', fontSize: '1.1rem' }}>{s.value}</div>
                  <div style={{ color: '#64748b', fontSize: '0.72rem' }}>{s.label}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Course grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
            {COURSES.map(course => (
              <div key={course.id} style={{
                background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)',
                borderRadius: '14px', overflow: 'hidden',
                transition: 'border-color 0.2s'
              }}>
                {/* Course header */}
                <div style={{ padding: '1.25rem 1.25rem 1rem', background: course.progress === 100 ? 'rgba(16,185,129,0.04)' : 'transparent' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                    <span style={{
                      padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.68rem', fontWeight: '700',
                      background: `${levelColor[course.level]}20`, color: levelColor[course.level]
                    }}>{course.level}</span>
                    {course.progress === 100 && <CheckCircle size={18} style={{ color: '#10b981' }} />}
                    {course.progress > 0 && course.progress < 100 && (
                      <span style={{ color: '#f59e0b', fontSize: '0.75rem' }}>{course.progress}% done</span>
                    )}
                  </div>
                  <h3 style={{ color: '#fff', fontSize: '0.95rem', fontWeight: '700', lineHeight: '1.4', marginBottom: '0.75rem' }}>
                    {course.title}
                  </h3>
                  <div style={{ display: 'flex', gap: '1.25rem', color: '#64748b', fontSize: '0.75rem' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <Clock size={12} />{course.duration}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <BookOpen size={12} />{course.modules} modules
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <Users size={12} />{course.enrolled.toLocaleString()}
                    </span>
                  </div>
                </div>

                {/* Progress bar */}
                {course.progress > 0 && (
                  <div style={{ padding: '0 1.25rem' }}>
                    <div style={{ height: '4px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px', overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${course.progress}%`, background: course.progress === 100 ? '#10b981' : 'var(--primary-color)', transition: 'width 0.6s ease', borderRadius: '2px' }} />
                    </div>
                  </div>
                )}

                {/* Topics */}
                <div style={{ padding: '0.75rem 1.25rem', borderTop: '1px solid rgba(255,255,255,0.03)', marginTop: '0.75rem' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.75rem' }}>
                    {course.topics.map((topic, i) => (
                      <span key={i} style={{ padding: '0.15rem 0.5rem', background: 'rgba(255,255,255,0.04)', borderRadius: '4px', color: '#94a3b8', fontSize: '0.7rem' }}>
                        {topic}
                      </span>
                    ))}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', color: '#f59e0b', fontSize: '0.82rem' }}>
                      <Star size={13} fill="#f59e0b" />{course.rating}
                    </div>
                    <button style={{
                      padding: '0.4rem 1rem', borderRadius: '6px', border: 'none', cursor: 'pointer',
                      fontSize: '0.8rem', fontWeight: '600',
                      background: course.progress === 100 ? 'rgba(16,185,129,0.15)' : course.progress > 0 ? 'var(--primary-color)' : 'rgba(255,255,255,0.08)',
                      color: course.progress === 100 ? '#10b981' : '#fff',
                      display: 'flex', alignItems: 'center', gap: '0.35rem'
                    }}>
                      {course.progress === 100 ? <><Award size={13} />Certified</> : course.progress > 0 ? <><Play size={13} />Continue</> : <><Play size={13} />Start</>}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Template Marketplace */}
      {activeTab === 'marketplace' && (
        <div>
          {/* Search + filter */}
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.25rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <Search size={15} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#475569' }} />
              <input
                placeholder="Search templates..."
                value={templateSearch}
                onChange={e => setTemplateSearch(e.target.value)}
                style={{ width: '100%', padding: '0.625rem 1rem 0.625rem 36px', background: '#0f172a', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', color: '#e2e8f0', fontSize: '0.875rem', outline: 'none' }}
              />
            </div>
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
              {categories.map(cat => (
                <button key={cat} onClick={() => setSelectedFilter(cat)} style={{
                  padding: '0.375rem 0.75rem', borderRadius: '20px', border: 'none', cursor: 'pointer',
                  fontSize: '0.78rem', fontWeight: selectedFilter === cat ? '600' : '400',
                  background: selectedFilter === cat ? 'var(--primary-color)' : 'rgba(255,255,255,0.05)',
                  color: selectedFilter === cat ? '#fff' : '#94a3b8', transition: 'all 0.2s'
                }}>{cat}</button>
              ))}
            </div>
          </div>

          {cartTemplate && (
            <div style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: '8px', padding: '0.625rem 1rem', marginBottom: '1rem', color: '#10b981', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <CheckCircle size={16} />"{cartTemplate}" added to workspace!
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
            {filteredTemplates.map(t => (
              <div key={t.id} style={{
                background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px', overflow: 'hidden'
              }}>
                <div style={{ padding: '1.25rem' }}>
                  <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>{t.preview}</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.35rem' }}>
                    <h4 style={{ color: '#fff', fontSize: '0.875rem', fontWeight: '700', lineHeight: '1.3', flex: 1, marginRight: '0.5rem' }}>{t.name}</h4>
                  </div>
                  <div style={{ color: '#64748b', fontSize: '0.72rem', marginBottom: '0.75rem' }}>{t.category}</div>
                  <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                    {t.tags.map(tag => (
                      <span key={tag} style={{ padding: '0.1rem 0.4rem', background: 'rgba(255,255,255,0.04)', borderRadius: '4px', color: '#64748b', fontSize: '0.65rem' }}>
                        #{tag}
                      </span>
                    ))}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div>
                      <div style={{ color: '#f59e0b', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                        <Star size={12} fill="#f59e0b" />{t.rating} · {t.sales} installs
                      </div>
                    </div>
                    <div style={{ color: t.price === 0 ? '#10b981' : 'var(--primary-color)', fontWeight: '800', fontSize: '1rem' }}>
                      {t.price === 0 ? 'FREE' : `฿${t.price}`}
                    </div>
                  </div>
                </div>
                <div style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                  <button onClick={() => handleAddToCart(t)} style={{
                    width: '100%', padding: '0.625rem', background: 'none', border: 'none',
                    color: 'var(--primary-color)', fontWeight: '600', fontSize: '0.82rem', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem',
                    transition: 'background 0.2s'
                  }}>
                    {t.price === 0 ? <><CheckCircle size={13} />Install Free</> : <><ShoppingBag size={13} />Get Template</>}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Interactive Setup Wizard */}
      {activeTab === 'wizard' && (
        <div style={{ maxWidth: '700px' }}>
          {/* Stepper */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0', marginBottom: '2.5rem' }}>
            {WIZARD_STEPS.map((step, i) => (
              <div key={step.id} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem', flex: 1 }}>
                  <div style={{
                    width: '44px', height: '44px', borderRadius: '50%',
                    background: wizardComplete || wizardStep > i ? 'var(--primary-color)' : wizardStep === i ? 'rgba(0,194,142,0.15)' : '#1e293b',
                    border: `2px solid ${wizardComplete || wizardStep > i ? 'var(--primary-color)' : wizardStep === i ? 'var(--primary-color)' : 'rgba(255,255,255,0.08)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '1.2rem', transition: 'all 0.4s'
                  }}>
                    {wizardComplete || wizardStep > i ? <CheckCircle size={20} color="#fff" /> : step.icon}
                  </div>
                  <span style={{ color: wizardStep >= i || wizardComplete ? '#fff' : '#64748b', fontSize: '0.75rem', fontWeight: '600', textAlign: 'center' }}>
                    {step.label}
                  </span>
                </div>
                {i < WIZARD_STEPS.length - 1 && (
                  <div style={{ height: '2px', width: '40px', flexShrink: 0, background: wizardStep > i || wizardComplete ? 'var(--primary-color)' : 'rgba(255,255,255,0.05)', transition: 'background 0.5s', alignSelf: 'flex-start', marginTop: '22px' }} />
                )}
              </div>
            ))}
          </div>

          {wizardComplete ? (
            <div style={{ textAlign: 'center', padding: '3rem' }}>
              <div style={{ fontSize: '4rem', marginBottom: '1rem' }}>🎉</div>
              <h3 style={{ color: '#fff', fontSize: '1.5rem', fontWeight: '800', marginBottom: '0.5rem' }}>Workspace Configured!</h3>
              <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                Your Zok workspace has been automatically set up based on your business profile.
                AI agent, integrations, and broadcast flows are ready.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem', marginBottom: '1.5rem' }}>
                {['AI Agent ✓', 'LINE OA ✓', 'Broadcast ✓'].map(item => (
                  <div key={item} style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: '8px', padding: '0.625rem', color: '#10b981', fontSize: '0.85rem', fontWeight: '600' }}>
                    {item}
                  </div>
                ))}
              </div>
              <button onClick={() => { setWizardStep(0); setWizardAnswers({}); setWizardComplete(false); setSetupProgress(0); }} style={{
                padding: '0.75rem 2rem', background: 'var(--primary-color)', border: 'none', borderRadius: '8px', color: '#fff', fontWeight: '700', cursor: 'pointer', fontSize: '0.9rem'
              }}>Start Over</button>
            </div>
          ) : wizardStep === WIZARD_STEPS.length - 1 && setupProgress > 0 ? (
            <div style={{ background: '#0f172a', borderRadius: '14px', padding: '2rem', textAlign: 'center' }}>
              <Zap size={40} style={{ color: 'var(--primary-color)', marginBottom: '1rem' }} />
              <h3 style={{ color: '#fff', fontSize: '1.1rem', marginBottom: '0.5rem' }}>Auto-configuring your workspace...</h3>
              <div style={{ height: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden', margin: '1.5rem 0' }}>
                <div style={{ height: '100%', width: `${setupProgress}%`, background: 'linear-gradient(90deg, var(--primary-color), #3b82f6)', borderRadius: '4px', transition: 'width 0.15s ease' }} />
              </div>
              <div style={{ color: '#64748b', fontSize: '0.85rem' }}>{setupProgress}% complete — setting up AI agent...</div>
            </div>
          ) : (
            <div style={{ background: '#0f172a', borderRadius: '14px', padding: '2rem' }}>
              <h3 style={{ color: '#fff', fontSize: '1.1rem', fontWeight: '700', marginBottom: '1.5rem' }}>
                {WIZARD_STEPS[wizardStep]?.question}
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                {(WIZARD_STEPS[wizardStep]?.options || []).map((opt, i) => (
                  <button key={i} onClick={() => handleWizardSelect(opt)} style={{
                    padding: '1rem', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '10px', color: '#e2e8f0', fontSize: '0.9rem', cursor: 'pointer', textAlign: 'left',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    transition: 'all 0.2s'
                  }}>
                    {opt}
                    <ChevronRight size={16} style={{ color: '#475569' }} />
                  </button>
                ))}
              </div>
              {wizardStep > 0 && (
                <button onClick={() => setWizardStep(s => s - 1)} style={{
                  marginTop: '1rem', background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: '0.85rem'
                }}>← Back</button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
