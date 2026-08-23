import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LegalPage } from "@/app/components/legal-page";
import { isLocale, type Locale } from "@/app/i18n/config";
import { getDictionary } from "@/app/i18n/messages";

type PrivacyPageProps = Readonly<{ params: Promise<{ locale: string }> }>;

async function getLocale(params: PrivacyPageProps["params"]): Promise<Locale> {
  const { locale: rawLocale } = await params;
  if (!isLocale(rawLocale)) notFound();
  return rawLocale as Locale;
}

export async function generateMetadata({ params }: PrivacyPageProps): Promise<Metadata> {
  const locale = await getLocale(params);
  const dictionary = getDictionary(locale);
  return { title: dictionary.privacy.meta.title, description: dictionary.privacy.meta.description };
}

export default async function PrivacyPage({ params }: PrivacyPageProps) {
  const locale = await getLocale(params);
  const dictionary = getDictionary(locale);
  return <LegalPage locale={locale} kind="privacy" copy={dictionary.privacy} dictionary={dictionary} />;
}
