"""Render actual CUA browser captures at their observed durations, with scope captions.
No generated UI, market fixtures or simulated automatic executions.
Requires Pillow for local media tooling only; not a product runtime dependency.
"""
import json,textwrap,subprocess,hashlib
from pathlib import Path
from datetime import datetime
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parent.parent
source=root/'artifacts/demo-recording-final';data=json.loads((source/'capture.json').read_text());frames=data['frames'];rendered=source/'captioned';rendered.mkdir(exist_ok=True)
font='/System/Library/Fonts/Supplemental/Arial Unicode.ttf';title=ImageFont.truetype(font,20);caption=ImageFont.truetype(font,26);small=ImageFont.truetype(font,15)
lines=[]
for i,f in enumerate(frames):
 image=Image.open(source/f['file']).convert('RGB');canvas=Image.new('RGB',(1440,900),'#10251f');draw=ImageDraw.Draw(canvas)
 draw.text((24,10),'观澜 · 正式线上页面实录 | 采样画面，按真实时长播放',font=title,fill='#a8d7c1')
 for j,line in enumerate(textwrap.wrap(f['stage'],width=48)):draw.text((24,43+j*33),line,font=caption,fill='white')
 canvas.paste(image,(0,120));stamp=datetime.fromtimestamp(f['at']/1000).strftime('%Y-%m-%d %H:%M:%S')
 draw.text((24,879),'采集时刻 '+stamp+' 北京时间 | 无口令、密钥或模拟市场数据',font=small,fill='white')
 p=rendered/f['file'];canvas.save(p)
 end=frames[i+1]['at'] if i+1<len(frames) else data['ended'];duration=max(.05,(end-f['at'])/1000)
 lines.extend([f"file '{p}'",f'duration {duration:.6f}'])
lines.append(f"file '{rendered/frames[-1]['file']}'")
concat=source/'frames.ffconcat';concat.write_text('\n'.join(lines)+'\n')
video=root/'artifacts/watchlist-demo-20261024-r2.mp4'
if video.exists():raise SystemExit('Video exists; preserve historical artifact')
run=subprocess.run(['ffmpeg','-hide_banner','-loglevel','warning','-f','concat','-safe','0','-i',str(concat),'-r','10','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart','-an',str(video)],capture_output=True,text=True)
(root/'artifacts/demo-video-render.log').write_text(run.stderr)
if run.returncode:raise SystemExit(run.returncode)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration,size:stream=width,height,codec_name','-of','json',str(video)]))
assert 60<=float(probe['format']['duration'])<=180
out={'video':str(video.relative_to(root)),'sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'capture_frame_count':len(frames),'capture_started_at':data['started'],'capture_ended_at':data['ended'],'format':probe,'recording_method':'actual CUA browser captures, observed timing retained; captioned sampled recording, not full-frame screen capture','date_chain':'real manual functional execution and persisted notification','automatic_schedule':'not accepted; overdue task shown without executions','price_judgment':'unknown; real observation, no price notification','passed_media_validation':True}
(root/'artifacts/demo-video-manifest-r2.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False))
