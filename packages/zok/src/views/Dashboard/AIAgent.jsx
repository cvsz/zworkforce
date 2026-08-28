import { useState, useRef, useEffect } from 'react';
import { Bot, Save, Plus, Trash2, Send, HelpCircle, FileText } from 'lucide-react';
import { apiFetch } from '../../lib/api';

const DEFAULT_QA = [
  { q: 'What is your return policy?', a: 'We offer a 14-day free return policy for all unused products. Returns are processed within 3 business days.' },
  { q: 'Do you offer free shipping?', a: 'Yes! We offer free shipping on all orders over $100. Standard shipping for smaller orders is $5.99.' },
  { q: 'Where are you located?', a: 'Our corporate headquarters are located in Singapore and Bangkok, Thailand. We ship globally!' }
];

export default function AIAgent() {
  const [agentName, setAgentName] = useState('Zok AI Sales Agent');
  const [persona, setPersona] = useState('sales');
  const [knowledgeBase, setKnowledgeBase] = useState(
    'Zok is an e-commerce brand offering direct-to-consumer lifestyle accessories. Standard delivery takes 3-5 days. All products have a 1-year product warranty. Customers can earn 5% cashback on purchases via our official loyalty program.'
  );
  const [qaPairs, setQaPairs] = useState(DEFAULT_QA);
  const [newQ, setNewQ] = useState('');
  const [newA, setNewA] = useState('');
  
  // Simulator states
  const [simMessages, setSimMessages] = useState([
    { sender: 'bot', text: 'Hello! I am your AI assistant. Ask me anything about our business or catalog.', time: '10:00 AM' }
  ]);
  const [simInput, setSimInput] = useState('');
  const simEndRef = useRef(null);

  // Load AI configurations on mount
  useEffect(() => {
    apiFetch('/api/ai-config')
      .then(res => res.json())
      .then(data => {
        if (data.agentName) setAgentName(data.agentName);
        if (data.persona) setPersona(data.persona);
        if (data.knowledgeBase) setKnowledgeBase(data.knowledgeBase);
        if (data.qaPairs) setQaPairs(data.qaPairs);
      })
      .catch(err => console.error('Error fetching AI config:', err));
  }, []);

  // Scroll to bottom of simulator
  useEffect(() => {
    simEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [simMessages]);

  const handleAddQA = (e) => {
    e.preventDefault();
    if (!newQ.trim() || !newA.trim()) return;
    setQaPairs([...qaPairs, { q: newQ.trim(), a: newA.trim() }]);
    setNewQ('');
    setNewA('');
  };

  const handleRemoveQA = (index) => {
    setQaPairs(qaPairs.filter((_, i) => i !== index));
  };

  const handleSimulateSend = (e) => {
    e.preventDefault();
    if (!simInput.trim()) return;

    const userMsg = {
      sender: 'user',
      text: simInput,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setSimMessages(prev => [...prev, userMsg]);
    const questionText = simInput.toLowerCase().trim();
    setSimInput('');

    // AI bot simple simulation response generator
    setTimeout(() => {
      let replyText = '';

      // Check direct QA matches
      const matchedQA = qaPairs.find(pair => 
        questionText.includes(pair.q.toLowerCase().replace('?', '')) ||
        pair.q.toLowerCase().replace('?', '').includes(questionText)
      );

      if (matchedQA) {
        replyText = matchedQA.a;
      } else {
        // Try simple keyword analysis on knowledgeBase or general context
        if (questionText.includes('delivery') || questionText.includes('shipping') || questionText.includes('time')) {
          replyText = `Regarding shipping/delivery: ${knowledgeBase.includes('delivery') ? 'Standard delivery takes 3-5 days.' : 'We support fast standard delivery globally.'}`;
        } else if (questionText.includes('warranty') || questionText.includes('guarantee')) {
          replyText = `Yes, all our items come with a 1-year product warranty. Please keep your invoice safe.`;
        } else if (questionText.includes('cashback') || questionText.includes('loyalty') || questionText.includes('discount')) {
          replyText = `We offer a loyalty program where customers earn 5% cashback on purchases!`;
        } else if (questionText.includes('price') || questionText.includes('cost') || questionText.includes('product')) {
          replyText = `Our prices vary depending on catalog items. Accessories start at $19.99.`;
        } else {
          replyText = `Thanks for asking. Here is some information: "${knowledgeBase.substring(0, 120)}...". If you need specific help, let me know or ask for a human operator!`;
        }
      }

      // Prepend persona style
      let finalReply = replyText;
      if (persona === 'sales') {
        finalReply = `✨ [Sales Bot] ${replyText} Would you like to check out some product catalog images?`;
      } else if (persona === 'support') {
        finalReply = `🛠️ [Support Specialist] ${replyText} Is there anything else I can check in your order details?`;
      } else if (persona === 'lead') {
        finalReply = `📋 [Lead Gen] ${replyText} Could you share your email or phone number so a sales executive can follow up?`;
      }

      const botMsg = {
        sender: 'bot',
        text: finalReply,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setSimMessages(prev => [...prev, botMsg]);
    }, 1200);
  };

  const handleSaveConfig = async () => {
    try {
      const res = await apiFetch('/api/ai-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agentName,
          persona,
          knowledgeBase,
          qaPairs
        })
      });
      if (res.ok) {
        alert('AI Agent Configurations successfully saved and updated to live triggers!');
      }
    } catch (err) {
      console.error('Error saving AI config:', err);
    }
  };

  return (
    <div style={{ padding: '2rem', height: '100%', overflowY: 'auto' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Bot size={28} style={{ color: 'var(--primary-color)' }} />
            AI Agent Studio
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Configure and train your 24/7 AI chat-commerce assistant with custom knowledge.
          </p>
        </div>
        <button
          onClick={handleSaveConfig}
          style={{
            backgroundColor: 'var(--primary-color)',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            padding: '0.6rem 1.25rem',
            fontWeight: '600',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            boxShadow: '0 4px 12px var(--primary-glow)'
          }}
        >
          <Save size={16} />
          Save Configurations
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: '2rem', height: 'auto' }}>
        {/* Left Side: Setup Forms */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          {/* Section 1: Basic Config & Persona */}
          <div style={{
            backgroundColor: '#0f172a',
            border: '1px solid rgba(255, 255, 255, 0.05)',
            borderRadius: '12px',
            padding: '1.5rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '1.25rem'
          }}>
            <h3 style={{ fontSize: '1.1rem', color: '#fff', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: '0.5rem' }}>
              Basic Settings
            </h3>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.5rem', fontWeight: '600' }}>
                  Agent Name
                </label>
                <input
                  type="text"
                  value={agentName}
                  onChange={(e) => setAgentName(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.65rem 1rem',
                    borderRadius: '8px',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    backgroundColor: '#11192e',
                    color: '#fff',
                    outline: 'none',
                    fontSize: '0.9rem'
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.5rem', fontWeight: '600' }}>
                  Agent Persona
                </label>
                <select
                  value={persona}
                  onChange={(e) => setPersona(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.65rem 1rem',
                    borderRadius: '8px',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    backgroundColor: '#11192e',
                    color: '#fff',
                    outline: 'none',
                    fontSize: '0.9rem',
                    cursor: 'pointer'
                  }}
                >
                  <option value="sales">Sales & Recommended Bot</option>
                  <option value="support">Customer Care Specialist</option>
                  <option value="lead">Lead Qualifier Bot</option>
                </select>
              </div>
            </div>
          </div>

          {/* Section 2: Knowledge Base Train */}
          <div style={{
            backgroundColor: '#0f172a',
            border: '1px solid rgba(255, 255, 255, 0.05)',
            borderRadius: '12px',
            padding: '1.5rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem'
          }}>
            <h3 style={{ fontSize: '1.1rem', color: '#fff', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <FileText size={18} style={{ color: 'var(--primary-color)' }} />
              Business Knowledge Base
            </h3>
            <p style={{ color: '#94a3b8', fontSize: '0.8rem' }}>
              Provide structured text, rules, product information, or guidelines to train your agent.
            </p>
            <textarea
              rows={5}
              value={knowledgeBase}
              onChange={(e) => setKnowledgeBase(e.target.value)}
              style={{
                width: '100%',
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                backgroundColor: '#11192e',
                color: '#fff',
                outline: 'none',
                fontFamily: 'inherit',
                fontSize: '0.9rem',
                lineHeight: '1.5',
                resize: 'vertical'
              }}
            />
          </div>

          {/* Section 3: Smart FAQ Rules */}
          <div style={{
            backgroundColor: '#0f172a',
            border: '1px solid rgba(255, 255, 255, 0.05)',
            borderRadius: '12px',
            padding: '1.5rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '1.25rem'
          }}>
            <h3 style={{ fontSize: '1.1rem', color: '#fff', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <HelpCircle size={18} style={{ color: 'var(--primary-color)' }} />
              Smart Q&A Rules (FAQ Shortcuts)
            </h3>

            {/* List current Q&A */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {qaPairs.map((pair, index) => (
                <div
                  key={index}
                  style={{
                    backgroundColor: '#11192e',
                    border: '1px solid rgba(255, 255, 255, 0.03)',
                    borderRadius: '8px',
                    padding: '0.75rem 1rem',
                    position: 'relative'
                  }}
                >
                  <button
                    onClick={() => handleRemoveQA(index)}
                    style={{
                      position: 'absolute',
                      right: '12px',
                      top: '12px',
                      backgroundColor: 'transparent',
                      color: '#ef4444',
                      border: 'none',
                      cursor: 'pointer',
                      padding: '0.2rem'
                    }}
                  >
                    <Trash2 size={14} />
                  </button>
                  <div style={{ fontWeight: '600', color: '#fff', fontSize: '0.85rem', marginBottom: '0.25rem', paddingRight: '1.5rem' }}>
                    Q: {pair.q}
                  </div>
                  <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>
                    A: {pair.a}
                  </div>
                </div>
              ))}
            </div>

            {/* Form to Add New */}
            <form onSubmit={handleAddQA} style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
              borderTop: '1px solid rgba(255, 255, 255, 0.05)',
              paddingTop: '1rem'
            }}>
              <div style={{ fontWeight: '600', fontSize: '0.85rem', color: '#fff' }}>Add Custom Q&A Rule</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <input
                  type="text"
                  placeholder="Customer Question (e.g. Do you support returns?)"
                  value={newQ}
                  onChange={(e) => setNewQ(e.target.value)}
                  style={{
                    padding: '0.6rem 0.8rem',
                    borderRadius: '6px',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    backgroundColor: '#11192e',
                    color: '#fff',
                    fontSize: '0.8rem',
                    outline: 'none'
                  }}
                />
                <input
                  type="text"
                  placeholder="Automated Answer (e.g. Yes, we support 14-day free returns.)"
                  value={newA}
                  onChange={(e) => setNewA(e.target.value)}
                  style={{
                    padding: '0.6rem 0.8rem',
                    borderRadius: '6px',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    backgroundColor: '#11192e',
                    color: '#fff',
                    fontSize: '0.8rem',
                    outline: 'none'
                  }}
                />
              </div>
              <button
                type="submit"
                style={{
                  alignSelf: 'flex-start',
                  backgroundColor: '#1e293b',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '0.5rem 1rem',
                  fontSize: '0.8rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem'
                }}
              >
                <Plus size={14} />
                Add Rule
              </button>
            </form>
          </div>
        </div>

        {/* Right Side: Simulator */}
        <div style={{
          backgroundColor: '#0a101f',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          borderRadius: '12px',
          display: 'flex',
          flexDirection: 'column',
          height: '550px',
          position: 'sticky',
          top: '20px'
        }}>
          {/* Simulator Header */}
          <div style={{
            padding: '1rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            backgroundColor: '#0f172a',
            borderRadius: '12px 12px 0 0'
          }}>
            <Bot size={16} style={{ color: 'var(--primary-color)' }} />
            <div>
              <div style={{ fontSize: '0.85rem', fontWeight: '600', color: '#fff' }}>Agent Simulator</div>
              <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Active Test Sandbox</span>
            </div>
          </div>

          {/* Simulator Body Messages */}
          <div style={{
            flex: 1,
            padding: '1rem',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem'
          }}>
            {simMessages.map((msg, i) => {
              const isBot = msg.sender === 'bot';
              return (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    justifyContent: isBot ? 'flex-start' : 'flex-end'
                  }}
                >
                  <div style={{
                    maxWidth: '85%',
                    backgroundColor: isBot ? '#11192e' : 'var(--primary-color)',
                    color: '#fff',
                    borderRadius: '8px',
                    padding: '0.5rem 0.75rem',
                    fontSize: '0.8rem',
                    lineHeight: '1.4'
                  }}>
                    {msg.text}
                  </div>
                </div>
              );
            })}
            <div ref={simEndRef} />
          </div>

          {/* Simulator Input Footer */}
          <form
            onSubmit={handleSimulateSend}
            style={{
              padding: '0.75rem',
              borderTop: '1px solid rgba(255, 255, 255, 0.05)',
              display: 'flex',
              gap: '0.5rem',
              backgroundColor: '#0f172a',
              borderRadius: '0 0 12px 12px'
            }}
          >
            <input
              type="text"
              placeholder="Ask simulator something..."
              value={simInput}
              onChange={(e) => setSimInput(e.target.value)}
              style={{
                flex: 1,
                padding: '0.5rem 0.75rem',
                borderRadius: '6px',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                backgroundColor: '#11192e',
                color: '#fff',
                fontSize: '0.8rem',
                outline: 'none'
              }}
            />
            <button
              type="submit"
              style={{
                backgroundColor: 'var(--primary-color)',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer'
              }}
            >
              <Send size={14} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
