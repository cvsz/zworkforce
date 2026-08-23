import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { ibmPlexSans, ibmPlexSansThai, jetBrainsMono } from "@/app/fonts";
import { getDictionary } from "@/app/i18n/messages";
import { isLocale, locales, type Locale } from "@/app/i18n/config";
import "../globals.css";

type LocaleLayoutProps = Readonly<{
  children: ReactNode;
  params: Promise<{ locale: string }>;
}>;

async function resolveLocale(params: LocaleLayoutProps["params"]): Promise<Locale> {
  const { locale } = await params;

  if (!isLocale(locale)) {
    notFound();
  }

  return locale;
}

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: LocaleLayoutProps): Promise<Metadata> {
  const locale = await resolveLocale(params);
  const dictionary = getDictionary(locale);

  return {
    title: dictionary.site.meta.title,
    description: dictionary.site.meta.description,
    other: { "codex-preview": "development" },
    icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
  };
}

export default async function LocaleLayout({ children, params }: LocaleLayoutProps) {
  const locale = await resolveLocale(params);

  return (
    <html lang={locale}>
      <body className={`${ibmPlexSans.variable} ${ibmPlexSansThai.variable} ${jetBrainsMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
