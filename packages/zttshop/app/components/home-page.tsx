import { Fragment } from "react";
import Link from "next/link";
import { localizedPath, type Locale } from "@/app/i18n/config";
import type { HomeCopy, Dictionary } from "@/app/i18n/messages";
import { ArrowIcon, CheckIcon, RouteIcon, ShieldIcon, StackIcon, TerminalIcon } from "@/app/components/icons";
import { SiteFooter, SiteNav, githubUrl } from "@/app/components/site-shell";
import { CopyButton } from "@/app/components/copy-button";

const installCode = "composer require haistar/tiktokshop-api-client";

const quickStart = `use Aftwork\\TiktokShop\\Common\\TiktokShopConfig;
use Aftwork\\TiktokShop\\Resource\\General\\TiktokShopGeneralResource;

$config = new TiktokShopConfig();
$config->setAppKey(getenv('APP_KEY'));
$config->setSecretKey(getenv('APP_SECRET'));
$config->setAccessToken(getenv('ACCESS_TOKEN'));

$shops = (new TiktokShopGeneralResource())->httpCallGet(
    getenv('SERVER_URL'),
    '/authorization/202309/shops',
    [],
    $config
);`;

function CapabilityIcon({ icon }: Readonly<{ icon: "shield" | "stack" | "route" }>) {
  if (icon === "shield") return <ShieldIcon />;
  if (icon === "stack") return <StackIcon />;
  return <RouteIcon />;
}

type HomePageProps = Readonly<{
  locale: Locale;
  copy: HomeCopy;
  common: Dictionary["common"];
}>;

