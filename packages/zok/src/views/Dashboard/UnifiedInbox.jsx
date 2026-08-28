import { useState, useEffect, useRef } from 'react';
import { 
  Search, MessageSquare, Send, Tag, 
  ShoppingBag, RefreshCw 
} from 'lucide-react';
import { apiFetch } from '../../lib/api';

const INITIAL_CHATS = [
  {
    id: 1,
    name: 'Panacee Medical Centre',
    avatar: 'PMC',
    channel: 'line',
    unread: 2,
    time: '10:24 AM',
    messages: [
      { sender: 'customer', text: 'Hello, what are your clinic hours for tomorrow?', time: '10:20 AM' },
      { sender: 'customer', text: 'I would like to book a general checkup.', time: '10:21 AM' }
    ],
    details: {
      phone: '+66 2 712 0333',
      email: 'info@panacee.com',
      assigned: 'Sarah Connor',
      tags: ['New Lead', 'LINE OA', 'Medical Service'],
      orders: [
        { id: 'ORD-8812', date: '2026-08-01', total: '$149.00', status: 'Delivered' }
      ]
    }
  },
  {
    id: 2,
    name: 'Karmart Customer Support',
    avatar: 'KM',
    channel: 'whatsapp',
    unread: 0,
    time: '9:15 AM',
    messages: [
      { sender: 'customer', text: 'Hi, is my order #5512 shipped yet?', time: '9:10 AM' },
      { sender: 'agent', text: 'Hello! Yes, it was dispatched yesterday. Your tracking link is: kmt.express/38821', time: '9:12 AM' },
      { sender: 'customer', text: 'Awesome, thank you!', time: '9:15 AM' }
    ],
    details: {
      phone: '+65 9123 4567',
      email: 'support@karmart.com.sg',
      assigned: 'Alex Rivera',
      tags: ['Shopify Buyer', 'WhatsApp', 'VIP'],
      orders: [
        { id: 'ORD-5512', date: '2026-08-09', total: '$48.50', status: 'Shipped' },
        { id: 'ORD-4390', date: '2026-07-15', total: '$112.00', status: 'Delivered' }
      ]
    }
  },
  {
    id: 3,
    name: 'Wilfried Buiron',
    avatar: 'WB',
    channel: 'messenger',
    unread: 1,
    time: 'Yesterday',
    messages: [
      { sender: 'customer', text: 'Do you offer custom API endpoints for Shopify syncing?', time: 'Yesterday' }
    ],
    details: {
      phone: '+1 650 882 1190',
      email: 'wilfried@zok.zeaz.dev',
      assigned: 'Sarah Connor',
      tags: ['Enterprise', 'Messenger', 'Developer'],
      orders: []
    }
  },
  {
    id: 4,
    name: 'Nattapong (TikTok Seller)',
    avatar: 'NT',
    channel: 'tiktok',
    unread: 0,
    time: 'Yesterday',
    messages: [
      { sender: 'customer', text: 'Thanks for the quick response. Will test the AI automation feature tonight.', time: 'Yesterday' }
    ],
    details: {
      phone: '+66 89 123 4567',
      email: 'nattapong.tkt@gmail.com',
      assigned: 'Automated Bot',
      tags: ['TikTok Shop', 'Active Demo'],
      orders: [
        { id: 'TKT-9912', date: '2026-08-05', total: '$29.90', status: 'Delivered' }
      ]
    }
  },
  {
    id: 5,
    name: 'Emily Davis',
    avatar: 'ED',
    channel: 'shopify',
    unread: 0,
    time: '2 days ago',
    messages: [
      { sender: 'customer', text: 'I received a damaged package. Can I get a replacement?', time: '2 days ago' },
      { sender: 'agent', text: 'We are very sorry to hear that. I have triggered a replacement shipment. Your new order code is ORD-9011.', time: '2 days ago' }
    ],
    details: {
      phone: '+44 7700 900077',
      email: 'emily.davis@gmail.com',
      assigned: 'Alex Rivera',
      tags: ['Shopify Buyer', 'Support Ticket'],
      orders: [
        { id: 'ORD-9011', date: '2026-08-08', total: '$0.00', status: 'Processing' },
        { id: 'ORD-8321', date: '2026-07-28', total: '$85.00', status: 'Delivered' }
      ]
    }
  }
];

