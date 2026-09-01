# UX/UI Review — ztrader (multi-lingual crypto trading terminal)

## Language and Coding Standards
- **Communication**: Always talk in Thai when interacting with users.
- **Code & Technical Assets**: All code, comments, documentation, and technical definitions must be in English.

Date: 2026-06-13
Scope: login, dashboard, admin, settings, navigation, GoogleSignIn, ChartWidget, TelegramLink, TradingViewConfig, ThemeCustomizer, NotificationPreferences, PromptPayTopup.
Locales: en, th, zh, ja.

## Executive summary

ztrader is a production-grade crypto trading terminal with a polished glassmorphism design system, full i18n across 4 locales, and real API connectivity. The current UI is functionally complete and visually cohesive, but several UX and accessibility gaps prevent it from being truly production-ready for diverse users:

1. **Near-zero ARIA and screen reader support** — dynamic regions (toasts, ticker, alerts) have no live regions; tab interfaces lack ARIA roles; no focus management.
2. **Inconsistent `<form>` usage** — several mutation actions use `onClick` buttons instead of `<form onSubmit>`, breaking keyboard submission.
3. **Heading hierarchy skips `<h2>`** — all pages go from `<h1>` → `<h3>` directly, which fails WCAG 1.3.1.
4. **Uneven empty-state and error-retry coverage** — some sections show helpful empty messages; others render nothing.
5. **Several Settings sub-components have hardcoded English strings** despite the app being fully localized.
6. **ChartWidget is completely inaccessible** — screen readers encounter an opaque `<div>` with no `aria-label` or fallback.

## Findings by evaluation criteria

### 1) Information architecture
- Login → Dashboard → Settings/Admin is a clean, linear flow.
- No workflow "next step" guidance between pages (e.g., after login, user lands on a dashboard with no onboarding prompt).
- Admin tabs (Overview, Users, Contracts, Risk) are logically grouped.

### 2) Navigation
- Fixed top bar with scroll-aware styling works well on desktop and mobile.
- Desktop menu items are clean and minimal (Dashboard, Settings, Admin).
- Mobile hamburger opens a full slide-down drawer duplicating the menu.
- **No persistent breadcrumb trail** — user navigating between Settings sections has no location context.
- **No `aria-expanded`** on the hamburger button.
- **No escape-key handler** to close the mobile drawer.
- **No `aria-current="page"`** on active nav links — screen readers cannot identify current page.

### 3) i18n coverage
- **Excellent at page level** — 256 translation keys across 4 locales, used in all major pages.
- **Inconsistent in Settings sub-components** — TelegramLink, TradingViewConfig, and NotificationPreferences have hardcoded English strings for error messages, descriptions, and helper text.
- All 4 locale files (en/th/zh/ja) are fully populated for page-level content.

### 4) Empty states
- Good: audit log shows "No audit logs yet.", TradingViewConfig shows "No webhook alerts captured yet."
- Missing: **bot list** on dashboard renders nothing when empty. **User and contract tables** on admin render no rows with no message. **ChartWidget** shows a blank canvas with no "No data" overlay.
- PromptPayTopup's `idle` state has all elements visible (method selector + amount form) which is correct progressive disclosure.

### 5) Loading states
- **Dashboard and Admin** use `Shimmer` skeleton components for async content (risk limits, charts, tables). Good pattern.
- **Settings components** use text-based loading indicators ("Saving...", "Processing...", "Linking Account..."). Functional but below the visual polish of the rest of the app.
- **ChartWidget** has no loading state — parent manages it with a skeleton placeholder.
- **TradingViewConfig** has **no loading state at all** — fetch errors go to `console.error` silently.

### 6) Error states
- Consistent toast/badge error pattern used in Dashboard, Admin, Settings, TelegramLink, NotificationPreferences, PromptPayTopup.
- Backend error detail parsing (`err.detail`) used in most mutation components.
- **No retry buttons** on any error state — user must refresh the page or wait for polling.
- **Login page** shows no user-visible error — OAuth errors go to `console.error` only.

### 7) Form validation
- **Dashboard** has good validation: notional > 0, fast/slow periods as integers, fast < slow, symbol contains `/`.
- **Settings API keys** validates `apiKey` and `apiSecret` are non-empty.
- **PromptPayTopup** validates amount > 0, checks Z Point balance.
- **TelegramLink** validates `chatId` is non-empty.
- **Admin risk settings** validates max notional is a number, symbols are comma-separated.
- **No inline error messages** next to fields — errors appear in a top-level message badge, not per-field.
- **No `required` HTML attributes** on any input — validation is JS-only.

