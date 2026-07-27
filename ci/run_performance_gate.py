#!/usr/bin/env python3
import argparse,json,time,urllib.request,statistics
from concurrent.futures import ThreadPoolExecutor,as_completed

def hit(url,token):
    h={};
    if token:h['Authorization']=f'token {token}'
    t=time.perf_counter()
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=30) as r:r.read();code=r.status
    except Exception:code=599
    return (time.perf_counter()-t)*1000,code

def percentile(v,p):
    s=sorted(v);return s[min(len(s)-1,max(0,int(len(s)*p)-1))]
def main():
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--requests',type=int,default=100);p.add_argument('--concurrency',type=int,default=10);p.add_argument('--max-p95-ms',type=float,default=1500);p.add_argument('--max-error-percent',type=float,default=1);p.add_argument('--token',default='');p.add_argument('--output');a=p.parse_args();out=[]
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        for f in as_completed([ex.submit(hit,a.url,a.token) for _ in range(a.requests)]):out.append(f.result())
    times=[x[0] for x in out];errors=sum(1 for _,c in out if not 200<=c<400);report={'requests':len(out),'mean_ms':round(statistics.mean(times),2),'p95_ms':round(percentile(times,.95),2),'max_ms':round(max(times),2),'error_percent':round(errors*100/len(out),2)};text=json.dumps(report,indent=2);print(text);open(a.output,'w').write(text+'\n') if a.output else None;raise SystemExit(0 if report['p95_ms']<=a.max_p95_ms and report['error_percent']<=a.max_error_percent else 1)
if __name__=='__main__':main()
