'use client';

import { Globe } from 'lucide-react';
import { useLanguage } from '@/lib/i18n-provider';
import { localeNames, Locale } from '@/i18n/config';

export function LanguageToggle() {
  const { locale, setLocale } = useLanguage();

  const toggleLanguage = () => {
    const newLocale: Locale = locale === 'en' ? 'es' : 'en';
    setLocale(newLocale);
  };

  return (
    <button
      onClick={toggleLanguage}
      className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
      title={`Switch to ${locale === 'en' ? 'Español' : 'English'}`}
    >
      <Globe className="h-4 w-4" />
      <span className="font-medium">{localeNames[locale]}</span>
    </button>
  );
}

export function LanguageToggleCompact() {
  const { locale, setLocale } = useLanguage();

  const toggleLanguage = () => {
    const newLocale: Locale = locale === 'en' ? 'es' : 'en';
    setLocale(newLocale);
  };

  return (
    <button
      onClick={toggleLanguage}
      className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-gray-500 dark:text-gray-400"
      title={`Switch to ${locale === 'en' ? 'Español' : 'English'}`}
    >
      <Globe className="h-5 w-5" />
    </button>
  );
}
