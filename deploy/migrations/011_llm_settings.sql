BEGIN;
SELECT pg_advisory_xact_lock(724102401);
CREATE TABLE watchlist.llm_settings (
 owner text PRIMARY KEY,
 provider text NOT NULL CHECK(provider IN ('deepseek','qwen')),
 model text NOT NULL CHECK(length(model) BETWEEN 1 AND 100),
 encrypted_key jsonb NOT NULL CHECK(encrypted_key->>'v'='1'),
 updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE watchlist.llm_settings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON watchlist.llm_settings FROM PUBLIC,anon,authenticated;
CREATE FUNCTION public.watchlist_llm_settings_v1(p_action text,p_owner text,p_body jsonb DEFAULT '{}'::jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE result jsonb;
BEGIN
 IF p_owner IS DISTINCT FROM 'demo' THEN RAISE EXCEPTION 'invalid_owner'; END IF;
 IF p_action='llm_get' THEN
  SELECT to_jsonb(s) INTO result FROM watchlist.llm_settings s WHERE owner=p_owner;
 ELSIF p_action='llm_save' THEN
  INSERT INTO watchlist.llm_settings AS target(owner,provider,model,encrypted_key) VALUES(p_owner,p_body->>'provider',p_body->>'model',p_body->'encrypted_key')
  ON CONFLICT(owner) DO UPDATE SET provider=excluded.provider,model=excluded.model,encrypted_key=excluded.encrypted_key,updated_at=clock_timestamp()
  RETURNING to_jsonb(target) INTO result;
 ELSIF p_action='llm_delete' THEN
  DELETE FROM watchlist.llm_settings WHERE owner=p_owner;
 ELSE RAISE EXCEPTION 'invalid_action'; END IF;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION public.watchlist_llm_settings_v1(text,text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.watchlist_llm_settings_v1(text,text,jsonb) TO service_role;
COMMIT;
