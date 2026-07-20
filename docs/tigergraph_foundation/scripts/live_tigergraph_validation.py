#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,ssl,sys,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def request(url,method='GET',body=None,token='',verify=True,timeout=120):
    headers={'Accept':'application/json'}
    data=None
    if body is not None:
        headers['Content-Type']='application/json'; data=json.dumps(body).encode()
    if token: headers['Authorization']='Bearer '+token
    context=None if verify else ssl._create_unverified_context()
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=timeout,context=context) as response:
        return json.loads(response.read().decode())

def main():
    p=argparse.ArgumentParser(description='Validate installed iPerform schema, data and 43 GSQL queries against live TigerGraph RESTPP.')
    p.add_argument('--restpp-url',default=os.getenv('TIGERGRAPH_RESTPP_URL','http://localhost:14240/restpp'))
    p.add_argument('--token',default=os.getenv('TIGERGRAPH_TOKEN',''))
    p.add_argument('--graph',default=os.getenv('GRAPH_NAME','iperform_insights_coaching_demo'))
    p.add_argument('--no-verify-ssl',action='store_true')
    args=p.parse_args(); base=args.restpp_url.rstrip('/')
    if not base.endswith('/restpp'): base+='/restpp'
    verify=not args.no_verify_ssl
    result={'status':'PASS','restpp_url':base,'graph':args.graph,'started_at':time.time(),'cardinality':[],'queries':[],'errors':[]}
    try:
        echo=request(base+'/echo',token=args.token,verify=verify)
        result['echo']=echo
    except Exception as exc:
        result['status']='FAIL'; result['errors'].append('RESTPP echo failed: '+str(exc)); finish(result); return 1
    manifest=json.load(open(ROOT/'data/manifest.json'))
    expected={'vertex':{},'edge':{}}
    for entry in manifest['files']:
        expected[entry['kind']][entry['target']]=entry['expected_rows']
    for kind,function,type_key in [('vertex','stat_vertex_number','v_type'),('edge','stat_edge_number','e_type')]:
        try:
            data=request(f'{base}/builtins/{args.graph}',method='POST',body={'function':function,'type':'*'},token=args.token,verify=verify)
            actual={x[type_key]:int(x.get('count',0)) for x in data.get('results',[])}
            for target,exp in sorted(expected[kind].items()):
                act=actual.get(target,0); status='PASS' if act==exp else 'FAIL'
                result['cardinality'].append({'kind':kind,'target':target,'expected':exp,'actual':act,'status':status})
                if status=='FAIL': result['status']='FAIL'
        except Exception as exc:
            result['status']='FAIL'; result['errors'].append(f'{kind} cardinality failed: {exc}')
    cases=json.load(open(ROOT/'tests/query_cases.json'))['cases']
    for case in cases:
        query=urllib.parse.urlencode(case.get('params',{}))
        url=f'{base}/query/{args.graph}/{case["query_name"]}'+(('?'+query) if query else '')
        started=time.time()
        try:
            data=request(url,token=args.token,verify=verify)
            result_objects=data.get('results',[]) if isinstance(data.get('results',[]),list) else []
            actual_keys=set()
            for item in result_objects:
                if isinstance(item,dict): actual_keys.update(item.keys())
            normalize=lambda value: ''.join(ch for ch in str(value).lower() if ch.isalnum())
            normalized_actual={normalize(k) for k in actual_keys}
            required=case.get('required_result_keys',[])
            missing=[k for k in required if normalize(k) not in normalized_actual]
            status='FAIL' if data.get('error') or missing else 'PASS'
            result['queries'].append({'id':case['id'],'query_name':case['query_name'],'status':status,'elapsed_ms':round((time.time()-started)*1000,1),'result_objects':len(result_objects),'actual_result_keys':sorted(actual_keys),'required_result_keys':required,'missing_result_keys':missing,'message':data.get('message','')})
            if status=='FAIL': result['status']='FAIL'
        except Exception as exc:
            result['status']='FAIL'; result['queries'].append({'id':case['id'],'query_name':case['query_name'],'status':'FAIL','elapsed_ms':round((time.time()-started)*1000,1),'error':str(exc)})
    finish(result); return 0 if result['status']=='PASS' else 1

def finish(result):
    result['completed_at']=time.time()
    out=ROOT/'reports/live_tigergraph_validation.json'; out.parent.mkdir(exist_ok=True); out.write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Live TigerGraph Validation','',f"**Status:** {result['status']}",'',f"- Cardinality checks: {len(result.get('cardinality',[]))}",f"- Query cases: {len(result.get('queries',[]))}",f"- Errors: {len(result.get('errors',[]))}",'','## Query Results']
    lines += [f"- {x['status']} — {x['id']} {x['query_name']} ({x.get('elapsed_ms','?')} ms)" for x in result.get('queries',[])]
    if result.get('errors'): lines += ['','## Errors']+[f"- {e}" for e in result['errors']]
    (ROOT/'reports/live_tigergraph_validation.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'status':result['status'],'cardinality_checks':len(result.get('cardinality',[])),'query_cases':len(result.get('queries',[])),'errors':result.get('errors',[])},indent=2))

if __name__=='__main__': sys.exit(main())