### 8) Form structure (keyboard submission)
- **Good forms**: Dashboard Start Bot (form + onSubmit), Settings API Keys (form + onSubmit), PromptPay Topup (form + onSubmit).
- **Broken for keyboard**: Admin users/contracts/risk sections use `<button onClick>` instead of `<form onSubmit>`. TelegramLink and NotificationPreferences also use button-only submission. These cannot be submitted by pressing Enter in an input field.

### 9) Mobile responsiveness
- Breakpoints at 768px, 640px, 480px, 360px.
- Tables transform to stacked cards at ≤640px using `data-label` attributes.
- LanguageSelector repositions to bottom-left at ≤768px.
- Background orbs hidden on mobile.
- Toast spans full width on mobile.
- `btn-sm` forced to 44×44px for WCAG 2.2 touch compliance.
- Container padding uses `clamp()` everywhere.
- **Admin contract form** collapses to 1 column via `.admin-three-col`.

### 10) Accessibility (WCAG)
- **ARIA: near-zero.** No `aria-live` on any dynamic region (toast, ticker, alerts feed). No `role="alert"` on error messages. No `role="tablist"`/`role="tab"`/`role="tabpanel"` on admin tabs. No `aria-expanded` on hamburger. No `aria-current` on navigation. No `role="radiogroup"` on payment method selector. No `aria-pressed` on kill-switch toggle.
- **Heading hierarchy**: All pages use `<h1>` → `<h3>` with no `<h2>`. WCAG 1.3.1 failure.
- **Labels**: All form controls have `<label>` elements — good.
- **Tables**: No `<caption>`, no `scope` on `<th>`, no `aria-sort`.
- **ChartWidget**: Canvas has no `aria-label`, no `role="img"`, no fallback text. Completely opaque to screen readers.
- **Focus management**: No focus management on toast appearance, modal drawer open/close, or form submission.
- **Color contrast**: Glassmorphism with semi-transparent backgrounds on light text may fail WCAG 1.4.3 at smaller font sizes. Needs verification.
- **Skip navigation**: No skip-to-content link.

### 11) CTA clarity
- Dashboard: Primary CTA is the "Start Bot" form (good placement below metrics).
- Admin: Kill-switch toggle is visually prominent with pulsing animation.
- Settings: API key form is the first item (correct priority).
- **No "recommended next step"** on any page after a user action completes.

### 12) Dashboard metrics usefulness
- PnL display with animated counter (good).
- Active bot count, execution mode, kill-switch status.
- **Missing**: historical performance trend, profit curve mini-chart, error rate, trade count today.
- Current metrics are real-time snapshots with no time-context.

### 13) Security UX
- Token URL param cleaned synchronously via `replaceState()` before `localStorage.setItem()` — excellent.
- CSP + HSTS headers configured.
- No backend error body leaked to users (status codes only).
- Passphrase inputs use `type="password"` with `autoComplete="off"`.
- **Gap**: No session timeout UX — token stored indefinitely in localStorage with no expiry UI.

### 14) Animation and micro-interactions
- Animated PnL counter (eased cubic interpolation) — excellent.
- Fade-in on page load (`animate-fade-in`).
- Kill-pulse and safe-pulse animations on admin kill-switch button.
- Slide-up on toast appearance.
- Shimmer skeleton animations on loading.
- **Missing**: hover states on table rows, transition on form submit, loading skeleton granularity (currently block-level, not per-field).

### 15) Visual and brand consistency
- Glassmorphism design system consistent across all pages.
- Background orbs, backdrop blur, consistent border/radius tokens, shared shadow system.
- Premium aesthetic with the `Outfit` font.
- 4-language support integrated into the visual design (LanguageSelector is polished).

## Page-by-page review

### 1. Login
- Strength: clean centered card, brand identity clear, "ztrader" logo with glow.
- Gaps: no user-visible error state (OAuth failures go to console only); no loading state during OAuth redirect; no "try again" action after failure.
- Improve: add inline error banner with retry CTA; show spinner during OAuth redirect; add `role="alert"` on error messages.

