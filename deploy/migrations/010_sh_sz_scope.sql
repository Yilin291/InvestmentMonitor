-- Expand validated equity import/cache namespaces only; retain current executor/read model.
BEGIN;
SELECT pg_advisory_xact_lock(724102401);
DO $patch$ DECLARE src text; BEGIN
 src:=pg_get_functiondef('public.watchlist_product_v1(text,text,jsonb)'::regprocedure);
 IF position($old0$ob->>'id' IS DISTINCT FROM 'CN.SH.'||(ob->>'code') OR ob->>'code' !~ '^6[0-9]{5}$' OR ob->>'market' IS DISTINCT FROM 'SH'$old0$ in src)=0 THEN RAISE EXCEPTION 'expected function fragment 0 absent; abort'; END IF;
 src:=replace(src,$old0$ob->>'id' IS DISTINCT FROM 'CN.SH.'||(ob->>'code') OR ob->>'code' !~ '^6[0-9]{5}$' OR ob->>'market' IS DISTINCT FROM 'SH'$old0$,$new0$ob->>'id' IS DISTINCT FROM 'CN.'||(ob->>'market')||'.'||(ob->>'code') OR NOT ((ob->>'market'='SH' AND ob->>'code' ~ '^6[0-9]{5}$') OR (ob->>'market'='SZ' AND ob->>'code' ~ '^[03][0-9]{5}$')) OR ob->>'market' IS NULL OR ob->>'code' IS NULL$new0$);
 IF position($old1$VALUES(ob->>'id','SH',ob->>'code'$old1$ in src)=0 THEN RAISE EXCEPTION 'expected function fragment 1 absent; abort'; END IF;
 src:=replace(src,$old1$VALUES(ob->>'id','SH',ob->>'code'$old1$,$new1$VALUES(ob->>'id',ob->>'market',ob->>'code'$new1$);
 IF position($old2$'^CN.SH.6[0-9]{5}:[0-9]{4}-[0-9]{2}-[0-9]{2}$'$old2$ in src)=0 THEN RAISE EXCEPTION 'expected function fragment 2 absent; abort'; END IF;
 src:=replace(src,$old2$'^CN.SH.6[0-9]{5}:[0-9]{4}-[0-9]{2}-[0-9]{2}$'$old2$,$new2$'^CN\.(SH\.6[0-9]{5}|SZ\.[03][0-9]{5}):[0-9]{4}-[0-9]{2}-[0-9]{2}$'$new2$);
 EXECUTE src;
END $patch$;
INSERT INTO watchlist.schema_version VALUES(10);
COMMIT;
