"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';

interface TVAlert {
  id: string;
  ticker: string;
  exchange: string;
  action: string;
  price?: number;
  strategy?: string;
  interval?: string;
  volume?: number;
  received_at: string;
}

export function TradingViewConfig() {
  const { t } = useTranslation();
  const [alerts, setAlerts] = useState<TVAlert[]>([]);
  const [webhookUrl, setWebhookUrl] = useState(
    'http://localhost:8000/api/v1/tradingview/webhook',
  );
  const [copied, setCopied] = useState(false);
  const [alertsError, setAlertsError] = useState(false);

  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  const fetchAlerts = useCallback(async () => {
    try {
      setAlertsError(false);
      const res = await fetch(
        `${backendUrl}/api/v1/tradingview/alerts?limit=10`,
      );
      if (res.ok) {
        const data = await res.json();
        setAlerts(data);
      } else {
        setAlertsError(true);
      }
    } catch {
      setAlertsError(true);
    }
  }, [backendUrl]);

  useEffect(() => {
    setWebhookUrl(`${backendUrl}/api/v1/tradingview/webhook`);
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 5000);
    return () => clearInterval(interval);
  }, [backendUrl, fetchAlerts]);

  const handleCopy = () => {
    navigator.clipboard.writeText(webhookUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="glass-card-static animate-fade-in">
      <h3 className="h3" style={{ marginBottom: '16px' }}>
        {t('tradingview.title')}
      </h3>

      <p
        className="text-secondary"
        style={{
          fontSize: '14px',
          lineHeight: '1.5',
          marginBottom: '20px',
        }}
      >
        {t('tradingview.desc')}
      </p>

      <div style={{ marginBottom: '24px' }}>
        <div className="form-group">
          <label className="form-label">{t('tradingview.webhook_url')}</label>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-input)',
              borderRadius: 'var(--radius-md)',
              padding: '8px 12px',
            }}
          >
            <code
              className="font-mono"
              style={{
                fontSize: '13px',
                color: 'var(--color-primary)',
                overflowX: 'auto',
                flex: 1,
                whiteSpace: 'nowrap',
              }}
            >
              {webhookUrl}
            </code>
            <button
              onClick={handleCopy}
              className="btn-base btn-sm"
              style={{
                marginLeft: '10px',
                color: copied
                  ? 'var(--color-accent)'
                  : 'var(--color-primary)',
              }}
            >
              {copied ? t('tradingview.copied') : t('tradingview.copy')}
            </button>
          </div>
        </div>

        <div
          style={{
            padding: '14px',
            background: 'var(--color-warning-bg)',
            border: '1px solid rgba(245, 158, 11, 0.2)',
            borderRadius: 'var(--radius-md)',
            fontSize: '13px',
            lineHeight: '1.5',
            color: 'var(--color-warning)',
          }}
        >
          <strong>{t('tradingview.required_header')}</strong>
          <code
            className="font-mono"
            style={{
              display: 'block',
              background: 'rgba(0,0,0,0.2)',
              padding: '6px 10px',
              borderRadius: 'var(--radius-sm)',
              marginTop: '6px',
              color: 'var(--text-primary)',
            }}
          >
            X-Webhook-Secret: &lt;your-webhook-secret-token&gt;
          </code>
        </div>
      </div>

      <div>
        <h4 className="h4" style={{ marginBottom: '12px' }}>
          {t('tradingview.recent_signals')}
        </h4>
        <div
          aria-live="polite"
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            maxHeight: '160px',
            overflowY: 'auto',
          }}
        >
          {alerts.map((al) => (
            <div
              key={al.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 14px',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                fontSize: '13px',
              }}
            >
              <div>
                <strong
                  style={{
                    color:
                      al.action === 'BUY'
                        ? 'var(--color-accent)'
                        : al.action === 'SELL'
                          ? 'var(--color-danger)'
                          : 'var(--text-secondary)',
                    marginRight: '8px',
                  }}
                >
                  {al.action}
                </strong>
                <span style={{ fontWeight: '600' }}>{al.ticker}</span>
                <span className="text-muted" style={{ marginLeft: '8px' }}>
                  ({al.strategy})
                </span>
              </div>
              <span className="text-secondary">
                {al.price ? `$${al.price.toFixed(2)}` : 'Market'}
              </span>
            </div>
          ))}
          {alerts.length === 0 && !alertsError && (
            <div
              className="text-muted"
              style={{
                textAlign: 'center',
                padding: '16px',
                fontSize: '13px',
              }}
            >
              {t('tradingview.no_alerts')}
            </div>
          )}
          {alertsError && (
            <div
              style={{
                textAlign: 'center',
                padding: '16px',
                fontSize: '13px',
              }}
            >
              <span className="text-muted" style={{ display: 'block', marginBottom: '8px' }}>
                Failed to load alerts
              </span>
              <button
                onClick={fetchAlerts}
                className="btn-base btn-sm"
                style={{ color: 'var(--color-primary)' }}
              >
                Retry
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
