#!/usr/bin/env node
// ZeaZDev [Picture Overview Program] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 //
// Author: ZeaZDev Meta-Intelligence //
// Description: Captures screenshots of all ABTPi18n pages //
// --- DO NOT EDIT HEADER --- //

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// Configuration
const BASE_URL = process.env.FRONTEND_URL || 'http://localhost:3000';
const OUTPUT_DIR = path.join(__dirname, '..', 'screenshots');
const LANGUAGES = ['en', 'ja', 'zh', 'th'];

// Pages to capture (path relative to language)
const PAGES = [
  { path: '/dashboard', name: 'dashboard' },
  { path: '/login', name: 'login' },
  { path: '/settings', name: 'settings' },
];

// Viewport sizes for responsive screenshots
const VIEWPORTS = [
  { name: 'desktop', width: 1920, height: 1080 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'mobile', width: 375, height: 667 },
];

/**
 * Create directory if it doesn't exist
 */
function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

/**
 * Take a screenshot of a page
 */
async function captureScreenshot(page, url, outputPath, viewport) {
  console.log(`  📸 Capturing: ${url} (${viewport.name})`);
  
  try {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    
    // Wait a bit for any animations to complete
    await page.waitForTimeout(1000);
    
    await page.screenshot({
      path: outputPath,
      fullPage: true,
    });
    
    console.log(`  ✅ Saved: ${outputPath}`);
  } catch (error) {
    console.error(`  ❌ Failed to capture ${url}:`, error.message);
  }
}

/**
 * Main function to capture all screenshots
 */
async function captureAllPages() {
  console.log('🚀 Starting Picture Overview Program for ABTPi18n');
  console.log(`📍 Base URL: ${BASE_URL}`);
  console.log(`📁 Output Directory: ${OUTPUT_DIR}`);
  console.log('');

  // Ensure output directory exists
  ensureDir(OUTPUT_DIR);

  const browser = await chromium.launch({
    headless: true,
  });

  try {
    for (const language of LANGUAGES) {
      console.log(`🌍 Processing Language: ${language.toUpperCase()}`);
      
      const langDir = path.join(OUTPUT_DIR, language);
      ensureDir(langDir);

      for (const pageInfo of PAGES) {
        console.log(`\n📄 Page: ${pageInfo.name}`);
        
        const pageDir = path.join(langDir, pageInfo.name);
        ensureDir(pageDir);

        const page = await browser.newPage();

        for (const viewport of VIEWPORTS) {
          const url = `${BASE_URL}/${language}${pageInfo.path}`;
          const filename = `${pageInfo.name}_${viewport.name}.png`;
          const outputPath = path.join(pageDir, filename);

          await captureScreenshot(page, url, outputPath, viewport);
        }

        await page.close();
      }
    }

    // Generate index.html for easy viewing
    await generateIndexHtml();

    console.log('\n✨ Screenshot capture complete!');
    console.log(`📁 Screenshots saved to: ${OUTPUT_DIR}`);
    console.log(`🌐 Open ${path.join(OUTPUT_DIR, 'index.html')} to view all screenshots`);

  } catch (error) {
    console.error('❌ Error during screenshot capture:', error);
    throw error;
  } finally {
    await browser.close();
  }
}

/**
 * Generate an HTML index page to view all screenshots
 */