export function HomePage({ locale, copy, common }: HomePageProps) {
  const monitor = copy.hero.monitor;

  return (
    <main className="home-page" id="top">
      <a className="skip-link" href="#content">{common.skipToContent}</a>

      <SiteNav locale={locale} copy={copy.nav} languageNames={common.languageNames} homeLabel={common.home} />

      <div id="content">
        <section className="hero shell">
          <div className="hero-copy">
            <p className="eyebrow"><span className="eyebrow-pulse" /> {copy.hero.eyebrow}</p>
            <h1>{copy.hero.titleBefore}<br /><em>{copy.hero.titleAccent}</em></h1>
            <p className="hero-lead">{copy.hero.lead}</p>

            <div className="hero-actions">
              <a className="button button-primary" href="#workflow">
                {copy.hero.primary} <ArrowIcon />
              </a>
              <a className="button button-secondary" href={githubUrl} target="_blank" rel="noreferrer">
                {copy.hero.secondary}
              </a>
            </div>

            <div className="install-bar" aria-label="Composer installation command">
              <span className="install-prompt">$</span>
              <code>{installCode}</code>
              <span className="install-label">{copy.hero.installLabel}</span>
              <CopyButton text={installCode} className="install-copy-button" />
            </div>

            <div className="hero-notes" aria-label="Product qualities">
              {copy.hero.notes.map((note) => <span key={note}><CheckIcon /> {note}</span>)}
            </div>
          </div>

          <div className="hero-visual" aria-label={monitor.title}>
            <div className="demo-shell">
              <div className="demo-toolbar">
                <span className="window-dots" aria-hidden="true"><i /><i /><i /></span>
                <span className="demo-title">zttshop / request monitor</span>
                <span className="demo-live"><span /> {monitor.live}</span>
              </div>

              <div className="demo-body">
                <div className="demo-context">
                  <div>
                    <span className="demo-label">{monitor.label}</span>
                    <strong>{monitor.statement}</strong>
                  </div>
                  <span className="demo-chip">{monitor.chip}</span>
                </div>

                <div className="request-card">
                  <div className="request-topline">
                    <span className="method-badge">GET</span>
                    <code>{monitor.path}</code>
                  </div>
                  <div className="request-meta">
                    <span><TerminalIcon /> {monitor.resource}</span>
                    <span><ShieldIcon /> {monitor.signed}</span>
                  </div>
                </div>

                <div className="flow-line" aria-hidden="true"><span /></div>

                <div className="response-card">
                  <div className="response-topline">
                    <span className="status-badge"><CheckIcon /> {monitor.status}</span>
                    <span className="response-time">{monitor.responseTime}</span>
                  </div>
                  <div className="response-grid">
                    {monitor.stats.map((stat) => <div key={stat.label}><span>{stat.label}</span><strong>{stat.value}</strong></div>)}
                  </div>
                </div>

                <div className="demo-footer">
                  <span className="demo-footer-icon"><RouteIcon /></span>
                  <span>{monitor.footer}</span>
                </div>
              </div>
            </div>

            <div className="visual-tag visual-tag-top"><span>01</span> {monitor.requestLabel}</div>
            <div className="visual-tag visual-tag-bottom"><span>02</span> {monitor.responseLabel}</div>
          </div>
        </section>

        <section className="proof-strip shell" aria-label="Package highlights">
          {copy.proof.map((point) => (
            <article key={point.label}>
              <strong>{point.value}</strong>
              <span>{point.label}</span>
            </article>
          ))}
        </section>

        <section className="section capabilities" id="capabilities">
          <div className="shell">
            <div className="section-intro">
              <p className="section-kicker"><span>01</span> {copy.capabilities.kicker}</p>
              <h2>{copy.capabilities.title}</h2>
              <p>{copy.capabilities.intro}</p>
            </div>

            <div className="capability-grid">
              {copy.capabilities.cards.map((card, index) => (
                <article className={index === 0 ? "capability-card capability-card-accent" : "capability-card"} key={card.code}>
                  <div className="card-topline"><span className="card-index">{card.index}</span><span className="card-status">{card.status}</span></div>
                  <div className="icon-frame"><CapabilityIcon icon={card.icon} /></div>
                  <h3>{card.title}</h3>
                  <p>{card.body}</p>
                  <span className="card-code">{card.code}</span>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="section workflow" id="workflow">
          <div className="shell">
            <div className="section-intro section-intro-dark">
              <p className="section-kicker"><span>02</span> {copy.workflow.kicker}</p>
              <h2>{copy.workflow.title}</h2>
              <p>{copy.workflow.intro}</p>
            </div>

            <div className="workflow-layout">
              <ol className="journey-list">
                {copy.workflow.steps.map((step, index) => (
                  <li className={index === 1 ? "journey-item journey-item-active" : "journey-item"} key={step.number}>
                    <span className="journey-number">{step.number}</span>
                    <div><span className="journey-label">{step.label}</span><h3>{step.title}</h3><p>{step.detail}</p></div>
                  </li>
                ))}
              </ol>

              <div className="code-panel">
                <div className="code-panel-header">
                  <div><span className="code-dot" /> {copy.workflow.fileName}</div>
                  <div className="code-panel-actions">
                    <span>{copy.workflow.language}</span>
                    <CopyButton text={quickStart} className="code-copy-button" />
                  </div>
                </div>
                <pre><code>{quickStart}</code></pre>
                <div className="code-panel-footer"><CheckIcon /> {copy.workflow.footer}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="section coverage" id="coverage">
          <div className="shell">
            <div className="section-intro coverage-intro">
              <p className="section-kicker"><span>03</span> {copy.coverage.kicker}</p>
              <h2>{copy.coverage.title}</h2>
              <p>{copy.coverage.intro}</p>
            </div>

            <div className="resource-grid">
              {copy.coverage.resources.map((resource) => (
                <article className="resource-card" key={resource.name}>
                  <span className="resource-index">{resource.index}</span>
                  <div><h3>{resource.name}</h3><p>{resource.detail}</p></div>
                  <ArrowIcon />
                </article>
              ))}
            </div>

            <div className="endpoint-ribbon" aria-label="Integration path">
              {copy.coverage.ribbon.map((step, index) => (
                <Fragment key={step.title}>
                  <span><b>{step.title}</b><small>{step.detail}</small></span>
                  {index < copy.coverage.ribbon.length - 1 && <i aria-hidden="true" />}
                </Fragment>
              ))}
            </div>
          </div>
        </section>

        <section className="final-cta shell">
          <div>
            <p className="section-kicker"><span>04</span> {copy.cta.kicker}</p>
            <h2>{copy.cta.title}</h2>
            <p>{copy.cta.body}</p>
          </div>
          <div className="cta-actions">
            <a className="button button-primary" href={githubUrl} target="_blank" rel="noreferrer">{copy.cta.github} <ArrowIcon /></a>
            <Link className="button button-secondary" href={localizedPath(locale, "terms")}>{copy.cta.terms}</Link>
          </div>
        </section>
      </div>

      <SiteFooter locale={locale} copy={copy.footer} common={common} />
    </main>
  );
}
