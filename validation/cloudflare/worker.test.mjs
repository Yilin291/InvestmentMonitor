// TEST fixtures only; never makes a live network request or creates cloud evidence.
import test from 'node:test';
import assert from 'node:assert/strict';
import worker, {runScheduled, slotKey} from './worker.mjs';

const scheduledTime = 1792838340000;
const controller = {scheduledTime, cron: '* * * * *'};
const env = {SCHEDULER_MODE: 'active', WATCHLIST_GATEWAY_ANON_KEY: 'TEST_ONLY_GATEWAY', TICK_SECRET: 'TEST_ONLY_SECRET_1234567890'};
const health = () => Response.json({status: 'ok', storage: 'postgresql_rpc', release: 'test-release'});
const completed = () => Response.json({processed: 1, run_id: 'test_run', task_id: 'test_task', decision: 'notified'});
async function invoke(responses, overrides = {}, event = controller) {
  const calls = [], logs = [];
  await runScheduled(event, {...env, ...overrides}, {now: () => event.scheduledTime,
    pause: async () => {}, log: row => logs.push(row), fetch: async (url, options) => {
      calls.push({url, options});
      const next = responses.shift();
      if (next instanceof Error) throw next;
      assert.ok(next, 'unexpected extra request');
      return next;
    }});
  return {calls, logs};
}
test('TEST stable key per minute, next minute changes key; invalid timestamp rejected', () => {
  assert.equal(slotKey(scheduledTime), slotKey(scheduledTime + 100));
  assert.notEqual(slotKey(scheduledTime), slotKey(scheduledTime + 60000));
  assert.throws(() => slotKey(NaN));
});
test('TEST probe measures server network without sending a tick', async () => {
  const {calls, logs} = await invoke([health()], {SCHEDULER_MODE: 'probe'});
  assert.equal(calls.length, 1);
  assert.equal(logs.at(-1).status, 'probe_only_no_tick');
});
test('TEST active mode uses dual headers and logs result IDs only', async () => {
  const {calls, logs} = await invoke([health(), completed()]);
  assert.equal(calls[1].options.headers.Authorization, 'Bearer ' + env.WATCHLIST_GATEWAY_ANON_KEY);
  assert.equal(calls[1].options.headers['X-Tick-Secret'], env.TICK_SECRET);
  assert.equal(calls[1].options.headers['Idempotency-Key'], slotKey(scheduledTime));
  assert.equal(calls[1].options.redirect, 'manual');
  assert.equal(logs.at(-1).business.run_id, 'test_run');
  assert.ok(!JSON.stringify(logs).includes(env.TICK_SECRET));
  assert.ok(!JSON.stringify(logs).includes(env.WATCHLIST_GATEWAY_ANON_KEY));
});
test('TEST network failure retries once with SAME key; returned secret is redacted', async () => {
  const {calls, logs} = await invoke([health(), new Error(env.TICK_SECRET),
    Response.json({duplicate: true, key: env.TICK_SECRET, unknown: env.WATCHLIST_GATEWAY_ANON_KEY})]);
  assert.equal(calls.length, 3);
  assert.equal(calls[1].options.headers['Idempotency-Key'], calls[2].options.headers['Idempotency-Key']);
  assert.equal(logs.at(-1).status, 'accepted_requires_business_readback');
  assert.ok(!JSON.stringify(logs).includes(env.TICK_SECRET));
  assert.ok(!JSON.stringify(logs).includes(env.WATCHLIST_GATEWAY_ANON_KEY));
});
test('TEST three possible upstream failures are bounded at two tick attempts', async () => {
  const {calls, logs} = await invoke([health(), new Error('one'), new Error('two'), completed()]);
  assert.equal(calls.length, 3);
  assert.equal(logs.at(-1).error_code, 'bounded_attempts_ended');
});
test('TEST redirects, 401 and 429 are rejected without retry', async () => {
  for (const status of [301, 302, 307, 308, 401, 429]) {
    const {calls, logs} = await invoke([health(), Response.json({code: 'unauthorized'}, {status})]);
    assert.equal(calls.length, 2);
    assert.equal(logs.at(-1).status, 'failed');
  }
});
test('TEST 200 malformed JSON/business shape cannot count as accepted tick', async () => {
  for (const response of [new Response('not JSON'), Response.json({}), Response.json({code: 'storage_error'})]) {
    const {logs} = await invoke([health(), response]);
    assert.ok(!logs.some(row => row.status === 'accepted_requires_business_readback'));
  }
});
test('TEST failed health and missing secrets cannot send tick', async () => {
  const bad = await invoke([Response.json({status: 'bad'}, {status: 503})]);
  assert.equal(bad.calls.length, 1);
  const missing = await invoke([health()], {TICK_SECRET: ''});
  assert.equal(missing.calls.length, 1);
  assert.equal(missing.logs.at(-1).error_code, 'scheduler_secret_missing');
});
test('TEST external HTTP request cannot trigger tick', async () => {
  assert.equal((await worker.fetch(new Request('https://test.example/'))).status, 404);
});
test('TEST explicit replay occurs only in selected slot, primary still uses new key', async () => {
  const replayKey=slotKey(scheduledTime-60000);
  const overrides={VALIDATION_REPLAY_AT_SLOT:slotKey(scheduledTime),VALIDATION_REPLAY_KEY:replayKey};
  const {calls,logs}=await invoke([health(),Response.json({duplicate:true,key:replayKey}),completed()],overrides);
  assert.equal(calls.length,3);
  assert.equal(calls[1].options.headers['Idempotency-Key'],replayKey);
  assert.equal(calls[2].options.headers['Idempotency-Key'],slotKey(scheduledTime));
  assert.equal(logs.find(x=>x.phase==='validation_replay').status,'duplicate_requires_readback');
  const next=await invoke([health(),completed()],overrides,{scheduledTime:scheduledTime+60000,cron:'* * * * *'});
  assert.equal(next.calls.length,2);
});