async function generateIndexHtml() {
  console.log('\n📝 Generating index.html...');

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ABTPi18n - Page Screenshots Overview</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: #333;
      padding: 20px;
    }
    
    .container {
      max-width: 1400px;
      margin: 0 auto;
      background: white;
      border-radius: 16px;
      padding: 40px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    }
    
    h1 {
      color: #667eea;
      margin-bottom: 10px;
      font-size: 2.5em;
      text-align: center;
    }
    
    .subtitle {
      text-align: center;
      color: #666;
      margin-bottom: 40px;
      font-size: 1.1em;
    }
    
    .language-section {
      margin-bottom: 50px;
    }
    
    .language-title {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 15px 25px;
      border-radius: 8px;
      margin-bottom: 25px;
      font-size: 1.5em;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    
    .page-section {
      margin-bottom: 40px;
      border: 1px solid #e0e0e0;
      border-radius: 8px;
      padding: 20px;
      background: #f9f9f9;
    }
    
    .page-title {
      font-size: 1.3em;
      color: #444;
      margin-bottom: 20px;
      border-bottom: 2px solid #667eea;
      padding-bottom: 10px;
    }
    
    .screenshots-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 20px;
    }
    
    .screenshot-card {
      background: white;
      border-radius: 8px;
      padding: 15px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .screenshot-card:hover {
      transform: translateY(-5px);
      box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
    }
    
    .screenshot-label {
      font-weight: 600;
      color: #667eea;
      margin-bottom: 10px;
      text-transform: uppercase;
      font-size: 0.9em;
    }
    
    .screenshot-card img {
      width: 100%;
      height: auto;
      border-radius: 4px;
      border: 1px solid #ddd;
      cursor: pointer;
    }
    
    .screenshot-card img:hover {
      opacity: 0.9;
    }
    
    .footer {
      text-align: center;
      margin-top: 50px;
      padding-top: 30px;
      border-top: 2px solid #e0e0e0;
      color: #666;
    }
    
    .modal {
      display: none;
      position: fixed;
      z-index: 1000;
      left: 0;
      top: 0;
      width: 100%;
      height: 100%;
      background-color: rgba(0, 0, 0, 0.9);
    }
    
    .modal-content {
      margin: auto;
      display: block;
      max-width: 90%;
      max-height: 90%;
      margin-top: 2%;
    }
    
    .close {
      position: absolute;
      top: 15px;
      right: 35px;
      color: #f1f1f1;
      font-size: 40px;
      font-weight: bold;
      cursor: pointer;
    }
    
    .close:hover {
      color: #bbb;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>🖼️ ABTPi18n - Page Screenshots Overview</h1>
    <div class="subtitle">
      Auto Bot Trader Pro i18n - Visual Documentation
      <br>
      Generated: ${new Date().toLocaleString()}
    </div>

${generateLanguageSections()}

    <div class="footer">
      <p><strong>ABTPro i18n</strong> - Multi-language Automated Trading Platform</p>
      <p>Made with ❤️ by ZeaZDev</p>
    </div>
  </div>

  <!-- Modal for full-size image viewing -->
  <div id="imageModal" class="modal" onclick="closeModal()">
    <span class="close">&times;</span>
    <img class="modal-content" id="modalImage">
  </div>

  <script>
    function openModal(imgSrc) {
      const modal = document.getElementById('imageModal');
      const modalImg = document.getElementById('modalImage');
      modal.style.display = 'block';
      modalImg.src = imgSrc;
    }

    function closeModal() {
      document.getElementById('imageModal').style.display = 'none';
    }

    // Add click listeners to all images
    document.querySelectorAll('.screenshot-card img').forEach(img => {
      img.addEventListener('click', function() {
        openModal(this.src);
      });
    });

    // Close modal on Escape key
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') {
        closeModal();
      }
    });
  </script>
</body>
</html>`;

  fs.writeFileSync(path.join(OUTPUT_DIR, 'index.html'), html);
  console.log('✅ index.html generated successfully');
}

/**
 * Generate HTML sections for each language
 */
function generateLanguageSections() {
  const languageNames = {
    en: '🇬🇧 English',
    ja: '🇯🇵 Japanese (日本語)',
    zh: '🇨🇳 Chinese (中文)',
    th: '🇹🇭 Thai (ไทย)'
  };

  let html = '';

  for (const lang of LANGUAGES) {
    html += `
    <div class="language-section">
      <div class="language-title">
        <span>${languageNames[lang]}</span>
      </div>
`;

    for (const pageInfo of PAGES) {
      html += `
      <div class="page-section">
        <div class="page-title">📄 ${pageInfo.name.toUpperCase()}</div>
        <div class="screenshots-grid">
`;

      for (const viewport of VIEWPORTS) {
        const filename = `${pageInfo.name}_${viewport.name}.png`;
        const filepath = `${lang}/${pageInfo.name}/${filename}`;
        
        html += `
          <div class="screenshot-card">
            <div class="screenshot-label">${viewport.name} (${viewport.width}x${viewport.height})</div>
            <img src="${filepath}" alt="${pageInfo.name} - ${viewport.name}" loading="lazy">
          </div>
`;
      }

      html += `
        </div>
      </div>
`;
    }

    html += `
    </div>
`;
  }

  return html;
}

// Run the program
if (require.main === module) {
  captureAllPages().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { captureAllPages };
