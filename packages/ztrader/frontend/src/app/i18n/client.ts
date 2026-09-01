"use client";

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import enTranslation from '../../../public/locales/en/translation.json';
import thTranslation from '../../../public/locales/th/translation.json';
import zhTranslation from '../../../public/locales/zh/translation.json';
import jaTranslation from '../../../public/locales/ja/translation.json';

let initialized = false;

export function initI18n(locale: string) {
  if (!initialized) {
    i18n
      .use(LanguageDetector)
      .use(initReactI18next)
      .init({
        lng: locale,
        fallbackLng: 'en',
        supportedLngs: ['en', 'th', 'zh', 'ja'],
        defaultNS: 'translation',
        ns: ['translation'],
        detection: {
          order: ['path', 'querystring', 'navigator'],
          caches: [],
        },
        resources: {
          en: { translation: enTranslation },
          th: { translation: thTranslation },
          zh: { translation: zhTranslation },
          ja: { translation: jaTranslation },
        },
      });
    initialized = true;
  } else if (i18n.language !== locale) {
    i18n.changeLanguage(locale);
  }
  return i18n;
}

export { i18n };
