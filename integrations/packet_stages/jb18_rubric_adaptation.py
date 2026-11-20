"""Narrow JB18 adaptations; all compatible original criteria remain blocking."""
from copy import deepcopy
CHANGES={
(0,0):('capacity units/time unspecified','Include capacity pressure grounded in observed order counts, item units and published daily capacity. State compatible units and horizon before ratios; otherwise use labeled scenarios or conditional capacity status, not asserted physical utilization.'),
(0,3):('customer coverage/unknown records','Include satisfaction from actual Survey_Results with sample counts and transparent handling of missing/unconfirmed observations; do not invent point scores.'),
(1,2):('observed is not permanently active','Verify every observed-order plant occurs in capacity and port tables; distinguish seven observed plants from all nineteen and from permanent inactivity.'),
(2,0):('unsupported fixed feasibility','Identify receivers for each candidate. Establish feasibility under compatible stated units/horizon; otherwise present conditional capacity requirements and no-go/monitor recommendations.'),
(2,1):('order count versus units/horizon mismatch','Show conserved transfers and receiving loads before and after transfer. Quantify utilization on a justified common basis; check joint load across simultaneous closures and disclose unresolved unit/horizon assumptions.'),
(2,2):('example mixes counts and capacity units','Distinguish PLANT03 8,541 observed orders from Unit_Quant totals and Daily_Capacity 1,013. Test aggregate transferred load under explicit interpretations; small candidates alone do not prove feasibility.'),
(3,0):('unknown complaint attribution','Derive per-plant complaint counts from visible records and delivered confirmations. For unconfirmed C-001 location use conditional counts/risk rather than a default-world fixed distribution. Preserve known records and deduplicate copies.'),
(4,0):('variable expense is not fixed closure saving','Calculate origin variable warehouse cost from matching observed units and WhCosts; distinguish this component from evidenced avoidable fixed shutdown savings.'),
(4,1):('freight mapping may be incomplete','Calculate receiving warehouse cost and changed freight using matching carrier, route, weight band, service and minimum charge. If matching evidence is unavailable, disclose and quantify assumptions/scenarios without invented quotes.'),
(4,2):('annual horizon is not observed','Present net cost impact using actual warehouse rates and receiving/origin units. Label annualization as a scenario with explicit horizon; do not present the one-date shipment sample as observed annual demand.'),
(6,0):('capacity basis ambiguous','For each of 3-5 candidates report capacity/utilization under an explicit compatible basis or conditional status, actual unit warehouse cost and observed late rate.'),
(6,1):('customer points may be unconfirmed','For each candidate report sourced satisfaction with sample count or an explicit uncertainty/scenario treatment, and a receiving-plant redistribution plan justified by shared ports.'),
(6,2):('annualization requires assumptions','Give candidate net annual cost scenarios with explicit annualization assumptions and identify uncertainty in their use for decisions.'),
(6,3):('examples must not predetermine candidates','Give a retention counterargument for each chosen candidate. Justify selection from operational/customer evidence and do not infer permanent zero demand solely from absent orders.'),
(8,1):('categorical never-consolidate conclusion unsupported','Assess PLANT03 centrality and concentration risk, including additional PORT04 transfers; any closure/consolidation recommendation requires justified feasibility and business continuity. Do not force a predetermined action.')}

def adapt(original):
 result=deepcopy(original);changes=[]
 for (i,j),(reason,text) in CHANGES.items():
  old=result[i]['criterion'][j];result[i]['criterion'][j]=text
  changes.append(dict(rubric_index=i,criterion_index=j,reason=reason,original=old,adapted=text))
 total=sum(len(r['criterion']) for r in original)
 return result,dict(adapted_criteria=len(changes),unchanged_blocking_criteria=total-len(changes),unchanged_weights=True,changes=changes,scope='Original diagnostic remains byte-identical. Active gate preserves every unlisted criterion.')
