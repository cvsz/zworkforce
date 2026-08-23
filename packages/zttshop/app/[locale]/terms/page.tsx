import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LegalPage } from "@/app/components/legal-page";
import { isLocale, type Locale } from "@/app/i18n/config";
import { getDictionary } from "@/app/i18n/messages";

type TermsPageProps = Readonly<{ params: Promise<{ locale: string }> }>;

async function getLocale(params: TermsPageProps["params"]): Promise<Locale> {
  const { locale: rawLocale } = await params;
  if (!isLocale(rawLocale)) notFound();
  return rawLocale as Locale;
}

export async function generateMetadata({ params }: TermsPageProps): Promise<Metadata> {
  const locale = await getLocale(params);
  const dictionary = getDictionary(locale);
  return { title: dictionary.terms.meta.title, description: dictionary.terms.meta.description };
}

export default async function TermsPage({ params }: TermsPageProps) {
  const locale = await getLocale(params);
  const dictionary = getDictionary(locale);
  return <LegalPage locale={locale} kind="terms" copy={dictionary.terms} dictionary={dictionary} />;
}
