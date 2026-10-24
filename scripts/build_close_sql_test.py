from pathlib import Path
s=Path('deploy/migrations/007_daily_close.sql').read_text()
funcs=s[s.index('CREATE FUNCTION watchlist.close_transition'):s.index('INSERT INTO watchlist.schema_version VALUES(7);')]
funcs=funcs.replace('watchlist.','watchlist_close_test.').replace('public.watchlist_product_v1','watchlist_close_test.product_rpc')
pre="BEGIN;\nCREATE SCHEMA watchlist_close_test;\n"
tables=['instruments','tasks','rule_versions','runtime','runs','observations','events','calendar_entries','evidence','notifications','audit','parser_audit','ticks','close_cache','close_records']
pre+='\n'.join(f'CREATE TABLE watchlist_close_test.{t} (LIKE watchlist.{t} INCLUDING ALL);' for t in tables)+'\nINSERT INTO watchlist_close_test.instruments SELECT * FROM watchlist.instruments;\n'
fixture='''
-- TEST only. Synthetic prices/times below stay inside this isolated rolled-back schema.
CREATE FUNCTION watchlist_close_test.check_price(tid text,dt text,val text,quality text,key text) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE c jsonb;s jsonb;ob jsonb;ev jsonb;n double precision:=extract(epoch from clock_timestamp());BEGIN
 UPDATE watchlist_close_test.runtime SET next_run=n-1 WHERE task_id=tid;
 c:=watchlist_close_test.product_rpc('claim','demo',jsonb_build_object('key',key));
 IF c->>'task_id' IS DISTINCT FROM tid THEN RAISE EXCEPTION 'TEST claim mismatch';END IF;
 SELECT spec::jsonb INTO s FROM watchlist_close_test.rule_versions WHERE task_id=tid ORDER BY version DESC LIMIT 1;
 ob:=jsonb_build_object('instrument_id','CN.SH.600519','field','close_price','value',val,'unit','CNY','source_time',NULL,'trade_date',dt,'adjust','none','mapping_version','fuyao-daily-close-v1','fetched_at',to_timestamp(n)::text,'provider','fuyao','source_ref','TEST synthetic fixture, not market data','quality',quality);
 ev:=jsonb_build_object('mapping_version','fuyao-daily-close-v1','result',CASE WHEN quality='valid' THEN val::numeric<110 ELSE NULL END,'valid_until',n+300,'next_check',n+900,'market',jsonb_build_object('expected_trade_date',dt),'evidence',jsonb_build_array(jsonb_build_object('condition',s#>'{rule,conditions,0}','observation',ob,'quality',quality,'result',CASE WHEN quality='valid' THEN val::numeric<110 ELSE NULL END)));
 RETURN watchlist_close_test.product_rpc('finish','demo',c||jsonb_build_object('evaluation',ev));END $$;
DO $$
#variable_conflict use_variable
DECLARE s jsonb:='{"name":"TEST synthetic daily close","instrument_id":"CN.SH.600519","rule":{"kind":"close_price_group","combinator":"all","conditions":[{"id":"p1","field":"close_price","operator":"lt","value":"110","currency":"CNY"}]},"schedule":{"mode":"daily_close","timezone":"Asia/Shanghai","interval_seconds":86400},"notification_policy":{"mode":"on_episode","cooldown_seconds":86400}}';t jsonb;x jsonb;c jsonb;id text;before_state text;num integer;
BEGIN
 t:=watchlist_close_test.product_rpc('create','demo',jsonb_build_object('spec',s));id:=t->>'id';
 PERFORM watchlist_close_test.product_rpc('activate','demo',jsonb_build_object('id',id,'expected_version',1));
 x:=watchlist_close_test.check_price(id,'2026-10-20','100','valid','TEST-slot-01');IF x->>'decision'<>'notify' THEN RAISE EXCEPTION 'TEST first notify: %',x;END IF;
 c:=watchlist_close_test.product_rpc('claim','demo','{"key":"TEST-slot-01"}');IF c->>'duplicate'<>'true' THEN RAISE EXCEPTION 'TEST duplicate key';END IF;
 x:=watchlist_close_test.check_price(id,'2026-10-20','100','valid','TEST-slot-02');IF x->>'decision'<>'already_notified' THEN RAISE EXCEPTION 'TEST same bar duplicate';END IF;
 x:=watchlist_close_test.check_price(id,'2026-10-21','120','valid','TEST-slot-03');IF x->>'decision'<>'no_match' THEN RAISE EXCEPTION 'TEST false';END IF;
 x:=watchlist_close_test.check_price(id,'2026-10-22','100','valid','TEST-slot-04');IF x->>'decision'<>'cooldown_suppressed' THEN RAISE EXCEPTION 'TEST cooldown';END IF;
 SELECT state INTO before_state FROM watchlist_close_test.runtime WHERE task_id=id;
 x:=watchlist_close_test.check_price(id,'2026-10-22',NULL,'missing','TEST-slot-05');IF x->>'decision'<>'insufficient_data' OR (SELECT state FROM watchlist_close_test.runtime WHERE task_id=id)<>before_state THEN RAISE EXCEPTION 'TEST unknown state';END IF;
 UPDATE watchlist_close_test.runtime SET state=(state::jsonb||'{"cooldown_until":0}'::jsonb)::text WHERE task_id=id;
 x:=watchlist_close_test.check_price(id,'2026-10-22','100','valid','TEST-slot-06');IF x->>'decision'<>'notify' THEN RAISE EXCEPTION 'TEST deferred notify';END IF;
 x:=watchlist_close_test.check_price(id,'2026-10-23','100','valid','TEST-slot-07');IF x->>'decision'<>'already_notified' THEN RAISE EXCEPTION 'TEST next date continuous true';END IF;
 x:=watchlist_close_test.check_price(id,'2026-10-22','100','valid','TEST-slot-08');IF x->>'decision'<>'insufficient_data' THEN RAISE EXCEPTION 'TEST date regression';END IF;
 x:=watchlist_close_test.check_price(id,'2026-10-23','99','valid','TEST-slot-09');IF x->>'decision'<>'insufficient_data' THEN RAISE EXCEPTION 'TEST correction conflict';END IF;
 SELECT count(*) INTO num FROM watchlist_close_test.notifications WHERE task_id=id;IF num<>2 THEN RAISE EXCEPTION 'TEST two episodes exactly two notifications, got %',num;END IF;
 UPDATE watchlist_close_test.runtime SET next_run=0 WHERE task_id=id;
 c:=watchlist_close_test.product_rpc('claim','demo','{"key":"TEST-slot-10"}');PERFORM watchlist_close_test.product_rpc('pause','demo',jsonb_build_object('id',id));
 x:=watchlist_close_test.product_rpc('finish','demo',c);IF x->>'decision'<>'superseded' THEN RAISE EXCEPTION 'TEST paused in flight';END IF;
 PERFORM watchlist_close_test.product_rpc('delete','demo',jsonb_build_object('id',id));
 x:=watchlist_close_test.product_rpc('get','demo',jsonb_build_object('id',id));IF x->>'lifecycle'<>'deleted' THEN RAISE EXCEPTION 'TEST deleted history';END IF;
 x:=watchlist_close_test.product_rpc('runs','demo',jsonb_build_object('id',id));IF jsonb_array_length(x)<>10 THEN RAISE EXCEPTION 'TEST runs retained';END IF;
 BEGIN PERFORM watchlist_close_test.product_rpc('resume','demo',jsonb_build_object('id',id,'expected_version',1));RAISE EXCEPTION 'TEST deleted resumed';EXCEPTION WHEN OTHERS THEN IF SQLERRM<>'invalid_lifecycle' THEN RAISE;END IF;END;
END $$;
SELECT 'TEST isolated schema: first/same bar/new date/false/unknown/cooldown/conflict/regression/idempotency/pause/deleted history passed; rolled back' AS result;
ROLLBACK;
'''
Path('artifacts/close-isolated-state-test-r2.sql').write_text(pre+funcs+fixture)
