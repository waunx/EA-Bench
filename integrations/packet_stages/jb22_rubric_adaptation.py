"""Retain all eight original groups; narrowly remove exact-grid-count and false regulatory attribution."""
from copy import deepcopy
import json

def adapt(original,context):
 active=deepcopy(original);changes=[]
 replacements={
  0:'The matrix spans at least two justified power levels including supplied90% sensitivity and the actual primary level when determined. Unconfirmed primary designs must be clearly conditional;80% is not uniquely required when the approved protocol differs.',
  1:'Span at least two justified clinically meaningful absolute effects including supplied5-percentage-point target. The original3-point effect is a valid example, not uniquely stated in the proposal.',
  3:'Show the complete crossing of declared powers, effects and unadjusted/interim-adjusted designs with per-group and total n: at least eight combinations. Additional documented scenarios are allowed.'}
 for index,text in replacements.items():
  old=active[2]['criterion'][index];active[2]['criterion'][index]=text
  changes.append(dict(rubric_index=2,criterion_index=index,original=old,adapted=text,reason='Proposal specifies90% sensitivity and5-point target but no unique3-point effect; primary power can differ. Complete additional scenarios are valid.'))
 headers=[]
 for index,text,reason in [(2,'Does the workbook contain the complete baseline sensitivity grid and any clearly documented additional design scenarios?','Avoid rejecting useful additional scenarios merely because there are more than eight rows.'),(4,'Does the analysis identify any strata below the pragmatic n30 screen and discuss E9Section5.7 adequacy principles without inventing an FDA universal n30 rule?','E9 gives adequacy/interpretation principles, not a universal numerical subgroup cutoff.')]:
  headers.append(dict(rubric_index=index,original=active[index]['rubric'],adapted=text,reason=reason));active[index]['rubric']=text
 for index in [1,2]:active[index]['rubric']+=' Private protocol context (not requested output text): '+json.dumps(context)
 return active,dict(changed_criteria=changes,changed_headers=headers,unchanged_criteria=sum(len(r['criterion']) for r in original)-3,all_eight_groups_and_weights_preserved=True)
