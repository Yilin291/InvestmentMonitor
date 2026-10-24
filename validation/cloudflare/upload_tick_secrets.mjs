// Copy exactly two existing secrets to the already-authorized Worker via stdin.
// Wrangler disk logging and telemetry disabled; stdout/stderr never forwarded.
import {readFileSync, lstatSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
const cwd = fileURLToPath(new URL('.', import.meta.url));
const path = fileURLToPath(new URL('../../.product-data/production-config.json', import.meta.url));
if (!process.argv.includes('--upload')) {
  console.log(JSON.stringify({status: 'not_run', reason: 'requires_upload_argument_after_account_authorization'}));
  process.exit(2);
}
try {
  const stat = lstatSync(path);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.mode & 0o077) throw new Error();
  const config = JSON.parse(readFileSync(path, 'utf8'));
  if (config.APP_ORIGIN !== 'https://ucdte4eh02uv.meoo.info') throw new Error();
  const fields = ['WATCHLIST_GATEWAY_ANON_KEY', 'TICK_SECRET'];
  const selected = Object.fromEntries(fields.map(key => [key, config[key]]));
  if (fields.some(key => typeof selected[key] !== 'string' || selected[key].length < 24)) throw new Error();
  const child = spawn(cwd + 'node_modules/.bin/wrangler', ['secret', 'bulk', '--name', 'tonghuashun-tick'], {
    cwd, env: {...process.env, WRANGLER_WRITE_LOGS: 'false', WRANGLER_LOG_SANITIZE: 'true',
      WRANGLER_SEND_METRICS: 'false'}, stdio: ['pipe', 'pipe', 'pipe'],
  });
  child.stdout.resume();
  child.stderr.resume();
  child.stdin.on('error', () => {});
  child.on('error', () => {console.log(JSON.stringify({status:'failed',reason:'wrangler_launch_failed'}));process.exitCode=1;});
  child.on('close', code => {
    console.log(JSON.stringify({status: code === 0 ? 'uploaded' : 'failed',
      secret_names: fields, values_logged: false, exit_code: code}));
    if (code !== 0) process.exitCode = 1;
  });
  child.stdin.end(JSON.stringify(selected));
} catch {
  console.log(JSON.stringify({status:'not_run',reason:'secure_product_config_unavailable_or_invalid'}));
  process.exitCode = 2;
}
