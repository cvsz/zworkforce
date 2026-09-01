"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';

interface TelegramLinkProps {
  userId?: string;
}

interface TelegramStatus {
  linked: boolean;
  chatId?: string;
  username?: string;
  verified?: boolean;
}

export function TelegramLink({
  userId = 'user-default',
}: TelegramLinkProps) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<TelegramStatus>({ linked: false });
  const [loading, setLoading] = useState(false);
  const [chatId, setChatId] = useState('');
  const [username, setUsername] = useState('');
  const [message, setMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  const [statusError, setStatusError] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      setStatusError(false);
      const response = await fetch(
        `${backendUrl}/api/v1/telegram/status/${userId}`,
      );
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      } else {
        setStatusError(true);
      }
    } catch {
      setStatusError(true);
    }
  }, [backendUrl, userId]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleLink = async () => {
    if (!chatId.trim()) {
      setMessage({
        type: 'error',
        text: t('telegram.enter_chat_id'),
      });
      return;
    }
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(`${backendUrl}/api/v1/telegram/link`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          chat_id: chatId.trim(),
          username: username.trim() || null,
        }),
      });
      if (response.ok) {
        setMessage({
          type: 'success',
          text: t('telegram.linked_success'),
        });
        setChatId('');
        setUsername('');
        await loadStatus();
      } else {
        const err = await response.json();
        setMessage({
          type: 'error',
          text: err.detail || t('telegram.link_failed'),
        });
      }
    } catch (error) {
      console.error('Telegram link error:', error);
      setMessage({
        type: 'error',
        text: t('telegram.link_failed_try'),
      });
    } finally {
      setLoading(false);
    }
  };

  const handleUnlink = async () => {
    if (
      !confirm(t('telegram.unlink_confirm'))
    )
      return;
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(
        `${backendUrl}/api/v1/telegram/unlink`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: userId }),
        },
      );
      if (response.ok) {
        setMessage({
          type: 'success',
          text: t('telegram.unlinked_success'),
        });
        await loadStatus();
      } else {
        const err = await response.json();
        setMessage({
          type: 'error',
          text: err.detail || t('telegram.unlink_failed'),
        });
      }
    } catch (error) {
      console.error('Telegram unlink error:', error);
      setMessage({
        type: 'error',
        text: t('telegram.unlink_failed'),
      });
    } finally {
      setLoading(false);
    }
  };

  const handleTestNotification = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(
        `${backendUrl}/api/v1/telegram/notify/test`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: userId }),
        },
      );
      if (response.ok) {
        setMessage({
          type: 'success',
          text: t('telegram.test_sent'),
        });
      } else {
        const err = await response.json();
        setMessage({
          type: 'error',
          text: err.detail || t('telegram.notify_failed'),
        });
      }
    } catch (error) {
      console.error('Telegram test notification error:', error);
      setMessage({
        type: 'error',
        text: t('telegram.test_failed'),
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-card-static animate-fade-in">
      <h3 className="h3" style={{ marginBottom: '16px' }}>
        {t('telegram.title')}
      </h3>

      {status.linked ? (
        <div>
          <div
            style={{
              marginBottom: '20px',
              padding: '14px',
              background: 'var(--color-primary-bg)',
              border: '1px solid var(--color-primary-border)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <p style={{ marginBottom: '8px', fontSize: '14px' }}>
              <strong>{t('telegram.status')}</strong>{' '}
              <span className="text-accent" style={{ fontWeight: '600' }}>
                {t('telegram.linked')}
              </span>
            </p>
            {status.username && (
              <p style={{ marginBottom: '8px', fontSize: '14px' }}>
                <strong>{t('telegram.username')}</strong> @{status.username}
              </p>
            )}
            <p
              style={{
                fontSize: '14px',
                color: 'var(--text-secondary)',
              }}
            >
              <strong>{t('telegram.chat_id')}</strong> {status.chatId}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              onClick={handleTestNotification}
              disabled={loading}
              className="btn-base btn-accent btn-sm"
              style={{ flex: 1 }}
            >
              {t('telegram.test_notification')}
            </button>
            <button
              onClick={handleUnlink}
              disabled={loading}
              className="btn-base btn-danger btn-sm"
            >
              {t('telegram.unlink')}
            </button>
          </div>
        </div>
      ) : (
        <div>
          <p
            className="text-secondary"
            style={{
              marginBottom: '20px',
              fontSize: '14px',
              lineHeight: '1.5',
            }}
          >
            {t('telegram.desc')}
          </p>
          <form onSubmit={(e) => { e.preventDefault(); handleLink(); }}>
            <div className="form-group">
              <label className="form-label">{t('telegram.chat_id_label')}</label>
              <input
                type="text"
                value={chatId}
                onChange={(e) => setChatId(e.target.value)}
                placeholder={t('telegram.chat_id_placeholder')}
                className="input-field"
              />
              <small
                className="text-muted"
                style={{ fontSize: '11px', display: 'block', marginTop: '4px' }}
              >
                {t('telegram.send_message_hint')}{' '}
                <a
                  href="https://t.me/userinfobot"
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    color: 'var(--color-primary)',
                    textDecoration: 'none',
                  }}
                >
                  @userinfobot
                </a>{' '}
                {t('telegram.find_chat_id_hint')}
              </small>
            </div>
            <div className="form-group">
              <label className="form-label">
                {t('telegram.username_label')}
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={t('telegram.username_placeholder')}
                className="input-field"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="btn-base btn-primary btn-full"
            >
              {loading ? t('telegram.linking') : t('telegram.link')}
            </button>
          </form>
        </div>
      )}

      {statusError && !status.linked && (
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
          <span>Failed to load Telegram status</span>
          <button
            onClick={loadStatus}
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
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            style={{ flexShrink: 0, marginRight: '8px' }}
          >
            {message.type === 'success' ? (
              <polyline points="20 6 9 17 4 12" />
            ) : (
              <>
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </>
            )}
          </svg>
          <span>{message.text}</span>
        </div>
      )}
    </div>
  );
}
