"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';

type PaymentMethod = 'promptpay' | 'truemoney' | 'shopeepay' | 'linepay' | 'zpoint';

interface PaymentSession {
  id: string;
  amount: number;
  qr_image_base64?: string;
  redirect_url?: string;
  promptpay_id?: string;
  expires_at: string;
  status: 'pending' | 'paid' | 'expired' | 'failed';
}

interface ZPointBalance {
  balance: number;
}

const METHOD_META: Record<PaymentMethod, { label: string; icon: string; desc: string; color: string }> = {
  promptpay: {
    label: 'PromptPay',
    icon: '🏦',
    desc: 'Thai instant bank transfer via QR',
    color: '#003764',
  },
  truemoney: {
    label: 'TrueMoney',
    icon: '📱',
    desc: 'TrueMoney Wallet — Thai e-wallet',
    color: '#E11B22',
  },
  shopeepay: {
    label: 'ShopeePay',
    icon: '🛒',
    desc: 'Shopee Pay — scan & pay via Shopee app',
    color: '#EE4D2D',
  },
  linepay: {
    label: 'LINE Pay',
    icon: '💬',
    desc: 'LINE Pay — redirect to LINE for payment',
    color: '#00C300',
  },
  zpoint: {
    label: 'Z Point',
    icon: '⭐',
    desc: 'ZeaZ loyalty points — deduct from balance',
    color: '#F59E0B',
  },
};

