"use client";

import React, { useState, useRef, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useTranslation } from 'react-i18next';

const languages = [
  { code: 'en', name: 'English', flag: '🇬🇧', short: 'EN' },
  { code: 'th', name: 'ไทย', flag: '🇹🇭', short: 'TH' },
  { code: 'zh', name: '中文', flag: '🇨🇳', short: 'ZH' },
  { code: 'ja', name: '日本語', flag: '🇯🇵', short: 'JA' },
];

export function LanguageSelector() {
  const router = useRouter();
  const pathname = usePathname();
  const { i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const currentLang =
    languages.find((l) => l.code === (i18n.language || 'en')) ?? languages[0];

  const handleSelect = (code: string) => {
    setOpen(false);
    const parts = pathname.split('/');
    const hasLang = languages.some((l) => l.code === parts[1]);
    const newPath = hasLang
      ? ['', code, ...parts.slice(2)].join('/')
      : `/${code}${pathname}`;
    router.push(newPath);
  };

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="lang-selector" ref={ref}>
      <style>{`
        .lang-selector { position: relative; }
        .lang-trigger {
          display: flex; align-items: center; gap: 7px;
          padding: 7px 12px;
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 10px;
          cursor: pointer;
          font-family: 'Outfit', sans-serif;
          font-size: 14px; font-weight: 600;
          color: #d1d5db;
          transition: all 0.2s cubic-bezier(0.4,0,0.2,1);
          user-select: none;
          white-space: nowrap;
        }
        .lang-trigger:hover {
          background: rgba(59,130,246,0.1);
          border-color: rgba(59,130,246,0.3);
          color: #f3f4f6;
        }
        .lang-trigger.open {
          background: rgba(59,130,246,0.12);
          border-color: rgba(59,130,246,0.35);
          color: #60a5fa;
          box-shadow: 0 0 14px rgba(59,130,246,0.15);
        }
        .lang-flag { font-size: 16px; line-height: 1; }
        .lang-chevron {
          display: flex; opacity: 0.6;
          transition: transform 0.2s;
        }
        .lang-trigger.open .lang-chevron { transform: rotate(180deg); opacity: 1; }
        .lang-dropdown {
          position: absolute;
          top: calc(100% + 8px);
          right: 0;
          min-width: 160px;
          background: rgba(10, 14, 26, 0.98);
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          border: 1px solid rgba(59,130,246,0.18);
          border-radius: 12px;
          overflow: hidden;
          box-shadow: 0 16px 48px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.03);
          transform-origin: top right;
          transform: scale(0.92) translateY(-6px);
          opacity: 0;
          pointer-events: none;
          transition: transform 0.2s cubic-bezier(0.4,0,0.2,1), opacity 0.18s;
          z-index: 1001;
        }
        .lang-dropdown.open {
          transform: scale(1) translateY(0);
          opacity: 1;
          pointer-events: auto;
        }
        .lang-option {
          display: flex; align-items: center; gap: 10px;
          padding: 10px 14px;
          cursor: pointer;
          font-family: 'Outfit', sans-serif;
          font-size: 14px; font-weight: 500;
          color: #9ca3af;
          transition: all 0.15s;
          border-bottom: 1px solid rgba(255,255,255,0.03);
        }
        .lang-option:last-child { border-bottom: none; }
        .lang-option:hover {
          background: rgba(59,130,246,0.1);
          color: #e5e7eb;
        }
        .lang-option.active {
          background: rgba(59,130,246,0.12);
          color: #60a5fa;
          font-weight: 600;
        }
        .lang-option-check {
          margin-left: auto;
          color: #3B82F6;
        }
      `}</style>
      <button
        className={`lang-trigger${open ? ' open' : ''}`}
        onClick={() => setOpen(!open)}
        aria-label="Select language"
      >
        <span className="lang-flag">{currentLang.flag}</span>
        <span>{currentLang.short}</span>
        <span className="lang-chevron">
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </span>
      </button>

      <div className={`lang-dropdown${open ? ' open' : ''}`}>
        {languages.map((lang) => (
          <div
            key={lang.code}
            className={`lang-option${lang.code === currentLang.code ? ' active' : ''}`}
            onClick={() => handleSelect(lang.code)}
          >
            <span style={{ fontSize: '16px' }}>{lang.flag}</span>
            <span>{lang.name}</span>
            {lang.code === currentLang.code && (
              <span className="lang-option-check">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
