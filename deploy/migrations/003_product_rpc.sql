-- Product-specific fixed operations. Existing business tables and immutable versions retained.
BEGIN;
SELECT pg_advisory_xact_lock(724102401);
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM watchlist.schema_version WHERE version=1) THEN RAISE EXCEPTION 'watchlist_v1_required'; END IF; END $$;
CREATE FUNCTION watchlist.product_task_json(p_id text,p_owner text) RETURNS jsonb
LANGUAGE sql STABLE SET search_path=pg_catalog AS $$
 SELECT to_jsonb(t)||jsonb_build_object('spec',v.spec::jsonb,'runtime',(to_jsonb(r)-'lease_token')||jsonb_build_object('state',r.state::jsonb,'overdue',t.lifecycle='enabled' AND r.next_run IS NOT NULL AND extract(epoch from statement_timestamp())>r.next_run+greatest(coalesce((v.spec::jsonb#>>'{schedule,interval_seconds}')::int,60),60)), 'instrument',to_jsonb(i),'unread',(SELECT count(*) FROM watchlist.notifications n WHERE n.task_id=t.id AND n.read_at IS NULL))
 FROM watchlist.tasks t JOIN watchlist.rule_versions v ON v.task_id=t.id AND v.version=t.version JOIN watchlist.runtime r ON r.task_id=t.id LEFT JOIN watchlist.instruments i ON i.id=t.instrument_id WHERE t.id=p_id AND t.owner=p_owner AND t.lifecycle<>'deleted'
$$;
REVOKE ALL ON FUNCTION watchlist.product_task_json(text,text) FROM PUBLIC,anon,authenticated;
CREATE FUNCTION public.watchlist_product_v1(p_action text,p_owner text,p_body jsonb DEFAULT '{}'::jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET statement_timeout='5s' SET lock_timeout='3s' AS $$
#variable_conflict use_variable
DECLARE n double precision:=extract(epoch from clock_timestamp()); tid text:=p_body->>'id'; s jsonb:=p_body->'spec'; t watchlist.tasks%ROWTYPE; rt watchlist.runtime%ROWTYPE; rr watchlist.runs%ROWTYPE; out jsonb; due double precision; ver int; st jsonb; life text; rid text; tok text; decision text; details jsonb; k text; cnt int; lim int:=50; offst int:=0;
BEGIN
 IF p_owner IS DISTINCT FROM 'demo' THEN RAISE EXCEPTION 'owner_rejected' USING ERRCODE='42501'; END IF;
 -- Serializes task limit, lifecycle fences, tick keys and completion across workers.
 PERFORM pg_advisory_xact_lock(724102401);
 n:=extract(epoch from clock_timestamp());
 IF p_action='health' THEN RETURN jsonb_build_object('status','ok','storage','postgresql_rpc','server_time',n,'production_validated',false); END IF;
 IF p_action='instruments' THEN SELECT coalesce(jsonb_agg(to_jsonb(x)),'[]') INTO out FROM (SELECT * FROM watchlist.instruments WHERE name LIKE '%'||left(coalesce(p_body->>'q',''),100)||'%' OR code LIKE '%'||left(coalesce(p_body->>'q',''),100)||'%' ORDER BY code LIMIT 30)x; RETURN out; END IF;
 IF p_action='list' THEN SELECT coalesce(jsonb_agg(watchlist.product_task_json(x.id,p_owner)),'[]') INTO out FROM (SELECT id FROM watchlist.tasks WHERE owner=p_owner AND lifecycle<>'deleted' ORDER BY created_at DESC)x; RETURN out; END IF;
 IF p_action='notifications' THEN SELECT coalesce(jsonb_agg(to_jsonb(x)||jsonb_build_object('detail',x.detail::jsonb)),'[]') INTO out FROM (SELECT a.* FROM watchlist.notifications a JOIN watchlist.tasks b ON b.id=a.task_id WHERE b.owner=p_owner ORDER BY a.created_at DESC LIMIT 100)x; RETURN out; END IF;
 IF p_action='read' THEN UPDATE watchlist.notifications a SET read_at=coalesce(read_at,n) FROM watchlist.tasks b WHERE a.task_id=b.id AND b.owner=p_owner AND a.id=tid; IF NOT FOUND THEN RAISE EXCEPTION 'not_found'; END IF; RETURN jsonb_build_object('id',tid,'read',true); END IF;
 IF p_action='parser_audit' THEN INSERT INTO watchlist.parser_audit(at,model,prompt_version,outcome,detail) VALUES(n,'deepseek-flash','watchlist-v1-deno',p_body->>'outcome',(p_body->'detail')::text); RETURN '{}'::jsonb; END IF;
 IF p_action IN ('create','edit') THEN
  IF s IS NULL OR s->>'name' IS NULL OR length(btrim(s->>'name')) NOT BETWEEN 1 AND 100 OR s#>>'{rule,kind}' NOT IN ('calendar_once','price_group') THEN RAISE EXCEPTION 'invalid_spec'; END IF;
  IF s#>>'{rule,kind}'='calendar_once' THEN due:=extract(epoch from (s#>>'{rule,scheduled_at}')::timestamptz); IF due<=n THEN RAISE EXCEPTION 'past_time'; END IF;
  ELSE IF NOT EXISTS(SELECT 1 FROM watchlist.instruments WHERE id=s->>'instrument_id') THEN RAISE EXCEPTION 'instrument_unverified'; END IF; due:=n; END IF;
 END IF;
 IF p_action='create' THEN
  SELECT count(*) INTO cnt FROM watchlist.tasks WHERE owner=p_owner AND lifecycle<>'deleted'; IF cnt>=10 THEN RAISE EXCEPTION 'task_limit'; END IF;
  tid:=replace(gen_random_uuid()::text,'-','');
  INSERT INTO watchlist.tasks VALUES(tid,p_owner,s->>'name',s->>'instrument_id',1,0,'draft',n,n);
  INSERT INTO watchlist.rule_versions VALUES(tid,1,s::text,n,'创建草稿');
  INSERT INTO watchlist.runtime(task_id,state) VALUES(tid,'{"last_result":null,"episode":0,"episode_notified":false,"cooldown_until":0}');
  IF s#>>'{rule,kind}'='calendar_once' THEN INSERT INTO watchlist.calendar_entries VALUES(tid,1,due); END IF;
  INSERT INTO watchlist.audit(task_id,at,action,detail) VALUES(tid,n,'created','{}');
  RETURN watchlist.product_task_json(tid,p_owner);
 END IF;
 IF p_action='claim' THEN
  k:=p_body->>'key'; IF k IS NULL OR k!~'^[A-Za-z0-9:_-]{8,128}$' THEN RAISE EXCEPTION 'invalid_idempotency_key'; END IF;
  INSERT INTO watchlist.ticks(id,started_at) VALUES(k,n) ON CONFLICT DO NOTHING;
  IF NOT FOUND THEN RETURN jsonb_build_object('duplicate',true,'key',k); END IF;
  SELECT a.* INTO t FROM watchlist.tasks a JOIN watchlist.runtime b ON b.task_id=a.id WHERE a.owner=p_owner AND a.lifecycle='enabled' AND b.next_run<=n AND (b.lease_until IS NULL OR b.lease_until<=n) ORDER BY b.next_run,a.id LIMIT 1;
  IF NOT FOUND THEN UPDATE watchlist.ticks SET finished_at=n,outcome='{"processed":0}' WHERE id=k; RETURN jsonb_build_object('processed',0,'key',k); END IF;
  SELECT * INTO rt FROM watchlist.runtime WHERE task_id=t.id;
  UPDATE watchlist.runs SET status='superseded',finished_at=n,decision='superseded' WHERE task_id=t.id AND status='running';
  IF FOUND THEN INSERT INTO watchlist.audit(task_id,at,action,detail) VALUES(t.id,n,'expired_lease_recovered','{}'); END IF;
  rid:=replace(gen_random_uuid()::text,'-',''); tok:=gen_random_uuid()::text;
  INSERT INTO watchlist.runs VALUES(rid,t.id,t.version,t.generation,tok,rt.next_run,n,NULL,'running',NULL,NULL,'{}');
  UPDATE watchlist.runtime SET lease_token=tok,lease_until=n+45 WHERE task_id=t.id;
  RETURN jsonb_build_object('run_id',rid,'token',tok,'key',k,'task_id',t.id,'version',t.version,'lease_until',n+45);
 END IF;
 IF p_action='finish' THEN
  SELECT * INTO rr FROM watchlist.runs WHERE id=p_body->>'run_id';
  IF NOT FOUND THEN RAISE EXCEPTION 'not_found'; END IF;
  SELECT * INTO t FROM watchlist.tasks WHERE id=rr.task_id AND owner=p_owner; IF NOT FOUND THEN RAISE EXCEPTION 'not_found'; END IF;
  SELECT * INTO rt FROM watchlist.runtime WHERE task_id=t.id;
  IF rr.lease_token IS DISTINCT FROM p_body->>'token' THEN RAISE EXCEPTION 'lease_rejected' USING ERRCODE='42501'; END IF;
  IF rr.status<>'running' THEN RETURN jsonb_build_object('duplicate',true,'run_id',rr.id,'decision',rr.decision); END IF;
  IF t.lifecycle<>'enabled' OR t.version<>rr.version OR t.generation<>rr.generation OR rt.lease_token IS DISTINCT FROM rr.lease_token OR rt.lease_until<=n THEN
   UPDATE watchlist.runs SET status='superseded',decision='superseded',finished_at=n WHERE id=rr.id;
   UPDATE watchlist.ticks SET finished_at=n,outcome='{"decision":"superseded"}' WHERE id=p_body->>'key';
   RETURN jsonb_build_object('decision','superseded','run_id',rr.id);
  END IF;
  SELECT spec::jsonb INTO s FROM watchlist.rule_versions WHERE task_id=t.id AND version=t.version;
  st:=rt.state::jsonb;
  IF s#>>'{rule,kind}'='calendar_once' THEN
   due:=extract(epoch from (s#>>'{rule,scheduled_at}')::timestamptz);
   decision:=CASE WHEN n<due THEN 'skipped_not_due' WHEN n-due>86400 THEN 'missed' ELSE 'notify' END;
   details:=jsonb_build_object('result',decision='notify','evaluated_at',n,'decision',decision,'calendar',jsonb_build_object('scheduled_at',due,'actual_at',n,'late_seconds',greatest(0,n-due)),'evidence','[]'::jsonb);
   IF decision<>'skipped_not_due' THEN st:=st||jsonb_build_object('calendar_done',due); END IF;
   UPDATE watchlist.runtime SET next_run=CASE WHEN decision='skipped_not_due' THEN due ELSE NULL END WHERE task_id=t.id;
   IF decision='notify' THEN
    INSERT INTO watchlist.notifications VALUES(replace(gen_random_uuid()::text,'-',''),t.id,rr.id,'calendar:'||t.id||':'||due::text,n,NULL,jsonb_build_object('name',t.name,'evidence',details)::text) ON CONFLICT(dedup_key) DO NOTHING;
    IF NOT FOUND THEN decision:='already_notified'; END IF;
   END IF;
  ELSE
   decision:='insufficient_data';
   SELECT jsonb_agg(jsonb_build_object('condition',c,'result',NULL,'quality','missing','reason_code','quote_time_and_calendar_unverified','observation',jsonb_build_object('instrument_id',t.instrument_id,'field','last_price','value',NULL,'source_time',NULL,'quality','missing'))) INTO out FROM jsonb_array_elements(s#>'{rule,conditions}') c;
   details:=jsonb_build_object('result',NULL,'evaluated_at',n,'decision',decision,'evidence',out,'warnings',jsonb_build_array('交易所行情时间、时效及日历覆盖未核验'),'market',jsonb_build_object('status','unknown','reason_code','calendar_coverage_unverified'));
   UPDATE watchlist.runtime SET next_run=n+(s#>>'{schedule,interval_seconds}')::int WHERE task_id=t.id;
  END IF;
  UPDATE watchlist.runs SET status='succeeded',finished_at=n,result=(details->'result')::text,decision=decision,detail=details::text WHERE id=rr.id;
  INSERT INTO watchlist.evidence(run_id,detail) SELECT rr.id,value::text FROM jsonb_array_elements(details->'evidence');
  IF s#>>'{rule,kind}'='calendar_once' THEN INSERT INTO watchlist.evidence(run_id,detail) VALUES(rr.id,jsonb_build_object('calendar',details->'calendar','result',details->'result')::text); END IF;
  UPDATE watchlist.runtime SET state=st::text,last_checked=n,last_success=CASE WHEN decision='insufficient_data' THEN last_success ELSE n END,health=CASE WHEN decision='insufficient_data' THEN 'degraded' ELSE 'healthy' END,decision=decision,lease_token=NULL,lease_until=NULL WHERE task_id=t.id;
  UPDATE watchlist.ticks SET finished_at=n,outcome=jsonb_build_object('processed',1,'run_id',rr.id,'decision',decision)::text WHERE id=p_body->>'key';
  RETURN jsonb_build_object('processed',1,'run_id',rr.id,'task_id',t.id,'decision',decision);
 END IF;
 -- All remaining operations require an owned, nondeleted task.
 SELECT * INTO t FROM watchlist.tasks WHERE id=tid AND owner=p_owner AND lifecycle<>'deleted';
 IF NOT FOUND THEN RAISE EXCEPTION 'not_found'; END IF;
 IF p_action='get' THEN RETURN watchlist.product_task_json(tid,p_owner); END IF;
 IF p_action IN ('runs','versions','audit') THEN
  lim:=least(100,greatest(1,coalesce((p_body->>'limit')::int,50))); offst:=greatest(0,coalesce((p_body->>'offset')::int,0));
  IF p_action='runs' THEN SELECT coalesce(jsonb_agg((to_jsonb(x)-'lease_token')||jsonb_build_object('detail',x.detail::jsonb,'result',x.result::jsonb,'evidence',coalesce((SELECT jsonb_agg(e.detail::jsonb) FROM watchlist.evidence e WHERE e.run_id=x.id AND e.detail::jsonb ? 'condition'),'[]'::jsonb))),'[]') INTO out FROM (SELECT * FROM watchlist.runs WHERE task_id=tid ORDER BY started_at DESC LIMIT lim OFFSET offst)x;
  ELSIF p_action='versions' THEN SELECT coalesce(jsonb_agg(to_jsonb(x)||jsonb_build_object('spec',x.spec::jsonb)),'[]') INTO out FROM (SELECT * FROM watchlist.rule_versions WHERE task_id=tid ORDER BY version DESC LIMIT lim OFFSET offst)x;
  ELSE SELECT coalesce(jsonb_agg(to_jsonb(x)||jsonb_build_object('detail',x.detail::jsonb)),'[]') INTO out FROM (SELECT * FROM watchlist.audit WHERE task_id=tid ORDER BY at DESC LIMIT lim OFFSET offst)x; END IF; RETURN out;
 END IF;
 SELECT * INTO rt FROM watchlist.runtime WHERE task_id=tid;
 IF p_action IN ('edit','activate','resume') AND (p_body->>'expected_version')::int IS DISTINCT FROM t.version THEN RAISE EXCEPTION 'version_conflict'; END IF;
 IF p_action='edit' THEN
  ver:=t.version+1;
  INSERT INTO watchlist.rule_versions VALUES(tid,ver,s::text,n,'规则已修改；重置事件段，保留冷却。');
  IF s#>>'{rule,kind}'='calendar_once' THEN INSERT INTO watchlist.calendar_entries VALUES(tid,ver,due); END IF;
  UPDATE watchlist.tasks SET name=s->>'name',instrument_id=s->>'instrument_id',version=ver,generation=generation+1,updated_at=n WHERE id=tid;
  UPDATE watchlist.runtime SET state=((state::jsonb-'calendar_done')||'{"last_result":null,"episode_notified":false}'::jsonb)::text,next_run=CASE WHEN t.lifecycle='enabled' THEN due ELSE NULL END,lease_token=NULL,lease_until=NULL,health='pending',decision=NULL WHERE task_id=tid;
 ELSE
  SELECT spec::jsonb INTO s FROM watchlist.rule_versions WHERE task_id=tid AND version=t.version;
  IF p_action='activate' AND t.lifecycle='draft' THEN life:='enabled';
  ELSIF p_action='resume' AND t.lifecycle='paused' THEN life:='enabled';
  ELSIF p_action='pause' AND t.lifecycle IN ('enabled','paused') THEN life:='paused';
  ELSIF p_action='delete' THEN life:='deleted'; ELSE RAISE EXCEPTION 'invalid_lifecycle'; END IF;
  due:=CASE WHEN s#>>'{rule,kind}'='calendar_once' THEN extract(epoch from (s#>>'{rule,scheduled_at}')::timestamptz) ELSE n END;
  IF p_action='activate' AND due<n AND s#>>'{rule,kind}'='calendar_once' THEN RAISE EXCEPTION 'past_time'; END IF;
  IF life<>'enabled' OR (rt.state::jsonb->>'calendar_done')::double precision=due THEN due:=NULL; END IF;
  UPDATE watchlist.tasks SET lifecycle=life,generation=generation+1,updated_at=n WHERE id=tid;
  UPDATE watchlist.runtime SET next_run=due,lease_token=NULL,lease_until=NULL,pause_at=CASE WHEN life='paused' THEN n ELSE NULL END WHERE task_id=tid;
 END IF;
 INSERT INTO watchlist.audit(task_id,at,action,detail) VALUES(tid,n,p_action,jsonb_build_object('from_version',t.version,'gap_from',CASE WHEN p_action='resume' THEN rt.pause_at ELSE NULL END,'gap_to',CASE WHEN p_action='resume' THEN n ELSE NULL END,'historical_prices_replayed',false)::text);
 IF p_action='delete' THEN RETURN jsonb_build_object('id',tid,'lifecycle','deleted'); END IF;
 RETURN watchlist.product_task_json(tid,p_owner);
END $$;
REVOKE ALL ON FUNCTION public.watchlist_product_v1(text,text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.watchlist_product_v1(text,text,jsonb) TO service_role;
INSERT INTO watchlist.schema_version VALUES(3);
NOTIFY pgrst,'reload schema';
COMMIT;
