-- Incremental feasibility probe only. No product data reset or original migration replay.
BEGIN;
SELECT pg_advisory_xact_lock(724102401);
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM watchlist.schema_version WHERE version=1) THEN
  RAISE EXCEPTION 'watchlist_v1_required';
 END IF;
END $$;
CREATE TABLE watchlist.rpc_probe_records (
 id uuid PRIMARY KEY, owner text NOT NULL CHECK(owner='demo'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
REVOKE ALL ON watchlist.rpc_probe_records FROM PUBLIC, anon, authenticated;
CREATE FUNCTION public.watchlist_probe_v1(p_action text,p_id uuid,p_owner text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog
SET statement_timeout = '5s'
AS $$
DECLARE r watchlist.rpc_probe_records%ROWTYPE;
BEGIN
 IF p_owner IS DISTINCT FROM 'demo' THEN RAISE EXCEPTION 'owner_rejected' USING ERRCODE='42501'; END IF;
 IF p_action IN ('write','fail') THEN
  INSERT INTO watchlist.rpc_probe_records(id,owner) VALUES(p_id,p_owner);
  IF p_action='fail' THEN RAISE EXCEPTION 'intentional_probe_rollback' USING ERRCODE='P0001'; END IF;
 ELSIF p_action='cleanup' THEN
  DELETE FROM watchlist.rpc_probe_records WHERE id=p_id AND owner=p_owner;
 ELSIF p_action<>'read' OR p_action IS NULL THEN
  RAISE EXCEPTION 'invalid_action' USING ERRCODE='22023';
 END IF;
 SELECT * INTO r FROM watchlist.rpc_probe_records WHERE id=p_id AND owner=p_owner;
 RETURN jsonb_build_object('found',FOUND,'id',r.id,'owner',r.owner,'created_at',r.created_at,'database_time',clock_timestamp());
END $$;
REVOKE ALL ON FUNCTION public.watchlist_probe_v1(text,uuid,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.watchlist_probe_v1(text,uuid,text) TO service_role;
NOTIFY pgrst, 'reload schema';
COMMIT;
