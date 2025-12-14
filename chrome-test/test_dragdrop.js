const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

(async () => {
  console.log('=== Testing Jamovi Drag-Drop CSV Upload ===\n');
  
  const browser = await puppeteer.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-web-security'
    ]
  });

  const page = await browser.newPage();
  
  // Track console messages
  const consoleMessages = [];
  page.on('console', msg => {
    const text = msg.text();
    consoleMessages.push({ type: msg.type(), text });
    if (msg.type() === 'error' || msg.type() === 'warning') {
      console.log(`[BROWSER ${msg.type().toUpperCase()}]`, text);
    }
  });

  // Track network requests
  const networkRequests = [];
  page.on('request', request => {
    if (request.url().includes('/open')) {
      networkRequests.push({
        url: request.url(),
        method: request.method(),
        postData: request.postData() ? request.postData().substring(0, 200) : null
      });
      console.log('[REQUEST]', request.method(), request.url());
    }
  });

  page.on('response', async response => {
    if (response.url().includes('/open')) {
      console.log('[RESPONSE]', response.status(), response.url());
      if (response.status() === 400) {
        try {
          const text = await response.text();
          console.log('[RESPONSE BODY]', text.substring(0, 500));
        } catch (e) {}
      }
    }
  });

  console.log('1. Navigating to jamovi...');
  await page.goto('https://jamovi.truyenthong.edu.vn/', {
    waitUntil: 'networkidle2',
    timeout: 60000
  });

  console.log('2. Waiting for page to initialize...');
  await new Promise(resolve => setTimeout(resolve, 5000));

  console.log('3. Checking if main.js loaded correctly...');
  const jsInfo = await page.evaluate(() => {
    return {
      mainScripts: Array.from(document.querySelectorAll('script[type="module"]')).map(s => s.src),
      allScripts: Array.from(document.querySelectorAll('script')).map(s => s.src || '(inline)'),
      hasBackstageModel: typeof backstageModel !== 'undefined'
    };
  });
  console.log('Scripts loaded:', JSON.stringify(jsInfo, null, 2));

  console.log('4. Preparing to simulate drag-drop...');
  
  // Read CSV file
  const csvPath = path.resolve('/root/jamovi/KT_Maple.csv');
  if (!fs.existsSync(csvPath)) {
    console.error('CSV file not found:', csvPath);
    await browser.close();
    return;
  }

  const csvContent = fs.readFileSync(csvPath, 'utf-8');
  const csvBlob = Buffer.from(csvContent).toString('base64');

  console.log('CSV file size:', csvContent.length, 'bytes');

  // Simulate drag-drop event
  console.log('5. Simulating drag-drop...');
  const dropResult = await page.evaluate((base64Data, fileName) => {
    try {
      // Convert base64 back to File object
      const byteCharacters = atob(base64Data);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const file = new File([byteArray], fileName, { type: 'text/csv' });

      // Create DataTransfer
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(file);

      // Trigger ondrop event
      const event = new DragEvent('drop', {
        bubbles: true,
        cancelable: true,
        dataTransfer: dataTransfer
      });

      document.dispatchEvent(event);
      
      return { success: true, fileSize: file.size, fileName: file.name };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }, csvBlob, 'KT_Maple.csv');

  console.log('Drop result:', dropResult);

  console.log('6. Waiting for upload to complete...');
  await new Promise(resolve => setTimeout(resolve, 10000));

  // Check for errors in console
  const errors = consoleMessages.filter(m => m.type === 'error');
  console.log('\n=== Console Errors ===');
  console.log('Total errors:', errors.length);
  errors.forEach((err, i) => {
    console.log(`${i + 1}. ${err.text}`);
  });

  // Check network requests
  console.log('\n=== Network Requests to /open ===');
  console.log('Total requests:', networkRequests.length);
  networkRequests.forEach((req, i) => {
    console.log(`${i + 1}. ${req.method} ${req.url}`);
    if (req.postData) {
      console.log('   POST data preview:', req.postData);
    }
  });

  // Take screenshot
  await page.screenshot({ path: '/root/jamovi/chrome-test/dragdrop_screenshot.png', fullPage: true });
  console.log('\nScreenshot saved to dragdrop_screenshot.png');

  await browser.close();
  
  // Exit with error code if there were errors
  if (errors.length > 0) {
    console.log('\n❌ Test failed with errors');
    process.exit(1);
  } else {
    console.log('\n✅ Test completed');
    process.exit(0);
  }
})();
