"use client";

import React from 'react';

interface ToastProps {
  msg: string;
  type: 'success' | 'error';
}

export function Toast({ msg, type }: ToastProps) {
  const ok = type === 'success';
  return (
    <div
      role="alert"
      aria-live="assertive"
      tabIndex={-1}
      className="animate-slide-up"
      style={{
        position: 'fixed',
        bottom: '28px',
        right: '28px',
        zIndex: 9999,
        padding: '14px 20px',
        borderRadius: 'var(--radius-lg)',
        background: ok ? 'rgba(10,26,20,0.97)' : 'rgba(26,10,10,0.97)',
        border: `1px solid ${ok ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)'}`,
        color: ok ? '#10B981' : '#EF4444',
        fontSize: '14px',
        fontWeight: '600',
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        boxShadow: `0 8px 32px ${ok ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)'}`,
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        maxWidth: '420px',
      }}
    >
      {ok ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      )}
      {msg}
    </div>
  );
}
