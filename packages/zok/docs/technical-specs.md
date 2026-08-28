# Technical Specifications: Zaapi Platform Copy-Clone

This document outlines the coding standards, folder structures, CSS variables styling specifications, package dependencies, and simulation rules.

---

## 1. Directory Blueprint
```text
/mnt/zok/
├── index.html                # Entry point & Favicon config
├── package.json              # Vite & React dependencies list
├── vite.config.js            # Bundler configurations
├── src/
│   ├── main.jsx              # DOM mount entry
│   ├── index.css             # Tailored HSL theme, marquee, and node CSS
│   ├── App.jsx               # Router & Dark-mode controller
│   └── views/
│       ├── LandingPage.jsx   # Landing copy-clone
│       └── Dashboard/
│           ├── DashboardNav.jsx    # Sidebar selector
│           ├── UnifiedInbox.jsx    # Inbox & CRM sync
│           ├── AIAgent.jsx         # AI Training Sandbox
│           ├── FlowBuilder.jsx     # Canvas & Nodes editor
│           ├── Broadcasts.jsx      # Campaign logs & Sender progress
│           ├── Analytics.jsx       # Efficacy grids & Traffic columns
│           └── Integrations.jsx    # Channel switches & Webhook debug
```

---

## 2. Design System Details (`src/index.css`)
We use custom CSS properties to achieve premium dark & light styling:

| Variable | Light Theme Token | Dark Theme Token | Purpose |
| :--- | :--- | :--- | :--- |
| `--primary-color` | `#00c28e` | `#00c28e` | Zaapi emerald accent |
| `--primary-glow` | `rgba(0,194,142,0.15)` | `rgba(0,194,142,0.35)` | Neon box shadow glow |
| `--light-bg` / `--dark-bg` | `#f8fafc` | `#070b19` | Main layout backgrounds |
| `--light-surface` / `--dark-surface` | `#ffffff` | `#0f172a` | Container card surfaces |
| `--light-border` / `--dark-border` | `#e2e8f0` | `rgba(255,255,255,0.08)`| Separation line boundaries |

---

## 3. Libraries & Packages
The project is built on minimalist dependencies to ensure reliability and speed:
* **Vite**: Modern bundler with hot module replacement (HMR).
* **React 19**: Frontend UI structure.
* **Lucide React**: Clean icons suite representing channels and controls.

---

## 4. Key Simulation Implementations

### 4.1 Keyword Matching Pipeline (`AIAgent.jsx` & `UnifiedInbox.jsx`)
Customer text queries are cleaned and parsed through a keyword routing script:
```javascript
const questionText = simInput.toLowerCase().trim();
const matchedQA = qaPairs.find(pair => 
  questionText.includes(pair.q.toLowerCase().replace('?', ''))
);
```

### 4.2 Automation Flow Canvas (`FlowBuilder.jsx`)
Nodes coordinates are updated inside the local state array. Svg connectors are computed based on static offsets:
* **Node Width**: 220px
* **Connector Input**: `left: -6px`, `top: 50%`
* **Connector Output**: `right: -6px`, `top: 50%`
* Svg path uses Cubic Bezier curve paths:
  `d="M 270 160 C 295 160, 295 120, 320 120"`
