const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

// File log
const logFile = path.join(__dirname, 'jamovi_console.log');

function logToFile(message) {
    const timestamp = new Date().toISOString();
    fs.appendFileSync(logFile, `[${timestamp}] ${message}\n`);
}

(async () => {
    // Allow optional local MAP via env var MAP_LOCAL=1
    const baseArgs = ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu', '--disable-extensions', '--disable-features=BlockInsecurePrivateNetworkRequests,IsolateOrigins'];
    if (process.env.MAP_LOCAL === '1') {
        baseArgs.push('--host-resolver-rules=MAP jamovi.truyenthong.edu.vn 127.0.0.1');
    }

    const browser = await puppeteer.launch({ 
        headless: true, 
        args: baseArgs,
        ignoreHTTPSErrors: true,
    });

    const page = await browser.newPage();

    // Bắt console log từ trang web
    page.on('console', msg => {
        const text = msg.text();
        console.log(`PAGE LOG: ${text}`);
        logToFile(text);
    });

    // Network/request logging for diagnosis
    page.on('request', request => {
        logToFile(`REQUEST: ${request.method()} ${request.url()} [${request.resourceType()}]`);
    });

    page.on('requestfailed', request => {
        const failure = request.failure();
        const failureMsg = failure ? (failure.errorText || JSON.stringify(failure)) : 'Unknown failure';
        logToFile(`REQUEST_FAILED: ${request.method()} ${request.url()} -> ${failureMsg}`);
    });

    page.on('response', response => {
        logToFile(`RESPONSE: ${response.status()} ${response.url()}`);
    });

    page.on('pageerror', err => {
        logToFile(`PAGE_ERROR: ${err.toString()}`);
    });

    page.on('dialog', async dialog => {
        logToFile(`DIALOG: ${dialog.type()} ${dialog.message()}`);
        try { await dialog.dismiss(); } catch (e) {}
    });

        try {
            // Use HTTP for local test (nginx on LXC is handling port 80); map hostname
            // to localhost via Chrome args above when MAP_LOCAL=1.
            await page.goto('http://jamovi.truyenthong.edu.vn/', { waitUntil: 'networkidle0' });
            // Give the page some time to run client-side JS (open WebSocket, etc.)
            await new Promise(r => setTimeout(r, 8000));
    } catch (err) {
        console.error('Error loading page:', err);
        logToFile(`Error loading page: ${err.message}`);
    }

    await browser.close();
})();
