-- TEST ONLY synthetic prices; run exclusively in rollback schema.
CREATE FUNCTION watchlist_recovery_test.check_price(tid text,dt text,val text,quality text,key text) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE c jsonb;s jsonb;ob jsonb;ev jsonb;n double precision:=extract(epoch from clock_timestamp());BEGIN
 UPDATE watchlist_recovery_test.runtime SET next_run=n-1 WHERE task_id=tid;
 c:=watchlist_recovery_test.product_rpc('claim','demo',jsonb_build_object('key',key));
 IF c->>'task_id' IS DISTINCT FROM tid THEN RAISE EXCEPTION 'TEST claim mismatch';END IF;
 SELECT spec::jsonb INTO s FROM watchlist_recovery_test.rule_versions WHERE task_id=tid ORDER BY version DESC LIMIT 1;
 ob:=jsonb_build_object('instrument_id','CN.SH.600519','field','close_price','value',val,'unit','CNY','source_time',NULL,'trade_date',dt,'adjust','none','mapping_version','fuyao-daily-close-v1','fetched_at',to_timestamp(n)::text,'provider','fuyao','source_ref','TEST synthetic fixture, not market data','quality',quality);
 ev:=jsonb_build_object('mapping_version','fuyao-daily-close-v1','result',CASE WHEN quality='valid' THEN val::numeric<110 ELSE NULL END,'valid_until',n+300,'next_check',n+900,'market',jsonb_build_object('expected_trade_date',dt),'evidence',jsonb_build_array(jsonb_build_object('condition',s#>'{rule,conditions,0}','observation',ob,'quality',quality,'result',CASE WHEN quality='valid' THEN val::numeric<110 ELSE NULL END)));
 RETURN watchlist_recovery_test.product_rpc('finish','demo',c||jsonb_build_object('evaluation',ev));END $$;
