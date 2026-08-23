import { notFound } from "next/navigation";
import { HomePage } from "@/app/components/home-page";
import { isLocale, type Locale } from "@/app/i18n/config";
import { getDictionary } from "@/app/i18n/messages";

export default async function LocalizedHomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: rawLocale } = await params;

  if (!isLocale(rawLocale)) {
    notFound();
  }

  const locale = rawLocale as Locale;
  const dictionary = getDictionary(locale);

  return <HomePage locale={locale} copy={dictionary.home} common={dictionary.common} />;
}
