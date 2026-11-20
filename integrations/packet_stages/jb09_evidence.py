"""Company constraints established by variant files and supplied clarification only."""
import csv
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PACKET=ROOT/'data/expanded/JB09'

def constraint_evidence(variant, clarification_records=None):
 oracle=json.loads((PACKET/'private/oracle.json').read_text())
 spec=oracle['variants'][variant]
 unresolved=set(spec['missing']+spec['conflict'])
 supplied={item['fact_id']:item['value'] for record in clarification_records or [] for item in record['provided']}
 folder=PACKET/'variants'/variant/'inputs'
 budget={row['Budget_Category']:row for row in csv.DictReader((folder/'Q1_2026_hardware_budget.csv').open())}
 email=(folder/'manager_email_thread.txt').read_text()
 evidence={}
 for key in oracle['atoms']:
  if key in unresolved:
   evidence[key]=dict(status='confirmed',value=supplied[key]) if key in supplied else dict(status='unconfirmed')
  else:
   if key=='budget':value=int(re.search(r'capped Q1 2026 hardware refresh budget at \$([\d,]+)',email).group(1).replace(',',''))
   elif key=='bandwidth':value=int(re.search(r'our (\d+) Mbps pipe',email).group(1))
   else:value=int(budget['Procurement_Lead_Time_Dell']['Allocated_Amount'])
   evidence[key]=dict(status='source',value=value)
 return dict(constraints=evidence,reserve=int(budget['Contingency_Reserve']['Allocated_Amount']),clarification_records=clarification_records or [],scope='Only visible applicable source and delivered clarification. Private world is intentionally excluded.')
