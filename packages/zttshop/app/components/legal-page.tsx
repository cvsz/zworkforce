import Link from "next/link";
import type { Locale } from "@/app/i18n/config";
import { localizedPath } from "@/app/i18n/config";
import type { Dictionary, LegalCopy } from "@/app/i18n/messages";
import { SiteFooter, SiteNav } from "@/app/components/site-shell";

type LegalPageProps = Readonly<{
  locale: Locale;
  kind: "privacy" | "terms";
  copy: LegalCopy;
  dictionary: Dictionary;
}>;

export function LegalPage({ locale, kind, copy, dictionary }: LegalPageProps) {
  const homeHref = localizedPath(locale);

  return (
    <main className="legal-page" id="top">
      <a className="skip-link" href="#legal-content">{dictionary.common.skipToContent}</a>
      <SiteNav
        locale={locale}
        copy={dictionary.home.nav}
        languageNames={dictionary.common.languageNames}
        pathname={kind}
        homeLabel={dictionary.common.home}
      />

      <header className="legal-hero shell">
        <p className="section-kicker legal-kicker">{copy.kicker}</p>
        <h1>{copy.title}</h1>
        <p className="legal-intro">{copy.intro}</p>
        <span>{copy.effective}</span>
      </header>

      <article className="legal-content shell" id="legal-content">
        <nav className="legal-index" aria-label={copy.indexLabel}>
          <b>{copy.indexLabel}</b>
          {copy.sections.map((section) => <a href={`#${section.id}`} key={section.id}>{section.title}</a>)}
        </nav>

        <div className="legal-copy">
          {copy.sections.map((section) => (
            <section id={section.id} key={section.id} aria-labelledby={`${section.id}-title`}>
              <span>{section.number}</span>
              <h2 id={`${section.id}-title`}>{section.title}</h2>
              <p>
                {section.body}
                {section.link && (
                  <>
                    {" "}
                    <a href={section.link.href} target="_blank" rel="noreferrer">{section.link.label}</a>
                    {section.link.suffix}
                  </>
                )}
              </p>
            </section>
          ))}
        </div>
      </article>

      <div className="legal-return shell">
        <Link className="button button-secondary" href={homeHref}>{copy.backToHome}</Link>
      </div>

      <SiteFooter locale={locale} copy={dictionary.home.footer} common={dictionary.common} variant="legal" />
    </main>
  );
}
