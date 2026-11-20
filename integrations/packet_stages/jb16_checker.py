"""JB16 whole-estimate checker with independent geometry and bar controls."""
import json
from pathlib import Path
from dataclasses import asdict
from .author_english_jb16 import RELEASE
from .jb16_evidence import expected
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance
BOOK='Miller_Creek_Culvert_Estimate.xlsx'
def structural_checks(artifacts):
 import openpyxl
 root=Path(artifacts);hashes=artifact_hashes(root);p=root/BOOK;checks={'named_workbook':p.is_file()};details={}
 if p.is_file():
  try:
   b=openpyxl.load_workbook(p,data_only=False);checks['nonempty_workbook']=any(sum(c.value is not None for row in s for c in row)>1 for s in b);checks['no_excel_errors']=not any(c.data_type=='e' or '#REF!' in str(c.value) for s in b for row in s for c in row);details['sheets']=b.sheetnames
  except Exception as e:checks['readable_workbook']=False;details['error']=str(e)
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=hashes)
CRITERIA=[
'Deliver the named workbook with clear executive summary, quantity takeoff, local/WSDOT unit analysis, reinforcement verification, detailed estimate/contingencies and assumptions/risks functions. Accept equivalent clear sheet names. Every reported total must trace to quantities, prices and allowances, and all six functions must be substantive.',
'Takeoff explicitly handles the15-degree skew for excavation and four wing walls. The source takeoff template specifies a projected excavation base72/cos15≈74.54ft and perpendicular-width area; use a consistent geometric interpretation with declared clearance, depth and slopes. Keep the actual purchased culvert length at9segments×8ft=72ft rather than enlarging it again. Show acute/obtuse wing-wall differences and reconcile results with the specification allowances; missing design dimensions require explicit assumptions, not fabricated certainty.',
'Account for all original scope: demolition of65ftCMP and affected pavement, clearing, excavation/foundation, bedding/backfill,72ftprecast and joints, wing/headwalls, both aprons, reinforcing, road restoration, riprap/geotextile, traffic, erosion, diversion/dewatering and survey. Reconcile spec estimates against calculations. Inlet apron is8×14×8/12/27≈2.7654CY; outlet12×14×10/12/27≈5.1852CY; riprap150×1.5/27≈8.3333CY. Any different adopted geometry or quantity must be explained. Use correctft/in/CY/SY/TON conversions and stated density; do not imply all template quantities are independently verified.',
'Verify every bar mark: counts, total length and length times published standard unit weight, with bar/section/grand totals and5-percent waste/lap applied once to cast-in-place steel only. WW1=816×1.043=851.088lb andWW2=882×1.043=919.926lb. Exact subtotal4006.9075lb gives4207.252875lb with waste; source per-line half-up rounding gives4006.93 and4207.28lb. Accept an explicitly consistent rounding convention. Use0.376/0.668/1.043lbperft for#3/#4/#5 and cite the independent published table, distinguishing it from the original schedule. Precast factory steel is included in its unit rate, not charged again.',
'Price required epoxy-coated Grade60steel at the supported local installed1.70/lb (1.15material+.50labor+.05equipment) or justify a different actually supported rate; do not accidentally substitute black-bar1.35. Build the10x8precast installed price from the confirmed material/labor/equipment components, and keep the8x6/12x10products separate. Treat a cost as confirmed only when supplied by the actual file or clarification; otherwise state a supported provisional basis or range.',
'Compare all applicable local prices against the actual24Z011 bid-tab items, identifying units, local rate, ACME low-contract-bidder rate, engineer estimate, percentage variance, selected price and rationale. Low bidder means the lowest total contract bidder, not the minimum individual item among bidders. Do not swap second-bidder prices into the low-bidder column. Distinguish direct matches from roadway-versus-structure excavation, asphalt-grade differences, scope/quantity/geographic effects, and items with no comparable culvert benchmark. Reference the actual job/contract document rather than inventing benchmark prices.',
'Detailed estimate shows quantities×selected rates, category subtotals, confidence classification and item-level contingency rates that are lower for stronger validated support and higher for weak/no comparisons. Explain the chosen rates and weighted-average contingency. The user did not mandate8/12/15percent: those or another defensible differentiated set are acceptable. Do not leave the template flat10percent contingency unexplained as if it met the requested confidence-based method.',
'Apply mobilization according to the supplied cost tiers (10percent below$1M;8percent from$1Mto$5M) on an explicitly defined noncircular construction subtotal and reconcile the grand total. Do not add separate formwork to a395/CYinstalled CIP rate already including forming without an offset/scope explanation, double-compaction to placed/compacted borrow, factory reinforcement to precast, or operator labor already embedded in equipment rates. Account for duration-dependent traffic/site costs and fish-window constraints using supported45/60day or other declared planning assumptions, not an unsupported confirmed duration.',
'Executive summary presents the project estimate, principal cost drivers, benchmarking conclusions, contingency confidence and unresolved risks. Assumptions identify missing design dimensions, excavation support/dewatering, quantity conflicts, scope inclusions, price comparability and source limitations. State what requires engineering confirmation rather than presenting a signed or fully verified design. Neighbor-project schedules, other-size culvert quotes and duplicated equipment components cannot silently replace the project basis or add costs.'
]

