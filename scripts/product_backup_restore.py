"""Read-only source snapshot, then restore into a new isolated schema in the same DB.
Never overwrites product tables. This is not proof of off-instance disaster recovery.
"""
import hashlib,json,subprocess,datetime
from pathlib import Path
schema='watchlist_restore_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
root=Path('artifacts')
tables=['schema_version','instruments','tasks','rule_versions','runtime','runs','observations','events','calendar_entries','evidence','notifications','audit','parser_audit','ticks','close_records']
def query(sql,label):
 p=root/(schema+'-'+label+'.sql');p.write_text(sql)
 r=subprocess.run(['meoo','--json','db','query','--project','ucdte4eh02uv','--file',str(p)],capture_output=True,text=True)
 out=root/(schema+'-'+label+'.json');out.write_text(r.stdout)
 if r.returncode: raise RuntimeError(label+'_exit_'+str(r.returncode))
 d=json.loads(r.stdout)
 if not d.get('success'):raise RuntimeError(label+'_failed')
 return d['data']['rows']
def snapshot_sql(sc):
 return 'SELECT jsonb_build_object('+','.join("'%s',(SELECT coalesce(jsonb_agg(to_jsonb(x)), '[]'::jsonb) FROM %s.%s x)"%(t,sc,t) for t in tables)+') AS backup;'
snap=query(snapshot_sql('watchlist'),'backup')[0]['backup']
if isinstance(snap,str):snap=json.loads(snap)
backup=root/(schema+'-snapshot.json');backup.write_text(json.dumps(snap,ensure_ascii=False,indent=2));backup.chmod(0o600)
constraints=query("SET search_path=pg_catalog; SELECT c.conrelid::regclass::text AS tab,c.conname,pg_get_constraintdef(c.oid) AS def FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='watchlist' AND c.contype='f'",'foreign-keys')
quote=lambda s:"'"+s.replace("'","''")+"'"
sql=['BEGIN;',f'CREATE SCHEMA {schema};',f'REVOKE ALL ON SCHEMA {schema} FROM PUBLIC,anon,authenticated;']
for t in tables:
 sql.append(f'CREATE TABLE {schema}.{t} (LIKE watchlist.{t} INCLUDING ALL);')
 sql.append(f'INSERT INTO {schema}.{t} SELECT * FROM jsonb_populate_recordset(NULL::{schema}.{t}, {quote(json.dumps(snap[t],ensure_ascii=False))}::jsonb);')
for c in constraints:
 t=c['tab'].split('.')[-1]
 if t in tables:sql.append(f'ALTER TABLE {schema}.{t} ADD CONSTRAINT {c["conname"]} '+c['def'].replace('REFERENCES watchlist.',f'REFERENCES {schema}.')+';')
for t in ['audit','parser_audit','evidence']:
 sql.append(f"SELECT setval(pg_get_serial_sequence('{schema}.{t}','id'), greatest(1,coalesce((SELECT max(id) FROM {schema}.{t}),0)), EXISTS(SELECT 1 FROM {schema}.{t}));")
sql.extend([f'CREATE TRIGGER immutable_rule_versions BEFORE UPDATE ON {schema}.rule_versions FOR EACH ROW EXECUTE FUNCTION watchlist.reject_rule_update();',f'REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM PUBLIC,anon,authenticated;',f'REVOKE ALL ON ALL SEQUENCES IN SCHEMA {schema} FROM PUBLIC,anon,authenticated;','COMMIT;'])
query('\n'.join(sql),'restore')
restored=query(snapshot_sql(schema),'readback')[0]['backup']
if isinstance(restored,str):restored=json.loads(restored)
def digest(rows):return hashlib.sha256(json.dumps(sorted(rows,key=lambda r:json.dumps(r,sort_keys=True)),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
checks={t:{'source_rows':len(snap[t]),'restored_rows':len(restored[t]),'equal':digest(snap[t])==digest(restored[t])} for t in tables}
out={'isolated_schema':schema,'source_unchanged':True,'same_instance_only':True,'off_instance_recovery_tested':False,'snapshot_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'tables':checks,'passed':all(c['equal'] for c in checks.values()),'foreign_keys_restored':sum(c['tab'].split('.')[-1] in tables for c in constraints),'ephemeral_excluded':['login_attempts','close_cache','llm_settings'],'ephemeral_policy':'recreate excluded tables empty from migrations; custom model keys must be re-entered; snapshot is not executable and lease fields must be cleared before activating a replacement worker','restore_scope':'business records including daily close conflict history; not a runnable replacement instance','immutable_trigger_restored':True}
(root/(schema+'-assessment.json')).write_text(json.dumps(out,indent=2));print(json.dumps(out));raise SystemExit(0 if out['passed'] else 1)
