# Picture Overview Program - Quick Usage Examples

## Language and Coding Standards
- **Communication**: Always talk in Thai when interacting with users.
- **Code & Technical Assets**: All code, comments, documentation, and technical definitions must be in English.

## Example 1: Basic Screenshot Capture

```bash
# 1. Navigate to tools directory
cd tools

# 2. Install dependencies (first time only)
npm install

# 3. Install Playwright browsers (first time only)
npx playwright install chromium

# 4. Start the frontend in another terminal
cd ../apps/frontend
npm run dev

# 5. Return to tools directory and run screenshot capture
cd ../tools
npm run screenshot
```

## Example 2: Using the Quick Start Script

```bash
# Navigate to tools directory
cd tools

# Run the automated setup and screenshot script
./run_screenshots.sh
```

The script will:
- ✅ Check Node.js version
- ✅ Install dependencies if needed
- ✅ Install Playwright browsers if needed
- ✅ Verify frontend is accessible
- ✅ Capture all screenshots
- ✅ Generate interactive viewer
- ✅ Optionally open the viewer in your browser

## Example 3: Custom Frontend URL

```bash
# For a different port
FRONTEND_URL=http://localhost:3001 npm run screenshot

# For staging environment
FRONTEND_URL=https://staging.example.com npm run screenshot

# For production
FRONTEND_URL=https://abtpi18n.com npm run screenshot
```

## Example 4: Viewing Demo Output

```bash
# Generate demo with placeholder images
node generate_demo.js

# Open demo in browser (macOS)
open demo_output/index.html

# Open demo in browser (Linux)
xdg-open demo_output/index.html

# Or navigate to: demo_output/index.html in any browser
```

## Example 5: Testing Setup

```bash
# Run setup validation tests
node test_setup.js
```

This will verify:
- ✅ All required files exist
- ✅ Package.json is configured correctly
- ✅ Scripts are executable
- ✅ Documentation is present
- ✅ Script components are properly structured

## Output Structure

After running, you'll get:

```
tools/
├── screenshots/           # Generated screenshots
│   ├── index.html        # Interactive viewer
│   ├── en/              # English screenshots
│   │   ├── dashboard/
│   │   │   ├── dashboard_desktop.png
│   │   │   ├── dashboard_tablet.png
│   │   │   └── dashboard_mobile.png
│   │   ├── login/
│   │   └── settings/
│   ├── ja/              # Japanese screenshots
│   ├── zh/              # Chinese screenshots
│   └── th/              # Thai screenshots
```

## Common Workflows

### Development Workflow
```bash
# 1. Make UI changes
# 2. Test locally
# 3. Capture screenshots
cd tools && npm run screenshot

# 4. Review screenshots
open screenshots/index.html

# 5. Share screenshots with team
# (Commit screenshots/ to a separate docs repo or share the HTML file)
```

### Documentation Workflow
```bash
# Before release, capture all page states
FRONTEND_URL=http://localhost:3000 npm run screenshot

# Review completeness
open screenshots/index.html

# Copy screenshots to documentation
cp -r screenshots/ ../docs/images/v1.0.0/
```

### CI/CD Integration
```bash
# In your CI pipeline
- name: Generate Screenshots
  run: |
    cd apps/frontend
    npm run build
    npm start &
    sleep 10
    cd ../../tools
    npm install
    npx playwright install chromium
    npm run screenshot

- name: Upload Screenshots Artifact
  uses: actions/upload-artifact@v3
  with:
    name: screenshots
    path: tools/screenshots/
```

## Customization

### Add More Pages

Edit `screenshot_pages.js`:
```javascript
const PAGES = [
  { path: '/dashboard', name: 'dashboard' },
  { path: '/login', name: 'login' },
  { path: '/settings', name: 'settings' },
  { path: '/profile', name: 'profile' },        // Add new page
  { path: '/analytics', name: 'analytics' },    // Add new page
];
```

### Add More Languages

Edit `screenshot_pages.js`:
```javascript
const LANGUAGES = ['en', 'ja', 'zh', 'th', 'fr', 'de']; // Add fr, de
```

### Add More Viewports

Edit `screenshot_pages.js`:
```javascript
const VIEWPORTS = [
  { name: 'desktop', width: 1920, height: 1080 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'mobile', width: 375, height: 667 },
  { name: '4k', width: 3840, height: 2160 },     // Add 4K
  { name: 'ultrawide', width: 3440, height: 1440 }, // Add ultrawide
];
```

## Tips

1. **Run during off-peak hours** - Screenshot capture takes time
2. **Ensure stable frontend** - Make sure no errors in console
3. **Check authentication** - Some pages may require login
4. **Review output** - Always check the generated viewer
5. **Clean up old screenshots** - Remove previous runs if needed

## Troubleshooting

### Frontend not accessible
```bash
# Check if frontend is running
curl http://localhost:3000

# Start frontend if needed
cd apps/frontend
npm run dev
```

### Playwright errors
```bash
# Reinstall Playwright browsers
npx playwright install chromium --force
```

### Permission errors
```bash
# Fix permissions
chmod +x run_screenshots.sh
chmod 755 tools/
```

### Old screenshots
```bash
# Clean up before new run
rm -rf screenshots/
npm run screenshot
```

## Support

For more details, see:
- Main documentation: `README_SCREENSHOTS.md`
- Issues: Report on GitHub
- Questions: Check the main project README

---

Made with ❤️ by ZeaZDev | Part of ABTPro i18n
