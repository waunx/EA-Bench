"""WB07 visible metric/task records and authored task-board writes."""
from copy import deepcopy
from .packet_interface import PacketInterface,SYSTEM,OUTPUT_FORMAT
from .english_packet import inputs
from .english_wb07 import load,NeedFact
from .wb07_state import WB07Checker,initial_state,task_records
FIELDS=dict(board='board alias or ID',owner='person ID or email',status='task status',title='task title',due='YYYY-MM-DD or null')
API_FORMATS=dict(get_context={},list_metrics={},list_tasks={},list_task_history={},list_boards={},list_people={},
    create_task=FIELDS,update_task=dict(task='task ID',**FIELDS))
class OpenWB07(PacketInterface):
    case='WB07';validation_layer='authored_fixture';api_formats=API_FORMATS;need_fact_error=NeedFact
    fact_labels=dict(qa='Backfill acceptance',t3_owner='Task owner',p2_sessions='Measured session count')
    def __init__(self,variant='full',answers=None,ask_handler=None):
        self.variant,self.folder=variant,inputs('WB07',variant);self.data=load(variant)
        self.answers,self.confirmed=deepcopy(answers or {}),{}
        self.state=initial_state(self.data,self.answers);self.checker=WB07Checker(variant,self.answers,self)
        self.files={p.name:p for p in self.folder.iterdir() if p.is_file()}
        self.events,self.calls,self.effects=[],[],{};self.public_writes=set()
        self.done=False;self.result=None;self.ask_handler=ask_handler
    def call(self,name,args):
        if name not in API_FORMATS:raise ValueError('Unknown API')
        if set(args)!=set(API_FORMATS[name]):raise ValueError('Arguments must match API format')
        if name=='get_context':return deepcopy(self.data['analytics_context.json'])
        if name=='list_metrics':return {'partitions':deepcopy(self.data['metric_partitions.csv']+self.data.get('metric_history.csv',[]))}
        if name=='list_boards':return {'aliases':deepcopy(self.data['board_aliases.csv'])}
        if name=='list_people':return {'people':deepcopy(self.data['people.csv'])}
        if name=='list_task_history':return {'history':deepcopy(self.data['completed_tasks.csv']+self.data.get('task_archive.csv',[])+self.data.get('task_worklog.csv',[]))}
        if name=='list_tasks':
            public=task_records(self.data);old={r['task'] for r in public};state={r['task']:r for r in self.state['tasks']}
            return {'tasks':[deepcopy(state[r['task']]) if r['task'] in self.public_writes else r for r in public]+[deepcopy(r) for k,r in state.items() if k not in old]}
        return self.write(name,args)
    def write(self,name,args):
        from datetime import date
        if any(not isinstance(v,str) or not v.strip() for k,v in args.items() if k!='due'):raise ValueError('Expected nonempty strings')
        if args['due'] is not None:date.fromisoformat(args['due'])
        people={r['owner']:r['email'] for r in self.data['people.csv']}
        owner=people.get(args['owner'],args['owner'])
        if owner not in people.values():raise ValueError('Unknown person')
        boards={r['alias'].casefold():r['canonical'] for r in self.data['board_aliases.csv']}
        boards.update({r['canonical'].casefold():r['canonical'] for r in self.data['board_aliases.csv']})
        board=boards.get(args['board'].casefold())
        if board is None:raise ValueError('Unknown board')
        status=args['status'].lower()
        if status not in {'backlog','in progress','in review','completed','done','reopened'}:raise ValueError('Unknown task status')
        rows=self.state['tasks'];before=deepcopy(rows)
        if name=='create_task':
            identity='T'+str(1000+len(rows));row=dict(task=identity,revision=1,board=board,owner=owner,status=status,title=args['title'],due=args['due']);rows.append(row)
        else:
            matches=[r for r in rows if r['task']==args['task']]
            if len(matches)!=1:raise ValueError('Unknown task')
            row=matches[0];row.update(board=board,owner=owner,status=status,title=args['title'],due=args['due'])
        if before!=rows:self.state['task_events'].append(dict(op=name,record=deepcopy(row)))
        self.public_writes.add(row['task']);self.calls.append(name)
        return dict(task=row['task'],status='saved')
