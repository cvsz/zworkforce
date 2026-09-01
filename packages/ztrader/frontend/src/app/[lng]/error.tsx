'use client';

import { useEffect } from 'react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Route error:', error);
  }, [error]);

  return (
    <div
      style={{
        maxWidth: '480px',
        margin: '120px auto',
        padding: '48px 32px',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          width: '56px',
          height: '56px',
          margin: '0 auto 20px',
          borderRadius: '50%',
          background: 'rgba(239,68,68,0.1)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--color-danger)',
        }}
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h2
        style={{
          fontSize: '20px',
          fontWeight: '700',
          marginBottom: '8px',
          color: 'var(--text-primary)',
        }}
      >
        Something went wrong
      </h2>
      <p
        style={{
          fontSize: '14px',
          color: 'var(--text-muted)',
          marginBottom: '28px',
          lineHeight: 1.6,
        }}
      >
        An unexpected error occurred. Please try again.
      </p>
      <button
        onClick={reset}
        className="btn-base btn-primary"
        style={{
          padding: '12px 32px',
          fontSize: '14px',
          fontWeight: '600',
          cursor: 'pointer',
        }}
      >
        Try Again
      </button>
    </div>
  );
}
