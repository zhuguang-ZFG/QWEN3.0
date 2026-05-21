/**
 * Kimi Token 自动刷新脚本
 * 每 6 小时运行一次，用保存的 cookies 重新获取 access_token
 * 并更新 CF Worker 的环境变量
 */
const { chromium } = require('playwright');
const fs = require('fs');
const { execSync } = require('child_process');

const SESSION_FILE = 'D:/ollama_server/kimi_session.json';
const CF_TOKEN = 'cfut_t3gYSHnANVMmiY13rKsDS908wFFVpbzRzljqIu8mffb419ee';
const CF_ACCOUNT = '3e8dfc378deaf1a6f39fda85ceaca32b';
const WORKER_NAME = 'kimi';

async function refreshToken() {
  console.log(`[${new Date().toISOString()}] Refreshing Kimi token...`);
  const session = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf-8'));

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  await context.addCookies(session.cookies);
  const page = await context.newPage();

  let newToken = null;
  page.on('request', req => {
    const auth = req.headers()['authorization'] || '';
    if (auth.startsWith('Bearer ') && auth.length > 200) {
      newToken = auth;
    }
  });

  await page.goto('https://kimi.moonshot.cn', {
    waitUntil: 'networkidle', timeout: 30000
  }).catch(() => {});
  await page.waitForTimeout(5000);

  const newCookies = await context.cookies();
  await browser.close();

  if (newToken && newToken.length > 200) {
    session.authToken = newToken;
    session.cookies = newCookies;
    session.lastRefresh = new Date().toISOString();
    fs.writeFileSync(SESSION_FILE, JSON.stringify(session, null, 2));
    console.log(`  Token refreshed: ${newToken.substring(0, 50)}...`);
    updateWorkerSecret(newToken);
    return true;
  } else {
    console.log('  FAILED: No token captured. Login expired.');
    console.log('  Run: node kimi_login.js');
    return false;
  }
}

function updateWorkerSecret(token) {
  try {
    const cmd = `npx wrangler secret put KIMI_TOKEN --name ${WORKER_NAME}`;
    execSync(cmd, {
      input: token,
      env: { ...process.env, CLOUDFLARE_API_TOKEN: CF_TOKEN },
      cwd: 'D:/ollama_server',
      timeout: 15000
    });
    console.log('  CF Worker secret updated.');
  } catch (e) {
    console.log('  CF Worker update failed:', e.message);
    console.log('  Fallback: redeploy with --var');
    try {
      execSync(
        `npx wrangler deploy kimi-worker.js --name kimi --compatibility-date 2024-09-23 --route "kimi.zhuguang.ccwu.cc/*" --var "KIMI_TOKEN:${token}"`,
        { env: { ...process.env, CLOUDFLARE_API_TOKEN: CF_TOKEN }, cwd: 'D:/ollama_server', timeout: 30000 }
      );
      console.log('  Redeployed with new token.');
    } catch (e2) {
      console.log('  Redeploy also failed:', e2.message);
    }
  }
}

refreshToken().then(ok => {
  process.exit(ok ? 0 : 1);
}).catch(e => {
  console.error('Fatal:', e);
  process.exit(1);
});
