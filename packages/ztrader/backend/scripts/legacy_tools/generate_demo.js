#!/usr/bin/env node
// Demo generator for Picture Overview Program
// Creates a demo HTML viewer with placeholder images

const fs = require('fs');
const path = require('path');

console.log('🎨 Generating Picture Overview Demo');
console.log('===================================\n');

const DEMO_DIR = path.join(__dirname, 'demo_output');
const LANGUAGES = ['en', 'ja', 'zh', 'th'];
const PAGES = ['dashboard', 'login', 'settings'];
const VIEWPORTS = ['desktop', 'tablet', 'mobile'];

// Create demo directory structure
if (fs.existsSync(DEMO_DIR)) {
  fs.rmSync(DEMO_DIR, { recursive: true });
}

fs.mkdirSync(DEMO_DIR, { recursive: true });

// Create placeholder SVG images
function createPlaceholderSVG(text, width, height) {
  return `<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#667eea;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#764ba2;stop-opacity:1" />
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#grad)"/>
  <text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="white" font-size="24" font-family="Arial, sans-serif">${text}</text>
</svg>`;
}

// Create placeholder images for each language/page/viewport
for (const lang of LANGUAGES) {
  const langDir = path.join(DEMO_DIR, lang);
  fs.mkdirSync(langDir, { recursive: true });
  
  for (const page of PAGES) {
    const pageDir = path.join(langDir, page);
    fs.mkdirSync(pageDir, { recursive: true });
    
    for (const viewport of VIEWPORTS) {
      const dimensions = {
        desktop: { width: 1920, height: 1080 },
        tablet: { width: 768, height: 1024 },
        mobile: { width: 375, height: 667 }
      };
      
      const dim = dimensions[viewport];
      const text = `${lang.toUpperCase()}\n${page}\n${viewport}\n${dim.width}x${dim.height}`;
      const svg = createPlaceholderSVG(text, dim.width, dim.height);
      const filename = `${page}_${viewport}.png.svg`;
      
      fs.writeFileSync(path.join(pageDir, filename), svg);
    }
  }
}

// Generate index.html (similar to the real one but with demo data)
const languageNames = {
  en: '🇬🇧 English',
  ja: '🇯🇵 Japanese (日本語)',
  zh: '🇨🇳 Chinese (中文)',
  th: '🇹🇭 Thai (ไทย)'
};

let languageSections = '';
for (const lang of LANGUAGES) {
  languageSections += `
    <div class="language-section">
      <div class="language-title">
        <span>${languageNames[lang]}</span>
      </div>
`;

  for (const page of PAGES) {
    languageSections += `
      <div class="page-section">
        <div class="page-title">📄 ${page.toUpperCase()}</div>
        <div class="screenshots-grid">
`;

    for (const viewport of VIEWPORTS) {
      const dimensions = {
        desktop: '1920x1080',
        tablet: '768x1024',
        mobile: '375x667'
      };
      
      const filename = `${page}_${viewport}.png.svg`;
      const filepath = `${lang}/${page}/${filename}`;
      
      languageSections += `
          <div class="screenshot-card">
            <div class="screenshot-label">${viewport} (${dimensions[viewport]})</div>
            <img src="${filepath}" alt="${page} - ${viewport}" loading="lazy">
          </div>
`;
    }

    languageSections += `
        </div>
      </div>
`;
  }

  languageSections += `
    </div>
`;
}

const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ABTPi18n - Page Screenshots Overview (DEMO)</title>
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
      margin-bottom: 20px;
      font-size: 1.1em;
    }
    
    .demo-notice {
      background: #fff3cd;
      border: 2px solid #ffc107;
      border-radius: 8px;
      padding: 15px;
      margin-bottom: 30px;
      text-align: center;
      color: #856404;
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
    
    <div class="demo-notice">
      <strong>📌 DEMO MODE</strong><br>
      This is a demonstration of the Picture Overview Program output.<br>
      Placeholder images shown. Run the actual tool to capture real screenshots.
    </div>

${languageSections}

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

    document.querySelectorAll('.screenshot-card img').forEach(img => {
      img.addEventListener('click', function() {
        openModal(this.src);
      });
    });

    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') {
        closeModal();
      }
    });
  </script>
</body>
</html>`;

fs.writeFileSync(path.join(DEMO_DIR, 'index.html'), html);

console.log('✅ Demo generated successfully!');
console.log(`📁 Location: ${DEMO_DIR}`);
console.log(`🌐 Open: ${path.join(DEMO_DIR, 'index.html')}`);
console.log('\n📊 Demo Statistics:');
console.log(`   - Languages: ${LANGUAGES.length}`);
console.log(`   - Pages: ${PAGES.length}`);
console.log(`   - Viewports: ${VIEWPORTS.length}`);
console.log(`   - Total screenshots: ${LANGUAGES.length * PAGES.length * VIEWPORTS.length}`);
console.log('\n💡 This demo shows the layout and structure of the actual output.');
console.log('   Run the real tool to capture actual page screenshots.\n');
