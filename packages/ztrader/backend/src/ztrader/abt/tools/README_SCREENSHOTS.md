# 📸 Picture Overview Program

## Language and Coding Standards
- **Communication**: Always talk in Thai when interacting with users.
- **Code & Technical Assets**: All code, comments, documentation, and technical definitions must be in English.

This tool automatically captures screenshots of all ABTPi18n pages across all supported languages and viewports.

## Overview

The Picture Overview Program generates visual documentation for the ABTPi18n platform by:
- Capturing screenshots of all pages (Dashboard, Login, Settings)
- Supporting all languages (English, Japanese, Chinese, Thai)
- Generating responsive screenshots (Desktop, Tablet, Mobile)
- Creating an interactive HTML viewer for easy browsing

## Prerequisites

- Node.js 18+ installed
- ABTPi18n frontend application running (default: http://localhost:3000)
- Internet connection for downloading Playwright browsers

## Installation

1. Navigate to the tools directory:
   ```bash
   cd tools
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Install Playwright browsers (first time only):
   ```bash
   npx playwright install chromium
   ```

## Usage

### Basic Usage

With the frontend running on the default port (3000):

```bash
npm run screenshot
```

### Custom Frontend URL

If your frontend is running on a different URL or port:

```bash
FRONTEND_URL=http://localhost:3001 npm run screenshot
```

### Production Environment

For capturing screenshots from a production deployment:

```bash
FRONTEND_URL=https://your-production-domain.com npm run screenshot
```

## Output

Screenshots are saved to the `screenshots/` directory with the following structure:

```
screenshots/
├── index.html              # Interactive viewer for all screenshots
├── en/                     # English language screenshots
│   ├── dashboard/
│   │   ├── dashboard_desktop.png
│   │   ├── dashboard_tablet.png
│   │   └── dashboard_mobile.png
│   ├── login/
│   │   ├── login_desktop.png
│   │   ├── login_tablet.png
│   │   └── login_mobile.png
│   └── settings/
│       ├── settings_desktop.png
│       ├── settings_tablet.png
│       └── settings_mobile.png
├── ja/                     # Japanese language screenshots
│   └── ... (same structure)
├── zh/                     # Chinese language screenshots
│   └── ... (same structure)
└── th/                     # Thai language screenshots
    └── ... (same structure)
```

## Viewing Screenshots

After running the tool, open the generated viewer:

```bash
open screenshots/index.html
```

Or navigate to `screenshots/index.html` in your web browser.

The viewer provides:
- Organized view by language and page
- Responsive layout for easy comparison
- Click-to-zoom functionality
- Generation timestamp
- Viewport size labels

## Configuration

You can modify the screenshot configuration in `screenshot_pages.js`:

### Add New Pages

```javascript
const PAGES = [
  { path: '/dashboard', name: 'dashboard' },
  { path: '/login', name: 'login' },
  { path: '/settings', name: 'settings' },
  { path: '/your-new-page', name: 'your-new-page' }, // Add here
];
```

### Add New Languages

```javascript
const LANGUAGES = ['en', 'ja', 'zh', 'th', 'fr']; // Add new language code
```

### Modify Viewport Sizes

```javascript
const VIEWPORTS = [
  { name: 'desktop', width: 1920, height: 1080 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'mobile', width: 375, height: 667 },
  { name: 'wide', width: 2560, height: 1440 }, // Add new viewport
];
```

## Troubleshooting

### Frontend Not Running

```
Error: net::ERR_CONNECTION_REFUSED at http://localhost:3000
```

**Solution**: Ensure the frontend is running:
```bash
cd apps/frontend
npm run dev
```

### Playwright Browser Not Installed

```
Error: browserType.launch: Executable doesn't exist
```

**Solution**: Install Playwright browsers:
```bash
npx playwright install chromium
```

### Permission Denied on screenshots Directory

```
Error: EACCES: permission denied, mkdir 'screenshots'
```

**Solution**: Ensure you have write permissions:
```bash
chmod 755 .
```

### Page Timeout

```
Error: page.goto: Timeout 30000ms exceeded
```

**Solution**: 
1. Verify the frontend is accessible at the specified URL
2. Check if the page requires authentication (may need to modify script)
3. Increase timeout in the script if needed

## Advanced Usage

### Programmatic Usage

You can also use the screenshot tool programmatically:

```javascript
const { captureAllPages } = require('./screenshot_pages');

// Set custom base URL
process.env.FRONTEND_URL = 'http://custom-url:3000';

// Run screenshot capture
captureAllPages()
  .then(() => console.log('Screenshots complete!'))
  .catch(error => console.error('Error:', error));
```

### CI/CD Integration

Add to your CI/CD pipeline for automated visual documentation:

```yaml
# .github/workflows/screenshots.yml
name: Generate Screenshots
on:
  push:
    branches: [main]

jobs:
  screenshots:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: |
          cd tools
          npm install
          npx playwright install chromium
      - name: Start frontend
        run: |
          cd apps/frontend
          npm install
          npm run build
          npm start &
          sleep 10
      - name: Generate screenshots
        run: |
          cd tools
          npm run screenshot
      - name: Upload screenshots
        uses: actions/upload-artifact@v3
        with:
          name: screenshots
          path: tools/screenshots/
```

## Features

✅ **Multi-Language Support**: Captures all supported languages (EN, JA, ZH, TH)

✅ **Responsive Screenshots**: Desktop, tablet, and mobile viewports

✅ **Interactive Viewer**: Beautiful HTML interface with zoom capability

✅ **Full-Page Capture**: Captures entire scrollable page content

✅ **Organized Structure**: Clean directory organization by language and page

✅ **Production Ready**: Works with local, staging, and production deployments

✅ **Customizable**: Easy to add new pages, languages, or viewports

## Example Output

The tool generates a beautiful interactive viewer showing all screenshots:

- **Language Sections**: Organized by language with flag emojis
- **Page Categories**: Grouped by page type (Dashboard, Login, Settings)
- **Viewport Comparison**: Side-by-side comparison of different screen sizes
- **Click-to-Zoom**: Full-screen modal view of any screenshot
- **Responsive Layout**: Viewer adapts to your screen size

## Notes

- Screenshots are captured in headless mode (no browser window opens)
- Each screenshot includes a 1-second delay for animations to complete
- The `fullPage: true` option captures entire scrollable content
- Screenshots are saved as PNG files for quality
- The viewer works offline after generation

## Support

For issues or questions about the Picture Overview Program:
1. Check the troubleshooting section above
2. Review the console output for specific error messages
3. Open an issue on the GitHub repository

---

**Made with ❤️ by ZeaZDev** | Part of ABTPro i18n Project
