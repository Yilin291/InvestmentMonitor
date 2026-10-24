// Runs only on Cloudflare ScheduledEvents. No public HTTP trigger is provided.
const BASE = 'https://ucdte4eh02uv.meoo.info/sb-api/functions/v1/watchlist-api';
const REVISION = 'cf-cron-v4';
const safeText = value => typeof value === 'string' && /^[A-Za-z0-9:_-]{1,160}$/.test(value) ? value : null;

export function slotKey(scheduledTime) {
  if (!Number.isSafeInteger(scheduledTime) || scheduledTime < 0) throw new Error('invalid_schedule_time');
  return `cf-cron:ucdte4eh02uv:${Math.floor(scheduledTime / 60000)}`;
}

// Explicit allowlist: never log whole response bodies, headers, env or errors.
function businessSummary(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const result = {};
  for (const field of ['run_id', 'task_id', 'notification_id', 'decision', 'key', 'code', 'release']) {
    const v = safeText(value[field]);
    if (v !== null) result[field] = v;
  }
  for (const field of ['processed', 'version']) {
    if (Number.isSafeInteger(value[field]) && value[field] >= 0) result[field] = value[field];
  }
  if (typeof value.duplicate === 'boolean') result.duplicate = value.duplicate;
  return result;
}

async function boundedJson(response) {
  if (!response.body) return null;
  const reader = response.body.getReader();
  let length = 0;
  const chunks = [];
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    length += value.length;
    if (length > 32768) { await reader.cancel(); throw new Error('body_limit'); }
    chunks.push(value);
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return JSON.parse(new TextDecoder().decode(bytes));
}

