"""Same-origin HTTP CookieJar readback; not browser UI acceptance."""
import http.cookiejar,json,urllib.request,urllib.error,time
from pathlib import Path
secret=json.loads(Path('.product-data/production-config.json').read_text())['TICK_SECRET']
jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
url='https://ucdte4eh02uv.meoo.info/sb-api/functions/v1/watchlist-probe'
results=[]
for action in ('cookie_set','cookie_read','cookie_clear','cookie_read'):
 req=urllib.request.Request(url,data=json.dumps({'action':action}).encode(),headers={'Content-Type':'application/json','Origin':'https://ucdte4eh02uv.meoo.info','X-Probe-Secret':secret})
 start=time.monotonic()
 with opener.open(req,timeout=12) as r:
  header=r.headers.get('Set-Cookie','')
  results.append({'action':action,'status':r.status,'body':json.load(r),'elapsed_seconds':round(time.monotonic()-start,3),'set_cookie_flags':{k:k in header for k in ('HttpOnly','Secure','SameSite=Strict','Path=/')} if header else None})
passed=all(r['status']==200 for r in results) and results[1]['body'].get('cookie_present') is True and results[3]['body'].get('cookie_present') is False and all(results[0]['set_cookie_flags'].values())
out={'url':url,'scope':'HTTP CookieJar transport only; not browser UI acceptance','passed':passed,'results':results}
with Path('artifacts/deno-cookie-readback.json').open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(out));raise SystemExit(0 if passed else 1)
