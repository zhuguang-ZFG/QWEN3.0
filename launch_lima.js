const pty = require('node-pty');
const path = require('path');

if (!process.env.LIMA_API_KEY && !process.env.LIMA_CODE_API_KEY) {
  throw new Error('LIMA_API_KEY or LIMA_CODE_API_KEY env var is required');
}

const env = Object.assign({}, process.env, {
  LIMA_CODE_SERVER_URL: 'https://chat.donglicao.com',
  LIMA_API_KEY: process.env.LIMA_API_KEY || process.env.LIMA_CODE_API_KEY,
  LIMA_CODE_API_KEY: process.env.LIMA_CODE_API_KEY || process.env.LIMA_API_KEY,
});

const ptyProcess = pty.spawn('node', [
  'D:\GIT\deepcode-cli\node_modules\tsx\dist\cli.mjs',
  'D:\GIT\deepcode-cli\src\cli.tsx'
], {
  name: 'xterm-256color',
  cols: 120,
  rows: 40,
  cwd: 'D:\GIT',
  env: env,
});

ptyProcess.onData((data) => {
  process.stdout.write(data);
});

ptyProcess.onExit(({ exitCode }) => {
  console.log(`\n[LiMa Code exited with code ${exitCode}]`);
});

// Auto-send commands after delay
setTimeout(() => ptyProcess.write('/lima status\r'), 5000);
setTimeout(() => {
  ptyProcess.write('/quit\r');
  setTimeout(() => process.exit(0), 2000);
}, 15000);
