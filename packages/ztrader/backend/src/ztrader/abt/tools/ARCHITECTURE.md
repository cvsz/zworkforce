# Picture Overview Program - Architecture & Workflow

## Language and Coding Standards
- **Communication**: Always talk in Thai when interacting with users.
- **Code & Technical Assets**: All code, comments, documentation, and technical definitions must be in English.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Picture Overview Program                      │
└─────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
            ┌───────▼────────┐       ┌───────▼────────┐
            │  screenshot_   │       │  run_          │
            │  pages.js      │       │  screenshots.sh│
            │  (Main Script) │       │  (Quick Start) │
            └────────────────┘       └────────────────┘
                    │
         ┌──────────┼──────────┐
         │          │          │
    ┌────▼───┐ ┌───▼────┐ ┌───▼─────┐
    │Config  │ │Capture │ │Generate │
    │        │ │Engine  │ │Viewer   │
    └────────┘ └────────┘ └─────────┘
         │          │          │
         └──────────┴──────────┘
                    │
         ┌──────────▼──────────┐
         │   Playwright API    │
         │   (Browser Control) │
         └─────────────────────┘
                    │
         ┌──────────▼──────────┐
         │   Chromium Browser  │
         │   (Headless Mode)   │
         └─────────────────────┘
                    │
         ┌──────────▼──────────┐
         │   Frontend App      │
         │   (localhost:3000)  │
         └─────────────────────┘
```

## Workflow Diagram

```
START
  │
  ├─► Check Node.js version
  │   └─► ✓ 18+
  │
  ├─► Install dependencies
  │   ├─► npm install
  │   └─► playwright install chromium
  │
  ├─► Verify frontend accessible
  │   └─► curl http://localhost:3000
  │
  ├─► Initialize browser
  │   └─► chromium.launch({ headless: true })
  │
  ├─► FOR EACH language (en, ja, zh, th)
  │   │
  │   ├─► FOR EACH page (dashboard, login, settings)
  │   │   │
  │   │   ├─► FOR EACH viewport (desktop, tablet, mobile)
  │   │   │   │
  │   │   │   ├─► Set viewport size
  │   │   │   ├─► Navigate to URL
  │   │   │   ├─► Wait for network idle
  │   │   │   ├─► Wait 1 second (animations)
  │   │   │   ├─► Capture screenshot
  │   │   │   └─► Save to file
  │   │   │
  │   │   └─► Next viewport
  │   │
  │   └─► Next page
  │
  ├─► Close browser
  │
  ├─► Generate index.html
  │   ├─► Create HTML structure
  │   ├─► Add CSS styling
  │   ├─► Embed screenshot references
  │   └─► Add JavaScript interactivity
  │
  ├─► Save index.html
  │
  ├─► Display summary
  │   ├─► Total screenshots: 36
  │   ├─► Output location: ./screenshots/
  │   └─► Viewer: ./screenshots/index.html
  │
  └─► COMPLETE ✓
```

## Data Flow

```
Input Configuration
        │
        ├─► LANGUAGES = ['en', 'ja', 'zh', 'th']
        ├─► PAGES = ['/dashboard', '/login', '/settings']
        ├─► VIEWPORTS = [{1920×1080}, {768×1024}, {375×667}]
        └─► BASE_URL = 'http://localhost:3000'
        │
        ▼
Screenshot Generation
        │
        ├─► URL: http://localhost:3000/en/dashboard
        │   ├─► Viewport: 1920×1080
        │   └─► Output: screenshots/en/dashboard/dashboard_desktop.png
        │
        ├─► URL: http://localhost:3000/en/dashboard
        │   ├─► Viewport: 768×1024
        │   └─► Output: screenshots/en/dashboard/dashboard_tablet.png
        │
        ├─► URL: http://localhost:3000/en/dashboard
        │   ├─► Viewport: 375×667
        │   └─► Output: screenshots/en/dashboard/dashboard_mobile.png
        │
        └─► ... (repeat for all combinations)
        │
        ▼
Output Structure
        │
        ├─► screenshots/
        │   ├─► index.html (Interactive Viewer)
        │   ├─► en/ (English)
        │   │   ├─► dashboard/ (3 PNGs)
        │   │   ├─► login/ (3 PNGs)
        │   │   └─► settings/ (3 PNGs)
        │   ├─► ja/ (Japanese) - same structure
        │   ├─► zh/ (Chinese) - same structure
        │   └─► th/ (Thai) - same structure
        │
        └─► Total: 36 PNG files + 1 HTML file
```

## Component Interaction

```
┌──────────────────┐
│   User/Dev       │
└────────┬─────────┘
         │
         │ Runs: ./run_screenshots.sh
         │       or npm run screenshot
         ▼
┌──────────────────┐
│  Entry Point     │
│  - Validate env  │
│  - Install deps  │
│  - Run main      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  screenshot_     │
│  pages.js        │
│                  │
│  1. Config       │◄───── Configuration
│  2. Browser      │       - Languages
│  3. Navigate     │       - Pages
│  4. Capture      │       - Viewports
│  5. Save         │
│  6. Generate     │
└────────┬─────────┘
         │
         ├─────────► Playwright ──► Chromium ──► Frontend
         │
         │
         ▼
