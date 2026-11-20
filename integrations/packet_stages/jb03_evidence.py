"""Source-only HPC survey context, permitting honest conditional planning."""
import json,csv
from functools import lru_cache
from copy import deepcopy
from .validate_jb03 import load,metrics,resolve_exports
from .author_english_jb03 import RELEASE

@lru_cache(maxsize=32)
def source_context(folder,signature):
    import openpyxl
    vendor=openpyxl.load_workbook(folder/'vendor_hardware_quote.xlsx',data_only=True)
    peers=openpyxl.load_workbook(folder/'nsf_herd_cs_rd_expenditures.xlsx',data_only=True)
    return dict(original_schedule=list(csv.DictReader((folder/'project_schedule_wbs.csv').open())),
        vendor_source_rows={s.title:list(s.values) for s in vendor},
        nsf_fy2023_thousands=[dict(institution=r[0],total=r[8]) for r in peers.active.values
            if isinstance(r[1],(int,float)) and isinstance(r[8],(int,float))])

def build(variant,world=None,clarification_records=None):
    data=load(variant);folder=RELEASE/'variants'/variant/'inputs'
    oracle=json.loads((RELEASE/'private/oracle.json').read_text());unresolved=[]
    for key,a in oracle['atoms'].items():
        row=next(r for r in data[a['table']] if r['id']==a['id'])
        if row[a['field']] not in ['',None]:continue
        path=folder/(key+'_records.json');value=resolve_exports(json.loads(path.read_text())) if path.exists() else None
        for record in clarification_records or []:
            for fact in record.get('provided',[]):
                if fact.get('fact_id')==key:value=fact['value']
        row[a['field']]=value
        if value is None:unresolved.append(dict(table=a['table'],id=a['id'],field=a['field']))
    context=dict(survey=data,unresolved_fields=unresolved,
        policy='Use only the visible rows and actually supplied confirmations. Unknown cells are null; no private selected values are expectations. Quantified conditional scenarios, applicable observed partial aggregates, sensitivities and verification recommendations are acceptable when conclusions are honest and all deliverables reconcile. Do not require questions or invention. Fixed historical full-data counts are not requirements for unresolved or alternative data. Per-researcher versus workload-tier memory conventions must be explicitly and consistently explained.')
    if not unresolved:context['independently_recomputed_metrics']=metrics(data)
    rows=data['computing_needs']
    context['observed_numeric_checks']=dict(
        storage_tb=sum(r['storage_tb_required'] for r in rows),
        observed_monthly_gpu_hours=sum(r['gpu_hours_monthly'] for r in rows if r['gpu_hours_monthly'] is not None),
        unknown_gpu_hour_rows=sum(r['gpu_hours_monthly'] is None for r in rows),
        procurement_after_discount=2713000*.95,
        procurement_with_contingency=2713000*.95*1.10,
        corrected_pre_pue_kw=86.22,annual_power_cash=86.22*1.5*.09*8760,
        quoted_gpu_count=64,quoted_annual_calendar_gpu_hours=64*8760,
        note='Quoted-cluster arithmetic is a comparison baseline; justified alternate footprints need their own quantities and loads. Unknown demand is not zero.')
    names=['vendor_hardware_quote.xlsx','nsf_herd_cs_rd_expenditures.xlsx','project_schedule_wbs.csv']
    signature=tuple(((folder/n).stat().st_mtime_ns,(folder/n).stat().st_size) for n in names)
    context.update(deepcopy(source_context(folder,signature)))
    return context
