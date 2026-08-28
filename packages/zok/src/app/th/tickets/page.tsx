'use client';

import React from 'react';
import Sidebar from '@/components/Sidebar';
import { MessageSquare, PlayCircle, Link as LinkIcon } from 'lucide-react';
import EmptyState from '@/components/EmptyState';
import Link from 'next/link';

export default function TicketsPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar trialDaysRemaining={6} />
      
      <main className="lg:ml-64 pt-12 lg:pt-16 min-h-screen">
        {/* Top header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">ทิกเก็ต</h1>
          </div>
        </div>

        {/* Ticket filters */}
        <div className="px-6 py-4">
          <div className="flex items-center space-x-2 mb-6">
            <button className="px-4 py-2 bg-blue-50 text-blue-600 rounded-lg font-medium text-sm">
              ทิกเก็ตที่เปิดอยู่
            </button>
            <button className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium text-sm">
              ยังไม่ได้มอบหมาย
            </button>
            <button className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium text-sm">
              ทั้งหมด
            </button>
            <div className="flex-1" />
            <button className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium text-sm">
              ที่คุณปักหมุดไว้
            </button>
          </div>

          <div className="flex items-center space-x-2 mb-6 border-b border-gray-200 pb-2">
            <button className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium text-sm">
              ทั้งหมด
            </button>
            <button className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium text-sm">
              เสร็จสิ้น
            </button>
            <button className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium text-sm">
              ปิดแล้ว
            </button>
            <button className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium text-sm">
              กล่องสแปม
            </button>
          </div>
        </div>

        {/* Empty state */}
        <div className="px-6">
          <EmptyState
            icon={MessageSquare}
            title="⚡️พร้อมเริ่มต้นใช้งานหรือยัง?"
            actions={
              <>
                <Link
                  href="//book-a-demo"
                  className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  <PlayCircle size={18} className="mr-2" />
                  ดูเดโมสั้น ๆ
                </Link>
                <Link
                  href="https://demo.zok.zeaz.dev/?zcwopen=1&widgetId=26632d66-ddcd-4ff1-a993-fdee80d5091f"
                  target="_blank"
                  className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  <MessageSquare size={18} className="mr-2" />
                  ส่งข้อความทดสอบ
                </Link>
                <Link
                  href="/th/settings/chat-integrations"
                  className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
                >
                  <LinkIcon size={18} className="mr-2" />
                  เชื่อมต่อบัญชี
                </Link>
              </>
            }
          />
        </div>
      </main>
    </div>
  );
}
