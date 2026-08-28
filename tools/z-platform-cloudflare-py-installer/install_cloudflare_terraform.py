#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, re, shutil, stat, subprocess, sys
from pathlib import Path

TOKEN_RE=re.compile(r'^[A-Za-z0-9_-]+$')
HEX32_RE=re.compile(r'^[A-Fa-f0-9]{32}$')
UUID_RE=re.compile(r'^[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}$')
STACK_REL=Path('infrastructure/terraform/cloudflare')
ADDR='cloudflare_dns_record.app_routes["phase6"]'

class Error(RuntimeError): pass

def log(s): print(f'\n==> {s}', flush=True)
def run(cmd,cwd=None,env=None,check=True,capture=False):
    print('+ executing command (arguments omitted)',flush=True)
    return subprocess.run(cmd,cwd=cwd,env=env,check=check,text=True,capture_output=capture)

def parse_env(path:Path):
    if not path.is_file(): raise Error(f'Missing env file: {path}')
    out={}
    for n,raw in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
        line=raw.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('export '): line=line[7:].lstrip()
        if '=' not in line: continue
        k,v=line.split('=',1); k=k.strip(); v=v.strip()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',k): raise Error(f'{path}:{n}: invalid variable name')
        if len(v)>=2 and v[0]==v[-1] and v[0] in "'\"": v=v[1:-1]
        if '$(' in v or '`' in v: raise Error(f'{path}:{n}: command substitution forbidden')
        out[k]=v.replace('\r','').replace('\n','')
    return out

def validate(v):
    req=['CLOUDFLARE_API_TOKEN','CLOUDFLARE_ACCOUNT_ID','CLOUDFLARE_ZONE_ID','CLOUDFLARE_TUNNEL_ID']
    for k in req: print(f'{k}: '+(f'configured (length={len(v.get(k,""))})' if v.get(k) else 'MISSING'))
    missing=[k for k in req if not v.get(k)]
    if missing: raise Error('Missing: '+', '.join(missing))
    if not TOKEN_RE.fullmatch(v['CLOUDFLARE_API_TOKEN']): raise Error('Invalid Cloudflare API token character set')
    if not HEX32_RE.fullmatch(v['CLOUDFLARE_ACCOUNT_ID']): raise Error('Account ID must be 32 hex characters')
    if not HEX32_RE.fullmatch(v['CLOUDFLARE_ZONE_ID']): raise Error('Zone ID must be 32 hex characters')
    if not UUID_RE.fullmatch(v['CLOUDFLARE_TUNNEL_ID']): raise Error('Tunnel ID must be UUID')

def ensure_tools():
    miss=[x for x in ('git','terraform','curl') if shutil.which(x) is None]
    if miss: raise Error('Missing commands: '+', '.join(miss))

def checkout(repo:Path,branch:str,skip:bool):
    if not (repo/'.git').exists(): raise Error(f'Not a git repository: {repo}')
    if skip: return
    run(['git','fetch','origin',branch],cwd=repo)
    local=run(['git','show-ref','--verify','--quiet',f'refs/heads/{branch}'],cwd=repo,check=False)
    if local.returncode==0:
        run(['git','switch',branch],cwd=repo); run(['git','pull','--ff-only','origin',branch],cwd=repo)
    else: run(['git','switch','--track',f'origin/{branch}'],cwd=repo)

def ensure_stack(stack:Path):
    need={'providers.tf','variables.tf','main.tf','outputs.tf','terraform.tfvars.example'}
    have={p.name for p in stack.glob('*') if p.is_file()}
    missing=sorted(need-have)
    if missing: raise Error(f'Incomplete Terraform stack at {stack}; missing: {", ".join(missing)}')

def write_tfvars(path:Path,v,hostname,origin,port):
    q=json.dumps
    text=f'''cloudflare_account_id = {q(v["CLOUDFLARE_ACCOUNT_ID"])}\ncloudflare_zone_id    = {q(v["CLOUDFLARE_ZONE_ID"])}\ncloudflare_tunnel_id  = {q(v["CLOUDFLARE_TUNNEL_ID"])}\n\napp_routes = {{\n  phase6 = {{\n    app_id      = "phase6-api"\n    hostname    = {q(hostname)}\n    origin      = {q(origin)}\n    port        = {port}\n    role        = "phase6-readiness"\n    status      = "active"\n    health_path = "/health"\n  }}\n}}\n'''
    path.write_text(text,encoding='utf-8'); path.chmod(stat.S_IRUSR|stat.S_IWUSR)

def exclusions(repo:Path):
    p=repo/'.git/info/exclude'; p.parent.mkdir(parents=True,exist_ok=True)
    wanted=['.env.cloudflare','**/terraform.tfvars','*.tfstate','*.tfstate.*','**/.terraform/','**/tfplan','**/tfplan.json']
    old=p.read_text(encoding='utf-8').splitlines() if p.exists() else []
    add=[x for x in wanted if x not in old]
    if add:
        with p.open('a',encoding='utf-8') as f:
            if p.exists() and p.stat().st_size: f.write('\n')
            f.write('\n'.join(add)+'\n')

