import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import '../styles/globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Zok - Omnichannel Customer Support Platform',
  description: 'Manage all your customer conversations in one place. Facebook, Instagram, WhatsApp, LINE, Shopee, Lazada, TikTok Shop, and more.',
  keywords: ['customer support', 'helpdesk', 'omnichannel', 'live chat', 'ticketing system'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="th">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
