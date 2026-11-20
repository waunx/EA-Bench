"""JB13 complete portfolio report and constrained credit memoranda."""
import json
from pathlib import Path
from dataclasses import asdict
from .author_english_jb13 import RELEASE
from .jb13_evidence import expected
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance

def structural_checks(artifacts):
 import openpyxl,fitz
 root=Path(artifacts);hashes=artifact_hashes(root);books=list(root.glob('*.xlsx'));pdfs=list(root.glob('*.pdf'));checks=dict(workbook=len(books)==1,decision_pdf=len(pdfs)==1);details={}
 if len(books)==1:
  try:
   b=openpyxl.load_workbook(books[0],data_only=False);checks['workbook_nonempty']=any(sum(c.value is not None for row in s for c in row)>1 for s in b);checks['no_excel_errors']=not any(c.data_type=='e' or '#REF!' in str(c.value) for s in b for row in s for c in row);details['sheets']=b.sheetnames
  except Exception as e:checks['readable_workbook']=False;details['xlsx_error']=str(e)
 if len(pdfs)==1:
  try:
   d=fitz.open(pdfs[0]);checks['pdf_nonempty']=len(d)>0 and all(bool(p.get_text().strip() or p.get_images() or p.get_drawings()) for p in d);details['pdf_pages']=len(d)
  except Exception as e:checks['readable_pdf']=False;details['pdf_error']=str(e)
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=hashes)
CRITERIA=[
'Workbook dashboard reconciles all source records and outstanding balances by loan type, concentrations, balance-weighted rates and portfolio yield. Distinguish 88 source records from 84 not-paid-off records; four paid-off zero-balance records must not distort exposure or current-loan counts. Total outstanding is $50,612,786.91, weighted contractual rate about 7.02863 percent. Explain treatment of nonaccrual loans when calling a measure realized yield rather than contractual yield.',
'Cross-tabulate payment status against risk rating with counts and dollar balances, including transparent treatment of Paid_Off records. Compute NPA/noncurrent proxy from six Nonaccrual or 90-plus loans totaling $2,833,459.34: approximately 5.5983 percent of outstanding. Benchmark the correct FDIC Q4 2024 Total Loans and Leases noncurrent rate 0.984466 percent (source FK464), adverse variance approximately 461.384 basis points. State definition differences: the supplied file supports a noncurrent-loan proxy, not unobserved OREO or other assets.',
'Analyze every sector concentration with an explicit denominator and classification of blank Industry_Sector entries, the 20-percent ceiling, grandfathering and next annual review. Identify the five largest loan exposures and assess borrower aggregation using documented identity, without assuming unrelated borrowers are affiliated. Do not use $820M assets as regulatory lending-limit capital. Healthcare above20 percent is an existing grandfathered exposure, not automatic permission for new lending.',
'Include all fourteen adversely rated loans (8 Special Mention, 5 Substandard, 1 Doubtful), totaling $9,231,113.95, with source balance and CDFI objective components, justified subjective adjustments, final points/rating or a transparent missing-input range. Apply worksheet LTV, credit score, debt/assets and liquidity bands; allow its explicitly permitted borderline interpolation if explained. The actual data lack some borrower total/current assets/liabilities: do not substitute template examples, loan collateral for all assets or DSCR for liquidity without labeling an approximation. Apply maximum total subjective adjustment plus/minus4, maximum2 per fact, and distinguish source bank rating from new CDFI score.',
'Ground watch-list action items in OCC credit-risk guidance. Identify Ironbridge as the largest problem exposure, with roughly $704,020 collateral shortfall and DSCR0.96; recommend proportionate workout, updated financials/valuation, specialist/legal review and loss recognition assessment without inventing recovery certainty. Negative collateral plus CDFI points19+ maps to Projected Loss; collateral deficit alone must not fabricate missing CDFI factor scores.',
'Model an explicit plus200bp parallel rate shock for every watch-list loan with base/stressed debt service and recalculated DSCR, declared coverage threshold and breach flags. State cash-flow, amortization, remaining-term and repricing assumptions because rate type and complete cash-flow/debt-service detail are not supplied. A transparent interest-only approximation or amortizing sensitivity is acceptable if consistently calculated and labeled; multiplying DSCR by an arbitrary haircut is not. Distinguish a planning scenario from an actual covenant or repricing event.',
'Provide individual credit memoranda for all six applications, including reasoned recommendation, complete CDFI factor detail/uncertainty, borrower capacity/collateral/credit analysis, OCC citations, structure/conditions and portfolio impact. Address medical-office concentration, retail seasonality/equipment depreciation, restaurant startup/projected DSCR and co-guarantor, mortgage DTI/reserves/PMI, Trevor Hsu hotel request $2.8M with DSCR0.95, $45K loss,92-percentLTV,22-percent revenue decline,51-percent occupancy and unfunded$650K renovation, and Derek credit/debt/bankruptcy. Supported approval, decline, deferral or conditions are evaluated on source evidence, not a hidden mandatory portfolio allocation.',
'Reconcile all proposed commitments against the $3,000,000 cap with per-application amount, committed/conditional/deferred classification, cumulative approvals and remaining capacity. Recompute sector ratios using the post-lending denominator. New lending cannot rely on an unapproved Board waiver or grandfathering as an exception for new exposures. Participation/sell-down conditions must quantify the required exposure reduction and timing; contingent amounts are not reported as unconditional committed capacity. Do not double-count a participation sale as both capacity release and new capital without support.',
'For Derek, only verified current facts may be cited: FICO580 is below620, while640 is not; personal annual income52000/65000 implies DTI55.0/44.0 percent using monthly debt2385; June2021 versus June2015 discharge is inside/outside a January2025 seven-year window. Passing a FICO threshold is not sufficient for approval. A supported decline based on independent known weaknesses or a conditional/uncertain score can be valid without resolving every nonessential field; do not force clarification just to repeat an already-supported decision. Never reward lucky unsupported use of hidden values.',
'Include a clearly identifiable one-to-two-page executive summary within the same PDF, addressed to the CCO/Board. It summarizes source-grounded portfolio health/FDIC variance, three material risks with OCC-referenced remedies, and a capital-allocation table or clear arithmetic reconciling commitments/remaining capacity, post-lending concentrations and asset-quality impact assumptions. New sound loans may dilute the NPA ratio mechanically but do not cure existing problem balances. Check summary page extent and readability using actual PDF pages, not a self-reported page count.',
'Old credit reports, application-income mirrors and other applicant summaries do not create current verified evidence for Derek. Use record dates/identity and actual clarification transcripts. Scope-change counterfactuals in private tests are not facts in the active packet. Preserve private original-rubric comparison separately from source-grounded complete task acceptance.'
]

