-- ON-01: one database-backed rolling window shared by every Edge Function instance.
BEGIN;
SELECT pg_advisory_xact_lock(724102401);
CREATE TABLE watchlist.login_attempts(at timestamptz NOT NULL);
CREATE INDEX login_attempts_at ON watchlist.login_attempts(at);
REVOKE ALL ON watchlist.login_attempts FROM PUBLIC,anon,authenticated;
CREATE FUNCTION public.watchlist_login_gate_v1(p_owner text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET statement_timeout='5s' SET lock_timeout='3s' AS $$
DECLARE n timestamptz; oldest timestamptz; attempts int;
BEGIN
 IF p_owner IS DISTINCT FROM 'demo' THEN RAISE EXCEPTION 'owner_rejected' USING ERRCODE='42501'; END IF;
 PERFORM pg_advisory_xact_lock(724102406);
 n:=clock_timestamp();
 DELETE FROM watchlist.login_attempts WHERE at<=n-interval '60 seconds';
 SELECT count(*),min(at) INTO attempts,oldest FROM watchlist.login_attempts;
 IF attempts>=10 THEN
  RETURN jsonb_build_object('allowed',false,'retry_after',greatest(1,ceil(extract(epoch from oldest+interval '60 seconds'-n))::int));
 END IF;
 INSERT INTO watchlist.login_attempts(at) VALUES(n);
 RETURN jsonb_build_object('allowed',true,'retry_after',0);
END $$;
REVOKE ALL ON FUNCTION public.watchlist_login_gate_v1(text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.watchlist_login_gate_v1(text) TO service_role;
INSERT INTO watchlist.schema_version VALUES(6);
NOTIFY pgrst,'reload schema';
COMMIT;
