"""JB28 source-backed FAT judging with separate original diagnostic."""
from pathlib import Path
from dataclasses import asdict
import json,copy,importlib,sys
import openpyxl
from .jb28_evidence import build,PACKET
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance

def structural_checks(artifacts):
 p=Path(artifacts);x=p/'rebalancing_analysis.xlsx';pdf=p/'client_memo.pdf';checks=dict(workbook=x.is_file(),pdf=pdf.is_file());details={}
 checks['data_quality_notes']=(p/'data_quality_notes.csv').is_file()
 if all(checks.values()):
  try:
   w=openpyxl.load_workbook(x,data_only=False);details['sheets']=w.sheetnames;checks['no_excel_errors']=not any(c.data_type=='e' for s in w for row in s for c in row);w.close()
   try:mod=importlib.import_module('pymupdf')
   except ModuleNotFoundError:sys.path.append('/tmp/ea-bench-analysis-deps');mod=importlib.import_module('pymupdf')
   with mod.open(pdf) as d:details['pages']=len(d);checks['memo_at_most_four_pages']=len(d)<=4
  except Exception as exc:checks['readable']=False;details['error']=str(exc)
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(p),scope='Named readable deliverables only; no sheet-count or keyword gate')

CRITERIA=[
'Audit actual files: missing values, gaps, anomalies, and account-versus-holdings balances. Reconcile $2,380,888.80 itemized holdings against $2.8M summary, gap $419,111.20, by account. No invented cash balancing plug. Use documented cleaned data and distinguish missing dates from weekends/holidays. Label 2025 macro observations as historical/future relative to planning date; no look-ahead assertion.',
'Compute 2024 monthly 10Y minus 2Y slopes using a declared mean or month-end method. Source daily series first positive is August 28, 2024; distinguish temporary crossing from sustained September normalization. December 31 10Y 4.58, 2Y 4.25, slope 33bp. Compute trailing CPI inflation and real policy rate at matched dates, not subtract CPI index level; disclose gap/anomaly cleaning and latest summary. S&P file is daily despite name; filter Jan2024-Jan2025 and aggregate consistently. Monthly means or month-end returns are both valid if explained.',
'Gift $150,000 from XXX-3789: document every taxable holding, basis, gains and sales. Cash $82,500 plus $67,500 of VXUS realizes about $10,477.82 gain, indicative $1,571.67 at 15%; verify actual preferential stacking, NIIT and Virginia tax or explain excluded scope. This is a feasible low-gain plan, not uniquely mandatory. Fractional share and whole-share rounding alternatives allowed. Account for cash remainder and tax funding; do not sell more shares than owned. Missing NVDA basis means global optimality cannot be certified solely from the private selected world.',
'Gift planning uses $19,000 annual exclusion per donor per donee for 2025; joint $150,000 gift leaves $112,000 potentially using lifetime exemption, not automatically gift tax payable. Discuss ownership, consent and Form709 gift splitting/returns by appropriate 2026 deadline; clarify no federal income deduction. Do not assume both spouses can report one joint gift-tax return.',
'Post-gift itemized portfolio is $2,230,888.80 before sale-tax funding, not unexplained $2.65M. Recompute target amounts and actual weights by asset class. Trades must identify account/ticker/shares/amount and reconcile cash and post-trade weights; prioritize IRAs/Roth for realizing gains. No current loss-harvest benefit inside IRAs/Roth; all listed taxable holdings have positive or zero gains only when supported basis is known. Quantify tech overlap without double counting ETF look-through. Specific diversification and bond trades must remain feasible under missing balance reconciliation.',
]
CRITERIA += [
'RMD analysis:2025-2040 side by side; Robert age73 in2029, prior December31 balance divided by Uniform Lifetime factor26.5 then25.5,24.6,23.7,22.9,22,21.1,20.2,19.4,18.5,17.7,16.8. Start$1.45M, grow6%, convert$100K each2025-2028, show Roth growth. State beginning/end-year conversion and distribution timing. Do not convert RMD. Assess spending$120K and outside tax funding without inventing assets.',
'Complete income means pension plus SS$70,800, dividends$18,500+$4,200, interest$32,600 and capital-gain distributions$8,400. Portfolio total$63,700 is not all ordinary. Default pension$36K gives gross$170,500, provisional$135,100 before/$235,100 after conversion;85%SS=$60,180 already taxable in both. Unknown pension permits conditional formula, not default assertion. Dividend classification affects ordinary/preferential stacking. Apply disclosed MFJ deductions, ordinary/capital-gain rates, state-tax assumptions and consistent baseline versus incremental taxes. Net savings can be negative.',
'Concrete cumulative A/B and difference must reconcile16 annual rows and memo recommendation. Compare horizon limits, Roth legacy/ending wealth and tax-rate sensitivity; current law or explicit historical planning assumptions allowed. TCJA sunset is not inevitable under later2025 law. Sequence Q2gift,Q2-Q3conversion,Q3-Q4rebalancing with dependencies; midyear timing alone does not alter annual brackets.',
'Unknown facts may be clarified or handled with supported conditional analysis, symbolic formulas or honest bounds; no private exact answer or mandatory question. Equal-revision claims have no ordering. Archived other-year pension, closed/different-account lots and scoped dividend copies cannot repair active facts. No forced action counts or hidden reasoning transcript. Judge arithmetic/evidence rather than keywords.'
]

