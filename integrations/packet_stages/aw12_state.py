"""AW12 complete new-account migration, unchanged existing accounts and integrity timing."""
from copy import deepcopy
from .authored import reviewed_worlds
from .english_aw12 import load,solve,fact
from .acceptance import CheckResult
from .session import BindingError,canonical

def same(a,b):return canonical(a)==canonical(b)
def initial_state(data):
    return dict(source_data=deepcopy(data),accounts=deepcopy(data['account_registry.json']),migration_events=[])

def normalized(account):
    if not isinstance(account,dict) or set(account)!={'owner','songs','albums','playlists'}:return None
    playlists=account['playlists']
    if not isinstance(playlists,list) or any(not isinstance(p,dict) or set(p)!={'playlist','name','private','tracks'} for p in playlists):return None
    if len({p['playlist'] for p in playlists})!=len(playlists):return None
    return dict(songs=account['songs'],albums=account['albums'],
        playlists=sorted([{k:v for k,v in p.items() if k!='playlist'} for p in playlists],key=lambda p:p['name']))

class AW12Checker:
    def __init__(self,variant,answers,backend):
        self.data=load(variant);self.target=solve(self.data,answers);self.batch=fact(self.data,'batch',answers)
        matches=[e for a,e in reviewed_worlds('AW12',variant) if same(a,answers)]
        if len(matches)!=1 or not same(matches[0],self.target):raise BindingError('AW12 reviewed result mismatch')
        self.backend,self.initial=backend,backend.snapshot()
        if not same(self.initial,initial_state(self.data)):raise BindingError('AW12 initial state mismatch')
    def final(self,report):
        state=self.backend.snapshot();accounts=state.get('accounts',{});old=self.initial['accounts']
        new={k:v for k,v in accounts.items() if k not in old};single=len(new)==1
        account=next(iter(new.values())) if single else None
        expected=dict(self.target,playlists=sorted(self.target['playlists'],key=lambda p:p['name']))
        ledger,timing=self.replay(state)
        checks=dict(one_new_user_account=single and account.get('owner')=='self',
            exact_migrated_content=single and same(normalized(account),expected),
            existing_accounts_preserved=all(same(accounts.get(k),v) for k,v in old.items()),
            migration_effect_ledger=ledger,selected_backup_verified_before_migration=timing,
            source_records_preserved=same(state.get('source_data'),self.initial['source_data']),
            state_fields_preserved=set(state)==set(self.initial),
            report=isinstance(report,dict) and set(report)=={'summary'} and isinstance(report['summary'],str) and bool(report['summary'].strip()))
        return CheckResult.evaluated('authored_state',checks,backend='authored_fixture')
    def replay(self,state):
        accounts=deepcopy(self.initial['accounts']);verified=False;timing=True
        try:
            for event in state.get('migration_events',[]):
                op=event['op']
                if op=='verify_backup':
                    name=event['file']
                    if set(event)!={'op','file','sha256'} or event['sha256']!=self.data['digests'][name]:return False,False
                    if name==self.batch:verified=True
                    continue
                identity=event['account']
                if op=='create_account':
                    if set(event)!={'op','account'} or identity in accounts:return False,False
                    accounts[identity]=dict(owner='self',songs=[],albums=[],playlists=[]);continue
                if not verified:timing=False
                account=accounts[identity]
                if op in {'add_song','add_album'}:
                    key='track' if op=='add_song' else 'album';field='songs' if key=='track' else 'albums'
                    if set(event)!={'op','account',key} or event[key] in account[field]:return False,False
                    account[field].append(event[key]);account[field].sort()
                elif op in {'create_playlist','update_playlist'}:
                    if set(event)!={'op','account','playlist','name','private','tracks'}:return False,False
                    record={k:deepcopy(v) for k,v in event.items() if k not in {'op','account'}}
                    matches=[p for p in account['playlists'] if p['playlist']==event['playlist']]
                    if op=='create_playlist':
                        if matches:return False,False
                        account['playlists'].append(record)
                    else:
                        if len(matches)!=1:return False,False
                        matches[0].update(record)
                else:return False,False
        except (KeyError,TypeError,ValueError):return False,False
        return same(accounts,state.get('accounts')),verified and timing