def judge_evidence(variant, clarification_records=None):
 o=json.loads((RELEASE/'private/oracle.json').read_text());spec=o['variants'][variant]
 values={k:atom['default'] for k,atom in o['atoms'].items()}
 unconfirmed=set(spec['missing']+spec['conflict'])
 for record in clarification_records or []:
  for item in record.get('provided',[]):
   if item['fact_id'] in unconfirmed:
    values[item['fact_id']]=item['value'];unconfirmed.remove(item['fact_id'])
 ev=expected(variant,values)
 for key in unconfirmed:ev['world'][key]=None
 for key,controls in {'fico':['fico_gate_pass','shortfall'],'income':['dti_pct'],'discharged':['bankruptcy_recent']}.items():
  if key in unconfirmed:
   for control in controls:ev['derek_controls'][control]=None
 ev['clarification_audit']=dict(records=clarification_records or [],unconfirmed_fields=sorted(unconfirmed),unconfirmed_alternatives={k:[o['atoms'][k]['default'],o['atoms'][k]['alternative']] for k in sorted(unconfirmed)},instruction='Assess decisions and scoring ranges using facts actually supplied. Independent supported rejection grounds may suffice without clarifying unused facts. Null controls are unresolved; no hidden selected value is supplied, and alternatives are illustrations rather than confirmed observations.')
 return ev

def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**config):
 root=Path(private_root);root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if structure['status']!='pass':return dict(case='JB13',status='fail',structural=structure,original=dict(status='not_run'),completion=dict(status='not_run'))
 source,_,original=load_task('JB13');ev=judge_evidence(variant,clarification_records)
 unconfirmed=ev['clarification_audit']['unconfirmed_fields']
 (root/'source_evidence.json').write_text(json.dumps(ev,indent=2,default=str)+'\n')
 completion=[dict(rubric='Complete portfolio risk, constrained credit decisions and executive summary',weight=1,criterion=CRITERIA+['Private source-grounded portfolio, credit and CDFI evidence; explicitly distinguish unobserved assets/liabilities from verified factor inputs: '+json.dumps(ev,default=str)])]
 combined=original+completion;rp=root/'rubrics.json';rp.write_text(json.dumps(dict(rubrics=combined),indent=2)+'\n');judge=OfficialJudge(rp,root/'judge',**config)
 JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,combined,judge)({},{})
 raw=json.loads((judge.last_run/'details.json').read_text());score=lambda rubrics,data:asdict(JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)._score(data,structure['artifact_hashes']))
 native=score(original,raw['rubrics'][:len(original)]);active=score(completion,[dict(r,index=r['index']-len(original)) for r in raw['rubrics'][len(original):]])
 return dict(case='JB13',variant=variant,status='pass' if active['status']=='passed' else 'fail',structural=structure,original=native,completion=active,unconfirmed_credit_fields=sorted(unconfirmed),judge_run=str(judge.last_run),scope='Full source-grounded artifact scoring; original rubric comparison separate and no native environment replay.')