┌──────────────────┐
│  Screenshots     │
│  Directory       │
│                  │
│  - en/...        │
│  - ja/...        │
│  - zh/...        │
│  - th/...        │
│  - index.html    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  HTML Viewer     │
│  (User opens)    │
│                  │
│  - View shots    │
│  - Click zoom    │
│  - Navigate      │
└──────────────────┘
```

## File Dependency Graph

```
run_screenshots.sh
    │
    ├─► Checks: package.json exists
    ├─► Runs: npm install
    ├─► Runs: npx playwright install
    └─► Executes: node screenshot_pages.js
                      │
                      ├─► Requires: playwright
                      ├─► Requires: fs (built-in)
                      ├─► Requires: path (built-in)
                      │
                      ├─► Reads: Environment variables
                      │   └─► FRONTEND_URL (default: localhost:3000)
                      │
                      ├─► Creates: screenshots/ directory
                      │   ├─► en/, ja/, zh/, th/ subdirs
                      │   └─► index.html
                      │
                      └─► Outputs: 36 PNG files + 1 HTML
```

## Execution Timeline

```
Time    Action                              Status
─────────────────────────────────────────────────────
0:00    Start execution                     ⏳
0:01    Initialize browser                  ⏳
0:02    Begin language: en                  ⏳
0:03    ├─ dashboard/desktop               ✓
0:05    ├─ dashboard/tablet                ✓
0:07    ├─ dashboard/mobile                ✓
0:09    ├─ login/desktop                   ✓
0:11    ├─ login/tablet                    ✓
0:13    ├─ login/mobile                    ✓
0:15    ├─ settings/desktop                ✓
0:17    ├─ settings/tablet                 ✓
0:19    └─ settings/mobile                 ✓
0:20    Begin language: ja                  ⏳
0:38    Language ja complete                ✓
0:39    Begin language: zh                  ⏳
0:57    Language zh complete                ✓
0:58    Begin language: th                  ⏳
1:16    Language th complete                ✓
1:17    Close browser                       ✓
1:18    Generate index.html                 ✓
1:19    Write index.html                    ✓
1:20    Complete!                           ✓

Total: ~1-2 minutes (varies by network)
```

## Error Handling Flow

```
Try:
  ├─► Initialize browser
  │   └─► Catch: Browser launch failed
  │       └─► Suggest: npx playwright install
  │
  ├─► Navigate to page
  │   └─► Catch: Connection refused
  │       └─► Suggest: Start frontend
  │
  ├─► Wait for network idle
  │   └─► Catch: Timeout
  │       └─► Suggest: Increase timeout / Check page
  │
  ├─► Take screenshot
  │   └─► Catch: Screenshot failed
  │       └─► Log error, continue to next
  │
  └─► Write file
      └─► Catch: Permission denied
          └─► Suggest: Check write permissions

Finally:
  └─► Always close browser (prevent resource leak)
```

## Configuration Matrix

```
┌──────────────────────────────────────────────┐
│           Screenshot Matrix                   │
├──────────────────────────────────────────────┤
│                                              │
│     Languages (4) × Pages (3) × Viewports (3) │
│                                              │
│  en ──┬── dashboard ──┬── desktop            │
│       │               ├── tablet             │
│       │               └── mobile             │
│       │                                      │
│       ├── login ──────┬── desktop            │
│       │               ├── tablet             │
│       │               └── mobile             │
│       │                                      │
│       └── settings ───┬── desktop            │
│                       ├── tablet             │
│                       └── mobile             │
│                                              │
│  ja ──┬── (same structure)                   │
│  zh ──┤                                      │
│  th ──┘                                      │
│                                              │
│  = 36 total screenshots                      │
└──────────────────────────────────────────────┘
```

## Technology Stack

```
┌─────────────────────────────────────┐
│         Technology Stack            │
├─────────────────────────────────────┤
│                                     │
│  Runtime:                           │
│  └─► Node.js 18+                    │
│                                     │
│  Browser Automation:                │
│  └─► Playwright 1.40+               │
│      └─► Chromium (headless)        │
│                                     │
│  Built-in Modules:                  │
│  ├─► fs (File System)               │
│  ├─► path (Path Operations)         │
│  └─► process (Environment Vars)     │
│                                     │
│  Output Formats:                    │
│  ├─► PNG (Screenshots)              │
│  └─► HTML (Viewer)                  │
│                                     │
│  Styling:                           │
│  └─► Embedded CSS                   │
│      ├─► Flexbox                    │
│      ├─► Grid                       │
│      └─► Gradients                  │
│                                     │
│  Interactivity:                     │
│  └─► Vanilla JavaScript             │
│      ├─► Modal                      │
│      ├─► Event Listeners            │
│      └─► Keyboard Navigation        │
│                                     │
└─────────────────────────────────────┘
```

---

**Version**: 1.0.0  
**Author**: ZeaZDev  
**Project**: ABTPro i18n Picture Overview Program
