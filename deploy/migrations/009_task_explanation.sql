-- Additive read model only. Does not mutate tasks, rules, runs, notifications or scheduler.
BEGIN;
SELECT pg_advisory_xact_lock(724102401);
CREATE OR REPLACE FUNCTION watchlist.product_task_json(p_id text,p_owner text) RETURNS jsonb
LANGUAGE sql STABLE SET search_path=pg_catalog AS $$
 SELECT to_jsonb(t)||jsonb_build_object(
  'spec',v.spec::jsonb,
  'runtime',(to_jsonb(r)-'lease_token')||jsonb_build_object('state',r.state::jsonb,'overdue',t.lifecycle='enabled' AND r.next_run IS NOT NULL AND extract(epoch from statement_timestamp())>r.next_run+CASE WHEN v.spec::jsonb#>>'{rule,kind}'='close_price_group' THEN 600 ELSE greatest(coalesce((v.spec::jsonb#>>'{schedule,interval_seconds}')::int,60),60) END),
  'instrument',to_jsonb(i),
  'last_evaluation',(SELECT jsonb_build_object('run_id',lr.id,'version',lr.version,'evaluated_at',lr.finished_at,'result',lr.result::jsonb,'decision',lr.decision,'trade_date',lr.detail::jsonb#>>'{evidence,0,observation,trade_date}','expected_trade_date',lr.detail::jsonb#>>'{market,expected_trade_date}','reason_code',lr.detail::jsonb#>>'{evidence,0,reason_code}','evidence',coalesce(lr.detail::jsonb->'evidence','[]'::jsonb),'calendar',lr.detail::jsonb->'calendar','trigger_request_id',(SELECT tk.id FROM watchlist.ticks tk WHERE tk.outcome::jsonb->>'run_id'=lr.id ORDER BY tk.started_at LIMIT 1)) FROM watchlist.runs lr WHERE lr.task_id=t.id AND lr.version=t.version AND lr.status='succeeded' ORDER BY lr.finished_at DESC LIMIT 1),
  'scheduler_observation',jsonb_build_object('server_time',extract(epoch from statement_timestamp()),'last_request',(SELECT max(started_at) FROM watchlist.ticks),'last_finished',(SELECT max(finished_at) FROM watchlist.ticks),'last_cloud_request',(SELECT max(started_at) FROM watchlist.ticks WHERE id LIKE 'cf-cron:ucdte4eh02uv:%'),'last_cloud_finished',(SELECT max(finished_at) FROM watchlist.ticks WHERE id LIKE 'cf-cron:ucdte4eh02uv:%'),'expected_interval_seconds',60,'warning_after_seconds',180,'source_basis','authenticated_tick_request_id_prefix','automatic_execution_verified',false),
  'unread',(SELECT count(*) FROM watchlist.notifications n WHERE n.task_id=t.id AND n.read_at IS NULL))
 FROM watchlist.tasks t JOIN watchlist.rule_versions v ON v.task_id=t.id AND v.version=t.version JOIN watchlist.runtime r ON r.task_id=t.id LEFT JOIN watchlist.instruments i ON i.id=t.instrument_id WHERE t.id=p_id AND t.owner=p_owner
$$;
REVOKE ALL ON FUNCTION watchlist.product_task_json(text,text) FROM PUBLIC,anon,authenticated;
INSERT INTO watchlist.schema_version VALUES(9);
COMMIT;
