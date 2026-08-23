"use client";

import { useEffect, useRef, useState, type MouseEvent } from "react";
import Link from "next/link";
import type { HomeCopy } from "@/app/i18n/messages";
import { localeNames, localizedPath, locales, type Locale } from "@/app/i18n/config";
import { ArrowIcon, GlobeIcon, MenuIcon } from "@/app/components/icons";

const githubUrl = "https://github.com/cvsz/zttshop-php";
const setupUrl = "https://github.com/cvsz/zttshop-php/blob/main/SETUP.md";

type BrandProps = Readonly<{ compact?: boolean }>;

export function Brand({ compact = false }: BrandProps) {
  return (
    <span className="brand-lockup">
      <span className="brand-mark">zT</span>
      <span className={compact ? "brand-text brand-text-compact" : "brand-text"}>
        <strong>zTTShop</strong>
        <small>PHP SDK</small>
      </span>
    </span>
  );
}

type LanguageSwitcherProps = Readonly<{
  locale: Locale;
  pathname: "" | "privacy" | "terms";
  label: string;
  names: Record<Locale, string>;
}>;

function LanguageSwitcher({ locale, pathname, label, names }: LanguageSwitcherProps) {
  const [hash, setHash] = useState(() => (typeof window !== "undefined" ? window.location.hash : ""));

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handleHashChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  return (
    <div className="language-switcher" aria-label={label}>
      <GlobeIcon />
      <span className="language-switcher-label">{label}</span>
      <span className="language-switcher-options">
        {locales.map((targetLocale) => {
          const targetHref = `${localizedPath(targetLocale, pathname)}${hash}`;
          return (
            <Link
              className={targetLocale === locale ? "language-option language-option-active" : "language-option"}
              href={targetHref}
              key={targetLocale}
              aria-current={targetLocale === locale ? "page" : undefined}
              onClick={() => {
                if (typeof window !== "undefined") {
                  setHash(window.location.hash);
                }
              }}
            >
              {names[targetLocale] ?? localeNames[targetLocale]}
            </Link>
          );
        })}
      </span>
    </div>
  );
}

type SiteNavProps = Readonly<{
  locale: Locale;
  copy: HomeCopy["nav"];
  languageNames: Record<Locale, string>;
  pathname?: "" | "privacy" | "terms";
  homeLabel: string;
}>;

export function SiteNav({ locale, copy, languageNames, pathname = "", homeLabel }: SiteNavProps) {
  const homeHref = localizedPath(locale);
  const detailsRef = useRef<HTMLDetailsElement>(null);

  const handleMobileNavClick = (e: MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (target.closest("a")) {
      if (detailsRef.current) {
        detailsRef.current.open = false;
      }
    }
  };

  return (
    <header className="site-nav shell">
      <Link className="brand" href={homeHref} aria-label={`${homeLabel} zTTShop`}>
        <Brand />
      </Link>

      <nav className="nav-links" aria-label={homeLabel}>
        <a href={`${homeHref}#capabilities`}>{copy.capabilities}</a>
        <a href={`${homeHref}#workflow`}>{copy.workflow}</a>
        <a href={`${homeHref}#coverage`}>{copy.coverage}</a>
      </nav>

      <div className="nav-actions">
        <a className="nav-source" href={githubUrl} target="_blank" rel="noreferrer">
          {copy.source} <ArrowIcon />
        </a>
        <LanguageSwitcher locale={locale} pathname={pathname} label={copy.language} names={languageNames} />
        <a className="button button-primary button-small" href={`${homeHref}#workflow`}>
          {copy.startBuilding} <ArrowIcon />
        </a>
        <details ref={detailsRef} className="mobile-menu">
          <summary className="mobile-menu-toggle" aria-label={copy.openMenu}>
            <MenuIcon />
          </summary>
          <div className="mobile-menu-panel" onClick={handleMobileNavClick}>
            <a href={`${homeHref}#capabilities`}>{copy.capabilities}</a>
            <a href={`${homeHref}#workflow`}>{copy.workflow}</a>
            <a href={`${homeHref}#coverage`}>{copy.coverage}</a>
            <a href={githubUrl} target="_blank" rel="noreferrer">{copy.source}</a>
            <LanguageSwitcher locale={locale} pathname={pathname} label={copy.language} names={languageNames} />
            <a className="button button-primary mobile-menu-cta" href={`${homeHref}#workflow`}>
              {copy.startBuilding} <ArrowIcon />
            </a>
          </div>
        </details>
      </div>
    </header>
  );
}

type SiteFooterProps = Readonly<{
  locale: Locale;
  copy: HomeCopy["footer"];
  common: {
    privacy: string;
    terms: string;
    setup: string;
    source: string;
  };
  variant?: "home" | "legal";
}>;

export function SiteFooter({ locale, copy, common, variant = "home" }: SiteFooterProps) {
  const homeHref = localizedPath(locale);

  return (
    <footer className={variant === "legal" ? "footer legal-footer shell" : "footer shell"}>
      <Link className="brand" href={homeHref} aria-label="zTTShop home">
        <Brand />
      </Link>
      <p>{copy.description}</p>
      <div className="footer-links">
        <a href={setupUrl} target="_blank" rel="noreferrer">{copy.setup || common.setup}</a>
        <a href={githubUrl} target="_blank" rel="noreferrer">{copy.source || common.source}</a>
        <Link href={localizedPath(locale, "privacy")}>{copy.privacy || common.privacy}</Link>
        <Link href={localizedPath(locale, "terms")}>{copy.terms || common.terms}</Link>
      </div>
    </footer>
  );
}

export { githubUrl, setupUrl };