def completion_rubrics(evidence):
 original=copy.deepcopy(load_task('JB28')[2])
 changes={
 (0,1):'Use visible or confirmed pension and complete portfolio income, separating ordinary and preferential income; apply disclosed2025 MFJ deductions and stacking. Unresolved income permits conditional computations and supported bounds.',
 (2,2):'Assess taxable losses using supported basis. VMFXX has zero gain and other known positions gains. Unconfirmed NVDA basis cannot establish absence of all taxable losses.',
 (3,0):'Actual Treasury first positive daily10Y-2Y August28,2024; distinguish temporary from sustained September normalization and monthly aggregation. December31 4.58%-4.25%=33bp,30Y4.78%.',
 (3,2):'Consider duration risk using dated Fed observations, avoiding late2025 look-ahead in Q2 planning.',
 (4,1):'Sequence2025 conversion with annual provisional income and brackets; midyear timing alone does not lower annual tax.',
 (5,0):'Aggregate actual daily FRED January2024-January2025 consistently. Monthly-mean return24.4568%; month-end24.6588% also valid with method stated.',
 (5,1):'Requested comparison spans13 months; downloaded daily source spans more dates. Filter period and disclose rolling-window availability.',
 (5,2):'Latest and recent high must use same aggregation and requested dates; do not impose a monthly-mean high on month-end analysis.',
 (6,0):'Provisional income includes actual pension, portfolio income, conversion, halfSS and any tax-exempt interest, without counting taxableSS twice.',
 (6,1):'Default pension gives provisional$235,100 with conversion and85%SS=$60,180; use confirmed amounts or conditional formulas if unresolved.',
 (6,2):'Default no-conversion provisional$135,100 already yields85%SS; use actual supported income or conditional calculations.',
 (8,0):'Give an actionable supported recommendation; qualify unresolved facts and prerequisites rather than inventing a definitive point result.',
 (8,3):'Assess tax-rate uncertainty under explicitly dated law; historical sunset sensitivity allowed, but no claim that sunset remains inevitable after later2025 legislation.'}
 for (r,c),value in changes.items():original[r]['criterion'][c]=value
 original[0]['rubric']='Does the Roth analysis model four $100K conversions, supported complete-income taxation and reduced RMDs?'
 import re
 clean=lambda s:re.sub(r'(?<=[a-zA-Z])(?=\d)|(?<=\d)(?=[a-zA-Z])',' ',s)
 for row in original:row['criterion']=[clean(s) for s in row['criterion']]
 return original+[dict(rubric='Complete source-backed financial planning',weight=10,criterion=[clean(s) for s in CRITERIA]+['Selected visible financial evidence and illustrative controls: '+json.dumps(evidence)])]

def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**config):
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if structure['status']!='pass':return dict(case='JB28',status='fail',structural=structure,original=dict(status='not_run'))
 evidence=build(variant,world,clarification_records);(private_root/'source_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
 source,path,rubrics=load_task('JB28');judge=OfficialJudge(path,private_root/'original_judge',**config)
 original=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)({},{})
 active=completion_rubrics(evidence);rp=private_root/'completion_rubrics.json';rp.write_text(json.dumps(dict(rubrics=active),indent=2)+'\n');other=OfficialJudge(rp,private_root/'completion_judge',**config)
 completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,active,other)({},{})
 return dict(case='JB28',status='pass' if completion.status=='passed' else 'fail',structural=structure,original=asdict(original),completion=asdict(completion),original_judge_run=str(judge.last_run),completion_judge_run=str(other.last_run),scope='Source calculations and separate original/active semantic judgments; no native replay')
