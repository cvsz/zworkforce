'use client';

import React from 'react';
import Sidebar from '@/components/Sidebar';
import { Bot, Database, Sparkles, User, PlayCircle, CheckCircle, BarChart3 } from 'lucide-react';
import Link from 'next/link';

export default function AIBotPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar trialDaysRemaining={6} />
      
      <main className="lg:ml-64 pt-12 lg:pt-16 min-h-screen">
        {/* Top header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <h1 className="text-2xl font-bold text-gray-900">แชทบอท AI</h1>
        </div>

        <div className="flex">
          {/* Sidebar menu */}
          <aside className="w-64 border-r border-gray-200 bg-white min-h-[calc(100vh-140px)]">
            <nav className="p-4 space-y-1">
              <div className="mb-4">
                <h3 className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  สอน AI
                </h3>
                <Link
                  href="/th/ai-bot/knowledge"
                  className="flex items-center px-3 py-2 text-sm font-medium bg-blue-50 text-blue-600 rounded-lg"
                >
                  <Database size={18} className="mr-3" />
                  เพิ่มฐานข้อมูล
                </Link>
                <Link
                  href="/th/ai-bot/prompts"
                  className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg"
                >
                  <Sparkles size={18} className="mr-3" />
                  กำหนดชุดคำสั่ง
                </Link>
                <Link
                  href="/th/ai-bot/personality"
                  className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg"
                >
                  <User size={18} className="mr-3" />
                  สร้างบุคลิก AI
                </Link>
              </div>

              <div className="mb-4">
                <h3 className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  เริ่มใช้งาน
                </h3>
                <Link
                  href="/th/ai-bot/test"
                  className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg"
                >
                  <PlayCircle size={18} className="mr-3" />
                  ทดสอบ
                </Link>
                <Link
                  href="/th/ai-bot/activate"
                  className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg"
                >
                  <CheckCircle size={18} className="mr-3" />
                  เปิดใช้งาน
                </Link>
              </div>

              <div>
                <h3 className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  การติดตาม
                </h3>
                <Link
                  href="/th/ai-bot/analytics"
                  className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg"
                >
                  <BarChart3 size={18} className="mr-3" />
                  วิเคราะห์ข้อมูล
                </Link>
              </div>
            </nav>
          </aside>

          {/* Main content */}
          <div className="flex-1 p-6">
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div className="mb-6">
                <h2 className="text-xl font-bold text-gray-900 mb-2">เพิ่มฐานข้อมูล</h2>
                <p className="text-gray-600">
                  ช่วยให้ AI ตอบได้ดีขึ้นโดยการเพิ่มข้อมูลสำคัญ เช่น นโยบาย คำถามที่พบบ่อย 
                  และรายละเอียดเกี่ยวกับธุรกิจ ผลิตภัณฑ์ หรือบริการของคุณ
                </p>
              </div>

              {/* Storage info */}
              <div className="mb-6 p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700">พื้นที่จัดเก็บ:</span>
                  <span className="text-sm text-gray-600">0/7,500,000 ตัวอักษร</span>
                </div>
                <div className="mt-2 bg-gray-200 rounded-full h-2">
                  <div className="bg-blue-600 h-2 rounded-full" style={{ width: '0%' }}></div>
                </div>
              </div>

              {/* Add database button */}
              <button className="mb-6 px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700">
                เพิ่มฐานข้อมูล
              </button>

              {/* Filter tabs */}
              <div className="flex items-center space-x-2 mb-4 border-b border-gray-200 pb-2">
                <button className="px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded">
                  ประเภทของฐานข้อมูล
                </button>
                <button className="px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded">
                  ช่องทาง
                </button>
                <button className="px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded">
                  สร้างโดย
                </button>
              </div>

              {/* Empty table */}
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">สถานะ</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ชื่อฐานข้อมูล</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ประเภทของฐานข้อมูล</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ใช้กับการเชื่อมต่อ</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ตัวอักษร</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">อัปโหลดโดย</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">อัพเดตโดย</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">สร้างเมื่อ</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    <tr>
                      <td colSpan={8} className="px-6 py-12 text-center">
                        <div className="flex flex-col items-center">
                          <Database size={48} className="text-gray-300 mb-4" />
                          <p className="text-gray-500">ไม่มีข้อมูล</p>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
