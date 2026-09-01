"use client";

import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../contexts/ThemeContext';

export function ThemeCustomizer() {
  const { t } = useTranslation();
  const { theme, setTheme, primaryColor, secondaryColor, accentColor, setPrimaryColor, setSecondaryColor, setAccentColor } = useTheme();

  const [tempPrimaryColor, setTempPrimaryColor] = useState(primaryColor);
  const [tempSecondaryColor, setTempSecondaryColor] = useState(secondaryColor);
  const [tempAccentColor, setTempAccentColor] = useState(accentColor);

  const handleApplyColors = () => {
    setPrimaryColor(tempPrimaryColor || '#3B82F6');
    setSecondaryColor(tempSecondaryColor || '#8B5CF6');
    setAccentColor(tempAccentColor || '#10B981');
  };

  const handleResetColors = () => {
    const defaultPrimary = '#3B82F6';
    const defaultSecondary = '#8B5CF6';
    const defaultAccent = '#10B981';
    setTempPrimaryColor(defaultPrimary);
    setTempSecondaryColor(defaultSecondary);
    setTempAccentColor(defaultAccent);
    setPrimaryColor(defaultPrimary);
    setSecondaryColor(defaultSecondary);
    setAccentColor(defaultAccent);
  };

  return (
    <div className="glass-card-static animate-fade-in">
      <h3 className="h3" style={{ marginBottom: '20px' }}>{t('theme.customize')}</h3>

      <div className="form-group">
        <label className="form-label">{t('theme.mode')}</label>
        <div style={{ display: 'flex', gap: '10px' }}>
          {(['light', 'dark', 'auto'] as const).map((mode) => (
            <button key={mode} onClick={() => setTheme(mode)}
              className={`btn-base btn-sm ${theme === mode ? 'btn-primary' : 'btn-ghost'}`}
              style={{ flex: 1, justifyContent: 'center' }}>
              {mode === 'light' ? t('theme.light') : mode === 'dark' ? t('theme.dark') : t('theme.auto')}
            </button>
          ))}
        </div>
      </div>

      <div className="form-group">
        <h4 className="h4" style={{ marginBottom: '16px' }}>{t('theme.custom_colors')}</h4>
        {[
          { label: t('theme.primary_color'), state: tempPrimaryColor, setState: setTempPrimaryColor },
          { label: t('theme.secondary_color'), state: tempSecondaryColor, setState: setTempSecondaryColor },
          { label: t('theme.accent_color'), state: tempAccentColor, setState: setTempAccentColor },
        ].map((item, idx) => (
          <div key={idx} style={{ marginBottom: '12px' }}>
            <label className="form-label">{item.label}</label>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <input type="color" value={item.state} onChange={(e) => item.setState(e.target.value)}
                style={{ width: '48px', height: '38px', border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer', background: 'transparent' }} />
              <input type="text" value={item.state} onChange={(e) => item.setState(e.target.value)}
                className="input-field font-mono" />
            </div>
          </div>
        ))}
        <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
          <button onClick={handleApplyColors} className="btn-base btn-primary btn-sm" style={{ flex: 1 }}>
            {t('theme.apply_colors')}
          </button>
          <button onClick={handleResetColors} className="btn-base btn-ghost btn-sm">
            {t('theme.reset')}
          </button>
        </div>
      </div>

      <div style={{ padding: '16px', background: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
        <h4 className="form-label" style={{ marginBottom: '12px' }}>{t('theme.preview')}</h4>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {[
            { label: t('theme.primary'), color: tempPrimaryColor },
            { label: t('theme.secondary'), color: tempSecondaryColor },
            { label: t('theme.accent'), color: tempAccentColor },
          ].map((c, idx) => (
            <div key={idx} style={{
              width: '74px', height: '74px', backgroundColor: c.color,
              borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center',
              justifyContent: 'center', color: 'white', fontSize: '11px',
              fontWeight: '600', boxShadow: '0 4px 10px rgba(0, 0, 0, 0.15)',
            }}>
              {c.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