export function PromptPayTopup() {
  const { t } = useTranslation();

  const [method, setMethod] = useState<PaymentMethod>('promptpay');
  const [amount, setAmount] = useState<number>(500);
  const [session, setSession] = useState<PaymentSession | null>(null);
  const [paymentStatus, setPaymentStatus] = useState<'idle' | 'waiting' | 'success' | 'expired'>('idle');
  const [countdown, setCountdown] = useState(120);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [zpointBalance, setZpointBalance] = useState<number | null>(null);

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (paymentStatus === 'waiting' && countdown > 0) {
      timer = setTimeout(() => setCountdown(countdown - 1), 1000);
    } else if (countdown === 0 && paymentStatus === 'waiting') {
      setPaymentStatus('expired');
      setSession(null);
    }
    return () => clearTimeout(timer);
  }, [paymentStatus, countdown]);

  useEffect(() => {
    if (method === 'zpoint') {
      fetch(`${backendUrl}/api/v1/payments/zpoint/balance`, {
        headers: buildAuthHeaders(),
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((d: ZPointBalance | null) => {
          if (d) setZpointBalance(d.balance);
        })
        .catch(() => {});
    }
  }, [method, backendUrl]);

  const buildAuthHeaders = (): Record<string, string> => {
    const token = typeof window !== 'undefined' ? window.localStorage.getItem('ztrader_admin_token') : null;
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const pollPaymentStatus = useCallback(async (sessionId: string) => {
    try {
      const res = await fetch(
        `${backendUrl}/api/v1/payments/${method}/status/${sessionId}`,
        { headers: buildAuthHeaders() },
      );
      if (res.ok) {
        const data: PaymentSession = await res.json();
        if (data.status === 'paid') {
          setPaymentStatus('success');
          setMessage({ type: 'success', text: t('topup.received', { method: METHOD_META[method].label, amount: data.amount.toFixed(2) }) });
          return true;
        }
        if (data.status === 'expired' || data.status === 'failed') {
          setPaymentStatus('expired');
          setSession(null);
          setMessage({ type: 'error', text: t('topup.expired_or_failed') });
          return true;
        }
      }
      return false;
    } catch {
      return false;
    }
  }, [backendUrl, method]);

  useEffect(() => {
    if (paymentStatus !== 'waiting' || !session) return;
    const interval = setInterval(async () => {
      const done = await pollPaymentStatus(session.id);
      if (done) clearInterval(interval);
    }, 3000);
    return () => clearInterval(interval);
  }, [paymentStatus, session, pollPaymentStatus]);

  const generateEndpoint = (): string => {
    switch (method) {
      case 'promptpay': return `${backendUrl}/api/v1/payments/promptpay/generate`;
      case 'truemoney': return `${backendUrl}/api/v1/payments/truemoney/generate`;
      case 'shopeepay': return `${backendUrl}/api/v1/payments/shopeepay/generate`;
      case 'linepay': return `${backendUrl}/api/v1/payments/linepay/generate`;
      case 'zpoint': return `${backendUrl}/api/v1/payments/zpoint/topup`;
    }
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (amount <= 0) {
      setMessage({ type: 'error', text: t('topup.enter_valid_amount') });
      return;
    }

    if (method === 'zpoint') {
      if (zpointBalance !== null && amount > zpointBalance) {
        setMessage({ type: 'error', text: t('topup.insufficient_zpoint', { balance: zpointBalance.toFixed(0) }) });
        return;
      }
    }

    setLoading(true);
    setMessage(null);
    try {
      const res = await fetch(generateEndpoint(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...buildAuthHeaders() },
        body: JSON.stringify({ amount }),
      });
      if (res.ok) {
        const data: PaymentSession = await res.json();
        setSession(data);
        setPaymentStatus(method === 'zpoint' ? 'success' : 'waiting');
        setCountdown(method === 'linepay' ? 300 : 120);
        if (method === 'zpoint' && zpointBalance !== null) {
          setZpointBalance(zpointBalance - amount);
          setMessage({ type: 'success', text: t('topup.zpoint_deducted', { amount, balance: (zpointBalance - amount).toFixed(0) }) });
        }
      } else {
        const err = await res.json().catch(() => ({}));
        setMessage({ type: 'error', text: err.detail || t('topup.payment_request_failed') });
      }
    } catch {
      setMessage({ type: 'error', text: t('topup.connect_failed') });
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setPaymentStatus('idle');
    setSession(null);
    setAmount(500);
    setMessage(null);
  };

  const meta = METHOD_META[method];

  return (
    <div className="glass-card-static animate-fade-in" style={{ textAlign: 'center' }}>
      <h3 className="h3" style={{ marginBottom: '16px', textAlign: 'left' }}>
        {t('topup.action')}
      </h3>

      {paymentStatus === 'idle' && (
        <form onSubmit={handleGenerate} style={{ textAlign: 'left' }}>
          <p className="text-secondary" style={{ fontSize: '14px', lineHeight: '1.5', marginBottom: '20px' }}>
            {t('topup.desc')}
          </p>

          <label className="form-label" style={{ marginBottom: '10px' }} id="payment-method-label">
            {t('topup.payment_method')}
          </label>
          <div
            role="radiogroup"
            aria-labelledby="payment-method-label"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
              gap: '8px',
              marginBottom: '20px',
            }}
          >
            {(Object.keys(METHOD_META) as PaymentMethod[]).map((pm) => {
              const m = METHOD_META[pm];
              const active = pm === method;
              const handleKeyDown = (e: React.KeyboardEvent) => {
                const keys = Object.keys(METHOD_META) as PaymentMethod[];
                const idx = keys.indexOf(pm);
                let next = idx;
                if (e.key === 'ArrowRight') next = (idx + 1) % keys.length;
                else if (e.key === 'ArrowLeft') next = (idx - 1 + keys.length) % keys.length;
                else if (e.key === 'Home') next = 0;
                else if (e.key === 'End') next = keys.length - 1;
                else return;
                e.preventDefault();
                setMethod(keys[next]);
                document.getElementById(`payment-method-${keys[next]}`)?.focus();
              };
              return (
                <button
                  key={pm}
                  id={`payment-method-${pm}`}
                  role="radio"
                  aria-checked={active}
                  aria-label={m.label}
                  tabIndex={active ? 0 : -1}
                  type="button"
                  onKeyDown={handleKeyDown}
                  onClick={() => {
                    setMethod(pm);
                    setMessage(null);
                  }}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '14px 8px',
                    borderRadius: 'var(--radius-lg)',
                    border: active ? `2px solid ${m.color}` : '1px solid var(--border-subtle)',
                    background: active ? `${m.color}12` : 'var(--bg-surface)',
                    cursor: 'pointer',
                    transition: 'var(--transition-smooth)',
                    fontSize: '12px',
                    fontWeight: active ? '700' : '500',
                    color: active ? m.color : 'var(--text-secondary)',
                    opacity: 1,
                  }}
                >
                  <span style={{ fontSize: '24px', lineHeight: 1 }}>{m.icon}</span>
                  <span>{m.label}</span>
                </button>
              );
            })}
          </div>

          <div className="form-group">
            <label className="form-label">
              {method === 'zpoint' ? t('topup.amount_zpoints') : t('topup.select_amount')}
            </label>
            {method !== 'zpoint' && (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: '10px',
                  marginBottom: '12px',
                }}
              >
                {[300, 500, 1000].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setAmount(val)}
                    className={`btn-base btn-sm ${amount === val ? 'btn-primary' : 'btn-ghost'}`}
                    style={{ justifyContent: 'center' }}
                  >
                    ฿{val}
                  </button>
                ))}
              </div>
            )}
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(Number(e.target.value))}
              placeholder={t('topup.custom_amount_placeholder')}
              className="input-field font-mono"
            />
          </div>

          {method === 'zpoint' && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '12px 16px',
                borderRadius: 'var(--radius-md)',
                background: 'rgba(245,158,11,0.06)',
                border: '1px solid rgba(245,158,11,0.2)',
                marginBottom: '18px',
                fontSize: '13px',
                color: 'var(--text-secondary)',
              }}
            >
              <span style={{ fontSize: '16px' }}>⭐</span>
              <span>
                {t('topup.available_balance')}{' '}
                <strong style={{ color: '#F59E0B' }}>
                  {zpointBalance !== null ? `${zpointBalance.toFixed(0)} ${t('topup.points_unit')}` : '—'}
                </strong>
              </span>
            </div>
          )}

          {message && (
            <div
              className={`badge ${message.type === 'success' ? 'badge-accent' : 'badge-danger'}`}
              style={{
                display: 'flex',
                marginBottom: '12px',
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
              }}
            >
              <span>{message.text}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-base btn-primary btn-full"
          >
            {loading
              ? t('topup.processing')
              : method === 'zpoint'
                ? t('topup.deduct_zpoints')
                : t('topup.pay_with', { method: meta.label })}
          </button>
        </form>
      )}

      {paymentStatus === 'waiting' && session && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '10px 0' }}>
          {session.redirect_url ? (
            <>
              <div
                style={{
                  width: '72px',
                  height: '72px',
                  borderRadius: '50%',
                  background: `${meta.color}15`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '32px',
                  marginBottom: '16px',
                }}
              >
                {meta.icon}
              </div>
              <h4 className="h4" style={{ marginBottom: '8px' }}>
                {t('topup.redirecting_to', { method: meta.label })}
              </h4>
              <p className="text-secondary" style={{ fontSize: '14px', marginBottom: '20px', lineHeight: '1.5' }}>
                {t('topup.redirect_desc')}
              </p>
              <a
                href={session.redirect_url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-base btn-primary"
                style={{ textDecoration: 'none', marginBottom: '12px' }}
              >
                {t('topup.open_method', { method: meta.label })}
              </a>
              <span className="text-muted" style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span className="status-dot status-dot-info animate-pulse" />
                {t('topup.waiting_confirmation', { seconds: countdown })}
              </span>
              <button onClick={handleReset} className="btn-base btn-ghost btn-sm" style={{ marginTop: '12px' }}>
                {t('topup.cancel')}
              </button>
            </>
          ) : session.qr_image_base64 ? (
            <>
              <div
                style={{
                  background: 'white',
                  padding: '16px',
                  borderRadius: 'var(--radius-lg)',
                  boxShadow: 'var(--shadow-lg)',
                  marginBottom: '16px',
                  display: 'inline-block',
                  position: 'relative',
                }}
              >
                <div
                  style={{
                    background: meta.color,
                    color: 'white',
                    fontSize: '12px',
                    fontWeight: '700',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    marginBottom: '8px',
                    textAlign: 'center',
                    letterSpacing: '0.05em',
                  }}
                >
                  {meta.label}
                </div>
                <img
                  src={`data:image/png;base64,${session.qr_image_base64}`}
                  alt={t('topup.qr_code_alt', { method: meta.label })}
                  style={{ width: '200px', height: '200px', borderRadius: '6px', display: 'block' }}
                />
              </div>
              <strong style={{ fontSize: '20px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                ฿{session.amount.toFixed(2)} THB
              </strong>
              <span className="text-secondary" style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '20px' }}>
                <span className="status-dot status-dot-info animate-pulse" />
                {t('topup.waiting_verification', { seconds: countdown })}
              </span>
              <button onClick={handleReset} className="btn-base btn-ghost btn-sm">
                {t('topup.cancel')}
              </button>
            </>
          ) : null}
        </div>
      )}

      {paymentStatus === 'success' && (
        <div style={{ padding: '24px 0', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              background: 'var(--color-accent-bg)',
              border: '2px solid var(--color-accent)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--color-accent)',
              fontSize: '28px',
              fontWeight: '700',
              marginBottom: '16px',
              boxShadow: 'var(--shadow-glow-accent)',
            }}
          >
            ✓
          </div>
          <h4 className="h4" style={{ color: 'var(--color-accent)', marginBottom: '8px' }}>
            {method === 'zpoint' ? t('topup.points_deducted_title') : t('topup.success_title')}
          </h4>
          <p className="text-secondary" style={{ fontSize: '14px', marginBottom: '20px', lineHeight: '1.5' }}>
            {method === 'zpoint'
              ? t('topup.points_deducted_desc', { amount })
              : t('topup.success_desc', { amount })}
          </p>
          <button onClick={handleReset} className="btn-base btn-primary">
            {t('topup.done')}
          </button>
        </div>
      )}

      {message && paymentStatus !== 'idle' && (
        <div
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
