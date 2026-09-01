"use client";

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useTranslation } from 'react-i18next';
import { initI18n } from '../app/i18n/client';

interface NavigationProps {
  lng: string;
}

const menuConfig = [
  {
    key: 'dashboard',
    i18nKey: 'menu.dashboard',
    path: 'dashboard',
    icon: (
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
      </svg>
    ),
  },
  {
    key: 'settings',
    i18nKey: 'menu.settings',
    path: 'settings',
    icon: (
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    ),
  },
  {
    key: 'admin',
    i18nKey: 'menu.admin',
    path: 'admin',
    icon: (
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
  },
  {
    key: 'tradingagents',
    i18nKey: 'menu.tradingagents',
    path: 'tradingagents',
    icon: (
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        <line x1="9" y1="10" x2="15" y2="10" />
        <line x1="12" y1="7" x2="12" y2="13" />
      </svg>
    ),
  },
];

export function Navigation({ lng }: NavigationProps) {
  const pathname = usePathname();
  const router = useRouter();
  initI18n(lng);
  const { t } = useTranslation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(
      typeof window !== 'undefined' ? window.location.search : '',
    );
    const urlToken = params.get('token');
    if (urlToken) {
      localStorage.setItem('ztrader_admin_token', urlToken);
      const clean = window.location.pathname + window.location.hash;
      window.history.replaceState(null, '', clean);
    }

    const token =
      typeof window !== 'undefined'
        ? window.localStorage.getItem('ztrader_admin_token')
        : null;
    setIsLoggedIn(!!token);

    const onStorage = () => {
      const t =
        typeof window !== 'undefined'
          ? window.localStorage.getItem('ztrader_admin_token')
          : null;
      setIsLoggedIn(!!t);
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [pathname]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [mobileOpen]);

  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mobileOpen || !drawerRef.current) return;
    const firstFocusable = drawerRef.current.querySelector<HTMLElement>('a, button, [tabindex]:not([tabindex="-1"])');
    firstFocusable?.focus();
  }, [mobileOpen]);

  useEffect(() => {
    if (!mobileOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !drawerRef.current) return;
      const focusable = drawerRef.current.querySelectorAll<HTMLElement>('a, button, [tabindex]:not([tabindex="-1"])');
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [mobileOpen]);

  const handleLogout = (e: React.MouseEvent) => {
    e.preventDefault();
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem('ztrader_admin_token');
    }
    setIsLoggedIn(false);
    router.push(`/${lng}/login`);
  };

  const isActive = (path: string) => pathname === `/${lng}/${path}`;

  return (
    <>
      <style>{`
        .nav-root {
          position: fixed;
          top: 0; left: 0; right: 0;
          z-index: 999;
          transition: var(--transition-smooth);
        }
        .nav-root.scrolled {
          background: rgba(6, 9, 19, 0.92);
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          border-bottom: 1px solid var(--color-primary-border);
          box-shadow: 0 4px 32px rgba(0,0,0,0.4), 0 1px 0 var(--color-primary-glow-soft);
        }
        .nav-root.top {
          background: rgba(6, 9, 19, 0.6);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          border-bottom: 1px solid var(--border-subtle);
        }
        .nav-inner {
          max-width: 1280px;
          margin: 0 auto;
          padding: 0 24px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          height: 68px;
        }
        .nav-brand {
          display: flex;
          align-items: center;
          gap: 10px;
          text-decoration: none;
          user-select: none;
        }
        .nav-brand-dot {
          position: relative;
          width: 10px; height: 10px;
        }
        .nav-brand-dot-core {
          width: 10px; height: 10px;
          border-radius: 50%;
          background: var(--color-primary);
          box-shadow: 0 0 10px var(--color-primary), 0 0 20px var(--color-primary-glow);
        }
        .nav-brand-dot-ring {
          position: absolute;
          inset: -3px;
          border-radius: 50%;
          border: 1px solid var(--color-primary-border);
          animation: nav-pulse 2.5s infinite ease-in-out;
        }
        @keyframes nav-pulse {
          0%, 100% { opacity: 0.4; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.15); }
        }
        .nav-brand-name {
          font-size: 22px;
          font-weight: 800;
          color: var(--text-primary);
          letter-spacing: 0.02em;
        }
        .nav-brand-name span { color: var(--color-primary); }
        .nav-menu {
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .nav-link {
          display: flex;
          align-items: center;
          gap: 7px;
          padding: 8px 14px;
          border-radius: 10px;
          text-decoration: none;
          font-size: 14px;
          font-weight: 500;
          color: var(--text-muted);
          background: transparent;
          border: 1px solid transparent;
          transition: var(--transition-smooth);
          white-space: nowrap;
          position: relative;
          cursor: pointer;
        }
        .nav-link:hover {
          color: var(--text-primary);
          border-color: var(--border-subtle);
          transform: translateY(-1px);
          background: rgba(255,255,255,0.03);
        }
        .nav-link.active {
          color: var(--color-primary-light);
          background: var(--color-primary-bg);
          border-color: var(--color-primary-border);
          font-weight: 600;
          box-shadow: 0 0 20px var(--color-primary-glow-soft), inset 0 1px 0 rgba(255,255,255,0.05);
        }
        .nav-link-icon { opacity: 0.7; flex-shrink: 0; }
        .nav-link.active .nav-link-icon { opacity: 1; color: var(--color-primary-light); }
        .nav-divider {
          width: 1px; height: 20px;
          background: var(--border-subtle);
          margin: 0 6px;
        }
        .nav-hamburger {
          display: none;
          flex-direction: column;
          gap: 5px;
          cursor: pointer;
          padding: 8px;
          border-radius: 8px;
          border: 1px solid var(--border-subtle);
          background: rgba(255,255,255,0.03);
          transition: var(--transition-fast);
        }
        .nav-hamburger:hover { background: rgba(255,255,255,0.07); border-color: var(--color-primary-border); }
        .nav-hamburger-bar {
          width: 20px; height: 2px;
          background: var(--text-muted);
          border-radius: 2px;
          transition: var(--transition-smooth);
        }
        .nav-hamburger.open .nav-hamburger-bar:nth-child(1) { transform: translateY(7px) rotate(45deg); background: var(--color-primary-light); }
        .nav-hamburger.open .nav-hamburger-bar:nth-child(2) { opacity: 0; transform: scaleX(0); }
        .nav-hamburger.open .nav-hamburger-bar:nth-child(3) { transform: translateY(-7px) rotate(-45deg); background: var(--color-primary-light); }
        .nav-mobile-drawer {
          position: fixed;
          top: 68px; left: 0; right: 0;
          background: rgba(6, 9, 19, 0.97);
          backdrop-filter: blur(24px);
          -webkit-backdrop-filter: blur(24px);
          border-bottom: 1px solid var(--color-primary-border);
          padding: 12px 20px 20px;
          display: flex;
          flex-direction: column;
          gap: 4px;
          transform: translateY(-110%);
          opacity: 0;
          transition: transform 0.3s cubic-bezier(0.4,0,0.2,1), opacity 0.25s;
          z-index: 998;
        }
        .nav-mobile-drawer.open {
          transform: translateY(0);
          opacity: 1;
        }
        .nav-mobile-link {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 12px 16px;
          border-radius: 10px;
          text-decoration: none;
          font-size: 15px;
          font-weight: 500;
          color: var(--text-muted);
          border: 1px solid transparent;
          transition: var(--transition-fast);
        }
        .nav-mobile-link:hover { color: var(--text-primary); background: rgba(255,255,255,0.04); border-color: var(--border-subtle); }
        .nav-mobile-link.active { color: var(--color-primary-light); background: var(--color-primary-bg); border-color: var(--color-primary-border); font-weight: 600; }
        @media (max-width: 768px) {
          .nav-menu { display: none; }
          .nav-hamburger { display: flex; }
        }
      `}</style>

      <nav className={`nav-root ${scrolled ? 'scrolled' : 'top'}`}>
        <div className="nav-inner">
          <Link href={`/${lng}/dashboard`} className="nav-brand">
            <div className="nav-brand-dot">
              <div className="nav-brand-dot-core" />
              <div className="nav-brand-dot-ring" />
            </div>
            <span className="nav-brand-name">
              z<span>trader</span>
            </span>
          </Link>

          <div className="nav-menu">
            {isLoggedIn ? (
              <>
                {menuConfig.map((item) => (
                  <Link
                    key={item.key}
                    href={`/${lng}/${item.path}`}
                    className={`nav-link${isActive(item.path) ? ' active' : ''}`}
                    {...(isActive(item.path) ? { 'aria-current': 'page' as const } : {})}
                  >
                    <span className="nav-link-icon">{item.icon}</span>
                    {t(item.i18nKey)}
                  </Link>
                ))}
                <div className="nav-divider" />
                <button
                  onClick={handleLogout}
                  className="nav-link"
                  style={{ border: '1px solid transparent', width: 'auto' }}
                >
                  <span className="nav-link-icon">
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                      <polyline points="16 17 21 12 16 7" />
                      <line x1="21" y1="12" x2="9" y2="12" />
                    </svg>
                  </span>
                  {t('menu.logout')}
                </button>
              </>
            ) : (
              <Link
                href={`/${lng}/login`}
                className={`nav-link${isActive('login') ? ' active' : ''}`}
              >
                <span className="nav-link-icon">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
                    <polyline points="10 17 15 12 10 7" />
                    <line x1="15" y1="12" x2="3" y2="12" />
                  </svg>
                </span>
                {t('menu.login')}
              </Link>
            )}
          </div>

          <button
            className={`nav-hamburger${mobileOpen ? ' open' : ''}`}
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle menu"
            aria-expanded={mobileOpen}
            aria-controls="nav-drawer"
          >
            <div className="nav-hamburger-bar" />
            <div className="nav-hamburger-bar" />
            <div className="nav-hamburger-bar" />
          </button>
        </div>
      </nav>

      <div
        id="nav-drawer"
        ref={drawerRef}
        role="dialog"
        aria-modal={mobileOpen}
        aria-hidden={!mobileOpen}
        aria-label="Navigation menu"
        className={`nav-mobile-drawer${mobileOpen ? ' open' : ''}`}
      >
        {isLoggedIn ? (
          <>
            {menuConfig.map((item) => (
              <Link
                key={item.key}
                href={`/${lng}/${item.path}`}
                className={`nav-mobile-link${isActive(item.path) ? ' active' : ''}`}
                {...(isActive(item.path) ? { 'aria-current': 'page' as const } : {})}
              >
                <span style={{ opacity: 0.8 }}>{item.icon}</span>
                {t(item.i18nKey)}
              </Link>
            ))}
            <div
              style={{
                height: '1px',
                background: 'var(--border-subtle)',
                margin: '8px 0',
              }}
            />
            <button
              onClick={handleLogout}
              className="nav-mobile-link"
              style={{
                background: 'transparent',
                border: '1px solid transparent',
                cursor: 'pointer',
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
              }}
            >
              <span style={{ opacity: 0.8 }}>
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
              </span>
              <span>{t('menu.logout')}</span>
            </button>
          </>
        ) : (
          <Link
            href={`/${lng}/login`}
            className={`nav-mobile-link${isActive('login') ? ' active' : ''}`}
            {...(isActive('login') ? { 'aria-current': 'page' as const } : {})}
          >
            <span style={{ opacity: 0.8 }}>
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
                <polyline points="10 17 15 12 10 7" />
                <line x1="15" y1="12" x2="3" y2="12" />
              </svg>
            </span>
            {t('menu.login')}
          </Link>
        )}
      </div>
    </>
  );
}
