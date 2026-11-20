"""Generic GPT-5.5 artifact runner: isolated shell, public references, private checker."""
import argparse,base64,importlib,json,os,shutil,time,hashlib,sys
from pathlib import Path,PurePosixPath
from .run_aw06 import ChatClient,parse_json,write,append,ROOT
from .authored import SOURCE,read_json
from .english_packet import inputs
from .artifact_sandbox import execute
from .clarification import ClarificationUser
SYSTEM=('Return exactly one JSON object per turn, with no text before or after it. '
    'Every action has a top-level "tool" string. The output_format entries are examples of action objects; '
    'return the selected example object with your values, without wrapping it in its entry name.')
FORMAT=dict(shell={'tool':'shell','command':'shell command in /workspace; read inputs/ and references/; write deliverables under output/'},
    list_files={'tool':'list_files'},list_references={'tool':'list_references'},fetch_reference={'tool':'fetch_reference','name':'reference filename'},
    view_image={'tool':'view_image','path':'relative image path'},ask_user={'tool':'ask_user','question':'question text'},
    submit={'tool':'submit','result':{'summary':'final response','artifacts':['relative output file path']}})

def configure_host_dependencies():
    """Use the same provisioned analysis packages as the isolated judge."""
    for name in ('ea-bench-notebook-compat','ea-bench-judge-deps','ea-bench-analysis-deps'):
        path=Path('/tmp')/name
        if path.is_dir() and str(path) not in sys.path:
            sys.path.append(str(path))

def configure_judge_from_eval(client=None):
    configure_host_dependencies()
    from ea_bench.config import role_config
    client=client or ChatClient(role_config('judge'))
    cfg=client.config;os.environ['JUDGE_API_BASE']=cfg['base_url'];os.environ['JUDGE_MODEL']=cfg['model']
    os.environ['JUDGE_API_KEY']=os.environ[cfg['api_key_env']]
    return dict(model=cfg['model'],api_base=cfg['base_url'])

def safe_path(root,relative):
    p=PurePosixPath(relative)
    if p.is_absolute() or '..' in p.parts:raise ValueError('Expected relative path without traversal')
    root=Path(root).resolve();path=root.joinpath(*p.parts)
    if not path.resolve().is_relative_to(root):raise ValueError('Path leaves allowed directory')
    if any(q.is_symlink() for q in [path,*path.parents] if q.is_relative_to(root)):raise ValueError('Symlinks are not allowed')
    return path

def validate_public_references(case,folder,adapter):
    """Prevent reference fetching from undoing a variant's redactions."""
    from .english_packet import RELEASE
    protected={'RUBRICS.json','oracle.json','REVIEW.md','VARIANT_REVIEW.json','check.py','task_card.md','TASK_INSTRUCTIONS.txt'}
    local_names={p.name for base in [SOURCE/case/'variants/full/inputs',RELEASE/case/'variants/full/inputs'] for p in base.rglob('*') if p.is_file()}
    for name,spec in getattr(adapter,'REFERENCES',{}).items():
        source=Path(spec['path']).resolve()
        if source.name in protected:raise ValueError('Private/task metadata cannot be a public reference: '+name)
        in_packet=any(source.is_relative_to(base) and 'variants' in source.relative_to(base).parts for base in [SOURCE,RELEASE])
        if source.name in local_names or in_packet:
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            matches=[p for p in folder.rglob('*') if p.is_file() and p.name==source.name]
            if not any(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p in matches):
                raise ValueError('Reference would expose a different or omitted packet input: '+name)

