// Checks the installed official client; never prints tokens or raw errors.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const root = path.join(os.homedir(), '.codex/skills/ifind-finance-data');

async function main() {
  const config = JSON.parse(fs.readFileSync(path.join(root, 'mcp_config.json'), 'utf8'));
  const client = require(path.join(root, 'call-node.js'));
  const localOk = typeof client.call === 'function' && typeof client.listTools === 'function';
  if (!localOk) throw new Error('Invalid client exports');
  const token = typeof config.auth_token === 'string' ? config.auth_token.trim() : '';
  if (token.length < 8 || /your|placeholder|密钥|填入/i.test(token)) {
    console.log(JSON.stringify({local_check: 'passed', online_check: 'not_run', reason: 'credential_missing'}));
    process.exitCode = 2;
    return;
  }
  const result = await client.listTools('stock');
  const toolList = result?.data?.result?.tools;
  const ok = result.ok === true && result.status_code === 200 && Array.isArray(toolList);
  console.log(JSON.stringify({local_check: 'passed', online_check: ok ? 'passed' : 'failed', status_code: result.status_code, tool_count: Array.isArray(toolList) ? toolList.length : 0}));
  process.exitCode = ok ? 0 : 1;
}

main().catch(error => {
  const status = String(error.message).match(/HTTP(?: Error:)?\s+(\d{3})/);
  console.log(JSON.stringify({online_check: 'failed', http_status: status ? Number(status[1]) : null, reason: 'authentication_network_or_protocol_error'}));
  process.exitCode = 1;
});
