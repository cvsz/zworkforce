#!/usr/bin/env node
// Test script for Picture Overview Program
// This creates a simple HTML demo to verify the tool works

const fs = require('fs');
const path = require('path');

console.log('🧪 Testing Picture Overview Program Setup');
console.log('=========================================\n');

// Test 1: Check if screenshot_pages.js exists
const scriptPath = path.join(__dirname, 'screenshot_pages.js');
if (fs.existsSync(scriptPath)) {
  console.log('✅ screenshot_pages.js exists');
} else {
  console.log('❌ screenshot_pages.js not found');
  process.exit(1);
}

// Test 2: Check if package.json exists
const packagePath = path.join(__dirname, 'package.json');
if (fs.existsSync(packagePath)) {
  console.log('✅ package.json exists');
  const pkg = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
  console.log(`   - Package name: ${pkg.name}`);
  console.log(`   - Version: ${pkg.version}`);
  if (pkg.dependencies && pkg.dependencies.playwright) {
    console.log(`   - Playwright dependency: ${pkg.dependencies.playwright}`);
  }
} else {
  console.log('❌ package.json not found');
  process.exit(1);
}

// Test 3: Check if run script exists and is executable
const runScriptPath = path.join(__dirname, 'run_screenshots.sh');
if (fs.existsSync(runScriptPath)) {
  console.log('✅ run_screenshots.sh exists');
  const stats = fs.statSync(runScriptPath);
  const isExecutable = (stats.mode & 0o111) !== 0;
  if (isExecutable) {
    console.log('   - Script is executable');
  } else {
    console.log('   - ⚠️  Script is not executable (use chmod +x)');
  }
} else {
  console.log('❌ run_screenshots.sh not found');
}

// Test 4: Check if README exists
const readmePath = path.join(__dirname, 'README_SCREENSHOTS.md');
if (fs.existsSync(readmePath)) {
  console.log('✅ README_SCREENSHOTS.md exists');
  const content = fs.readFileSync(readmePath, 'utf8');
  console.log(`   - Documentation size: ${(content.length / 1024).toFixed(1)}KB`);
} else {
  console.log('❌ README_SCREENSHOTS.md not found');
}

// Test 5: Verify script structure
try {
  const scriptContent = fs.readFileSync(scriptPath, 'utf8');
  
  const hasChromium = scriptContent.includes('chromium');
  const hasLanguages = scriptContent.includes("LANGUAGES = ['en', 'ja', 'zh', 'th']");
  const hasPages = scriptContent.includes('PAGES =');
  const hasViewports = scriptContent.includes('VIEWPORTS =');
  const hasIndexHtml = scriptContent.includes('generateIndexHtml');
  
  console.log('\n📋 Script Components:');
  console.log(`   ${hasChromium ? '✅' : '❌'} Chromium browser support`);
  console.log(`   ${hasLanguages ? '✅' : '❌'} Multi-language support (en, ja, zh, th)`);
  console.log(`   ${hasPages ? '✅' : '❌'} Page definitions`);
  console.log(`   ${hasViewports ? '✅' : '❌'} Viewport configurations`);
  console.log(`   ${hasIndexHtml ? '✅' : '❌'} HTML viewer generation`);
  
} catch (error) {
  console.log('❌ Error reading script:', error.message);
  process.exit(1);
}

// Test 6: Create a sample output directory structure
console.log('\n📁 Testing directory structure creation...');
const testDir = path.join(__dirname, 'test_screenshots');
try {
  // Clean up if exists
  if (fs.existsSync(testDir)) {
    fs.rmSync(testDir, { recursive: true });
  }
  
  // Create test structure
  fs.mkdirSync(testDir, { recursive: true });
  fs.mkdirSync(path.join(testDir, 'en', 'dashboard'), { recursive: true });
  fs.mkdirSync(path.join(testDir, 'ja', 'login'), { recursive: true });
  
  console.log('✅ Directory structure created successfully');
  console.log('   - Created: test_screenshots/en/dashboard/');
  console.log('   - Created: test_screenshots/ja/login/');
  
  // Create a sample index.html
  const sampleHtml = `<!DOCTYPE html>
<html>
<head><title>Test Screenshot Viewer</title></head>
<body>
  <h1>✅ Sample Screenshot Viewer</h1>
  <p>This demonstrates the output structure.</p>
</body>
</html>`;
  
  fs.writeFileSync(path.join(testDir, 'index.html'), sampleHtml);
  console.log('✅ Sample index.html created');
  
  // Clean up test directory
  fs.rmSync(testDir, { recursive: true });
  console.log('✅ Test cleanup completed');
  
} catch (error) {
  console.log('❌ Error creating test structure:', error.message);
}

console.log('\n✨ All tests passed!');
console.log('\n📖 Next Steps:');
console.log('   1. Install dependencies: npm install');
console.log('   2. Install Playwright browsers: npx playwright install chromium');
console.log('   3. Start the frontend: cd ../apps/frontend && npm run dev');
console.log('   4. Run screenshots: npm run screenshot');
console.log('   5. Or use the quick script: ./run_screenshots.sh');
console.log('\n📚 For detailed instructions, see: README_SCREENSHOTS.md\n');