### 2. Dashboard
- Strength: well-organized with ticker tape, metrics grid, bot controls, backtest, chart, audit log in clear zones.
- Gaps: no `<h1>` on the page (uses `<h3>` sections only); empty bot list renders nothing; no retry button on fetch errors; no historical context on PnL metric.
- Improve: add page-level `<h1>`; add empty-state message for bots; add retry buttons on failed fetches; add PnL trend sparkline.

### 3. Admin
- Strength: clean tabbed layout, real health metrics, kill-switch toggle with clear visual state.
- Gaps: tabs lack ARIA roles (no `role="tablist"`, `role="tab"`, `aria-selected`); no keyboard arrow navigation between tabs; risk/contract/user mutations use `<button>` not `<form>`; empty user/contract tables have no message.
- Improve: add full ARIA tab pattern with arrow-key navigation; wrap each mutation action in `<form onSubmit>`; add empty-state rows.

### 4. Settings
- Strength: two-column layout, clear section grouping, good form labels.
- Gaps: risk limits section not wrapped in `<form>`; no `aria-live` on status messages; heading hierarchy skips `<h2>`; no unsaved-changes guard.
- Improve: wrap risk limits in `<form>`; add `aria-live="polite"` on status area; add unsaved-changes prompt.

### 5. Navigation
- Strength: scroll-aware styling, mobile drawer, brand link, auth-aware menu.
- Gaps: no `aria-expanded` on hamburger; no focus trap in mobile drawer; no escape-key close; no `aria-current` on active links; no skip-to-content link.
- Improve: add ARIA expanded/current attributes; implement focus trap + escape key for mobile drawer; add skip-to-content link as first focusable element.

### 6. GoogleSignIn
- Strength: clean SVG button, loading state with "Connecting..." text.
- Gaps: no `aria-label` on the button (screen readers read SVG + "Connecting..."/"Sign in with Google" which is acceptable but could be clearer).
- Improve: add `aria-label="Sign in with Google"` for clarity; add `disabled` styling is already present.

### 7. ChartWidget
- Strength: integrates lightweight-charts, responsive resize, supports theme colors.
- Gaps: completely inaccessible to screen readers; no `aria-label` or `role="img"`; no fallback text or data table alternative; no empty-state overlay for zero data.
- Improve: add `role="img"` and `aria-label` describing the chart; add hidden data table fallback; add empty-state text overlay.

### 8. TelegramLink
- Strength: clear linked/unlinked states, status badge, test notification button.
- Gaps: no `<form>` wrapper (keyboard unfriendly); hardcoded English error messages; `confirm()` dialog not accessible.
- Improve: wrap in `<form onSubmit>`; extract all strings to `t()`; replace `confirm()` with accessible modal.

### 9. TradingViewConfig
- Strength: webhook URL with copy, warning box, alerts feed.
- Gaps: no loading/error states on fetch; alerts feed has no `role="log"` or `aria-live`; hardcoded English strings.
- Improve: add loading skeleton for alerts; add `aria-live="polite"` on alerts feed; add `role="alert"` on copy confirmation; localize all strings.

### 10. ThemeCustomizer
- Strength: toggle-based theme selection (dark/light/system).
- Gaps: hardcoded English labels; no preview of theme before selection.
- Improve: localize all labels; add live preview or "apply" confirmation.

### 11. NotificationPreferences
- Strength: 4 toggle-able preferences with clear labels and descriptions; excellent label wrapping on checkboxes.
- Gaps: no `<fieldset>`/`<legend>` grouping; no `<form>` wrapper; descriptions in hardcoded English.
- Improve: wrap in `<fieldset>` with `<legend>`; wrap in `<form onSubmit>`; localize all descriptions.

### 12. PromptPayTopup
- Strength: 4 distinct payment states (idle/waiting/success/expired), 5 payment methods, countdown timer, polling.
- Gaps: payment method selector lacks `role="radiogroup"` and `aria-checked`; no `aria-live` on countdown; no `aria-live` on status polling; no explicit expired-state card UI.
- Improve: add radio group ARIA to method selector; add `aria-live="polite"` for countdown and polling updates; add dedicated expired-state card.

## i18n gaps (hardcoded English strings)

| Component | Strings |
|-----------|---------|
| TelegramLink | Error messages, helper text for Chat ID, "Test Notification" result text |
| TradingViewConfig | Warning text about required headers, "Copy" / "Copied!" |
| NotificationPreferences | Descriptions for each preference toggle |
| ThemeCustomizer | Theme labels ("Dark", "Light", "System") |

## Missing states checklist (high impact)

