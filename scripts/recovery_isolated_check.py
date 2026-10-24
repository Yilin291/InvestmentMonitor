"""Build target PostgreSQL TEST-only regression; all mutations rollback, no synthetic production evidence."""
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--candidate',action='store_true');a=p.parse_args()
s=Path('deploy/migrations/013_monitor_recovery.sql').read_text().rsplit('COMMIT;',1)[0] if a.candidate else 'BEGIN;\n'
s+='CREATE SCHEMA watchlist_recovery_test;\n'
for t in ['instruments','tasks','rule_versions','runtime','runs','observations','events','calendar_entries','evidence','notifications','audit','parser_audit','ticks','close_cache','close_records']:
 s+=f'CREATE TABLE watchlist_recovery_test.{t} (LIKE watchlist.{t} INCLUDING ALL);\n'
s+='INSERT INTO watchlist_recovery_test.instruments SELECT * FROM watchlist.instruments;\n'
s+="""DO $$DECLARE src text;sig text;BEGIN
 FOREACH sig IN ARRAY ARRAY['watchlist.close_transition(jsonb,boolean,double precision,integer)','watchlist.product_task_json(text,text)','public.watchlist_product_v1(text,text,jsonb)'] LOOP
  src:=pg_get_functiondef(sig::regprocedure);src:=replace(src,'watchlist.','watchlist_recovery_test.');src:=replace(src,'public.watchlist_product_v1','watchlist_recovery_test.product_rpc');EXECUTE src;
 END LOOP;
END $$;
"""
s+=Path('tests/fixtures/recovery_price.sql').read_text()
s+=r'''
DO $$
#variable_conflict use_variable
DECLARE s jsonb:='{"name":"TEST recovery synthetic daily close","instrument_id":"CN.SH.600519","rule":{"kind":"close_price_group","combinator":"all","conditions":[{"id":"p1","field":"close_price","operator":"lt","value":"110","currency":"CNY"}]},"schedule":{"mode":"daily_close","timezone":"Asia/Shanghai","interval_seconds":86400},"notification_policy":{"mode":"on_episode","cooldown_seconds":86400}}';t jsonb;x jsonb;c jsonb;d jsonb;id text;before_state jsonb;num int;idx int;delay double precision;old_run text;old_key text;n double precision:=extract(epoch from clock_timestamp());
BEGIN
 t:=watchlist_recovery_test.product_rpc('create','demo',jsonb_build_object('spec',s));id:=t->>'id';
 PERFORM watchlist_recovery_test.product_rpc('activate','demo',jsonb_build_object('id',id,'expected_version',1));
 x:=watchlist_recovery_test.check_price(id,'2026-10-23','100','valid','TEST-recovery-true');IF x->>'decision'<>'notify' THEN RAISE EXCEPTION 'first notify';END IF;
 SELECT state::jsonb INTO before_state FROM watchlist_recovery_test.runtime WHERE task_id=id;
 FOR idx IN 1..4 LOOP
  x:=watchlist_recovery_test.check_price(id,'2026-10-23',NULL,'missing','TEST-recovery-fail-'||idx);
  IF x->>'decision'<>'insufficient_data' THEN RAISE EXCEPTION 'unknown incorrectly false';END IF;
  SELECT state::jsonb,next_run-last_checked INTO c,delay FROM watchlist_recovery_test.runtime WHERE task_id=id;
  IF (c-'failure_count'-'failure_since')<>before_state OR (c->>'failure_count')::int<>idx THEN RAISE EXCEPTION 'episode state changed or failure count wrong';END IF;
  IF abs(delay-least(3600,900*power(2,idx-1)))>0.1 THEN RAISE EXCEPTION 'backoff wrong %',delay;END IF;
 END LOOP;
 x:=watchlist_recovery_test.check_price(id,'2026-10-23','100','valid','TEST-recovery-restored');IF x->>'decision'<>'already_notified' THEN RAISE EXCEPTION 'duplicate on recovery';END IF;
 c:=watchlist_recovery_test.product_rpc('get','demo',jsonb_build_object('id',id));
 IF c#>>'{last_evaluation,recovery,previous_failures}'<>'4' OR c#>>'{last_evaluation,gap,historical_prices_replayed}'<>'false' OR c#>'{runtime,state}' ? 'failure_count' THEN RAISE EXCEPTION 'recovery evidence missing';END IF;
 SELECT count(*) INTO num FROM watchlist_recovery_test.notifications WHERE task_id=id;IF num<>1 THEN RAISE EXCEPTION 'duplicate notification';END IF;
 UPDATE watchlist_recovery_test.runtime SET next_run=n-1200 WHERE task_id=id;
 c:=watchlist_recovery_test.product_rpc('claim','demo','{"key":"TEST-recovery-abandon"}');old_run:=c->>'run_id';
 IF NOT EXISTS(SELECT 1 FROM watchlist_recovery_test.ticks tk WHERE tk.id='TEST-recovery-abandon' AND outcome::jsonb->>'run_id'=old_run) THEN RAISE EXCEPTION 'missing tick/run link';END IF;
 x:=watchlist_recovery_test.product_rpc('claim','demo','{"key":"TEST-recovery-abandon"}');IF x->>'duplicate'<>'true' THEN RAISE EXCEPTION 'claim replay not duplicate';END IF;
 x:=watchlist_recovery_test.product_rpc('claim','demo','{"key":"TEST-recovery-competing"}');IF x ? 'run_id' THEN RAISE EXCEPTION 'active lease claimed twice';END IF;
 UPDATE watchlist_recovery_test.runtime SET lease_until=n-1 WHERE task_id=id;
 d:=watchlist_recovery_test.product_rpc('claim','demo','{"key":"TEST-recovery-reclaim"}');
 IF NOT EXISTS(SELECT 1 FROM watchlist_recovery_test.ticks tk WHERE tk.id='TEST-recovery-abandon' AND finished_at IS NOT NULL AND outcome::jsonb->>'reason_code'='expired_lease_recovered') THEN RAISE EXCEPTION 'dangling abandoned tick';END IF;
 x:=watchlist_recovery_test.product_rpc('finish','demo',c);IF x->>'decision'<>'superseded' THEN RAISE EXCEPTION 'old execution not fenced';END IF;
 BEGIN
  PERFORM watchlist_recovery_test.product_rpc('finish','demo',d||'{"key":"TEST-recovery-abandon"}'::jsonb);RAISE EXCEPTION 'wrong key accepted';
 EXCEPTION WHEN OTHERS THEN IF SQLERRM<>'lease_rejected' THEN RAISE;END IF;END;
 PERFORM watchlist_recovery_test.product_rpc('pause','demo',jsonb_build_object('id',id));x:=watchlist_recovery_test.product_rpc('finish','demo',d);
 IF x->>'decision'<>'superseded' THEN RAISE EXCEPTION 'pause in flight not fenced';END IF;
 PERFORM watchlist_recovery_test.product_rpc('resume','demo',jsonb_build_object('id',id,'expected_version',1));
 c:=watchlist_recovery_test.product_rpc('claim','demo','{"key":"TEST-recovery-edit"}');
 PERFORM watchlist_recovery_test.product_rpc('edit','demo',jsonb_build_object('id',id,'expected_version',1,'spec',s));x:=watchlist_recovery_test.product_rpc('finish','demo',c);IF x->>'decision'<>'superseded' THEN RAISE EXCEPTION 'edit in flight not fenced';END IF;
 PERFORM watchlist_recovery_test.product_rpc('pause','demo',jsonb_build_object('id',id));
 -- Isolated TEST calendar checks: real DB clock, synthetic overdue state only in rollback schema.
 s:=jsonb_build_object('name','TEST overdue calendar','instrument_id',NULL,'rule',jsonb_build_object('kind','calendar_once','scheduled_at',to_timestamp(n+3600)),'schedule',jsonb_build_object('mode','once','timezone','Asia/Shanghai'),'notification_policy',jsonb_build_object('mode','on_episode','cooldown_seconds',86400));
 t:=watchlist_recovery_test.product_rpc('create','demo',jsonb_build_object('spec',s));id:=t->>'id';PERFORM watchlist_recovery_test.product_rpc('activate','demo',jsonb_build_object('id',id,'expected_version',1));
 UPDATE watchlist_recovery_test.rule_versions SET spec=jsonb_set(spec::jsonb,'{rule,scheduled_at}',to_jsonb(to_timestamp(n-120)))::text WHERE task_id=id;
 UPDATE watchlist_recovery_test.runtime SET next_run=n-120 WHERE task_id=id;
 c:=watchlist_recovery_test.product_rpc('claim','demo','{"key":"TEST-calendar-late"}');x:=watchlist_recovery_test.product_rpc('finish','demo',c);IF x->>'decision'<>'notify' THEN RAISE EXCEPTION 'late calendar failed';END IF;
 d:=watchlist_recovery_test.product_rpc('get','demo',jsonb_build_object('id',id));IF d#>>'{last_evaluation,gap,reason_code}'<>'scheduled_check_delayed' THEN RAISE EXCEPTION 'late gap missing';END IF;
 x:=watchlist_recovery_test.product_rpc('finish','demo',c);IF x->>'duplicate'<>'true' THEN RAISE EXCEPTION 'repeat finish not idempotent';END IF;
 PERFORM watchlist_recovery_test.product_rpc('pause','demo',jsonb_build_object('id',id));PERFORM watchlist_recovery_test.product_rpc('resume','demo',jsonb_build_object('id',id,'expected_version',1));
 IF (SELECT next_run FROM watchlist_recovery_test.runtime WHERE task_id=id) IS NOT NULL THEN RAISE EXCEPTION 'completed calendar rescheduled';END IF;
 UPDATE watchlist_recovery_test.rule_versions SET spec=jsonb_set(spec::jsonb,'{rule,scheduled_at}',to_jsonb(to_timestamp(n-90000)))::text WHERE task_id=id;
 UPDATE watchlist_recovery_test.runtime SET state='{}',next_run=n-90000 WHERE task_id=id;
 c:=watchlist_recovery_test.product_rpc('claim','demo','{"key":"TEST-calendar-missed"}');x:=watchlist_recovery_test.product_rpc('finish','demo',c);IF x->>'decision'<>'missed' THEN RAISE EXCEPTION 'calendar outside grace not missed';END IF;
 IF (SELECT count(*) FROM watchlist_recovery_test.notifications WHERE task_id=id)<>1 THEN RAISE EXCEPTION 'missed calendar emitted notification';END IF;
END $$;
SELECT 'TEST PASS: retry 15/30/60/60; unknown preserves episode; recovered no duplicate; gap/read-model; abandoned tick closure; old lease/wrong key/pause/edit fencing; late/missed calendar/idempotency/terminal resume; claim replay and held lease exclusion' AS result;
ROLLBACK;
'''
Path(a.output).write_text(s)
