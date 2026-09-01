"use client";

import React, { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { initI18n } from '../../i18n/client';
import { useTranslation } from 'react-i18next';
import { ThemeCustomizer } from '../../../components/settings/ThemeCustomizer';
import { TelegramLink } from '../../../components/settings/TelegramLink';
import { NotificationPreferences } from '../../../components/settings/NotificationPreferences';
import { PromptPayTopup } from '../../../components/settings/PromptPayTopup';
import { TradingViewConfig } from '../../../components/settings/TradingViewConfig';

interface StatusMessage {
  type: 'success' | 'error';
  text: string;
}

interface RiskLimits {
  max_notional: number;
  allowed_symbols: string[];
  live_trading: boolean;
}

export default function SettingsPage() {
  const pathname = usePathname();
  const lng = pathname?.split('/')[1] || 'en';
  initI18n(lng);
  const { t } = useTranslation('translation');

  const [exchange, setExchange] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [passphrase, setPassphrase] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<StatusMessage | null>(null);

  const [riskLimits, setRiskLimits] = useState<RiskLimits>({
    max_notional: 100.0,
    allowed_symbols: ['BTC/USDT', 'ETH/USDT'],
    live_trading: false,
  });

  const [riskSaving, setRiskSaving] = useState(false);
  const [riskMessage, setRiskMessage] = useState<StatusMessage | null>(null);

  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const [healthRes, limitsRes] = await Promise.all([
          fetch(`${backendUrl}/health`),
          fetch(`${backendUrl}/api/v1/risk/limits`).catch(() => null),
        ]);

        const healthData = healthRes.ok ? await healthRes.json() : null;

        let limits: Partial<RiskLimits> = {};
        if (limitsRes?.ok) {
          const d = await limitsRes.json();
          limits = {
            max_notional: d.max_notional ?? d.max_order_notional,
            allowed_symbols: d.allowed_symbols,
            live_trading: d.live_trading,
          };
        }

        setRiskLimits((prev) => ({
          ...prev,
          max_notional:
            limits.max_notional ?? prev.max_notional,
          allowed_symbols:
            limits.allowed_symbols ?? prev.allowed_symbols,
          live_trading:
            limits.live_trading ??
            healthData?.live_trading_enabled ??
            prev.live_trading,
        }));

        const exchangeRes = await fetch(
          `${backendUrl}/api/v1/keys/exchange`,
        ).catch(() => null);
        if (exchangeRes?.ok) {
          const exData = await exchangeRes.json();
          if (exData.exchange) setExchange(exData.exchange);
        }
      } catch (err) {
        console.error('Failed to load config:', err);
      }
    };
    loadConfig();
  }, [backendUrl]);

  const handleSubmitKeys = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatusMessage(null);

    if (!apiKey || !apiSecret) {
      setStatusMessage({
        type: 'error',
        text: t('settings.toast_required'),
      });
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch(`${backendUrl}/api/v1/keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          exchange,
          api_key: apiKey,
          api_secret: apiSecret,
          passphrase: passphrase || null,
        }),
      });

      if (res.ok) {
        setStatusMessage({
          type: 'success',
          text: t('settings.toast_saved'),
        });
        setApiKey('');
        setApiSecret('');
        setPassphrase('');
      } else {
        const errData = await res.json().catch(() => ({}));
        setStatusMessage({
          type: 'error',
          text: errData.detail || t('settings.toast_failed'),
        });
      }
    } catch (err) {
      console.error('Failed to save API keys:', err);
      setStatusMessage({
        type: 'error',
        text: t('settings.toast_failed'),
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveRiskLimits = async () => {
    setRiskSaving(true);
    setRiskMessage(null);
    try {
      const res = await fetch(`${backendUrl}/api/v1/risk/limits`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          max_notional: riskLimits.max_notional,
          allowed_symbols: riskLimits.allowed_symbols,
          live_trading: riskLimits.live_trading,
        }),
      });
      if (res.ok) {
        setRiskMessage({ type: 'success', text: 'Risk limits saved' });
      } else {
        const err = await res.json().catch(() => ({}));
        setRiskMessage({
          type: 'error',
          text: err.detail || 'Failed to save risk limits',
        });
      }
    } catch {
      setRiskMessage({ type: 'error', text: 'Failed to save risk limits' });
    } finally {
      setRiskSaving(false);
    }
  };

  const renderMessage = (msg: StatusMessage | null) => {
    if (!msg) return null;
    return (
      <div
        role="alert"
        aria-live="polite"
        className={`badge ${msg.type === 'success' ? 'badge-accent' : 'badge-danger'}`}
        style={{
          display: 'flex',
          marginBottom: '16px',
          padding: '10px 14px',
          borderRadius: 'var(--radius-md)',
        }}
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          style={{ flexShrink: 0, marginRight: '8px' }}
        >
          {msg.type === 'success' ? (
            <polyline points="20 6 9 17 4 12" />
          ) : (
            <>
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </>
          )}
        </svg>
        <span>{msg.text}</span>
      </div>
    );
  };

  return (
    <div
      style={{
        maxWidth: '1280px',
        margin: '0 auto',
        padding: 'clamp(16px, 4vw, 40px) clamp(12px, 3vw, 24px)',
        minHeight: '90vh',
      }}
    >
      <h1
        className="h1"
        style={{
          marginBottom: '32px',
          paddingBottom: '16px',
          borderBottom: '1px solid var(--border-card)',
        }}
      >
        {t('settings.title')}
      </h1>

      <div className="layout-auto" style={{ gap: '28px' }}>
        <div style={{ display: 'grid', gap: '28px' }}>
          <div className="glass-card-static animate-fade-in">
            <h3 className="h3" style={{ marginBottom: '20px' }}>
              {t('settings.api_settings')}
            </h3>
            <form onSubmit={handleSubmitKeys}>
              <div className="form-group">
                <label className="form-label">
                  {t('settings.exchange_platform')}
                </label>
                <select
                  value={exchange}
                  onChange={(e) => setExchange(e.target.value)}
                  className="input-field"
                >
                  <option value="binance.com">{t('exchange.binance_com')}</option>
                  <option value="binance.th">{t('exchange.binance_th')}</option>
                  <option value="okx">{t('exchange.okx')}</option>
                  <option value="bybit">{t('exchange.bybit')}</option>
                  <option value="kucoin">{t('exchange.kucoin')}</option>
                  <option value="MT5">{t('exchange.mt5')}</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">
                  {t('settings.api_key')}
                </label>
                <input
                  type="text"
                  placeholder={t('settings.enter_api_key')}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="input-field"
                />
              </div>

              <div className="form-group">
                <label className="form-label">
                  {t('settings.api_secret')}
                </label>
                <input
                  type="password"
                  placeholder={t('settings.enter_api_secret')}
                  value={apiSecret}
                  onChange={(e) => setApiSecret(e.target.value)}
                  className="input-field"
                />
              </div>

              <div className="form-group">
                <label className="form-label">
                  {t('settings.passphrase')}
                </label>
                <input
                  type="password"
                  placeholder={t('settings.enter_passphrase')}
                  value={passphrase}
                  onChange={(e) => setPassphrase(e.target.value)}
                  className="input-field"
                  autoComplete="off"
                />
              </div>

              {renderMessage(statusMessage)}

              <button
                type="submit"
                disabled={submitting}
                className="btn-base btn-primary btn-full"
              >
                {submitting ? 'Saving...' : t('settings.submit')}
              </button>
            </form>
          </div>

          <div className="glass-card-static animate-fade-in">
            <h3 className="h3" style={{ marginBottom: '20px' }}>
              Risk Limits
            </h3>
            <form onSubmit={(e) => { e.preventDefault(); handleSaveRiskLimits(); }}>
              <div className="form-group">
                <label className="form-label">Max Order Notional (USD)</label>
                <input
                  type="number"
                  step="0.01"
                  value={riskLimits.max_notional}
                  onChange={(e) =>
                    setRiskLimits((prev) => ({
                      ...prev,
                      max_notional: parseFloat(e.target.value) || 0,
                    }))
                  }
                  className="input-field"
                />
              </div>
              <div className="form-group">
                <label className="form-label">
                  Allowed Symbols (comma-separated)
                </label>
                <input
                  type="text"
                  value={riskLimits.allowed_symbols.join(', ')}
                  onChange={(e) =>
                    setRiskLimits((prev) => ({
                      ...prev,
                      allowed_symbols: e.target.value
                        .split(',')
                        .map((s) => s.trim())
                        .filter(Boolean),
                    }))
                  }
                  className="input-field"
                />
              </div>
              <fieldset style={{ border: 'none', padding: 0, margin: 0 }}>
                <legend className="visually-hidden">Live Trading Toggle</legend>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    marginBottom: '20px',
                  }}
                >
                  <input
                    type="checkbox"
                    id="live-trading"
                    checked={riskLimits.live_trading}
                    onChange={(e) =>
                      setRiskLimits((prev) => ({
                        ...prev,
                        live_trading: e.target.checked,
                      }))
                    }
                    style={{ accentColor: 'var(--color-danger)' }}
                  />
                  <label htmlFor="live-trading" style={{ fontSize: '14px' }}>
                    Enable Live Trading
                  </label>
                </div>
              </fieldset>
              {renderMessage(riskMessage)}
              <button
                type="submit"
                disabled={riskSaving}
                className="btn-base btn-primary btn-full"
              >
                {riskSaving ? 'Saving...' : 'Save Risk Limits'}
              </button>
            </form>
          </div>

          <PromptPayTopup />
        </div>

        <div style={{ display: 'grid', gap: '28px' }}>
          <TradingViewConfig />
          <TelegramLink />
          <NotificationPreferences />
          <ThemeCustomizer />
        </div>
      </div>
    </div>
  );
}
