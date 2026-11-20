from pathlib import Path
import json,hashlib,os,threading
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'evaluation/runs/packet-eval-20260930-low8-mc'
ERRORS={'service_or_runtime_error','runner_error','user_agent_error','timeout'}
def read(p,default=None):
    try:return json.loads(Path(p).read_text())
    except (OSError,ValueError):return default
def write(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+f'.tmp-{os.getpid()}-{threading.get_ident()}');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
_HASHES={}
def sha(p):
    p=Path(p);st=p.stat();stamp=(st.st_mtime_ns,st.st_size)
    if p not in _HASHES or _HASHES[p][0]!=stamp:_HASHES[p]=(stamp,hashlib.sha256(p.read_bytes()).hexdigest())
    return _HASHES[p][1]
def folder(run,model,eid):
    key=model+'/'+eid;overrides=read(run/'record_overrides.json',{})
    if key in overrides:return run/overrides[key]['path']
    phase=read(run/'active_phase.json',{}).get('full','full')
    return run/phase/model/eid