export default function UnifiedInbox() {
  const [chats, setChats] = useState(INITIAL_CHATS);
  const [activeChatId, setActiveChatId] = useState(1);
  const [filterChannel, setFilterChannel] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [messageInput, setMessageInput] = useState('');
  const [newTagInput, setNewTagInput] = useState('');
  const messagesEndRef = useRef(null);
  const activeChatIdRef = useRef(activeChatId);
  activeChatIdRef.current = activeChatId;

  const activeChat = chats.find(c => c.id === activeChatId) || chats[0];

  // Load chats on mount and poll to get simulated customer responses
  useEffect(() => {
    const loadChats = async () => {
      try {
        const res = await apiFetch('/api/chats');
        const data = await res.json();
        setChats(data);
      } catch (err) {
        console.error('Error fetching chats:', err);
      }
    };
    loadChats();
    const interval = setInterval(loadChats, 2000);
    return () => clearInterval(interval);
  }, []);

  // Scroll to bottom of conversation
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeChat?.messages]);

  // Handle Mark as Read on server
  useEffect(() => {
    if (activeChat && activeChat.unread > 0) {
      apiFetch(`/api/chats/${activeChat.id}/read`, { method: 'POST' })
        .then(res => res.json())
        .then(updatedChat => {
          setChats(prev => prev.map(c => c.id === updatedChat.id ? updatedChat : c));
        })
        .catch(err => console.error('Error marking read:', err));
    }
  }, [activeChatId, activeChat]);

  // Filter chats by channel & search query
  const filteredChats = chats.filter(chat => {
    const matchesChannel = filterChannel === 'all' || chat.channel === filterChannel;
    const matchesSearch = chat.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      chat.messages.some(m => m.text.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesChannel && matchesSearch;
  });

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!messageInput.trim()) return;

    const sentText = messageInput;
    setMessageInput('');

    try {
      const res = await apiFetch(`/api/chats/${activeChatId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sender: 'agent',
          text: sentText,
          activeChatId: activeChatId
        })
      });
      const updatedChat = await res.json();
      setChats(prev => prev.map(c => c.id === updatedChat.id ? updatedChat : c));
    } catch (err) {
      console.error('Error sending message:', err);
    }
  };

  const handleAddTag = async (e) => {
    e.preventDefault();
    if (!newTagInput.trim()) return;

    const updatedTags = [...activeChat.details.tags, newTagInput.trim()];
    setNewTagInput('');

    try {
      const res = await apiFetch(`/api/chats/${activeChatId}/tags`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tags: updatedTags })
      });
      const updatedChat = await res.json();
      setChats(prev => prev.map(c => c.id === updatedChat.id ? updatedChat : c));
    } catch (err) {
      console.error('Error adding tag:', err);
    }
  };

  const handleRemoveTag = async (tagToRemove) => {
    const updatedTags = activeChat.details.tags.filter(t => t !== tagToRemove);

    try {
      const res = await apiFetch(`/api/chats/${activeChatId}/tags`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tags: updatedTags })
      });
      const updatedChat = await res.json();
      setChats(prev => prev.map(c => c.id === updatedChat.id ? updatedChat : c));
    } catch (err) {
      console.error('Error removing tag:', err);
    }
  };

  return (
    <div style={{ display: 'flex', height: '100%', width: '100%' }}>
      {/* 1. Chat List & Filters Sidebar */}
      <div style={{
        width: '320px',
        borderRight: '1px solid rgba(255, 255, 255, 0.05)',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#0a101f',
        flexShrink: 0
      }}>
        {/* Search */}
        <div style={{ padding: '1rem', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', color: '#64748b' }} />
            <input
              type="text"
              placeholder="Search chat or message..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '0.6rem 1rem 0.6rem 2.2rem',
                borderRadius: '8px',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                backgroundColor: '#11192e',
                color: '#fff',
                fontSize: '0.9rem',
                outline: 'none'
              }}
            />
          </div>
        </div>

        {/* Channel Filters */}
        <div style={{
          display: 'flex',
          gap: '0.4rem',
          padding: '0.75rem 1rem',
          overflowX: 'auto',
          borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
          whiteSpace: 'nowrap'
        }}>
          {['all', 'whatsapp', 'line', 'messenger', 'tiktok', 'shopify'].map(channel => (
            <button
              key={channel}
              onClick={() => setFilterChannel(channel)}
              style={{
                padding: '0.35rem 0.7rem',
                borderRadius: '15px',
                border: 'none',
                backgroundColor: filterChannel === channel ? 'var(--primary-color)' : '#1e293b',
                color: filterChannel === channel ? '#fff' : '#94a3b8',
                fontSize: '0.75rem',
                fontWeight: '600',
                cursor: 'pointer',
                textTransform: 'capitalize',
                transition: 'all 0.2s'
              }}
            >
              {channel}
            </button>
          ))}
        </div>

        {/* Chats Scroll Area */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {filteredChats.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
              <MessageSquare size={32} style={{ marginBottom: '0.5rem', opacity: 0.5 }} />
              <p style={{ fontSize: '0.85rem' }}>No conversations found</p>
            </div>
          ) : (
            filteredChats.map(chat => (
              <div
                key={chat.id}
                onClick={() => setActiveChatId(chat.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  padding: '1rem',
                  borderBottom: '1px solid rgba(255, 255, 255, 0.02)',
                  cursor: 'pointer',
                  backgroundColor: activeChatId === chat.id ? 'rgba(255, 255, 255, 0.03)' : 'transparent',
                  borderLeft: activeChatId === chat.id ? '3px solid var(--primary-color)' : '3px solid transparent',
                  transition: 'background-color 0.2s'
                }}
              >
                {/* Avatar */}
                <div style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  backgroundColor: 'rgba(0, 194, 142, 0.1)',
                  color: 'var(--primary-color)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: '700',
                  fontSize: '0.85rem',
                  flexShrink: 0
                }}>
                  {chat.avatar}
                </div>

                {/* Details */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                    <h4 style={{
                      fontSize: '0.9rem',
                      fontWeight: '600',
                      color: '#f8fafc',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}>
                      {chat.name}
                    </h4>
                    <span style={{ fontSize: '0.7rem', color: '#64748b' }}>{chat.time}</span>
                  </div>
                  
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <p style={{
                      fontSize: '0.8rem',
                      color: '#94a3b8',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      marginRight: '0.5rem'
                    }}>
                      {chat.messages[chat.messages.length - 1]?.text}
                    </p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <span className={`channel-pill channel-${chat.channel}`} style={{ scale: '0.8' }}>
                        {chat.channel}
                      </span>
                      {chat.unread > 0 && (
                        <span style={{
                          backgroundColor: 'var(--primary-color)',
                          color: '#fff',
                          fontSize: '0.65rem',
                          fontWeight: '700',
                          padding: '0.15rem 0.35rem',
                          borderRadius: '10px',
                          display: 'inline-block'
                        }}>
                          {chat.unread}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 2. Main Chat Conversation Screen */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#070b19'
      }}>
        {/* Chat Header */}
        <div style={{
          height: '65px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
          padding: '0 1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: '#0a101f'
        }}>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: '600', color: '#fff' }}>{activeChat.name}</h3>
            <span style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <span style={{ width: '6px', height: '6px', backgroundColor: 'var(--primary-color)', borderRadius: '50%' }}></span>
              Connected • Assigned to {activeChat.details.assigned}
            </span>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <span className={`channel-pill channel-${activeChat.channel}`}>
              {activeChat.channel.toUpperCase()}
            </span>
          </div>
        </div>

        {/* Message Thread */}
        <div style={{
          flex: 1,
          padding: '1.5rem',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem'
        }}>
          {activeChat.messages.map((msg, i) => {
            const isAgent = msg.sender === 'agent';
            return (
              <div
                key={i}
                style={{
                  display: 'flex',
                  justifyContent: isAgent ? 'flex-end' : 'flex-start',
                  width: '100%'
                }}
              >
                <div style={{
                  maxWidth: '70%',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: isAgent ? 'flex-end' : 'flex-start'
                }}>
                  <div style={{
                    padding: '0.75rem 1rem',
                    borderRadius: isAgent ? '18px 18px 0px 18px' : '18px 18px 18px 0px',
                    backgroundColor: isAgent ? 'var(--primary-color)' : '#11192e',
                    color: '#fff',
                    fontSize: '0.9rem',
                    lineHeight: '1.4',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                  }}>
                    {msg.text}
                  </div>
                  <span style={{ fontSize: '0.65rem', color: '#64748b', marginTop: '0.25rem' }}>{msg.time}</span>
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <form
          onSubmit={handleSendMessage}
          style={{
            padding: '1rem 1.5rem',
            borderTop: '1px solid rgba(255, 255, 255, 0.05)',
            display: 'flex',
            gap: '0.75rem',
            backgroundColor: '#0a101f'
          }}
        >
          <input
            type="text"
            placeholder="Type your message..."
            value={messageInput}
            onChange={(e) => setMessageInput(e.target.value)}
            style={{
              flex: 1,
              padding: '0.75rem 1rem',
              borderRadius: '8px',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              backgroundColor: '#11192e',
              color: '#fff',
              outline: 'none',
              fontSize: '0.9rem'
            }}
          />
          <button
            type="submit"
            style={{
              padding: '0.75rem 1.25rem',
              borderRadius: '8px',
              border: 'none',
              backgroundColor: 'var(--primary-color)',
              color: '#fff',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.35rem',
              transition: 'background-color 0.2s'
            }}
          >
            <Send size={16} />
            <span>Send</span>
          </button>
        </form>
      </div>

      {/* 3. Customer CRM Panel (Right) */}
      <div style={{
        width: '280px',
        borderLeft: '1px solid rgba(255, 255, 255, 0.05)',
        backgroundColor: '#0a101f',
        padding: '1.5rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.5rem',
        overflowY: 'auto',
        flexShrink: 0
      }}>
        {/* Contact Info Header */}
        <div>
          <h4 style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', marginBottom: '0.75rem', fontWeight: '700' }}>
            Customer Profile
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.85rem' }}>
            <div>
              <div style={{ color: '#64748b' }}>Phone</div>
              <div style={{ color: '#e2e8f0', fontWeight: '500' }}>{activeChat.details.phone}</div>
            </div>
            <div>
              <div style={{ color: '#64748b' }}>Email</div>
              <div style={{ color: '#e2e8f0', fontWeight: '500', wordBreak: 'break-all' }}>{activeChat.details.email}</div>
            </div>
          </div>
        </div>

        {/* Tags management */}
        <div>
          <h4 style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', marginBottom: '0.75rem', fontWeight: '700' }}>
            Tags
          </h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginBottom: '0.75rem' }}>
            {activeChat.details.tags.map(t => (
              <span
                key={t}
                onClick={() => handleRemoveTag(t)}
                title="Click to remove tag"
                style={{
                  backgroundColor: 'rgba(0, 194, 142, 0.1)',
                  color: 'var(--primary-color)',
                  fontSize: '0.7rem',
                  fontWeight: '600',
                  padding: '0.2rem 0.5rem',
                  borderRadius: '15px',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.15rem'
                }}
              >
                <Tag size={10} />
                {t}
                <span style={{ fontSize: '0.8rem', marginLeft: '0.15rem', color: '#f43f5e' }}>×</span>
              </span>
            ))}
          </div>

          <form onSubmit={handleAddTag} style={{ display: 'flex', gap: '0.25rem' }}>
            <input
              type="text"
              placeholder="+ Add tag..."
              value={newTagInput}
              onChange={(e) => setNewTagInput(e.target.value)}
              style={{
                flex: 1,
                padding: '0.4rem 0.6rem',
                fontSize: '0.75rem',
                borderRadius: '4px',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                backgroundColor: '#11192e',
                color: '#fff',
                outline: 'none'
              }}
            />
            <button
              type="submit"
              style={{
                backgroundColor: '#1e293b',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                padding: '0 0.5rem',
                cursor: 'pointer',
                fontSize: '0.8rem'
              }}
            >
              +
            </button>
          </form>
        </div>

        {/* Shopify Order Integration */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h4 style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <ShoppingBag size={12} />
              Shopify Sync
            </h4>
            <span style={{ fontSize: '0.65rem', color: 'var(--primary-color)', display: 'flex', alignItems: 'center', gap: '0.1rem' }}>
              <RefreshCw size={10} className="glow-active" />
              Synced
            </span>
          </div>

          {activeChat.details.orders.length === 0 ? (
            <div style={{
              padding: '1rem',
              borderRadius: '6px',
              backgroundColor: '#11192e',
              textAlign: 'center',
              fontSize: '0.75rem',
              color: '#64748b'
            }}>
              No customer order history synced.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {activeChat.details.orders.map(order => (
                <div
                  key={order.id}
                  style={{
                    backgroundColor: '#11192e',
                    border: '1px solid rgba(255, 255, 255, 0.05)',
                    borderRadius: '6px',
                    padding: '0.6rem 0.8rem',
                    fontSize: '0.75rem'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                    <span style={{ fontWeight: '600', color: '#fff' }}>{order.id}</span>
                    <span style={{ color: '#10b981', fontWeight: '600' }}>{order.total}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8' }}>
                    <span>{order.date}</span>
                    <span style={{
                      color: order.status === 'Delivered' ? '#10b981' : order.status === 'Shipped' ? '#3b82f6' : '#f59e0b',
                      fontSize: '0.7rem'
                    }}>{order.status}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