export async function runScheduled(controller, env, deps = {}) {
  const transport = deps.fetch || fetch;
  const emit = deps.log || (row => console.log(JSON.stringify(row)));
  const now = deps.now || Date.now;
  const pause = deps.pause || (ms => new Promise(resolve => setTimeout(resolve, ms)));
  const key = slotKey(controller.scheduledTime);
  const base = {source: 'cloudflare_cron', revision: REVISION, cron: controller.cron,
    scheduled_at: new Date(controller.scheduledTime).toISOString(),
    scheduled_time_ms: controller.scheduledTime, request_key: key,
    started_at: new Date(now()).toISOString(), scheduler_mode: env.SCHEDULER_MODE,
    lateness_ms: Math.max(0, now() - controller.scheduledTime)};
  // Defence in depth: strip secret substrings even from allowlisted string values.
  const log = row => {
    let line = JSON.stringify({...base, ...row});
    for (const value of [env.WATCHLIST_GATEWAY_ANON_KEY, env.TICK_SECRET]) {
      if (typeof value === 'string' && value.length) line = line.split(value).join('[REDACTED]');
    }
    emit(JSON.parse(line));
  };
  if (!['probe', 'active'].includes(env.SCHEDULER_MODE)) {
    log({phase: 'complete', status: 'disabled'});
    return;
  }
  if (now() - controller.scheduledTime > 5 * 60_000 || controller.scheduledTime > now() + 60_000) {
    log({phase: 'complete', status: 'failed', error_code: 'slot_outside_dispatch_window'});
    return;
  }
  log({phase: 'started'});
  let health;
  try {
    const response = await transport(BASE + '/api/health', {redirect: 'manual', signal: AbortSignal.timeout(5000)});
    health = await boundedJson(response);
    const ready = response.ok && health?.status === 'ok' && health?.storage === 'postgresql_rpc';
    log({phase: 'health', status: ready ? 'passed' : 'failed', http_status: response.status,
      product_release: safeText(health?.release), error_code: ready ? null : 'health_not_ready'});
    if (!ready) return;
  } catch (error) {
    log({phase: 'health', status: 'failed', http_status: null, error_code: 'health_network_timeout_or_json', error_name: safeText(error?.name), diagnostic: String(error?.message || '').slice(0,240)});
    return;
  }
  if (env.SCHEDULER_MODE === 'probe') {
    log({phase: 'complete', status: 'probe_only_no_tick', finished_at: new Date(now()).toISOString()});
    return;
  }
  if (typeof env.WATCHLIST_GATEWAY_ANON_KEY !== 'string' || !env.WATCHLIST_GATEWAY_ANON_KEY ||
      typeof env.TICK_SECRET !== 'string' || env.TICK_SECRET.length < 24) {
    log({phase: 'complete', status: 'failed', error_code: 'scheduler_secret_missing'});
    return;
  }
  // Explicit, one-slot validation replay; never substitutes for the new primary slot.
  if (env.VALIDATION_REPLAY_AT_SLOT === key &&
      /^cf-cron:ucdte4eh02uv:[0-9]+$/.test(env.VALIDATION_REPLAY_KEY || '') &&
      env.VALIDATION_REPLAY_KEY !== key) {
    const replayKey = env.VALIDATION_REPLAY_KEY;
    try {
      const response = await transport(BASE + '/internal/monitor/tick', {
        method: 'POST', redirect: 'manual', signal: AbortSignal.timeout(8000),
        headers: {'Content-Type':'application/json',
          Authorization:'Bearer ' + env.WATCHLIST_GATEWAY_ANON_KEY,
          'X-Tick-Secret':env.TICK_SECRET, 'Idempotency-Key':replayKey}, body:'{"batch":1}',
      });
      const business = businessSummary(await boundedJson(response));
      log({phase:'validation_replay', validation_kind:'TEST_intentional_same_key_replay',
        replay_key:replayKey, http_status:response.status, business,
        status:response.ok && business?.duplicate === true ? 'duplicate_requires_readback' : 'failed'});
    } catch {
      log({phase:'validation_replay', validation_kind:'TEST_intentional_same_key_replay',
        replay_key:replayKey, status:'failed', error_code:'replay_network_or_json'});
    }
  }
  const started = now();
  for (let attempt = 1; attempt <= 2; attempt++) {
    const budget = Math.min(attempt === 1 ? 35000 : 12000, 50000 - (now() - started));
    if (budget < 1000) break;
    let retry = false;
    try {
      const response = await transport(BASE + '/internal/monitor/tick', {
        method: 'POST', redirect: 'manual', signal: AbortSignal.timeout(budget),
        headers: {'Content-Type': 'application/json',
          Authorization: 'Bearer ' + env.WATCHLIST_GATEWAY_ANON_KEY,
          'X-Tick-Secret': env.TICK_SECRET, 'Idempotency-Key': key}, body: '{"batch":1}',
      });
      let payload = null;
      try { payload = await boundedJson(response); } catch {}
      const business = businessSummary(payload);
      const recognized = !!business && !business.code && (typeof business.processed === 'number' || business.duplicate === true || !!business.decision);
      const accepted = response.ok && recognized;
      log({phase: 'tick', attempt, http_status: response.status,
        status: accepted ? 'accepted_requires_business_readback' : 'failed',
        business, error_code: accepted ? null : 'tick_http_or_protocol_error',
        finished_at: new Date(now()).toISOString()});
      // A 2xx duplicate is only transport acceptance; DB readback must prove completion.
      if (accepted) return;
      retry = [502, 503, 504].includes(response.status);
    } catch {
      log({phase: 'tick', attempt, http_status: null, status: 'failed',
        error_code: 'tick_network_timeout_or_redirect', finished_at: new Date(now()).toISOString()});
      retry = true;
    }
    if (!retry || attempt === 2) break;
    await pause(500);
  }
  log({phase: 'complete', status: 'failed', error_code: 'bounded_attempts_ended', finished_at: new Date(now()).toISOString()});
}

export default {
  async scheduled(controller, env) { await runScheduled(controller, env); },
  async fetch() { return new Response('Not found', {status: 404}); },
};
