#!/usr/bin/env python3
"""Generic last-inventory concurrency gate. Requires an API payload JSON and capacity."""
import argparse,json,urllib.request,urllib.error
from concurrent.futures import ThreadPoolExecutor,as_completed

def call(url,token,payload,key):
    body=dict(payload); headers={"Content-Type":"application/json","X-Idempotency-Key":key}
    if token: headers["Authorization"]=f"token {token}"
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers=headers,method="POST")
    try:
        with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:return e.code,json.loads(e.read())
        except Exception:return e.code,{"error":"non-json"}

def main():
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--payload',required=True);p.add_argument('--requests',type=int,default=10);p.add_argument('--expected-successes',type=int,required=True);p.add_argument('--token',default='');p.add_argument('--output');a=p.parse_args();payload=json.load(open(a.payload));results=[]
    with ThreadPoolExecutor(max_workers=a.requests) as ex:
        fs=[ex.submit(call,a.url,a.token,payload,f"CONCURRENCY-GATE-{i}") for i in range(a.requests)]
        for f in as_completed(fs):results.append(f.result())
    successes=[x for x in results if 200<=x[0]<300]; refs=[]
    for _,d in successes:
        m=d.get('message',d); ref=m.get('data',m).get('name') if isinstance(m,dict) else None
        if ref:refs.append(ref)
    report={"requests":a.requests,"successes":len(successes),"expected_successes":a.expected_successes,"unique_refs":len(set(refs)),"statuses":[x[0] for x in results]};text=json.dumps(report,indent=2);print(text);open(a.output,'w').write(text+'\n') if a.output else None
    raise SystemExit(0 if len(successes)==a.expected_successes and len(refs)==len(set(refs)) else 1)
if __name__=='__main__':main()
