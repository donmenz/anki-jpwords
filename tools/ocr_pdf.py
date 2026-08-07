#!/usr/bin/env python3
"""Render a scanned PDF and preserve raw OCR-server responses per page."""
from __future__ import annotations
import argparse, json, subprocess, tempfile
from pathlib import Path
from urllib.request import Request, urlopen

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('pdf', type=Path); ap.add_argument('out', type=Path)
    ap.add_argument('--url', default='http://127.0.0.1:8000/upload'); ap.add_argument('--dpi', type=int, default=120)
    ap.add_argument('--start', type=int, default=1); ap.add_argument('--end', type=int)
    args=ap.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    info=subprocess.check_output(['pdfinfo',str(args.pdf)], text=True)
    pages=next(int(x.split(':',1)[1]) for x in info.splitlines() if x.startswith('Pages:'))
    with tempfile.TemporaryDirectory(prefix='n1-pdf-') as td:
        for p in range(args.start, min(args.end or pages, pages)+1):
            target=Path(td)/f'page-{p:04d}'
            subprocess.run(['pdftoppm','-f',str(p),'-l',str(p),'-jpeg','-r',str(args.dpi),'-singlefile',str(args.pdf),str(target)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            probe=subprocess.check_output(['sips','-g','pixelWidth','-g','pixelHeight',str(target.with_suffix('.jpg'))], text=True)
            vals=[int(line.split(':',1)[1].strip()) for line in probe.splitlines() if ':' in line]
            w,h=vals[-2],vals[-1]
            pieces=[]
            for side,(x0,x1) in enumerate(((40,w//2+4),(w//2-4,w-30))):
                piece=Path(td)/f'page-{p:04d}-{side}.jpg'
                subprocess.run(['ffmpeg','-loglevel','error','-y','-i',str(target.with_suffix('.jpg')),'-vf',f'crop={x1-x0}:{h-80}:{x0}:40,scale={2*(x1-x0)}:{2*(h-80)}',str(piece)],check=True)
                image=piece.read_bytes()
                boundary='----CodexOCRBoundary'
                body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="page.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode()+image+f'\r\n--{boundary}--\r\n'.encode()
                req=Request(args.url,data=body,headers={'Content-Type':f'multipart/form-data; boundary={boundary}','Accept':'application/json'})
                with urlopen(req, timeout=90) as response: result=json.loads(response.read())
                for box in result.get('ocr_boxes',[]):
                    box['x']=(float(box.get('x',0))/2)+x0; box['y']=(float(box.get('y',0))/2)+40
                    box['w']=float(box.get('w',0))/2; box['h']=float(box.get('h',0))/2
                pieces.append(result)
            result={'success':all(x.get('success') for x in pieces), 'image_width':w, 'image_height':h,
                     'ocr_boxes':[b for x in pieces for b in x.get('ocr_boxes',[])],
                     'ocr_result':'\n'.join(x.get('ocr_result','') for x in pieces)}
            (args.out/f'page-{p:04d}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            if p%10==0 or p==min(args.end or pages, pages): print(f'{p}/{min(args.end or pages, pages)}', flush=True)
if __name__=='__main__': main()