def completion_rubrics(evidence):
    """Business modules score separately; complete acceptance still requires all."""
    names = ['Workbook coverage and traceability', 'Skewed excavation and wing-wall geometry', 'Complete scope and quantity conversions', 'Reinforcing bar verification', 'Source-grounded unit prices', 'Bid-tab comparison', 'Confidence-based contingencies', 'Mobilization and avoidance of duplicate costs', 'Executive summary and assumptions']
    context = "Private source evidence for independent verification, not required output wording: " + json.dumps(evidence, default=str)
    return [dict(rubric=name, weight=1, criterion=[criterion, context]) for name, criterion in zip(names, CRITERIA)]


def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**config):
 root=Path(private_root);root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if structure['status']!='pass':return dict(case='JB16',status='fail',structural=structure,original=dict(status='not_run'),completion=dict(status='not_run'))
 source,_,original=load_task('JB16');o=json.loads((RELEASE/'private/oracle.json').read_text());spec=o['variants'][variant]
 values={k:atom['default'] for k,atom in o['atoms'].items()}
 uncertain=set(spec['missing']+spec['conflict'])
 for record in clarification_records or []:
  for item in record.get('provided',[]):
   if item['fact_id'] in uncertain:values[item['fact_id']]=item['value']
 ev=expected(variant,values)
 provided={x['fact_id'] for r in (clarification_records or []) for x in r.get('provided',[])};unconfirmed=set(spec['missing']+spec['conflict'])-provided
 ev['world']={k:v for k,v in ev['world'].items() if k not in unconfirmed}
 if 'duration' in unconfirmed:ev['controls'].pop('duration',None)
 if unconfirmed & {'material','installation'}:
  ev['controls'].pop('installed_unit_cost',None);ev['controls'].pop('precast_line_cost',None)
 ev['clarification_audit']=dict(records=clarification_records or [],unconfirmed_alternatives={k:[o['atoms'][k]['default'],o['atoms'][k]['alternative']] for k in unconfirmed},instruction='Assess estimate assumptions and pricing using facts actually supplied. Supported provisional ranges can be valid; hidden actual values cannot justify an unsupported confirmed price or duration.')
 (root/'source_evidence.json').write_text(json.dumps(ev,indent=2,default=str)+'\n')
 completion = completion_rubrics(ev)
 _,original_path,_=load_task('JB16')
 native_judge=OfficialJudge(original_path,root/'original_judge',**config)
 native=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,original,native_judge)({},{})
 rp=root/'authored_completion_rubrics.json';rp.write_text(json.dumps(dict(rubrics=completion),indent=2)+'\n')
 judge=OfficialJudge(rp,root/'completion_judge',**config)
 active=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,completion,judge)({},{})
 return dict(case='JB16',variant=variant,status='pass' if active.status=='passed' else 'fail',structural=structure,original=asdict(native),completion=asdict(active),unconfirmed_estimate_fields=sorted(unconfirmed),original_judge_run=str(native_judge.last_run),completion_judge_run=str(judge.last_run),scope='Separate original diagnostic and active source-grounded judgment; unconfirmed selected-world point expectations withheld; no native replay')
