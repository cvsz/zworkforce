'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function NotFound() {
  const pathname = usePathname();
  const lng = pathname?.split('/')[1] || 'en';

  return (
    <div
      style={{
        maxWidth: '480px',
        margin: '120px auto',
        padding: '48px 32px',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          fontSize: '64px',
          fontWeight: '800',
          color: 'var(--text-muted)',
          lineHeight: 1,
          marginBottom: '12px',
          opacity: 0.3,
          letterSpacing: '-0.04em',
          fontFamily: 'var(--font-mono)',
        }}
      >
        404
      </div>
      <h2
        style={{
          fontSize: '20px',
          fontWeight: '700',
          marginBottom: '8px',
          color: 'var(--text-primary)',
        }}
      >
        Page Not Found
      </h2>
      <p
        style={{
          fontSize: '14px',
          color: 'var(--text-muted)',
          marginBottom: '28px',
          lineHeight: 1.6,
        }}
      >
        The page you are looking for does not exist or has been moved.
      </p>
      <Link
        href={`/${lng}/dashboard`}
        className="btn-base btn-primary"
        style={{
          padding: '12px 32px',
          fontSize: '14px',
          fontWeight: '600',
          textDecoration: 'none',
          display: 'inline-block',
        }}
      >
        Go to Dashboard
      </Link>
    </div>
  );
}
