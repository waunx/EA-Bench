"""AW08 English packet and explicit existing-request metadata."""
import csv
import hashlib
import io
import json
import re
from .authored import SOURCE, read_json
from .english_packet import RELEASE

PACKET=RELEASE/'AW08'
REQUEST_IDS={'KEEP':'REQ90'}
CONSTRAINTS=('Reconcile lunch event LUNCH-0928 using the final food replies, settled prepayments and request register. '
    'Keep correct pending requests; cancel incorrect pending requests before creating replacements. '
    'Cancelled requests do not collect money. Preserve records for other events. '
    'Apply the attached convention when shared costs leave indivisible cents.')
RULES=('Only settled payments assigned to this event reduce balances; reversed payments do not. '
    'Use the highest reply revision for each participant. Request registers include pending and cancelled entries; '
    'historical requested amounts are not guaranteed to match the final food replies. Only pending requests collect money. '
    'Do not request money from SELF. New requests must be public with the note Lunch Meeting Order.\n')


def build():
    if (PACKET/'MANIFEST.json').exists():raise FileExistsError('English AW08 already exists')
    source=read_json(SOURCE/'AW08/SOURCE.json'); manifest={}
    for variant,hashes in read_json(SOURCE/'AW08/MANIFEST.json').items():
        manifest[variant]={}
        for name,digest in hashes.items():
            raw=(SOURCE/'AW08/variants'/variant/name).read_bytes()
            assert hashlib.sha256(raw).hexdigest()==digest
            text=raw.decode()
            if name=='prompt.md':text=source['original_text']+' '+CONSTRAINTS+'\n'
            elif name=='inputs/settlement_rules.md':text=RULES
            elif name.endswith('_records.json'):
                records=json.loads(text)
                for row in records:
                    if 'text' in row:
                        if 'rounding' in name:
                            row['text']='Allocate residual cents by person ID in '+row['value']+' order.'
                        elif 'pay18_state' in name:
                            row['text']='PAY18 settlement status: '+str(row['value'])+'.'
                        else:
                            row['text']='PAY17 settled amount: '+str(row['value'])+' cents.'
                text=json.dumps(records,indent=2)+'\n'
            if name in {'inputs/request_register.csv','inputs/request_archive.csv'}:
                rows=list(csv.DictReader(io.StringIO(text)))
                for row in rows:
                    row['request']=REQUEST_IDS.get(row['request'],row['request'])
                    row['public']='true' if row['event_ref']=='LUNCH-0928' else 'false'
                    row['note']='Lunch Meeting Order' if row['event_ref']=='LUNCH-0928' else 'Other event'
                stream=io.StringIO(); writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows); text=stream.getvalue()
            assert not re.search('[\u3400-\u9fff]',text),name
            target=PACKET/'variants'/variant/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(text.encode());manifest[variant][name]=hashlib.sha256(text.encode()).hexdigest()
    source.update(presentation_revision='English narrative and request metadata',authored_request_id_mapping=REQUEST_IDS,
                  added_fields='public/note on request registers: current-event requests are public with the required note; other-event metadata remains separate.')
    (PACKET/'SOURCE.json').write_text(json.dumps(source,indent=2)+'\n')
    (PACKET/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Authored AW08:',len(manifest),'variants')


if __name__=='__main__':build()
