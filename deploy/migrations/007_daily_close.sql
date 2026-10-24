-- Daily close is a new explicit rule kind; existing immutable rules are not rewritten.
BEGIN;
SELECT pg_advisory_xact_lock(724102401);
CREATE TABLE watchlist.close_cache(key text PRIMARY KEY,value jsonb,expires double precision NOT NULL DEFAULT 0,token text,lease_until double precision);
CREATE TABLE watchlist.close_records(instrument_id text REFERENCES watchlist.instruments(id),trade_date date,value text NOT NULL,first_seen double precision NOT NULL,conflict boolean NOT NULL DEFAULT false,PRIMARY KEY(instrument_id,trade_date));
REVOKE ALL ON watchlist.close_cache,watchlist.close_records FROM PUBLIC,anon,authenticated;
CREATE FUNCTION watchlist.close_transition(s jsonb,result boolean,n double precision,cooldown integer) RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$
DECLARE decision text; episode integer:=coalesce((s->>'episode')::integer,0);
BEGIN
 IF result IS NULL THEN decision:='insufficient_data';
 ELSIF NOT result THEN s:=s||'{"last_result":false,"episode_notified":false}'::jsonb;decision:='no_match';
 ELSE
  IF (s->>'last_result')::boolean IS DISTINCT FROM true THEN episode:=episode+1;s:=s||jsonb_build_object('episode',episode,'episode_notified',false); END IF;
  s:=s||'{"last_result":true}'::jsonb;
  IF coalesce((s->>'episode_notified')::boolean,false) THEN decision:='already_notified';
  ELSIF n<coalesce((s->>'cooldown_until')::double precision,0) THEN decision:='cooldown_suppressed';
  ELSE decision:='notify';s:=s||jsonb_build_object('episode_notified',true,'cooldown_until',n+cooldown);END IF;
 END IF;
 RETURN jsonb_build_object('state',s,'decision',decision);
