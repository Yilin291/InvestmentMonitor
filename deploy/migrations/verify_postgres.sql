BEGIN;
SELECT pg_advisory_xact_lock(724102401);
SET LOCAL search_path TO watchlist;
DO $$
DECLARE
    rows_affected integer;
    immutable_rejected boolean := false;
BEGIN
    IF (SELECT count(*) FROM schema_version WHERE version=1) <> 1 THEN
        RAISE EXCEPTION 'schema_version_missing';
    END IF;
    INSERT INTO tasks VALUES('r2_rollback_sql_probe','TEST_ONLY','TEST ONLY rollback probe',NULL,1,0,'draft',0,0);
    INSERT INTO rule_versions VALUES('r2_rollback_sql_probe',1,'{}',0,'TEST ONLY rollback probe');
    BEGIN
        UPDATE rule_versions SET spec='{"changed":true}' WHERE task_id='r2_rollback_sql_probe';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM <> 'immutable_rule_version' THEN RAISE; END IF;
        immutable_rejected := true;
    END;
    IF NOT immutable_rejected THEN RAISE EXCEPTION 'immutable_trigger_failed'; END IF;
    INSERT INTO runs VALUES('r2_rollback_run','r2_rollback_sql_probe',1,0,'test-lease',0,0,0,'succeeded','true','notify','{}');
    INSERT INTO notifications VALUES('r2_notification_1','r2_rollback_sql_probe','r2_rollback_run','r2_unique_key',0,NULL,'{}');
    INSERT INTO notifications VALUES('r2_notification_2','r2_rollback_sql_probe','r2_rollback_run','r2_unique_key',0,NULL,'{}') ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    IF rows_affected <> 0 THEN RAISE EXCEPTION 'dedup_constraint_failed'; END IF;
    IF (SELECT count(*) FROM notifications WHERE task_id='r2_rollback_sql_probe') <> 1 THEN RAISE EXCEPTION 'wrong_notification_count'; END IF;
END $$;
ROLLBACK;
