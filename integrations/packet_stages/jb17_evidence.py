"""Full JB17 source controls; preserve unmatched identities and missing cells."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal
import csv,json,hashlib,openpyxl
ROOT=Path(__file__).resolve().parents[2]
PACKET=ROOT/'data/expanded/JB17'

def table(sheet,header_row):
 rows=list(sheet.values);keys=list(rows[header_row-1])
 return [dict(zip(keys,row)) for row in rows[header_row:] if row[0] is not None]

def source_evidence(variant):
 p=PACKET/'variants'/variant/'inputs'
 refs=json.loads((PACKET/'private/reference_controls.json').read_text())
 refroot=ROOT/'data/source/dataset/computer_and_information_systems_managers/task2/files_required_to_search'
 for name,row in refs.items():assert hashlib.sha256((refroot/name).read_bytes()).hexdigest()==row['sha256']
 with (p/'ITSM_incident_data_q4.csv').open(encoding='utf-8-sig',newline='') as f:incidents=list(csv.DictReader(f))
 by_ci=Counter(r['CI_Name'] for r in incidents);groups=defaultdict(list);categories=defaultdict(list)
 for r in incidents:
  groups[r['CI_Cat']].append(int(r['No_of_Reassignments']))
  categories[r['Category']].append(int(r['No_of_Reassignments']))
 w=openpyxl.load_workbook(p/'IT_Infrastructure_Inventory.xlsx',data_only=True)
 assets=table(w['Asset_Inventory'],1);w.close()
 w=openpyxl.load_workbook(p/'IT_Budget_Q4_2024.xlsx',data_only=True)
 budget={s.title:table(s,4) for s in w};w.close()
 cloud=[r for r in budget['Cloud_Cost_Detail'] if r.get('Service Provider')!='TOTAL']
 sums={k:str(sum(Decimal(str(r[k])) for r in cloud if isinstance(r.get(k),(int,float)))) for k in ['Monthly Cost','Q4 Budget','Q4 Actual MTD','YTD Spend']}
 ids={r['Asset_ID'] for r in assets}
 return dict(incident_rows=len(incidents),distinct_incident_ids=len({r['Incident_ID'] for r in incidents}),distinct_ci_names=len(by_ci),ci_counts=dict(by_ci),
  top_incident_cis=by_ci.most_common(10),
  reassignment_by_ci_category={k:dict(count=len(v),total=sum(v),mean=sum(v)/len(v),maximum=max(v)) for k,v in groups.items()},
  reassignment_by_incident_category={k:dict(count=len(v),total=sum(v),mean=sum(v)/len(v),maximum=max(v)) for k,v in categories.items()},
  inventory_assets=assets,exact_ci_asset_id_matches=sorted(set(by_ci)&ids),
  budget_source_tables=budget,cloud_detail_known_totals=sums,official_reference_extracts=refs,
  input_hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in p.iterdir() if f.is_file()},
  interpretation='Do not invent an identity crosswalk from different ID conventions. Report exact/unmatched records and distinguish inventory-reported incident counts from event-log counts. Missing budget cells remain missing; cloud MTD, monthly, quarterly and annual figures are different periods, and project allocation must be justified.')
