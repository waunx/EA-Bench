"""Visible customer evidence plus actually delivered confirmations, without hidden-point selection."""
import json,openpyxl
from pathlib import Path

def build(packet,variant,records=()):
 packet=Path(packet);folder=packet/'variants'/variant/'inputs';oracle=json.loads((packet/'private/oracle.json').read_text())
 book=openpyxl.load_workbook(folder/'Customer_Satisfaction_Survey_Q4.xlsx',data_only=True);tables={}
 for sheet in book:
  rows=list(sheet.values);tables[sheet.title]=[dict(zip(rows[0],row)) for row in rows[1:]]
 book.close();survey=next(r for r in tables['Survey_Results'] if r['Response_ID']==1);complaint=next(r for r in tables['Complaint_Log'] if r['Complaint_ID']=='C-001')
 raw=dict(satisfaction=survey['Overall_Satisfaction'],severity=complaint['Severity'],plant=complaint['Plant_Code']);points={k:v for k,v in raw.items() if v is not None};confirmed={}
 for record in records:
  for item in record['provided']:
   if item['fact_id'] in raw:confirmed[item['fact_id']]=item['value']
 points.update(confirmed);unknown=[k for k,v in raw.items() if v is None and k not in confirmed]
 return dict(sourced_or_actually_confirmed_points=points,actually_confirmed_points=confirmed,unconfirmed_attributes=unknown,feasible_alternative_illustrations={k:[oracle['atoms'][k]['default'],oracle['atoms'][k]['alternative']] for k in unknown},visible_customer_tables=tables,visible_supplements={p.name:json.loads(p.read_text()) for p in folder.glob('*.json')},policy='Alternative illustrations are equally feasible, not a selected hidden truth or mandatory endpoints. Accept sourced/confirmed points or defensible conditional customer metrics and risk/sensitivity where unconfirmed. Do not require a question or invent a point score.')
