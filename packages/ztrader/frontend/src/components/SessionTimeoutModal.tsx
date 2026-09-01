"use client";

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter, usePathname } from 'next/navigation';

const SESSION_TIMEOUT_MS = 30 * 60 * 1000;
const WARNING_BEFORE_MS = 60 * 1000;

export function SessionTimeoutModal() {
  const router = useRouter();
  const pathname = usePathname();
  const [showWarning, setShowWarning] = useState(false);
  const [showExpired, setShowExpired] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const warningRef = useRef<NodeJS.Timeout | null>(null);

  const getToken = () =>
    typeof window !== 'undefined'
      ? window.localStorage.getItem('ztrader_admin_token')
      : null;

  const resetTimers = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (warningRef.current) clearTimeout(warningRef.current);
    setShowWarning(false);
    setShowExpired(false);

    const token = getToken();
    if (!token) return;

    warningRef.current = setTimeout(
      () => setShowWarning(true),
      SESSION_TIMEOUT_MS - WARNING_BEFORE_MS,
    );
    timerRef.current = setTimeout(() => {
      setShowWarning(false);
      setShowExpired(true);
      window.localStorage.removeItem('ztrader_admin_token');
    }, SESSION_TIMEOUT_MS);
  }, []);

  useEffect(() => {
    resetTimers();
    const events = ['mousedown', 'keydown', 'touchstart', 'scroll'];
    const onActivity = () => {
      if (getToken()) resetTimers();
    };
    events.forEach((e) => window.addEventListener(e, onActivity, { passive: true }));
    return () => {
      events.forEach((e) => window.removeEventListener(e, onActivity));
      if (timerRef.current) clearTimeout(timerRef.current);
      if (warningRef.current) clearTimeout(warningRef.current);
    };
  }, [pathname, resetTimers]);

  const handleStayLoggedIn = () => {
    resetTimers();
  };

  const handleLogout = () => {
    window.localStorage.removeItem('ztrader_admin_token');
    setShowWarning(false);
    setShowExpired(false);
    router.push(loginPath());
  };

  const loginPath = () => {
    const lng = pathname?.split('/')[1] || 'en';
    return `/${lng}/login`;
  };

  if (!showWarning && !showExpired) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={showExpired ? 'Session expired' : 'Session timeout warning'}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 99999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.7)',
        backdropFilter: 'blur(4px)',
      }}
    >
      <div
        className="glass-card-static"
        style={{
          maxWidth: '400px',
          width: '90%',
          padding: '28px',
          textAlign: 'center',
        }}
      >
        {showExpired ? (
          <>
            <div
              style={{
                width: '56px',
                height: '56px',
                borderRadius: '50%',
                background: 'rgba(239,68,68,0.15)',
                border: '2px solid rgba(239,68,68,0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px',
                fontSize: '24px',
                color: '#EF4444',
              }}
            >
              ⏰
            </div>
            <h2 className="h3" style={{ marginBottom: '8px' }}>Session Expired</h2>
            <p className="text-secondary" style={{ fontSize: '14px', marginBottom: '24px', lineHeight: '1.5' }}>
              Your session has timed out due to inactivity. Please log in again.
            </p>
            <button
              onClick={handleLogout}
              className="btn-base btn-primary btn-full"
              autoFocus
            >
              Go to Login
            </button>
          </>
        ) : (
          <>
            <div
              style={{
                width: '56px',
                height: '56px',
                borderRadius: '50%',
                background: 'rgba(245,158,11,0.15)',
                border: '2px solid rgba(245,158,11,0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px',
                fontSize: '24px',
                color: '#F59E0B',
              }}
            >
              ⏳
            </div>
            <h2 className="h3" style={{ marginBottom: '8px' }}>Session Timeout</h2>
            <p className="text-secondary" style={{ fontSize: '14px', marginBottom: '24px', lineHeight: '1.5' }}>
              Your session will expire in 1 minute due to inactivity.
            </p>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                onClick={handleLogout}
                className="btn-base btn-ghost"
                style={{ flex: 1 }}
              >
                Log Out
              </button>
              <button
                onClick={handleStayLoggedIn}
                className="btn-base btn-primary"
                style={{ flex: 1 }}
                autoFocus
              >
                Stay Logged In
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
