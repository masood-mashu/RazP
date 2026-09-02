/**
 * Phase 2 Browser-Level Smoke Test.
 * Uses Playwright to verify the built React console served by FastAPI.
 * 
 * Verifications:
 * 1. SPA loads successfully
 * 2. Command Center renders
 * 3. Recovery Queue opens
 * 4. Case Workspace opens
 * 5. Case evaluation produces a result
 * 6. AI reasoning, policy decision, state transitions, and audit block are displayed
 * 7. Audit Ledger page loads
 * 8. Policy page loads
 * 9. Benchmark page loads
 * 10. Browser console contains NO uncaught errors
 */

import { createRequire } from 'module';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');

const require = createRequire(import.meta.url);
const playwrightPath = path.join(ROOT_DIR, 'frontend', 'node_modules', 'playwright');
const { chromium } = require(playwrightPath);

const BASE_URL = process.env.TEST_URL || 'http://127.0.0.1:8000';

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function isServerReady(url) {
  try {
    const res = await fetch(`${url}/api/system/status`);
    return res.ok;
  } catch (err) {
    return false;
  }
}

async function runBrowserSmokeTest() {
  console.log('='.repeat(70));
  console.log('PHASE 2 BROWSER SMOKE TEST (PLAYWRIGHT)');
  console.log('='.repeat(70));

  let serverProcess = null;
  const ready = await isServerReady(BASE_URL);

  if (!ready) {
    console.log(`FastAPI backend is not running at ${BASE_URL}. Spawning local test server...`);
    const serverEnv = {
      ...process.env,
      DATABASE_URL: process.env.DATABASE_URL || 'postgresql://postgres:postgres@127.0.0.1:5433/razp_test',
    };
    serverProcess = spawn('python', ['-m', 'uvicorn', 'server.app:app', '--host', '127.0.0.1', '--port', '8000'], {
      cwd: ROOT_DIR,
      env: serverEnv,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    serverProcess.stdout.on('data', (d) => {
      const msg = d.toString();
      if (msg.includes('ERROR') || msg.includes('Traceback')) console.log('[Server stdout]', msg.trim());
    });
    serverProcess.stderr.on('data', (d) => {
      const msg = d.toString();
      if (msg.includes('ERROR') || msg.includes('Traceback')) console.log('[Server stderr]', msg.trim());
    });

    let attempts = 0;
    while (attempts < 20) {
      await sleep(500);
      if (await isServerReady(BASE_URL)) {
        console.log('Local FastAPI test server is ready and serving SPA.');
        break;
      }
      attempts++;
    }

    if (!(await isServerReady(BASE_URL))) {
      if (serverProcess) serverProcess.kill();
      throw new Error('Failed to start local FastAPI server within 10 seconds.');
    }
  } else {
    console.log(`Connected to active FastAPI server at ${BASE_URL}`);
  }

  const consoleErrors = [];
  let browser;

  try {
    try {
      browser = await chromium.launch({ headless: true });
    } catch {
      browser = await chromium.launch({ channel: 'msedge', headless: true });
    }

    const context = await browser.newContext();
    const page = await context.newPage();

    // Listen for console logs
    page.on('console', (msg) => {
      const text = msg.text();
      console.log(`[Browser ${msg.type()}]`, text);
      if (msg.type() === 'error') {
        if (!text.includes('favicon.ico')) {
          consoleErrors.push(text);
        }
      }
    });

    page.on('pageerror', (err) => {
      console.log('[Browser pageerror]', err.message);
      consoleErrors.push(`Uncaught exception: ${err.message}`);
    });

    // Checkpoint 1: SPA loads successfully
    console.log('\n[Check 1/10] Loading SPA at', BASE_URL);
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 15000 });
    // Set default demo admin token in localStorage
    await page.evaluate(() => {
      localStorage.setItem('razp_auth_token', 'razp_master_admin_demo');
    });
    await page.reload({ waitUntil: 'networkidle', timeout: 15000 });
    const pageTitle = await page.title();
    console.log(`    Page title: "${pageTitle}"`);

    // Checkpoint 2: Command Center renders
    console.log('[Check 2/10] Verifying Command Center...');
    try {
      await page.waitForSelector('text=Recovery Command Center', { timeout: 10000 });
    } catch (e) {
      console.log('Page content:', await page.content());
      throw e;
    }
    const atRiskCard = await page.locator('text=Revenue at Risk').isVisible();
    const recoveredCard = await page.locator('text=Recovered Revenue (Gross)').isVisible();
    if (!atRiskCard || !recoveredCard) {
      throw new Error('Command Center StatCards not visible');
    }
    console.log('    ✓ Command Center header and exposure metrics rendered.');

    // Checkpoint 3: Recovery Queue opens
    console.log('[Check 3/10] Navigating to Recovery Queue...');
    await page.click('button:has-text("Recovery Queue")');
    await page.waitForSelector('text=Recovery Queue', { timeout: 5000 });
    await page.waitForSelector('input[placeholder*="Search payment"]', { timeout: 5000 });
    console.log('    ✓ Recovery Queue table and filters rendered.');

    // Checkpoint 4: Case Workspace opens
    console.log('[Check 4/10] Navigating to Case Workspace...');
    await page.click('button:has-text("Case Workspace")');
    await page.waitForSelector('text=Case Workspace & Decision Engine', { timeout: 5000 });
    await page.waitForSelector('text=Payment Telemetry', { timeout: 5000 });
    console.log('    ✓ Case Workspace form and telemetry fields rendered.');

    // Checkpoint 5: Case evaluation produces result
    console.log('[Check 5/10] Executing live case evaluation...');
    // Click Hinglish preset
    await page.click('button:has-text("Hinglish PTP")');
    await sleep(300);
    // Click evaluation button
    await page.click('button[type="submit"]');
    await page.waitForSelector('text=AI Reasoner Output', { timeout: 25000 });
    console.log('    ✓ Case evaluation completed and received response.');

    // Checkpoint 6: AI reasoning, policy decision, state transition, and audit block displayed
    console.log('[Check 6/10] Verifying evaluation outputs...');
    const hasAiReasoning = await page.locator('text=AI Reasoner Output').isVisible();
    const hasPolicyDecision = await page.locator('text=Deterministic Policy Gate Decision').isVisible();
    const hasTransitions = await page.locator('text=State Transitions (PostgreSQL)').isVisible();
    const hasAuditBlock = await page.locator('text=Persisted Audit Block').isVisible();

    if (!hasAiReasoning || !hasPolicyDecision || !hasTransitions || !hasAuditBlock) {
      throw new Error('Missing decision component on Case Workspace');
    }
    console.log('    ✓ AI reasoner card, Deterministic Policy Gate card, state transitions, and audit block displayed.');

    // Checkpoint 7: Audit Ledger page loads
    console.log('[Check 7/10] Navigating to Cryptographic Ledger...');
    await page.click('button:has-text("Cryptographic Ledger")');
    await page.waitForSelector('text=Cryptographic SHA-256 Audit Ledger', { timeout: 5000 });
    await page.waitForSelector('text=CRYPTOGRAPHIC INTEGRITY VERIFIED', { timeout: 8000 });
    console.log('    ✓ Audit Ledger page loaded with unbroken SHA-256 chain verification.');

    // Checkpoint 8: Policy page loads
    console.log('[Check 8/10] Navigating to Policy Engine...');
    await page.click('button:has-text("Policy Engine")');
    await page.waitForSelector('text=Deterministic Policy & Compliance Gate', { timeout: 5000 });
    await page.waitForSelector('text=TRAI Quiet Hours', { timeout: 5000 });
    await page.waitForSelector('text=Merchant Configurable Parameters', { timeout: 5000 });
    console.log('    ✓ Policy page rendered immutable statutory regulations and configurable parameters.');

    // Checkpoint 9: Benchmark page loads
    console.log('[Check 9/10] Navigating to Benchmark & Evaluation...');
    await page.click('button:has-text("Evaluation & Ablation")');
    await page.waitForSelector('text=Evaluation Harness & Benchmark Provenance', { timeout: 8000 });
    await page.waitForSelector('text=Six-Way Architectural Ablation', { timeout: 8000 });
    // Switch to Live Gemini tab
    await page.click('button:has-text("Live Gemini API Evaluation")');
    await page.waitForSelector('text=Live Gemini Performance & Safety Audit', { timeout: 8000 });
    console.log('    ✓ Benchmark page rendered Six-Way Ablation Matrix and Live Gemini evaluation metrics.');

    // Checkpoint 10: No uncaught errors in browser console
    console.log('[Check 10/10] Checking browser console log integrity...');
    if (consoleErrors.length > 0) {
      console.warn('    Found console error(s):', consoleErrors);
      throw new Error(`Browser console contained ${consoleErrors.length} uncaught error(s): ${consoleErrors.join(', ')}`);
    }
    console.log('    ✓ Zero uncaught exceptions or error logs in browser session.');

    console.log('\n' + '='.repeat(70));
    console.log('ALL 10 BROWSER SMOKE TEST CHECKS PASSED SUCCESSFULLY!');
    console.log('='.repeat(70));
  } finally {
    if (browser) await browser.close();
    if (serverProcess) {
      console.log('Terminating spawned local test server...');
      serverProcess.kill();
    }
  }
}

runBrowserSmokeTest().catch((err) => {
  console.error('\n❌ BROWSER SMOKE TEST FAILED:', err);
  process.exit(1);
});
