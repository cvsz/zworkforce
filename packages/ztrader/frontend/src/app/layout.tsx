import React from 'react';
import type { Metadata, Viewport } from 'next';
import './global.css';

export const metadata: Metadata = {
  title: 'ztrader | Unified Algorithmic Trading Platform',
  description:
    'Safety-First Multi-Language Algorithmic Trading Platform — Advanced order execution, risk management, and portfolio analytics.',
  keywords: [
    'algorithmic trading',
    'crypto trading bot',
    'trading platform',
    'ztrader',
    'quantitative trading',
  ],
  authors: [{ name: 'ZeaZDev' }],
  openGraph: {
    title: 'ztrader — Unified Trading Platform',
    description: 'Safety-First Multi-Language Algorithmic Trading Platform',
    type: 'website',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: [
    { media: '(prefers-color-scheme: dark)', color: '#060913' },
    { media: '(prefers-color-scheme: light)', color: '#f3f4f6' },
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
