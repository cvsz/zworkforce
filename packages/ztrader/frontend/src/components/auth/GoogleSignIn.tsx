"use client";

import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

interface GoogleSignInProps {
  onSuccess?: (user: unknown) => void;
  onError?: (error: string) => void;
}

export function GoogleSignIn({ onSuccess, onError }: GoogleSignInProps) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);

  const handleGoogleSignIn = async () => {
    setLoading(true);
    try {
      const backendUrl =
        process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      const response = await fetch(
        `${backendUrl}/auth/google/authorize`,
      );
      if (!response.ok) {
        throw new Error(`Authorization service returned ${response.status}`);
      }
      const text = await response.text();
      let data: { authorization_url?: string };
      try {
        data = JSON.parse(text);
      } catch {
        throw new Error('Backend did not return JSON — check auth service URL');
      }
      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      } else {
        throw new Error('Response missing authorization URL');
      }
    } catch (error) {
      console.error('Google Sign-In error:', error);
      if (onError) {
        onError(
          error instanceof Error ? error.message : 'Sign-in failed',
        );
      }
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleGoogleSignIn}
      disabled={loading}
      aria-label={loading ? 'Connecting...' : t('auth.google_signin')}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '12px',
        width: '100%',
        padding: '12px 24px',
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-input)',
        borderRadius: 'var(--radius-md)',
        color: 'var(--text-primary)',
        fontSize: '16px',
        fontWeight: '600',
        cursor: loading ? 'not-allowed' : 'pointer',
        opacity: loading ? 0.6 : 1,
        transition: 'var(--transition-smooth)',
      }}
      onMouseEnter={(e) => {
        if (!loading) {
          e.currentTarget.style.background = 'var(--bg-surface-hover)';
          e.currentTarget.style.borderColor =
            'var(--color-primary-border)';
          e.currentTarget.style.boxShadow = 'var(--shadow-glow-primary)';
        }
      }}
      onMouseLeave={(e) => {
        if (!loading) {
          e.currentTarget.style.background = 'var(--bg-surface)';
          e.currentTarget.style.borderColor = 'var(--border-input)';
          e.currentTarget.style.boxShadow = 'none';
        }
      }}
    >
      <svg width="20" height="20" viewBox="0 0 18 18">
        <path
          fill="#4285F4"
          d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"
        />
        <path
          fill="#34A853"
          d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z"
        />
        <path
          fill="#FBBC05"
          d="M3.964 10.707c-.18-.54-.282-1.117-.282-1.707s.102-1.167.282-1.707V4.961H.957C.347 6.175 0 7.55 0 9s.348 2.825.957 4.039l3.007-2.332z"
        />
        <path
          fill="#EA4335"
          d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.961L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"
        />
      </svg>
      <span>{loading ? 'Connecting...' : t('auth.google_signin')}</span>
    </button>
  );
}