def run(case,variant,out,adapter_name,world=None,max_actions=100):
    configure_host_dependencies()
    folder=inputs(case,variant);adapter=importlib.import_module(adapter_name)
    validate_public_references(case,folder,adapter)
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    private=out/'private';private.mkdir(mode=0o700);workspace=out/'workspace';workspace.mkdir();(workspace/'output').mkdir()
    cache=private/'reference_cache';cache.mkdir()
    oracle_path=Path(getattr(adapter,'ORACLE_PATH',SOURCE/case/'private/oracle.json')).resolve()
    if hasattr(adapter,'ORACLE_PATH'):
        from .english_packet import RELEASE
        if not oracle_path.is_relative_to(RELEASE/case/'private'):raise ValueError('Active oracle must belong to the assigned case private directory')
    oracle=read_json(oracle_path);spec=oracle['variants'][variant]
    world=world if world is not None else {k:oracle['atoms'][k]['default'] for k in spec['missing']+spec['conflict']}
    facts={k:world.get(k,v['default']) for k,v in oracle['atoms'].items()};write(private/'world.json',world)
    from ea_bench.config import role_config
    cfg=role_config('solver')
    client=ChatClient(cfg,on_response=lambda row:append(out/'api.jsonl',row))
    user_client=ChatClient(role_config('user'),on_response=lambda row:append(private/'user_api.jsonl',row))
    observation=dict(task_description=(folder.parent/'prompt.md').read_text(),output_format=FORMAT)
    user=ClarificationUser(user_client,observation['task_description'],adapter.knowledge(facts),lambda row:append(private/'user_dialogue.jsonl',row))
    write(out/'public_observation.json',observation);shutil.copytree(folder.parent,private/'packet')
    source_paths=list(Path(__file__).parent.glob('*.py'))+list((ROOT/'evaluation').glob('*.py'))
    for path in source_paths:
        target=private/'sources'/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(path.read_bytes())
    write(out/'implementation.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths})
    write(out/'configuration.json',dict(case=case,variant=variant,model=client.config['model'],max_actions=max_actions,
        validation_layer='authored_artifact',prompt_mode='task_description_and_generic_output_format',
        oracle_path=str(oracle_path.relative_to(ROOT)),oracle_sha256=hashlib.sha256(oracle_path.read_bytes()).hexdigest(),
        packet_hashes={str(p.relative_to(folder.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.parent.rglob('*') if p.is_file()}))
    messages=[dict(role='system',content=SYSTEM),dict(role='user',content=json.dumps(observation))]
    for message in messages:append(out/'dialogue.jsonl',message)
    started=time.monotonic();status='action_budget_exhausted';error=None;submitted=None;events=[]
    for turn in range(1,max_actions+1):
        try:raw=client.complete(messages)
        except Exception as exc:
            status='service_or_runtime_error';error=type(exc).__name__+': '+str(exc);break
        message=dict(role='assistant',content=raw);messages.append(message);append(out/'dialogue.jsonl',message)
        action=None
        try:
            action=parse_json(raw);tool=action.get('tool')
            if tool=='submit':
                if set(action)!={'tool','result'} or not isinstance(action['result'],dict):raise ValueError('Expected result object')
                submitted=action['result'];reply={'submission_received':True,'terminal':True};status='submitted'
            else:reply=dispatch(action,folder,workspace,cache,private,adapter,user)
        except (ValueError,TypeError,KeyError,FileNotFoundError) as exc:
            tool='invalid';reply={'error':str(exc)}
        except Exception as exc:
            status='service_or_runtime_error';error=type(exc).__name__+': '+str(exc);break
        event=dict(action=action,reply=reply);events.append(event);append(private/'events.jsonl',event)
        content=reply.pop('_image_content',None) if isinstance(reply,dict) and '_image_content' in reply else json.dumps(reply)
        message=dict(role='user',content=content);messages.append(message);append(out/'dialogue.jsonl',message)
        print(json.dumps(dict(turn=turn,tool=tool,terminal=status=='submitted')),flush=True)
        if status=='submitted':break
    write(private/'submission.json',submitted);write(private/'user_records.json',user.records)
    result=dict(case=case,variant=variant,model=client.config['model'],status=status,error=error,total_tool_calls=len(events),
        validation_layer='authored_artifact',evaluated_samples=int(status in {'submitted','action_budget_exhausted'}),success=None,
        seconds=round(time.monotonic()-started,3),usage=client.usage,model_api_attempts=client.calls,user_model_api_attempts=user_client.calls,
        ask_user_calls=sum(isinstance(e['action'],dict) and e['action'].get('tool')=='ask_user' for e in events),
        additional_information_items=user.information_items,
        completed_clarification_calls=len(user.records),
        unique_additional_information_items=user.unique_information_items,
        information_metric_scope='Delivered authored fact occurrences and distinct fact IDs; neither is a proven minimum or a bit count',
        tool_lower_bound=None,information_lower_bound=None,original_evaluator_runs=0)
    write(out/'metrics.json',result)
    if result['evaluated_samples']:
        artifact_dir=private/'artifacts';artifact_dir.mkdir()
        for p in (workspace/'output').rglob('*'):
            if p.is_symlink():raise RuntimeError('Submitted output contains a symlink')
            if p.is_file():
                dest=artifact_dir/p.relative_to(workspace/'output');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
        write(private/'artifact_hashes.json',{str(p.relative_to(artifact_dir)):hashlib.sha256(p.read_bytes()).hexdigest() for p in artifact_dir.rglob('*') if p.is_file()})
        configure_judge_from_eval()
        try:
            verdict=adapter.check(artifact_dir,private/'checker',variant,world);write(private/'verdict.json',verdict)
            result['checker_status']=verdict.get('status','reported');result['success']=verdict.get('status') in {'pass','passed'}
            if verdict.get('status') in {'unavailable','blocked','error'}:result['success']=None
        except Exception as exc:
            result.update(checker_status='infrastructure_error',checker_error=type(exc).__name__+': '+str(exc),success=None)
    from .judge_evidence import collect
    evidence=collect(case,private)
    write(private/'judge_evidence.json',evidence)
    result.update(original_rubric_judge_runs=evidence['original_rubric_judge_runs'],
        completed_judge_runs=evidence['completed_judge_runs'],native_environment_replays=0,
        original_evaluator_runs_scope='Legacy native environment counter; completed original-rubric judging is recorded separately')
    write(out/'metrics.json',result);print(json.dumps(result),flush=True);return result

def dispatch(action,folder,workspace,cache,private,adapter,user):
    tool=action.get('tool')
    if tool=='list_files' and set(action)=={'tool'}:return {'files':[str(p.relative_to(folder)) for p in sorted(folder.rglob('*')) if p.is_file()]}
    if tool=='list_references' and set(action)=={'tool'}:
        return {'references':[dict(name=k,url=v.get('url')) for k,v in adapter.REFERENCES.items()]}
    if tool=='fetch_reference' and set(action)=={'tool','name'}:
        name=action['name']
        if name not in adapter.REFERENCES:raise ValueError('Unknown reference filename')
        spec=adapter.REFERENCES[name];raw=Path(spec['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=spec['sha256']:raise RuntimeError('Reference integrity check failed')
        target=safe_path(cache,name);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        return dict(path='references/'+name,url=spec.get('url'),sha256=spec['sha256'],bytes=len(raw))
    if tool=='shell' and set(action)=={'tool','command'}:
        if not isinstance(action['command'],str) or not action['command'].strip():raise ValueError('Expected a shell command')
        return execute(folder.parent,workspace,action['command'],references=cache,timeout=180)
    if tool=='ask_user' and set(action)=={'tool','question'}:
        if not isinstance(action['question'],str) or not action['question'].strip():raise ValueError('Expected a question')
        return user.answer(action['question'])
    if tool=='view_image' and set(action)=={'tool','path'}:
        path=safe_path(workspace,action['path'])
        if path.stat().st_size>20*1024*1024:raise ValueError('Image exceeds 20 MiB')
        raw=path.read_bytes()
        if raw.startswith(b'\x89PNG\r\n\x1a\n'):mime='image/png'
        elif raw.startswith(b'\xff\xd8\xff'):mime='image/jpeg'
        else:raise ValueError('Expected a PNG or JPEG image')
        return {'_image_content':[dict(type='text',text='Image: '+action['path']),
            dict(type='image_url',image_url=dict(url='data:'+mime+';base64,'+base64.b64encode(raw).decode()))]}
    raise ValueError('Unknown tool or invalid fields')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',required=True,choices=['JB'+str(i).zfill(2) for i in range(1,31)])
    parser.add_argument('--variant',default='full')
    parser.add_argument('--out',required=True)
    parser.add_argument('--world',help='Private JSON file containing selected world values')
    parser.add_argument('--max-actions',type=int,default=100)
    args=parser.parse_args()
    if args.max_actions<1:parser.error('--max-actions must be positive')
    run(args.case,args.variant,args.out,'integrations.packet_stages.artifact_adapter_'+args.case.lower(),
        world=read_json(Path(args.world)) if args.world else None,max_actions=args.max_actions)

if __name__=='__main__':main()
