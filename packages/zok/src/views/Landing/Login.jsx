import { useState } from 'react';
import { ArrowRight, Lock, Mail, ShieldCheck } from 'lucide-react';

export default function Login({ onSwitchToRegister, onLaunchApp, isDark }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const textColor = isDark ? '#fff' : '#0f172a';
  const mutedColor = isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)';
  const inputBg = isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff';
  const borderStyle = `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError('Please enter your email and password.');
      return;
    }

    setError('');
    setIsSubmitting(true);
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(payload.error || 'Unable to sign in.');
        return;
      }
      await onLaunchApp();
    } catch {
      setError('The authentication service is unavailable.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: '400px', margin: '6rem auto', color: textColor, padding: '2rem', border: borderStyle, borderRadius: '16px', backgroundColor: isDark ? 'rgba(15,23,42,0.2)' : '#fff', boxShadow: '0 4px 30px rgba(0,0,0,0.05)' }}>
      <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
        <h2 style={{ fontSize: '1.8rem', letterSpacing: '-0.02em', marginBottom: '0.5rem' }}>Welcome Back</h2>
        <p style={{ color: mutedColor, fontSize: '0.85rem' }}>Log in to access your omnichannel sales dashboard.</p>
        {error && (
          <p role="alert" style={{ color: '#f87171', fontSize: '0.8rem', marginTop: '0.75rem' }}>{error}</p>
        )}
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '600', marginBottom: '0.5rem' }}>Email Address</label>
          <div style={{ position: 'relative' }}>
            <Mail size={14} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: mutedColor }} />
            <input
              type="email"
              required
              placeholder="name@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ width: '100%', padding: '0.75rem 0.75rem 0.75rem 2.25rem', borderRadius: '8px', border: borderStyle, backgroundColor: inputBg, color: textColor, outline: 'none' }}
            />
          </div>
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '600', marginBottom: '0.5rem' }}>Password</label>
          <div style={{ position: 'relative' }}>
            <Lock size={14} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: mutedColor }} />
            <input
              type="password"
              required
              placeholder="••••••••"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: '100%', padding: '0.75rem 0.75rem 0.75rem 2.25rem', borderRadius: '8px', border: borderStyle, backgroundColor: inputBg, color: textColor, outline: 'none' }}
            />
          </div>
        </div>

        <button type="submit" disabled={isSubmitting} className="btn-primary" style={{ width: '100%', padding: '0.8rem', justifyContent: 'center', borderRadius: '8px', fontSize: '0.9rem', marginTop: '0.5rem', opacity: isSubmitting ? 0.7 : 1 }}>
          {isSubmitting ? 'Signing in...' : 'Login to Dashboard'} <ArrowRight size={16} />
        </button>
      </form>

      <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center', marginTop: '1.5rem', fontSize: '0.85rem' }}>
        <span style={{ color: mutedColor }}>New to Zok?</span>
        <button onClick={onSwitchToRegister} style={{ background: 'transparent', border: 'none', color: 'var(--primary-color)', cursor: 'pointer', padding: 0, fontWeight: '600' }}>Create Account</button>
      </div>

      <div style={{ display: 'flex', justifyBetween: 'center', alignItems: 'center', gap: '0.35rem', marginTop: '2.5rem', fontSize: '0.7rem', color: mutedColor, borderTop: borderStyle, paddingTop: '1rem' }}>
        <ShieldCheck size={12} style={{ color: 'var(--primary-color)' }} /> Session protected by server authentication.
      </div>
    </div>
  );
}
