import { useState, useEffect } from 'react';
import { Network, Plus, Play, Info, Settings, Trash2 } from 'lucide-react';
import { apiFetch } from '../../lib/api';

const INITIAL_NODES = [
  {
    id: 'node-1',
    type: 'trigger',
    title: 'Trigger: Keyword Message',
    description: 'When message contains "price" or "catalog"',
    x: 50,
    y: 120,
    details: { keywords: 'price, catalog' }
  },
  {
    id: 'node-2',
    type: 'action',
    title: 'Send WhatsApp Template',
    description: 'Send Catalog Link Template message',
    x: 320,
    y: 80,
    details: { template: 'WhatsApp Catalog Link', variable: 'customer_name' }
  },
  {
    id: 'node-3',
    type: 'condition',
    title: 'Check Customer Tag',
    description: 'Verify if tag matches "Shopify Buyer"',
    x: 320,
    y: 240,
    details: { tag: 'Shopify Buyer' }
  },
  {
    id: 'node-4',
    type: 'action',
    title: 'Send Discount Code',
    description: 'Send discount coupon code "VIP10"',
    x: 600,
    y: 200,
    details: { text: 'Here is your 10% discount code: VIP10!' }
  }
];

export default function FlowBuilder() {
  const [nodes, setNodes] = useState(INITIAL_NODES);
  const [selectedNodeId, setSelectedNodeId] = useState('node-1');
  const [draggingNodeId, setDraggingNodeId] = useState(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  
  // Load flow nodes on mount
  useEffect(() => {
    apiFetch('/api/flow-nodes')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setNodes(data);
        }
      })
      .catch(err => console.error('Error fetching flow nodes:', err));
  }, []);

  const activeNode = nodes.find(n => n.id === selectedNodeId);

  // Handle drag mechanics
  const handleMouseDown = (nodeId, e) => {
    e.preventDefault();
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;
    setDraggingNodeId(nodeId);
    setSelectedNodeId(nodeId);
    setDragOffset({
      x: e.clientX - node.x,
      y: e.clientY - node.y
    });
  };

  // Handle global drag events to prevent sticky cursors
  useEffect(() => {
    const handleGlobalMouseMove = (e) => {
      if (!draggingNodeId) return;
      setNodes(prev => prev.map(node => {
        if (node.id === draggingNodeId) {
          const newX = Math.max(10, Math.min(800, e.clientX - dragOffset.x));
          const newY = Math.max(10, Math.min(450, e.clientY - dragOffset.y));
          return { ...node, x: newX, y: newY };
        }
        return node;
      }));
    };

    const handleGlobalMouseUp = () => {
      setDraggingNodeId(null);
    };

    if (draggingNodeId) {
      window.addEventListener('mousemove', handleGlobalMouseMove);
      window.addEventListener('mouseup', handleGlobalMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleGlobalMouseMove);
      window.removeEventListener('mouseup', handleGlobalMouseUp);
    };
  }, [draggingNodeId, dragOffset]);

  const handleAddNode = (type) => {
    const newId = `node-${Date.now()}`;
    const titles = {
      action: 'Send Message Action',
      condition: 'Condition Check',
      trigger: 'Trigger Event'
    };
    const newNode = {
      id: newId,
      type,
      title: titles[type],
      description: 'Click to configure details...',
      x: 150 + Math.random() * 100,
      y: 150 + Math.random() * 100,
      details: { text: 'New custom step content details.' }
    };
    setNodes([...nodes, newNode]);
    setSelectedNodeId(newId);
  };

  const handleRemoveNode = (nodeId) => {
    setNodes(nodes.filter(n => n.id !== nodeId));
    if (selectedNodeId === nodeId) {
      setSelectedNodeId(null);
    }
  };

  const updateNodeDetail = (key, value) => {
    setNodes(prev => prev.map(n => {
      if (n.id === selectedNodeId) {
        const updatedDetails = { ...n.details, [key]: value };
        // Generate description based on key changes
        let newDesc = n.description;
        if (key === 'keywords') newDesc = `When message contains "${value}"`;
        if (key === 'template') newDesc = `Send ${value} template message`;
        if (key === 'tag') newDesc = `Verify if tag matches "${value}"`;
        if (key === 'text') newDesc = `Send: "${value.substring(0, 30)}..."`;

        return {
          ...n,
          description: newDesc,
          details: updatedDetails
        };
      }
      return n;
    }));
  };

  const handlePublish = async () => {
    try {
      const res = await apiFetch('/api/flow-nodes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes })
      });
      if (res.ok) {
        alert('Flow successfully published and saved to backend! Live triggers have been refreshed.');
      }
    } catch (err) {
      console.error('Error saving flow nodes:', err);
    }
  };

  return (
    <div style={{ padding: '2rem', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* View Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexShrink: 0 }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Network size={28} style={{ color: 'var(--primary-color)' }} />
            No-Code Flow Builder
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Create automated chat structures and routing parameters without writing a single line of code.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={() => handleAddNode('action')}
            style={{
              backgroundColor: '#1e293b',
              color: '#fff',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '8px',
              padding: '0.6rem 1rem',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem'
            }}
          >
            <Plus size={14} />
            Add Action Node
          </button>
          <button
            onClick={handlePublish}
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
              gap: '0.35rem',
              boxShadow: '0 4px 12px var(--primary-glow)'
            }}
          >
            <Play size={14} />
            Publish Flow
          </button>
        </div>
      </div>

      {/* Main Flow Editor Area */}
      <div
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: '1fr 300px',
          gap: '2rem',
          minHeight: 0
        }}
      >
        {/* Canvas Area */}
        <div style={{
          position: 'relative',
          borderRadius: '12px',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          overflow: 'hidden',
          backgroundColor: '#070b19'
        }}>
          <div className="flow-canvas" style={{ minHeight: '480px' }}>
            {/* Draw SVG Connectors between nodes */}
            <svg style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              pointerEvents: 'none',
              zIndex: 1
            }}>
              {/* Trigger to WhatsApp template connector */}
              <path
                d="M 270 160 C 295 160, 295 120, 320 120"
                stroke="var(--primary-color)"
                strokeWidth="2"
                fill="none"
              />
              {/* Trigger to Condition checker connector */}
              <path
                d="M 270 160 C 295 160, 295 280, 320 280"
                stroke="var(--primary-color)"
                strokeWidth="2"
                fill="none"
              />
              {/* Condition to Send Discount code connector */}
              <path
                d="M 540 280 C 570 280, 570 240, 600 240"
                stroke="#64748b"
                strokeWidth="2"
                strokeDasharray="4,4"
                fill="none"
              />
            </svg>

            {/* Render Nodes */}
            {nodes.map(node => {
              const isActive = node.id === selectedNodeId;
              const nodeColors = {
                trigger: { border: '#eab308', text: '#eab308', bg: 'rgba(234, 179, 8, 0.1)' },
                action: { border: '#3b82f6', text: '#3b82f6', bg: 'rgba(59, 130, 246, 0.1)' },
                condition: { border: '#a855f7', text: '#a855f7', bg: 'rgba(168, 85, 247, 0.1)' }
              }[node.type] || { border: '#64748b', text: '#64748b', bg: 'rgba(100, 116, 139, 0.1)' };

              return (
                <div
                  key={node.id}
                  onMouseDown={(e) => handleMouseDown(node.id, e)}
                  style={{
                    position: 'absolute',
                    left: `${node.x}px`,
                    top: `${node.y}px`,
                    width: '220px',
                    backgroundColor: '#0f172a',
                    border: `1.5px solid ${isActive ? 'var(--primary-color)' : 'rgba(255, 255, 255, 0.1)'}`,
                    borderRadius: '10px',
                    padding: '0.85rem',
                    boxShadow: isActive 
                      ? '0 0 15px rgba(0, 194, 142, 0.25), 0 10px 15px -3px rgba(0,0,0,0.3)' 
                      : '0 8px 12px -3px rgba(0,0,0,0.3)',
                    cursor: draggingNodeId === node.id ? 'grabbing' : 'grab',
                    zIndex: 5,
                    userSelect: 'none'
                  }}
                >
                  {/* Connectors */}
                  {node.type !== 'trigger' && <div className="flow-connector input" />}
                  <div className="flow-connector output" />

                  {/* Header badge */}
                  <div style={{
                    display: 'inline-block',
                    backgroundColor: nodeColors.bg,
                    color: nodeColors.text,
                    fontSize: '0.65rem',
                    fontWeight: '700',
                    textTransform: 'uppercase',
                    padding: '0.15rem 0.4rem',
                    borderRadius: '4px',
                    marginBottom: '0.5rem'
                  }}>
                    {node.type}
                  </div>

                  <h4 style={{ fontSize: '0.85rem', color: '#fff', fontWeight: '600', marginBottom: '0.25rem' }}>
                    {node.title}
                  </h4>
                  <p style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: '1.3' }}>
                    {node.description}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Node Configuration Sidebar */}
        <div style={{
          backgroundColor: '#0a101f',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          borderRadius: '12px',
          padding: '1.25rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.25rem'
        }}>
          <h3 style={{ fontSize: '1rem', color: '#fff', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Settings size={16} style={{ color: 'var(--primary-color)' }} />
            Step Settings
          </h3>

          {activeNode ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Step ID</span>
                <div style={{ fontSize: '0.8rem', color: '#94a3b8', fontFamily: 'monospace' }}>{activeNode.id}</div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.4rem' }}>Node Title</label>
                <input
                  type="text"
                  value={activeNode.title}
                  onChange={(e) => {
                    const val = e.target.value;
                    setNodes(prev => prev.map(n => n.id === activeNode.id ? { ...n, title: val } : n));
                  }}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    borderRadius: '6px',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    backgroundColor: '#11192e',
                    color: '#fff',
                    fontSize: '0.8rem',
                    outline: 'none'
                  }}
                />
              </div>

              {/* Dynamic properties based on node content */}
              {activeNode.type === 'trigger' && (
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.4rem' }}>Keyword Triggers</label>
                  <input
                    type="text"
                    value={activeNode.details.keywords || ''}
                    onChange={(e) => updateNodeDetail('keywords', e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      borderRadius: '6px',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      backgroundColor: '#11192e',
                      color: '#fff',
                      fontSize: '0.8rem',
                      outline: 'none'
                    }}
                  />
                  <span style={{ fontSize: '0.65rem', color: '#64748b', marginTop: '0.25rem', display: 'block' }}>
                    Separate multiple keywords with commas.
                  </span>
                </div>
              )}

              {activeNode.type === 'action' && activeNode.id === 'node-2' && (
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.4rem' }}>Template Name</label>
                  <input
                    type="text"
                    value={activeNode.details.template || ''}
                    onChange={(e) => updateNodeDetail('template', e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      borderRadius: '6px',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      backgroundColor: '#11192e',
                      color: '#fff',
                      fontSize: '0.8rem',
                      outline: 'none'
                    }}
                  />
                </div>
              )}

              {activeNode.type === 'action' && activeNode.id !== 'node-2' && (
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.4rem' }}>Message Text</label>
                  <textarea
                    rows={4}
                    value={activeNode.details.text || ''}
                    onChange={(e) => updateNodeDetail('text', e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      borderRadius: '6px',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      backgroundColor: '#11192e',
                      color: '#fff',
                      fontSize: '0.8rem',
                      outline: 'none',
                      resize: 'none',
                      fontFamily: 'inherit'
                    }}
                  />
                </div>
              )}

              {activeNode.type === 'condition' && (
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.4rem' }}>Required Tag</label>
                  <input
                    type="text"
                    value={activeNode.details.tag || ''}
                    onChange={(e) => updateNodeDetail('tag', e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      borderRadius: '6px',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      backgroundColor: '#11192e',
                      color: '#fff',
                      fontSize: '0.8rem',
                      outline: 'none'
                    }}
                  />
                </div>
              )}

              <button
                onClick={() => handleRemoveNode(activeNode.id)}
                style={{
                  marginTop: '1rem',
                  backgroundColor: 'rgba(239, 68, 68, 0.15)',
                  color: '#ef4444',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '0.5rem',
                  fontSize: '0.8rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.35rem'
                }}
              >
                <Trash2 size={12} />
                Delete Node
              </button>
            </div>
          ) : (
            <div style={{
              padding: '1.5rem 1rem',
              borderRadius: '6px',
              backgroundColor: '#11192e',
              textAlign: 'center',
              fontSize: '0.8rem',
              color: '#64748b'
            }}>
              <Info size={24} style={{ margin: '0 auto 0.5rem', opacity: 0.5 }} />
              Select a node on the canvas to configure settings. Drag nodes to reposition them.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
