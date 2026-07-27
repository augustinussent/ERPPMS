from pathlib import Path
import argparse,json,runpy,sys
root=Path(__file__).resolve().parents[1]; endpoints=runpy.run_path(root/'hotel_pms/api/schema.py')['ENDPOINTS']
paths={}; items=[]
for name,spec in endpoints.items():
    route=f'/api/method/hotel_pms.api.v1.{name}'; op={'summary':spec['summary'],'responses':{'200':{'description':'OK'}}}
    if spec.get('query'):op['parameters']=[{'name':x,'in':'query','required':True,'schema':{'type':'string'}} for x in spec['query']]
    if spec.get('idempotency'):op.setdefault('parameters',[]).append({'name':'X-Idempotency-Key','in':'header','required':True,'schema':{'type':'string'}})
    paths[route]={spec['method'].lower():op}
    req={'method':spec['method'],'header':([{'key':'X-Idempotency-Key','value':'{{$guid}}'}] if spec.get('idempotency') else []),'url':{'raw':'{{base_url}}'+route,'host':['{{base_url}}'],'path':route.strip('/').split('/')}}
    items.append({'name':spec['summary'],'request':req})
openapi={'openapi':'3.1.0','info':{'title':'Hotel PMS API','version':'1.0.0-rc9'},'paths':paths,'components':{'securitySchemes':{'tokenAuth':{'type':'apiKey','in':'header','name':'Authorization'}}},'security':[{'tokenAuth':[]}]}
postman={'info':{'name':'Hotel PMS API v1','schema':'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'},'variable':[{'key':'base_url','value':'https://your-site.example'}],'item':items}
outputs={root/'docs/openapi-v1.json':json.dumps(openapi,indent=2)+'\n',root/'docs/hotel-pms-v1.postman_collection.json':json.dumps(postman,indent=2)+'\n'}
check='--check' in sys.argv
for path,content in outputs.items():
    if check and (not path.exists() or path.read_text()!=content):print(f'API documentation drift: {path}');sys.exit(1)
    if not check:path.write_text(content)
