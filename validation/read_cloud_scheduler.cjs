// Read-only association of actual Cloudflare slots to persisted business records.
const fs=require('node:fs');
const {execFileSync}=require('node:child_process');
const file=process.argv[2];
if(!file || fs.existsSync(file)) throw new Error('unique_output_path_required');
const sql=`SELECT t.id AS request_key,t.started_at,t.finished_at,t.outcome::jsonb AS outcome,
 (SELECT to_jsonb(r)-'lease_token' FROM watchlist.runs r WHERE r.id=t.outcome::jsonb->>'run_id') AS run,
 (SELECT coalesce(jsonb_agg(to_jsonb(e)),'[]') FROM watchlist.evidence e WHERE e.run_id=t.outcome::jsonb->>'run_id') AS evidence,
 (SELECT coalesce(jsonb_agg(to_jsonb(n)),'[]') FROM watchlist.notifications n WHERE n.run_id=t.outcome::jsonb->>'run_id') AS notifications
 FROM watchlist.ticks t WHERE t.id LIKE 'cf-cron:ucdte4eh02uv:%' ORDER BY t.started_at DESC LIMIT 120`;
try {
 const result=JSON.parse(execFileSync('meoo',['--json','db','query','--project','ucdte4eh02uv',sql],{encoding:'utf8',stdio:['ignore','pipe','pipe'],timeout:30000}));
 if(result.success!==true) throw new Error('query_failed');
 const rows=result.data.rows;
 fs.writeFileSync(file,JSON.stringify({checked_at:new Date().toISOString(),scope:'read_only_no_tick',rows},null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({file,slot_count:rows.length,processed:rows.filter(r=>r.run).length}));
} catch { console.log(JSON.stringify({status:'failed',reason:'readback_query_failed'}));process.exitCode=1; }
