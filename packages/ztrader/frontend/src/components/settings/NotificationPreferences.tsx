"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';

interface NotificationPreferencesProps {
  userId?: string;
}

interface Preferences {
  tradeAlerts: boolean;
  riskAlerts: boolean;
  systemAlerts: boolean;
  dailySummary: boolean;
}

export function NotificationPreferences({
  userId = 'user-default',
}: NotificationPreferencesProps) {
  const { t } = useTranslation();
  const [preferences, setPreferences] = useState<Preferences>({
    tradeAlerts: true,
    riskAlerts: true,
    systemAlerts: true,
    dailySummary: true,
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  const [prefsError, setPrefsError] = useState(false);

  const loadPreferences = useCallback(async () => {
    try {
      setPrefsError(false);
      const response = await fetch(
        `${backendUrl}/api/v1/user/notifications/preferences/${userId}`,
      );
      if (response.ok) {
        const data = await response.json();
        setPreferences(data);
      } else {
        setPrefsError(true);
      }
    } catch {
      setPrefsError(true);
    }
  }, [backendUrl, userId]);

  useEffect(() => {
    loadPreferences();
  }, [loadPreferences]);

  const handleSave = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(
        `${backendUrl}/api/v1/user/notifications/preferences`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: userId,
            trade_alerts: preferences.tradeAlerts,
            risk_alerts: preferences.riskAlerts,
            system_alerts: preferences.systemAlerts,
            daily_summary: preferences.dailySummary,
            tradeAlerts: preferences.tradeAlerts,
            riskAlerts: preferences.riskAlerts,
            systemAlerts: preferences.systemAlerts,
            dailySummary: preferences.dailySummary,
          }),
        },
      );
      if (response.ok) {
        setMessage({
          type: 'success',
          text: t('notifications.saved'),
        });
        setTimeout(() => setMessage(null), 3000);
      } else {
        const err = await response.json();
        setMessage({
          type: 'error',
          text: err.detail || t('notifications.save_failed'),
        });
      }
    } catch (error) {
      console.error('Failed to save preferences:', error);
      setMessage({
        type: 'error',
        text: t('notifications.save_failed_try'),
      });
    } finally {
      setLoading(false);
    }
  };

  const togglePreference = (key: keyof Preferences) => {
    setPreferences((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const items = [
    {
      key: 'tradeAlerts' as keyof Preferences,
      label: t('notifications.trade_alerts'),
      desc: t('notifications.trade_alerts_desc'),
    },
    {
      key: 'riskAlerts' as keyof Preferences,
      label: t('notifications.risk_alerts'),
      desc: t('notifications.risk_alerts_desc'),
    },
    {
      key: 'systemAlerts' as keyof Preferences,
      label: t('notifications.system_alerts'),
      desc: t('notifications.system_alerts_desc'),
    },
    {
      key: 'dailySummary' as keyof Preferences,
      label: t('notifications.daily_summary'),
      desc: t('notifications.daily_summary_desc'),
    },
  ];

  return (
    <div className="glass-card-static animate-fade-in">
      <h3 className="h3" style={{ marginBottom: '20px' }}>
        {t('notifications.title')}
      </h3>

      <form onSubmit={(e) => { e.preventDefault(); handleSave(); }}>
        <fieldset style={{ border: 'none', padding: 0, margin: 0 }}>
          <legend className="visually-hidden">{t('notifications.title')}</legend>
          <div style={{ display: 'grid', gap: '10px', marginBottom: '24px' }}>
            {items.map((item) => (
              <label
                key={item.key}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  padding: '14px',
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  cursor: 'pointer',
                  transition: 'var(--transition-fast)',
                }}
              >
                <input
                  type="checkbox"
                  checked={preferences[item.key]}
                  onChange={() => togglePreference(item.key)}
                  style={{
                    marginRight: '14px',
                    width: '18px',
                    height: '18px',
                    marginTop: '2px',
                    cursor: 'pointer',
                    accentColor: 'var(--color-primary)',
                  }}
                />
                <div>
                  <div
                    style={{
                      fontWeight: '600',
                      fontSize: '14px',
                      color: 'var(--text-primary)',
                    }}
                  >
                    {item.label}
                  </div>
                  <div
                    className="text-secondary"
                    style={{ fontSize: '12px', marginTop: '3px' }}
                  >
                    {item.desc}
                  </div>
                </div>
              </label>
            ))}
          </div>
        </fieldset>

        <button
          type="submit"
          disabled={loading}
          className="btn-base btn-primary btn-full"
        >
          {loading ? t('notifications.saving') : t('notifications.save')}
        </button>
      </form>

      {prefsError && (
        <div
          role="alert"
          className="badge badge-danger"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            marginTop: '16px',
            padding: '10px 14px',
            borderRadius: 'var(--radius-md)',
          }}
        >
          <span>Failed to load preferences</span>
          <button
            onClick={loadPreferences}
            className="btn-base btn-sm"
            style={{ color: 'var(--color-primary)', marginLeft: 'auto' }}
          >
            Retry
          </button>
        </div>
      )}

      {message && (
        <div
          role="alert"
          className={`badge ${message.type === 'success' ? 'badge-accent' : 'badge-danger'}`}
          style={{
            display: 'flex',
            marginTop: '16px',
            padding: '10px 14px',
            borderRadius: 'var(--radius-md)',
          }}
        >
          <span>{message.text}</span>
        </div>
      )}
    </div>
  );
}
