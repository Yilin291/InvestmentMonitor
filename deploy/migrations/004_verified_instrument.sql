-- Import only previously verified metadata, not market observations.
-- Evidence: deploy/instruments_verified.json, validation/evidence/ifind_live.json,
-- validation/evidence/fuyao_live_rerun.json. No inferred quote timestamps.
BEGIN;
SELECT pg_advisory_xact_lock(724102401);
INSERT INTO watchlist.instruments(id,market,code,name,asset_class,currency,provenance)
VALUES('CN.SH.600519','SH','600519','贵州茅台','stock','CNY','validation/evidence/ifind_live.json + validation/evidence/fuyao_live_rerun.json; verified metadata only') ON CONFLICT(id) DO NOTHING;
DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM watchlist.instruments WHERE id='CN.SH.600519' AND market='SH' AND code='600519' AND name='贵州茅台') THEN RAISE EXCEPTION 'instrument_identity_conflict'; END IF; END $$;
INSERT INTO watchlist.schema_version VALUES(4);
COMMIT;
