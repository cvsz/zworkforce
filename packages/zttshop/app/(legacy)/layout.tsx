import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ibmPlexSans, ibmPlexSansThai, jetBrainsMono } from "@/app/fonts";
import "../globals.css";

export const metadata: Metadata = {
  title: "zTTShop — TikTok Shop API Client for PHP",
  description: "A resource-first PHP SDK for building TikTok Shop integrations with a clear, consistent request layer.",
  other: { "codex-preview": "development" },
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
};

export default function LegacyLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${ibmPlexSans.variable} ${ibmPlexSansThai.variable} ${jetBrainsMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
