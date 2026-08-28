# Codebase Rules for Zok Clone

This file contains rules and guidelines that all developers and AI agents must adhere to when working on this project.

## 1. Design & CSS Styling Guidelines
* **Color Palette**: Always use variables defined in `src/index.css`. The primary color must always be `#00c28e` (Zok Emerald Green) with corresponding HSL tokens.
* **Component Modularity**: Maintain styling in `src/index.css` under utility classes or within specific component styles. Do not use ad-hoc inline styles unless dynamically calculated.
* **Dark Mode**: Support automatic dark mode styles. Check the body class `dark-mode` to override colors.

## 2. React Component Standards
* **State Operations**: Keep simulation states pure and clean. Avoid unnecessary re-renders. Use `useEffect` safely with appropriate dependency arrays.
* **Mock Pipelines**: All mock pipelines (Unified Inbox message timers, visual flow publishers, integrations logs) should simulate latency (e.g. 1.2s-2.0s timeouts) to resemble live web requests.
* **Icons**: Use `lucide-react` for UI icons. Do not import raw svgs unless custom-designed.

## 3. Build & CI Verification
* Always ensure that `npm run build` exits with code 0 before finalizing any feature changes.
* Check Oxlint configurations (`.oxlintrc.json`) and fix lint issues immediately.