1. **Dashboard bot list**: show "No trading bots configured. Start one below." with link to the bot start form.
2. **Dashboard ticker**: when offline, show "Market data unavailable" with a retry hint (currently just "OFFLINE").
3. **Admin user table**: show "No users registered yet." when empty.
4. **Admin contract table**: show "No rental contracts found." when empty.
5. **ChartWidget**: show "No chart data available." overlay when `data` is empty.
6. **TradingViewConfig**: loading skeleton while alerts fetch; error state with retry if fetch fails.
7. **All fetch errors**: add retry button pattern consistent across all components.

## Component reuse recommendations

- **No shared `EmptyState` component** — each page implements empty messages inline. Create a reusable `EmptyState` component with icon + message + optional CTA.
- **No shared `ErrorAlert` with retry** — errors use inline badges or toasts. Create a reusable `ErrorAlert` with retry callback prop.
- **No `FormField` wrapper** — form controls use raw `<label>` + `<input>` without a shared validation wrapper. Create a `FormField` component that renders label, description, input, inline error, and `aria-describedby`.
- **No accessible `Toast` component** — the toast is a fixed-position div with no ARIA. Convert to a component with `role="alert"` and `aria-live="assertive"`.
- **Admin tabs**: extract into a reusable `TabBar` component with full ARIA support (roving tabindex, arrow keys, `role="tablist"`).
- **Payment method selector**: extract into a `RadioCardGroup` component with `role="radiogroup"` and `aria-checked`.

## Prioritized UI implementation plan

### P0 (ship first)
1. **ARIA live regions**: add `aria-live="polite"` on ticker tape, alerts feed, and polling regions; add `role="alert"` on all toast/error messages.
2. **Form submission fix**: wrap Admin risk/users/contracts, TelegramLink, and NotificationPreferences in `<form onSubmit>` for keyboard accessibility.
3. **Heading hierarchy**: add `<h2>` level or change `<h3>` → `<h2>` where appropriate; ensure each page has exactly one `<h1>`.
4. **Dashboard `<h1>`**: add a page-level `<h1>` heading to the dashboard.
5. **Empty states**: add empty-state messages for bot list, user/contract tables, and ChartWidget.
6. **i18n completion**: localize all hardcoded English strings in TelegramLink, TradingViewConfig, NotificationPreferences, ThemeCustomizer.

### P1
1. **Admin tab ARIA**: add `role="tablist"`, `role="tab"`, `role="tabpanel"`, `aria-selected`, and arrow-key navigation.
2. **Focus management**: focus first heading after page navigation; focus toast on appearance; trap focus in mobile drawer.
3. **Navigation accessibility**: add `aria-expanded` on hamburger, `aria-current="page"` on active links, escape-key close for drawer.
4. **Skip-to-content link**: add as first focusable element in the layout.
5. **Retry buttons**: add retry action to all error states (fetch failures, mutation failures).
6. **ChartWidget accessibility**: add `role="img"`, `aria-label`, and hidden data table fallback.

### P2
1. **Session timeout UX**: add token expiry detection with soft logout and "Session expired" modal.
2. **Payment method radio group**: add full ARIA radio group pattern to PromptPayTopup method selector.
3. **Inline form validation**: move error messages next to fields instead of top-level badge.
4. **Toast component**: refactor into reusable component with `role="alert"` and `aria-live="assertive"`.
5. **FormField component**: create shared validation wrapper with label, error, and `aria-describedby`.
6. **Table accessibility**: add `<caption>` and `scope` attributes on all `<th>` elements.
7. **Fieldset grouping**: wrap Settings checkboxes and Admin tab forms in `<fieldset>` with `<legend>`.

## Suggested acceptance criteria

- All dynamic regions (toast, ticker, alerts feed, polling status) have `aria-live` and `role="alert"` where appropriate.
- All mutation actions use `<form onSubmit>` for keyboard submission.
- No page skips heading levels — every `<h1>` → `<h2>` → `<h3>` sequence is contiguous.
- All pages have exactly one `<h1>`.
- Empty states are shown for bot list, user/contract tables, and chart data.
- 100% of user-visible strings in all components pass through `t()`.
- Admin tabs support full keyboard navigation (Tab, Arrow keys) with correct ARIA roles.
- Navigation hamburger announces expanded state and closes on Escape.
- Chart has `aria-label` describing its content.
- Session expiry triggers a user-visible warning before logout.
