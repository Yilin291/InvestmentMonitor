BEGIN;
SELECT pg_advisory_xact_lock(724102401);
ALTER TABLE watchlist.llm_settings ADD COLUMN base_url text, ADD COLUMN enabled boolean NOT NULL DEFAULT true, ADD COLUMN last_error text;
ALTER TABLE watchlist.llm_settings DROP CONSTRAINT llm_settings_provider_check;
ALTER TABLE watchlist.llm_settings ADD CONSTRAINT llm_settings_provider_check CHECK(provider IN ('deepseek','qwen','openai','anthropic'));
ALTER TABLE watchlist.llm_settings DROP CONSTRAINT llm_settings_encrypted_key_check;
ALTER TABLE watchlist.llm_settings ADD CONSTRAINT llm_settings_encrypted_key_check CHECK(encrypted_key->>'v' IN ('1','2'));
ALTER TABLE watchlist.llm_settings ADD CONSTRAINT llm_settings_url_check CHECK(base_url IS NULL OR (length(base_url)<=512 AND base_url LIKE 'https://%'));
ALTER TABLE watchlist.llm_settings ADD CONSTRAINT llm_settings_error_check CHECK(last_error IS NULL OR length(last_error)<=500);
CREATE OR REPLACE FUNCTION public.watchlist_llm_settings_v1(p_action text,p_owner text,p_body jsonb DEFAULT '{}'::jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE result jsonb;
BEGIN
 IF p_owner IS DISTINCT FROM 'demo' THEN RAISE EXCEPTION 'invalid_owner'; END IF;
 IF p_action='llm_get' THEN
  SELECT to_jsonb(s) INTO result FROM watchlist.llm_settings s WHERE owner=p_owner;
 ELSIF p_action='llm_save' THEN
  INSERT INTO watchlist.llm_settings AS target(owner,provider,model,encrypted_key,base_url,enabled,last_error) VALUES(p_owner,p_body->>'provider',p_body->>'model',p_body->'encrypted_key',p_body->>'base_url',coalesce((p_body->>'enabled')::boolean,true),p_body->>'last_error')
  ON CONFLICT(owner) DO UPDATE SET provider=excluded.provider,model=excluded.model,encrypted_key=excluded.encrypted_key,base_url=excluded.base_url,enabled=excluded.enabled,last_error=excluded.last_error,updated_at=clock_timestamp()
  RETURNING to_jsonb(target) INTO result;
 ELSIF p_action='llm_delete' THEN
  DELETE FROM watchlist.llm_settings WHERE owner=p_owner;
 ELSE RAISE EXCEPTION 'invalid_action'; END IF;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION public.watchlist_llm_settings_v1(text,text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.watchlist_llm_settings_v1(text,text,jsonb) TO service_role;
COMMIT;
