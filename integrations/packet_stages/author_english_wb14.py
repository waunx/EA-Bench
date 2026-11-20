"""WB14 English cross-application narrative and neutral board identifiers."""
import csv,hashlib,io,json,re
from .authored import SOURCE,read_json
from .english_packet import RELEASE
PACKET=RELEASE/'WB14'
BOARDS={'B_FE':'B101','B_OLD':'B102','B_APP':'B103'}
NARRATIVE=('Use the accepted metric revisions and the contact and workspace bindings for this follow-up. '
    'Honor calendar cancellation state and historical owner aliases. Keep the two branches exclusive. '
    'CRM reassignment covers current undeleted Leads only; preserve customers, other owners and deleted records.')
RULES=('Use the snapshot date and working window in operation_context.json. The visit window includes October 1 of that year through the snapshot date. '
    'Use the highest accepted revision for each bucket; pending backfill requires its quality acceptance. Test strictly above 10. '
    'Tomorrow is the next calendar day. For self-owned appointments, confirmed and tentative intervals are busy and cancelled ones are free; intervals are half-open. '
    'Next Friday means Friday of the following Monday-based calendar week. '
    'The true branch creates only the requested task and meeting. The other branch sends the exact original email first, then reassigns Nadia\'s current Leads using normalized aliases.\n')
def build():
    if (PACKET/'MANIFEST.json').exists():raise FileExistsError('WB14 already exists')
    source=read_json(SOURCE/'WB14/SOURCE.json');manifest={}
    for variant,hashes in read_json(SOURCE/'WB14/MANIFEST.json').items():
        files={};manifest[variant]={}
        for name,digest in hashes.items():
            raw=(SOURCE/'WB14/variants'/variant/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
            value=raw.decode()
            if name=='prompt.md':value=source['original_text']+' '+NARRATIVE+'\n'
            elif name=='inputs/execution_rules.md':value=RULES
            elif name=='inputs/case_decision.md':value='The quality review for backfill QC2 is accepted.\n'
            elif name=='inputs/boards.csv':
                rows=list(csv.DictReader(io.StringIO(value)))
                for r in rows:r['id']=BOARDS[r['id']]
                value=csv_text(rows)
            elif name in {'inputs/calendar.csv','inputs/calendar_history.csv'}:
                rows=list(csv.DictReader(io.StringIO(value)))
                for r in rows:r.update(title='Existing appointment',attendees='[]')
                value=csv_text(rows)
            files[name]=value
        files['inputs/operation_context.json']=json.dumps(dict(snapshot_date='2023-11-30',working_start=540,working_end=1020),indent=2)+'\n'
        for name,value in files.items():
            assert not re.search('[\u3400-\u9fff]',value),name
            p=PACKET/'variants'/variant/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value.encode())
            manifest[variant][name]=hashlib.sha256(value.encode()).hexdigest()
    source.update(presentation_revision='English narrative; calculated dates replaced with calendar rules; neutral board IDs',authored_board_mapping=BOARDS,
        added_datasets='operation_context.json relocates the clock/window; calendar titles and attendee lists are authored preservation metadata')
    (PACKET/'SOURCE.json').write_text(json.dumps(source,indent=2)+'\n')
    (PACKET/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Authored WB14',len(manifest),'variants')
def csv_text(rows):
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows);return stream.getvalue()
if __name__=='__main__':build()
