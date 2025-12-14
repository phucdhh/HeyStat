const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  console.log('=== Testing Jamovi with CSV Upload ===\n');
  
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
  
  // Track WebSocket messages
  const wsMessages = [];
  const client = await page.target().createCDPSession();
  await client.send('Network.enable');
  
  client.on('Network.webSocketFrameReceived', ({ response }) => {
    try {
      const payload = JSON.parse(response.payloadData);
      if (payload.messageType || payload.type) {
        wsMessages.push({ direction: 'received', data: payload });
        console.log('[WS RECV]', JSON.stringify(payload).substring(0, 150));
      }
    } catch (e) {}
  });
  
  client.on('Network.webSocketFrameSent', ({ response }) => {
    try {
      const payload = JSON.parse(response.payloadData);
      if (payload.messageType || payload.type) {
        wsMessages.push({ direction: 'sent', data: payload });
        console.log('[WS SENT]', JSON.stringify(payload).substring(0, 150));
      }
    } catch (e) {}
  });

  // Log console errors
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log('[BROWSER ERROR]', msg.text());
    }
  });

  console.log('1. Navigating to jamovi...');
  await page.goto('https://jamovi.truyenthong.edu.vn/', {
    waitUntil: 'networkidle2',
    timeout: 60000
  });

  console.log('2. Waiting for page to load...');
  await new Promise(resolve => setTimeout(resolve, 5000));

  console.log('3. Looking for file upload button...');
  
  // Try to find and click open file button
  const openButtonClicked = await page.evaluate(() => {
    // Look for various possible selectors for open file
    const buttons = Array.from(document.querySelectorAll('button, .jmv-ribbon-button, [role="button"]'));
    const openButton = buttons.find(b => 
      b.textContent.includes('Open') || 
      b.getAttribute('aria-label')?.includes('Open') ||
      b.getAttribute('title')?.includes('Open')
    );
    
    if (openButton) {
      openButton.click();
      return true;
    }
    return false;
  });

  console.log('Open button clicked:', openButtonClicked);

  if (openButtonClicked) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Set file input
    const fileInput = await page.$('input[type="file"]');
    if (fileInput) {
      console.log('4. Uploading CSV file...');
      const csvPath = path.resolve('/root/jamovi/KT_Maple.csv');
      await fileInput.uploadFiles(csvPath);
      
      console.log('5. Waiting for file to load...');
      await new Promise(resolve => setTimeout(resolve, 5000));
      
      // Check if data is loaded
      const hasData = await page.evaluate(() => {
        const cells = document.querySelectorAll('.jmv-table-cell, td, [role="gridcell"]');
        return cells.length > 0;
      });
      
      console.log('Data loaded:', hasData);
      
      if (hasData) {
        console.log('6. Opening Analyses -> Exploration -> Descriptives...');
        
        // This would require more complex automation
        // For now, just check WebSocket messages
        await new Promise(resolve => setTimeout(resolve, 3000));
      }
    }
  }

  console.log('\n=== WebSocket Messages Summary ===');
  console.log('Total messages:', wsMessages.length);
  console.log('Sent:', wsMessages.filter(m => m.direction === 'sent').length);
  console.log('Received:', wsMessages.filter(m => m.direction === 'received').length);

  // Check for analysis-related messages
  const analysisMessages = wsMessages.filter(m => 
    JSON.stringify(m.data).includes('analysis') || 
    JSON.stringify(m.data).includes('Descriptives')
  );
  
  if (analysisMessages.length > 0) {
    console.log('\nAnalysis messages found:', analysisMessages.length);
  } else {
    console.log('\n⚠️  No analysis messages detected');
  }

  await browser.close();
})();