def tfenv(v):
    e=os.environ.copy(); e.update({'TF_IN_AUTOMATION':'1','TF_INPUT':'0','TF_VAR_cloudflare_api_token':v['CLOUDFLARE_API_TOKEN'],'TF_VAR_cloudflare_account_id':v['CLOUDFLARE_ACCOUNT_ID'],'TF_VAR_cloudflare_zone_id':v['CLOUDFLARE_ZONE_ID'],'TF_VAR_cloudflare_tunnel_id':v['CLOUDFLARE_TUNNEL_ID']}); return e

def lookup(v,hostname):
    url=f'https://api.cloudflare.com/client/v4/zones/{v["CLOUDFLARE_ZONE_ID"]}/dns_records?name={hostname}'
    r=run(['curl','-fsS','-H',f'Authorization: Bearer {v["CLOUDFLARE_API_TOKEN"]}','-H','Content-Type: application/json',url],capture=True)
    data=json.loads(r.stdout)
    if not data.get('success'): raise Error('Cloudflare DNS lookup failed')
    rows=data.get('result',[])
    if len(rows)>1: raise Error(f'Multiple records found for {hostname}')
    return rows[0] if rows else None

def in_state(stack,e):
    r=run(['terraform','state','list'],cwd=stack,env=e,check=False,capture=True)
    return r.returncode==0 and ADDR in r.stdout.splitlines()

def plan_summary(stack,e):
    r=run(['terraform','show','-json','tfplan'],cwd=stack,env=e,capture=True)
    data=json.loads(r.stdout); result={'create':[],'update':[],'delete_or_replace':[]}
    for rc in data.get('resource_changes',[]):
        a=rc.get('address','?'); acts=rc.get('change',{}).get('actions',[])
        if 'delete' in acts: result['delete_or_replace'].append(a)
        elif 'create' in acts: result['create'].append(a)
        elif 'update' in acts: result['update'].append(a)
    print(json.dumps(result,indent=2))
    if result['delete_or_replace']: raise Error('Plan contains delete/replace actions')

def main():
    p=argparse.ArgumentParser(description='Safe Cloudflare Terraform installer for z-platform')
    p.add_argument('--repo',type=Path,default=Path.home()/'z-platform')
    p.add_argument('--env-file',type=Path)
    p.add_argument('--branch',default='feat/cloudflare-terraform-stack')
    p.add_argument('--hostname',default='phase6.zeaz.dev')
    p.add_argument('--origin',default='http://phase6-api:8080')
    p.add_argument('--port',type=int,default=8080)
    p.add_argument('--skip-checkout',action='store_true')
    p.add_argument('--import-existing',action='store_true')
    p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    try:
        ensure_tools(); repo=a.repo.expanduser().resolve(); envfile=(a.env_file.expanduser().resolve() if a.env_file else repo/'.env.cloudflare'); stack=repo/STACK_REL
        v=parse_env(envfile); log('Validating inputs'); validate(v)
        checkout(repo,a.branch,a.skip_checkout); ensure_stack(stack); exclusions(repo)
        log('Writing terraform.tfvars without credentials'); write_tfvars(stack/'terraform.tfvars',v,a.hostname,a.origin,a.port)
        e=tfenv(v)
        log('Formatting, initializing, and validating'); run(['terraform','fmt','-check','-recursive'],cwd=stack,env=e); run(['terraform','init','-upgrade'],cwd=stack,env=e); run(['terraform','validate'],cwd=stack,env=e)
        log(f'Checking existing DNS record: {a.hostname}'); rec=lookup(v,a.hostname)
        if rec:
            print(json.dumps({'existing_record':True,'id':rec.get('id'),'name':rec.get('name'),'type':rec.get('type'),'content':rec.get('content'),'proxied':rec.get('proxied')},indent=2))
            if not in_state(stack,e):
                if not a.import_existing: raise Error('Existing DNS record is unmanaged. Re-run with --import-existing')
                run(['terraform','import',ADDR,f'{v["CLOUDFLARE_ZONE_ID"]}/{rec["id"]}'],cwd=stack,env=e)
        else: print(json.dumps({'existing_record':False,'hostname':a.hostname}))
        log('Creating plan'); run(['terraform','plan','-out=tfplan'],cwd=stack,env=e); plan_summary(stack,e)
        if a.apply:
            if rec and not in_state(stack,e): raise Error('Refusing apply: record not imported')
            log('Applying reviewed non-destructive plan'); run(['terraform','apply','tfplan'],cwd=stack,env=e)
        else:
            print(f'\nPlan ready. Review with:\n  terraform -chdir={stack} show -no-color tfplan\nApply was not performed.')
        return 0
    except (Error,subprocess.CalledProcessError,json.JSONDecodeError,OSError) as exc:
        print(f'\nERROR: {exc}',file=sys.stderr); return 1

if __name__=='__main__': raise SystemExit(main())