END $$;
REVOKE ALL ON FUNCTION watchlist.close_transition(jsonb,boolean,double precision,integer) FROM PUBLIC,anon,authenticated;
CREATE OR REPLACE FUNCTION watchlist.product_task_json(p_id text,p_owner text) RETURNS jsonb
LANGUAGE sql STABLE SET search_path=pg_catalog AS $$
 SELECT to_jsonb(t)||jsonb_build_object('spec',v.spec::jsonb,'runtime',(to_jsonb(r)-'lease_token')||jsonb_build_object('state',r.state::jsonb,'overdue',t.lifecycle='enabled' AND r.next_run IS NOT NULL AND extract(epoch from statement_timestamp())>r.next_run+greatest(coalesce((v.spec::jsonb#>>'{schedule,interval_seconds}')::int,60),60)), 'instrument',to_jsonb(i),'unread',(SELECT count(*) FROM watchlist.notifications n WHERE n.task_id=t.id AND n.read_at IS NULL))
 FROM watchlist.tasks t JOIN watchlist.rule_versions v ON v.task_id=t.id AND v.version=t.version JOIN watchlist.runtime r ON r.task_id=t.id LEFT JOIN watchlist.instruments i ON i.id=t.instrument_id WHERE t.id=p_id AND t.owner=p_owner
$$;
REVOKE ALL ON FUNCTION watchlist.product_task_json(text,text) FROM PUBLIC,anon,authenticated;
CREATE OR REPLACE FUNCTION public.watchlist_product_v1(p_action text,p_owner text,p_body jsonb DEFAULT '{}'::jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET statement_timeout='5s' SET lock_timeout='3s' AS $$
#variable_conflict use_variable
DECLARE n double precision:=extract(epoch from clock_timestamp()); tid text:=p_body->>'id'; s jsonb:=p_body->'spec'; t watchlist.tasks%ROWTYPE; rt watchlist.runtime%ROWTYPE; rr watchlist.runs%ROWTYPE; out jsonb; due double precision; ver int; st jsonb; life text; rid text; tok text; decision text; details jsonb; k text; cnt int; lim int:=50; offst int:=0; ob jsonb; ev jsonb; trans jsonb; valid_result boolean; bar_conflict boolean; next_check double precision;
BEGIN
 IF p_owner IS DISTINCT FROM 'demo' THEN RAISE EXCEPTION 'owner_rejected' USING ERRCODE='42501'; END IF;
 -- Serializes task limit, lifecycle fences, tick keys and completion across workers.
 PERFORM pg_advisory_xact_lock(724102401);
 n:=extract(epoch from clock_timestamp());
 IF p_action='health' THEN RETURN jsonb_build_object('status','ok','storage','postgresql_rpc','server_time',n,'production_validated',false); END IF;
 IF p_action='instrument_import' THEN
  FOR ob IN SELECT value FROM jsonb_array_elements(p_body->'items') LOOP
   IF ob->>'id' IS DISTINCT FROM 'CN.SH.'||(ob->>'code') OR ob->>'code' !~ '^6[0-9]{5}$' OR ob->>'market' IS DISTINCT FROM 'SH' OR ob->>'currency' IS DISTINCT FROM 'CNY' OR ob->>'asset_class' IS DISTINCT FROM 'stock' OR length(ob->>'name') NOT BETWEEN 1 AND 100 OR (ob->>'provenance')::jsonb->>'provider' IS DISTINCT FROM 'fuyao' THEN RAISE EXCEPTION 'instrument_unverified'; END IF;
   INSERT INTO watchlist.instruments VALUES(ob->>'id','SH',ob->>'code',ob->>'name','stock','CNY',ob->>'provenance') ON CONFLICT(id) DO UPDATE SET name=EXCLUDED.name,provenance=EXCLUDED.provenance;
  END LOOP;
  RETURN p_body->'items';
 END IF;
 IF p_action IN ('close_cache_get','close_cache_put') THEN
  k:=p_body->>'key';IF k !~ '^CN.SH.6[0-9]{5}:[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN RAISE EXCEPTION 'invalid_cache_key';END IF;
  IF p_action='close_cache_get' THEN
   SELECT value INTO out FROM watchlist.close_cache WHERE key=k AND expires>n;
   IF FOUND THEN RETURN jsonb_build_object('value',out); END IF;
   IF EXISTS(SELECT 1 FROM watchlist.close_cache WHERE key=k AND lease_until>n) THEN RETURN '{"busy":true}'::jsonb; END IF;
   tok:=gen_random_uuid()::text;INSERT INTO watchlist.close_cache(key,token,lease_until) VALUES(k,tok,n+30) ON CONFLICT(key) DO UPDATE SET token=EXCLUDED.token,lease_until=EXCLUDED.lease_until;
   RETURN jsonb_build_object('token',tok);
  ELSE
   UPDATE watchlist.close_cache SET value=p_body->'value',expires=least(n+86400,greatest(n+1,(p_body->>'expires')::double precision)),token=NULL,lease_until=NULL WHERE key=k AND token=p_body->>'token' AND lease_until>n;
   IF NOT FOUND THEN RAISE EXCEPTION 'lease_rejected';END IF; RETURN '{}'::jsonb;
  END IF;
 END IF;
 IF p_action='instruments' THEN SELECT coalesce(jsonb_agg(to_jsonb(x)),'[]') INTO out FROM (SELECT * FROM watchlist.instruments WHERE name LIKE '%'||left(coalesce(p_body->>'q',''),100)||'%' OR code LIKE '%'||left(coalesce(p_body->>'q',''),100)||'%' ORDER BY code LIMIT 30)x; RETURN out; END IF;
 IF p_action='list' THEN SELECT coalesce(jsonb_agg(watchlist.product_task_json(x.id,p_owner)),'[]') INTO out FROM (SELECT id FROM watchlist.tasks WHERE owner=p_owner AND lifecycle<>'deleted' ORDER BY created_at DESC)x; RETURN out; END IF;
 IF p_action='notifications' THEN SELECT coalesce(jsonb_agg(to_jsonb(x)||jsonb_build_object('detail',x.detail::jsonb)),'[]') INTO out FROM (SELECT a.* FROM watchlist.notifications a JOIN watchlist.tasks b ON b.id=a.task_id WHERE b.owner=p_owner ORDER BY a.created_at DESC LIMIT 100)x; RETURN out; END IF;
 IF p_action='read' THEN UPDATE watchlist.notifications a SET read_at=coalesce(read_at,n) FROM watchlist.tasks b WHERE a.task_id=b.id AND b.owner=p_owner AND a.id=tid; IF NOT FOUND THEN RAISE EXCEPTION 'not_found'; END IF; RETURN jsonb_build_object('id',tid,'read',true); END IF;
 IF p_action='parser_audit' THEN INSERT INTO watchlist.parser_audit(at,model,prompt_version,outcome,detail) VALUES(n,'deepseek-flash','watchlist-v1-deno',p_body->>'outcome',(p_body->'detail')::text); RETURN '{}'::jsonb; END IF;
 IF p_action IN ('create','edit') THEN
  IF s IS NULL OR s->>'name' IS NULL OR length(btrim(s->>'name')) NOT BETWEEN 1 AND 100 OR s#>>'{rule,kind}' NOT IN ('calendar_once','price_group','close_price_group') THEN RAISE EXCEPTION 'invalid_spec'; END IF;
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
  SELECT a.* INTO t FROM watchlist.tasks a JOIN watchlist.runtime b ON b.task_id=a.id WHERE a.owner=p_owner AND a.lifecycle='enabled' AND b.next_run<=n AND (b.lease_until IS NULL OR b.lease_until<=n) ORDER BY CASE WHEN EXISTS(SELECT 1 FROM watchlist.calendar_entries ce WHERE ce.task_id=a.id AND ce.version=a.version) THEN 0 ELSE 1 END,b.next_run,a.id LIMIT 1;
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
  ELSIF s#>>'{rule,kind}'='close_price_group' THEN
   details:=p_body->'evaluation';
   IF details->>'mapping_version' IS DISTINCT FROM 'fuyao-daily-close-v1' OR jsonb_array_length(details->'evidence') IS DISTINCT FROM jsonb_array_length(s#>'{rule,conditions}') THEN RAISE EXCEPTION 'invalid_close_evaluation'; END IF;
   out:='[]'::jsonb;
   FOR ev IN SELECT value FROM jsonb_array_elements(details->'evidence') LOOP
    IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(s#>'{rule,conditions}') c WHERE c=ev->'condition') THEN RAISE EXCEPTION 'invalid_close_condition';END IF;
    ob:=ev->'observation';
    IF ob->>'instrument_id' IS DISTINCT FROM t.instrument_id OR ob->>'field' IS DISTINCT FROM 'close_price' OR ob->>'unit' IS DISTINCT FROM 'CNY' OR ob->>'adjust' IS DISTINCT FROM 'none' OR ob->>'provider' IS DISTINCT FROM 'fuyao' OR ob->>'source_time' IS NOT NULL OR ob->>'mapping_version' IS DISTINCT FROM 'fuyao-daily-close-v1' THEN RAISE EXCEPTION 'invalid_observation';END IF;
    IF ob->>'quality'='valid' THEN
     IF (ob->>'value')::numeric<=0 OR ob->>'trade_date' IS DISTINCT FROM details#>>'{market,expected_trade_date}' OR (ob->>'trade_date')::date > (to_timestamp(n) AT TIME ZONE 'Asia/Shanghai')::date THEN RAISE EXCEPTION 'invalid_close_bar';END IF;
     INSERT INTO watchlist.close_records VALUES(t.instrument_id,(ob->>'trade_date')::date,ob->>'value',n,false) ON CONFLICT DO NOTHING;
     UPDATE watchlist.close_records SET conflict=true WHERE instrument_id=t.instrument_id AND trade_date=(ob->>'trade_date')::date AND value::numeric<>(ob->>'value')::numeric;
     SELECT conflict INTO bar_conflict FROM watchlist.close_records WHERE instrument_id=t.instrument_id AND trade_date=(ob->>'trade_date')::date;
     IF bar_conflict OR (st->>'last_trade_date')>(ob->>'trade_date') OR (details->>'valid_until')::double precision<=n THEN
      ob:=ob||jsonb_build_object('quality','conflict','reason_code',CASE WHEN bar_conflict THEN 'same_day_correction_conflict' WHEN (st->>'last_trade_date')>(ob->>'trade_date') THEN 'trade_date_regression' ELSE 'completed_day_changed' END);
      ev:=ev||jsonb_build_object('result',NULL,'quality','conflict','reason_code',ob->>'reason_code');
     ELSE
      valid_result:=CASE WHEN ev#>>'{condition,operator}'='gt' THEN (ob->>'value')::numeric>(ev#>>'{condition,value}')::numeric ELSE (ob->>'value')::numeric<(ev#>>'{condition,value}')::numeric END;
      IF ev->'result' IS DISTINCT FROM to_jsonb(valid_result) THEN RAISE EXCEPTION 'comparison_mismatch';END IF;
     END IF;
    ELSE ev:=ev||jsonb_build_object('result',NULL); END IF;
    tok:=replace(gen_random_uuid()::text,'-','');
    INSERT INTO watchlist.observations(id,instrument_id,field,value,unit,source_time,fetched_at,provider,source_ref,quality,reason_code) VALUES(tok,t.instrument_id,'close_price',ob->>'value','CNY',NULL,ob->>'fetched_at','fuyao',ob->>'source_ref',ob->>'quality',ob->>'reason_code');
    out:=out||jsonb_build_array(ev||jsonb_build_object('observation',ob,'observation_id',tok));
   END LOOP;
   IF s#>>'{rule,combinator}'='all' THEN
    valid_result:=CASE WHEN EXISTS(SELECT 1 FROM jsonb_array_elements(out) e WHERE e->>'result'='false') THEN false WHEN EXISTS(SELECT 1 FROM jsonb_array_elements(out) e WHERE e->>'result' IS NULL) THEN NULL ELSE true END;
   ELSE
    valid_result:=CASE WHEN EXISTS(SELECT 1 FROM jsonb_array_elements(out) e WHERE e->>'result'='true') THEN true WHEN EXISTS(SELECT 1 FROM jsonb_array_elements(out) e WHERE e->>'result' IS NULL) THEN NULL ELSE false END;
   END IF;
   trans:=watchlist.close_transition(st,valid_result,n,(s#>>'{notification_policy,cooldown_seconds}')::int);st:=trans->'state';decision:=trans->>'decision';
   IF valid_result IS NOT NULL THEN st:=st||jsonb_build_object('last_trade_date',out#>>'{0,observation,trade_date}','last_close_price',out#>>'{0,observation,value}');END IF;
   details:=details||jsonb_build_object('result',valid_result,'decision',decision,'evidence',out,'evaluated_at',n);
   next_check:=CASE WHEN valid_result IS NULL THEN n+900 ELSE greatest(n+60,least(n+86400,(details->>'next_check')::double precision)) END;
   IF decision='cooldown_suppressed' THEN next_check:=least(next_check,greatest(n+60,(st->>'cooldown_until')::double precision)); END IF;
   UPDATE watchlist.runtime SET next_run=next_check WHERE task_id=t.id;
   IF decision='notify' THEN
    INSERT INTO watchlist.notifications VALUES(replace(gen_random_uuid()::text,'-',''),t.id,rr.id,'close:'||t.id||':'||t.version||':'||(st->>'episode'),n,NULL,jsonb_build_object('name',t.name,'trade_date',st->>'last_trade_date','basis','日收盘价 / 不复权 / CNY / 首次已满足也会提醒','evidence',details)::text) ON CONFLICT(dedup_key) DO NOTHING;
    IF NOT FOUND THEN decision:='already_notified'; END IF;
   END IF;
  ELSE
   decision:='insufficient_data';
   SELECT jsonb_agg(jsonb_build_object('condition',c,'result',NULL,'quality','missing','reason_code','quote_time_and_calendar_unverified','observation',jsonb_build_object('instrument_id',t.instrument_id,'field','last_price','value',NULL,'source_time',NULL,'quality','missing'))) INTO out FROM jsonb_array_elements(s#>'{rule,conditions}') c;
   details:=jsonb_build_object('result',NULL,'evaluated_at',n,'decision',decision,'evidence',out,'warnings',jsonb_build_array('交易所行情时间、时效及日历覆盖未核验'),'market',jsonb_build_object('status','unknown','reason_code','calendar_coverage_unverified'));
   IF p_body#>>'{evaluation,decision}'='insufficient_data' AND jsonb_typeof(p_body#>'{evaluation,evidence}')='array' THEN
    -- Only unavailable observations may be persisted in this version. Never promote supplied results.
    out:='[]'::jsonb;
    FOR k IN SELECT value->>'id' FROM jsonb_array_elements(s#>'{rule,conditions}') LOOP
     SELECT value INTO st FROM jsonb_array_elements(p_body#>'{evaluation,evidence}') WHERE value#>>'{condition,id}'=k LIMIT 1;
     IF st#>>'{observation,instrument_id}' IS DISTINCT FROM t.instrument_id OR st#>>'{observation,provider}' IS DISTINCT FROM 'fuyao' OR st#>>'{observation,source_time}' IS NOT NULL THEN RAISE EXCEPTION 'invalid_observation'; END IF;
     st:=st||jsonb_build_object('result',NULL);
     tok:=replace(gen_random_uuid()::text,'-','');
     INSERT INTO watchlist.observations(id,instrument_id,field,value,unit,source_time,fetched_at,provider,source_ref,quality,reason_code)
     VALUES(tok,t.instrument_id,'last_price',st#>>'{observation,value}','CNY',NULL,st#>>'{observation,fetched_at}','fuyao',st#>>'{observation,source_ref}',coalesce(st#>>'{observation,quality}','missing'),st#>>'{observation,reason_code}');
     st:=st||jsonb_build_object('observation_id',tok);out:=out||jsonb_build_array(st);
    END LOOP;
    details:=details||jsonb_build_object('evidence',out,'market',(p_body#>'{evaluation,market}')||jsonb_build_object('status','unknown'),'warnings',p_body#>'{evaluation,warnings}');
    st:=rt.state::jsonb;
   END IF;
   UPDATE watchlist.runtime SET next_run=n+(s#>>'{schedule,interval_seconds}')::int WHERE task_id=t.id;
  END IF;
  UPDATE watchlist.runs SET status='succeeded',finished_at=n,result=(details->'result')::text,decision=decision,detail=details::text WHERE id=rr.id;
  INSERT INTO watchlist.evidence(run_id,observation_id,detail) SELECT rr.id,value->>'observation_id',value::text FROM jsonb_array_elements(details->'evidence');
  IF s#>>'{rule,kind}'='calendar_once' THEN INSERT INTO watchlist.evidence(run_id,detail) VALUES(rr.id,jsonb_build_object('calendar',details->'calendar','result',details->'result')::text); END IF;
  UPDATE watchlist.runtime SET state=st::text,last_checked=n,last_success=CASE WHEN decision='insufficient_data' THEN last_success ELSE n END,health=CASE WHEN decision='insufficient_data' THEN 'degraded' ELSE 'healthy' END,decision=decision,lease_token=NULL,lease_until=NULL WHERE task_id=t.id;
  UPDATE watchlist.ticks SET finished_at=n,outcome=jsonb_build_object('processed',1,'run_id',rr.id,'decision',decision)::text WHERE id=p_body->>'key';
  RETURN jsonb_build_object('processed',1,'run_id',rr.id,'task_id',t.id,'decision',decision);
 END IF;
 -- All remaining operations require an owned, nondeleted task.
 SELECT * INTO t FROM watchlist.tasks WHERE id=tid AND owner=p_owner;
 IF NOT FOUND THEN RAISE EXCEPTION 'not_found'; END IF;
 IF p_action='get' THEN RETURN watchlist.product_task_json(tid,p_owner); END IF;
 IF p_action IN ('runs','versions','audit') THEN
  lim:=least(100,greatest(1,coalesce((p_body->>'limit')::int,50))); offst:=greatest(0,coalesce((p_body->>'offset')::int,0));
  IF p_action='runs' THEN SELECT coalesce(jsonb_agg((to_jsonb(x)-'lease_token')||jsonb_build_object('detail',x.detail::jsonb,'result',x.result::jsonb,'evidence',coalesce((SELECT jsonb_agg(e.detail::jsonb) FROM watchlist.evidence e WHERE e.run_id=x.id AND e.detail::jsonb ? 'condition'),'[]'::jsonb))),'[]') INTO out FROM (SELECT * FROM watchlist.runs WHERE task_id=tid ORDER BY started_at DESC LIMIT lim OFFSET offst)x;
  ELSIF p_action='versions' THEN SELECT coalesce(jsonb_agg(to_jsonb(x)||jsonb_build_object('spec',x.spec::jsonb)),'[]') INTO out FROM (SELECT * FROM watchlist.rule_versions WHERE task_id=tid ORDER BY version DESC LIMIT lim OFFSET offst)x;
  ELSE SELECT coalesce(jsonb_agg(to_jsonb(x)||jsonb_build_object('detail',x.detail::jsonb)),'[]') INTO out FROM (SELECT * FROM watchlist.audit WHERE task_id=tid ORDER BY at DESC LIMIT lim OFFSET offst)x; END IF; RETURN out;
 END IF;
 IF t.lifecycle='deleted' THEN RAISE EXCEPTION 'invalid_lifecycle';END IF;
 SELECT * INTO rt FROM watchlist.runtime WHERE task_id=tid;
 IF p_action IN ('edit','activate','resume') AND (p_body->>'expected_version')::int IS DISTINCT FROM t.version THEN RAISE EXCEPTION 'version_conflict'; END IF;
 IF p_action='edit' THEN
  ver:=t.version+1;
  INSERT INTO watchlist.rule_versions VALUES(tid,ver,s::text,n,'规则已修改；重置事件段，保留冷却。');
  IF s#>>'{rule,kind}'='calendar_once' THEN INSERT INTO watchlist.calendar_entries VALUES(tid,ver,due); END IF;
  UPDATE watchlist.tasks SET name=s->>'name',instrument_id=s->>'instrument_id',version=ver,generation=generation+1,updated_at=n WHERE id=tid;
  UPDATE watchlist.runtime SET state=((state::jsonb-'calendar_done'-'last_trade_date'-'last_close_price')||'{"last_result":null,"episode_notified":false}'::jsonb)::text,next_run=CASE WHEN t.lifecycle='enabled' THEN due ELSE NULL END,lease_token=NULL,lease_until=NULL,health='pending',decision=NULL WHERE task_id=tid;
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
INSERT INTO watchlist.schema_version VALUES(7);
NOTIFY pgrst,'reload schema';
COMMIT;
