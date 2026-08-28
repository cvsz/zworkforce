'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  MessageSquare, 
  Users, 
  Ticket, 
  ShoppingCart, 
  FileText, 
  Settings, 
  Bot, 
  BarChart3, 
  Zap, 
  Send,
  Menu,
  X,
  Bell,
  Search,
  HelpCircle
} from 'lucide-react';

interface SidebarProps {
  trialDaysRemaining: number;
}

const menuItems = [
  { icon: MessageSquare, label: 'ทิกเก็ต', href: '/th/tickets', badge: null },
  { icon: Users, label: 'ผู้ติดต่อ', href: '/th/contacts', badge: null },
  { icon: Ticket, label: 'การสนทนา', href: '/th/conversations', badge: null },
  { icon: ShoppingCart, label: 'คำสั่งซื้อ', href: '/th/orders', badge: null },
  { icon: FileText, label: 'โน้ต', href: '/th/notes', badge: null },
  { type: 'divider' },
  { icon: Bot, label: 'แชทบอท AI', href: '/th/ai-bot', badge: null },
  { icon: BarChart3, label: 'วิเคราะห์', href: '/th/analytics', badge: 'ใหม่' },
  { icon: Zap, label: 'ระบบอัตโนมัติ', href: '/th/automations', badge: null },
  { icon: Send, label: 'บรอดแคสต์', href: '/th/broadcasts', badge: null },
  { type: 'divider' },
  { icon: Settings, label: 'ตั้งค่า', href: '/th/settings', badge: null },
];

export default function Sidebar({ trialDaysRemaining }: SidebarProps) {
  const pathname = usePathname();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <>
      {/* Mobile menu button */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <img src="/images/favicon.png" alt="Zok" className="h-8 w-8" />
          <span className="font-semibold text-lg">Zok</span>
        </div>
        <button
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          className="p-2 rounded-lg hover:bg-gray-100"
        >
          {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Trial banner */}
      <div className="fixed top-0 left-0 right-0 z-40 bg-gradient-to-r from-orange-50 to-amber-50 border-b border-orange-200 px-6 py-2 hidden lg:flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-sm text-orange-800">
            ทดลองใช้ฟรีจะหมดอายุใน <strong>{trialDaysRemaining}</strong> วัน
          </span>
        </div>
        <Link
          href="/th/register"
          className="text-sm font-medium text-orange-600 hover:text-orange-700"
        >
          สมัครตอนนี้ →
        </Link>
      </div>

      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 h-full w-64 bg-white border-r border-gray-200 z-30
        transform transition-transform duration-300 ease-in-out
        lg:translate-x-0 lg:pt-12
        ${isMobileMenuOpen ? 'translate-x-0 pt-12' : '-translate-x-full pt-12'}
      `}>
        {/* Logo */}
        <div className="px-6 py-4 border-b border-gray-100 hidden lg:block">
          <Link href="/th/dashboard" className="flex items-center space-x-3">
            <img src="/images/favicon.png" alt="Zok" className="h-8 w-8" />
            <span className="font-semibold text-xl">Zok</span>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="px-3 py-4 space-y-1 overflow-y-auto h-[calc(100vh-180px)]">
          {menuItems.map((item, index) => {
            if (item.type === 'divider') {
              return <div key={index} className="my-4 border-t border-gray-100" />;
            }

            const isActive = pathname === item.href || pathname?.startsWith(`${item.href}/`);
            const Icon = item.icon as React.ElementType;

            return (
              <Link
                key={index}
                href={item.href!}
                className={`
                  flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium
                  transition-colors duration-150
                  ${isActive 
                    ? 'bg-blue-50 text-blue-600' 
                    : 'text-gray-700 hover:bg-gray-50'
                  }
                `}
              >
                <div className="flex items-center space-x-3">
                  <Icon size={20} strokeWidth={isActive ? 2.5 : 2} />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-600 rounded-full">
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Help section */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-100 bg-white">
          <Link
            href="https://help.zok.zeaz.dev"
            target="_blank"
            className="flex items-center space-x-2 text-sm text-gray-600 hover:text-gray-900"
          >
            <HelpCircle size={18} />
            <span>ศูนย์ช่วยเหลือ</span>
          </Link>
        </div>
      </aside>

      {/* Mobile overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-20 lg:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}
    </>
  );
}
