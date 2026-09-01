"use client";

import React from 'react';
import { usePathname } from 'next/navigation';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { LanguageSelector } from '../../components/LanguageSelector';
import { Navigation } from '../../components/Navigation';
import { SessionTimeoutModal } from '../../components/SessionTimeoutModal';

export default function LangLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const lng = pathname?.split('/')[1] || 'en';

  return (
    <ThemeProvider>
      <div lang={lng}>
        <SessionTimeoutModal />
        <a
          href="#main-content"
          className="skip-link"
          style={{
            position: 'fixed',
            top: '-100%',
            left: '8px',
            zIndex: 10000,
            padding: '10px 16px',
            background: 'var(--color-primary)',
            color: '#fff',
            borderRadius: '0 0 8px 8px',
            fontSize: '14px',
            fontWeight: '600',
            textDecoration: 'none',
            transition: 'top 0.15s ease',
          }}
        >
          Skip to content
        </a>
        <NavigationWithLang lng={lng} />
        <div
          id="main-content"
          style={{ paddingTop: '80px', minHeight: '100vh', overflowX: 'hidden' }}
        >
          {children}
        </div>
      </div>
    </ThemeProvider>
  );
}

function NavigationWithLang({ lng }: { lng: string }) {
  return (
    <>
      <Navigation lng={lng} />
      <div
        className="lang-selector-fixed"
        style={{
          position: 'fixed',
          top: '14px',
          right: '24px',
          zIndex: 1000,
        }}
      >
        <LanguageSelector />
      </div>
    </>
  );
}
