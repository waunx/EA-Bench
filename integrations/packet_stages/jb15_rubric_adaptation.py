"""Preserve all six JB15 rubric groups; adapt only unresolved US metadata clauses."""
from copy import deepcopy

def adapt(original,context):
 active=deepcopy(original);before=deepcopy(original[2]);active[2]['rubric']='Does country_metadata retain all study countries, regions and sourced/actually confirmed numerical indicators with auditable verification for previously unresolved inputs?'
 active[2]['criterion']=[
 'Retain all 15 countries and regions and all sourced or actually confirmed original macro values. Previously unresolved US fields require an auditable determining source; numerical country coverage must remain complete. Do not substitute hidden defaults or silently drop the United States.',
 'Keep unaffected spot checks: Kenya (2080,0.4,0.75,55.1), Germany (51380,8.1,0.25,84.4), Nigeria (2180,0.6,0.78,223.8), Australia (65100,15.0,0.38,26.0), and US population331.9. US GDP/CO2/vulnerability must match sourced/actually confirmed points in the private reference context; unconfirmed fields have no selected expected point.',
 'No countries may be missing and no verified source values may be altered without justification. For previously unresolved fields, assess verification evidence rather than matching one private alternative. Source context is evaluator evidence, not required output text.']
 import json
 active[2]['rubric']+=' Private context: '+json.dumps(context)
 return active,dict(scope='Only metadata rubric header and its three US-related clauses adapted; all six rubric groups/weights preserved and every other criterion byte-identical.',original_metadata_rubric=before,adapted_metadata_criteria=active[2]['criterion'],adapted_criteria=3,unchanged_blocking_criteria=sum(len(r['criterion']) for i,r in enumerate(original) if i!=2))
