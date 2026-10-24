-- Bounded retry and explicit recovery evidence; no task/lifecycle rewrite.
BEGIN;
SELECT pg_advisory_xact_lock(724102401);
DO $patch$ DECLARE src text; BEGIN
 src:=pg_get_functiondef('public.watchlist_product_v1(text,text,jsonb)'::regprocedure);
 IF position($old0$UPDATE watchlist.runs SET status='superseded',finished_at=n,decision='superseded' WHERE task_id=t.id AND status='running';$old0$ in src)=0 THEN RAISE EXCEPTION 'recovery fragment 0 absent';END IF;
 src:=replace(src,$old0$UPDATE watchlist.runs SET status='superseded',finished_at=n,decision='superseded' WHERE task_id=t.id AND status='running';$old0$,$new0$UPDATE watchlist.ticks SET finished_at=n,outcome=(outcome::jsonb||jsonb_build_object('decision','superseded','reason_code','expired_lease_recovered'))::text
   WHERE finished_at IS NULL AND outcome::jsonb->>'run_id' IN (SELECT id FROM watchlist.runs WHERE task_id=t.id AND status='running');
  UPDATE watchlist.runs SET status='superseded',finished_at=n,decision='superseded',detail=(detail::jsonb||jsonb_build_object('reason_code','expired_lease_recovered'))::text WHERE task_id=t.id AND status='running';$new0$);
 IF position($old1$INSERT INTO watchlist.runs VALUES(rid,t.id,t.version,t.generation,tok,rt.next_run,n,NULL,'running',NULL,NULL,'{}');$old1$ in src)=0 THEN RAISE EXCEPTION 'recovery fragment 1 absent';END IF;
 src:=replace(src,$old1$INSERT INTO watchlist.runs VALUES(rid,t.id,t.version,t.generation,tok,rt.next_run,n,NULL,'running',NULL,NULL,'{}');$old1$,$new1$INSERT INTO watchlist.runs VALUES(rid,t.id,t.version,t.generation,tok,rt.next_run,n,NULL,'running',NULL,NULL,'{}');
  UPDATE watchlist.ticks SET outcome=jsonb_build_object('run_id',rid,'task_id',t.id,'state','running')::text WHERE id=k;$new1$);
 IF position($old2$IF rr.lease_token IS DISTINCT FROM p_body->>'token' THEN RAISE EXCEPTION 'lease_rejected' USING ERRCODE='42501'; END IF;$old2$ in src)=0 THEN RAISE EXCEPTION 'recovery fragment 2 absent';END IF;
 src:=replace(src,$old2$IF rr.lease_token IS DISTINCT FROM p_body->>'token' THEN RAISE EXCEPTION 'lease_rejected' USING ERRCODE='42501'; END IF;$old2$,$new2$IF rr.lease_token IS DISTINCT FROM p_body->>'token' THEN RAISE EXCEPTION 'lease_rejected' USING ERRCODE='42501'; END IF;
  IF EXISTS(SELECT 1 FROM watchlist.ticks WHERE outcome::jsonb->>'run_id'=rr.id) AND NOT EXISTS(SELECT 1 FROM watchlist.ticks WHERE id=p_body->>'key' AND outcome::jsonb->>'run_id'=rr.id) THEN RAISE EXCEPTION 'lease_rejected' USING ERRCODE='42501';END IF;$new2$);
 IF position($old3$next_check:=CASE WHEN valid_result IS NULL THEN n+900 ELSE$old3$ in src)=0 THEN RAISE EXCEPTION 'recovery fragment 3 absent';END IF;
 src:=replace(src,$old3$next_check:=CASE WHEN valid_result IS NULL THEN n+900 ELSE$old3$,$new3$next_check:=CASE WHEN valid_result IS NULL THEN n+least(3600,900*power(2,least(2,coalesce((rt.state::jsonb->>'failure_count')::int,0)))) ELSE$new3$);
 IF position($old4$  UPDATE watchlist.runs SET status='succeeded'$old4$ in src)=0 THEN RAISE EXCEPTION 'recovery fragment 4 absent';END IF;
 src:=replace(src,$old4$  UPDATE watchlist.runs SET status='succeeded'$old4$,$new4$  IF decision='insufficient_data' THEN
   st:=st||jsonb_build_object('failure_count',least(1000000,coalesce((rt.state::jsonb->>'failure_count')::int,0)+1),'failure_since',coalesce((rt.state::jsonb->>'failure_since')::double precision,n));
   details:=details||jsonb_build_object('retry',jsonb_build_object('consecutive_failures',st->'failure_count','next_retry_at',(SELECT next_run FROM watchlist.runtime WHERE task_id=t.id),'last_success',rt.last_success,'policy','15m_30m_60m_cap_for_daily_close'));
  ELSE
   IF coalesce((rt.state::jsonb->>'failure_count')::int,0)>0 THEN
    details:=details||jsonb_build_object('recovery',jsonb_build_object('previous_failures',rt.state::jsonb->'failure_count','recovered_at',n,'historical_prices_replayed',false));
   END IF;
   st:=st-'failure_count'-'failure_since';
  END IF;
  IF rt.state::jsonb ? 'failure_since' OR n-rr.scheduled_for>(CASE WHEN s#>>'{rule,kind}'='close_price_group' THEN 600 ELSE 60 END) THEN
   details:=details||jsonb_build_object('gap',jsonb_build_object('from',least(rr.scheduled_for,coalesce((rt.state::jsonb->>'failure_since')::double precision,rr.scheduled_for)),'to',n,'reason_code',CASE WHEN rt.state::jsonb ? 'failure_since' THEN 'data_unavailable' ELSE 'scheduled_check_delayed' END,'historical_prices_replayed',false));
  END IF;
  UPDATE watchlist.runs SET status='succeeded'$new4$);
 IF position($old5$state::jsonb-'calendar_done'-'last_trade_date'-'last_close_price'$old5$ in src)=0 THEN RAISE EXCEPTION 'recovery fragment 5 absent';END IF;
 src:=replace(src,$old5$state::jsonb-'calendar_done'-'last_trade_date'-'last_close_price'$old5$,$new5$state::jsonb-'calendar_done'-'last_trade_date'-'last_close_price'-'failure_count'-'failure_since'$new5$);
 IF position($old6$outcome='{"decision":"superseded"}'$old6$ in src)=0 THEN RAISE EXCEPTION 'recovery fragment 6 absent';END IF;
 src:=replace(src,$old6$outcome='{"decision":"superseded"}'$old6$,$new6$outcome=jsonb_build_object('decision','superseded','run_id',rr.id,'reason_code','lifecycle_or_lease_fence')::text$new6$);
 EXECUTE src;
 src:=pg_get_functiondef('watchlist.product_task_json(text,text)'::regprocedure);
 IF position($old$'calendar',lr.detail::jsonb->'calendar',$old$ in src)=0 THEN RAISE EXCEPTION 'read model fragment absent';END IF;
 src:=replace(src,$old$'calendar',lr.detail::jsonb->'calendar',$old$,$new$'calendar',lr.detail::jsonb->'calendar','gap',lr.detail::jsonb->'gap','retry',lr.detail::jsonb->'retry','recovery',lr.detail::jsonb->'recovery',$new$);
 EXECUTE src;
END $patch$;
INSERT INTO watchlist.schema_version VALUES(13);
COMMIT;
