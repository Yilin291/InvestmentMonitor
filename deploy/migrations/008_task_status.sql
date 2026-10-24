-- Read model only: actual evaluation and observed tick age, not a claim of automatic scheduler proof.
BEGIN;
SELECT pg_advisory_xact_lock(724102401);
CREATE OR REPLACE FUNCTION watchlist.product_task_json(p_id text,p_owner text) RETURNS jsonb
LANGUAGE sql STABLE SET search_path=pg_catalog AS $$
 SELECT to_jsonb(t)||jsonb_build_object('spec',v.spec::jsonb,'runtime',(to_jsonb(r)-'lease_token')||jsonb_build_object('state',r.state::jsonb,'overdue',t.lifecycle='enabled' AND r.next_run IS NOT NULL AND extract(epoch from statement_timestamp())>r.next_run+CASE WHEN v.spec::jsonb#>>'{rule,kind}'='close_price_group' THEN 600 ELSE greatest(coalesce((v.spec::jsonb#>>'{schedule,interval_seconds}')::int,60),60) END), 'instrument',to_jsonb(i),'last_evaluation',(SELECT jsonb_build_object('result',lr.result::jsonb,'decision',lr.decision,'trade_date',lr.detail::jsonb#>>'{evidence,0,observation,trade_date}','expected_trade_date',lr.detail::jsonb#>>'{market,expected_trade_date}','reason_code',lr.detail::jsonb#>>'{evidence,0,reason_code}') FROM watchlist.runs lr WHERE lr.task_id=t.id AND lr.status='succeeded' ORDER BY lr.finished_at DESC LIMIT 1),'scheduler_observation',jsonb_build_object('last_request',(SELECT max(started_at) FROM watchlist.ticks),'last_finished',(SELECT max(finished_at) FROM watchlist.ticks),'automatic_execution_verified',false),'unread',(SELECT count(*) FROM watchlist.notifications n WHERE n.task_id=t.id AND n.read_at IS NULL))
 FROM watchlist.tasks t JOIN watchlist.rule_versions v ON v.task_id=t.id AND v.version=t.version JOIN watchlist.runtime r ON r.task_id=t.id LEFT JOIN watchlist.instruments i ON i.id=t.instrument_id WHERE t.id=p_id AND t.owner=p_owner
$$;
REVOKE ALL ON FUNCTION watchlist.product_task_json(text,text) FROM PUBLIC,anon,authenticated;
INSERT INTO watchlist.schema_version VALUES(8);
COMMIT;
