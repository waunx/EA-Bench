"""JB17 complete artifact checker for infrastructure rationalization deliverables."""
import csv, json, zipfile
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
import openpyxl
from .jobbench import load_task, OfficialJudge
from .native import artifact_hashes, JobBenchAcceptance
from .jb17_evidence import source_evidence

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / 'data/expanded/JB17'
BOOK = 'Q4_Infrastructure_Rationalization.xlsx'
GAPCSV = 'gap_register.csv'
REQUIRED_SHEETS = ['Reconciliation','Migration_Plan','Gap_Register','Executive_Summary']
GAP_FIELDS = ['Gap_ID','NIST_Subcategory','Related_CI_Category','Severity','Mapped_Project_ID','Estimated_Cost','Remediation_Timeline']
NIST_PREFIXES = ('GV.','ID.','PR.','DE.','RS.','RC.')

def _read_csv(path, checks, details):
    try:
        with path.open(newline='', encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        checks['gap_csv_readable'] = True; details['gap_csv_rows'] = len(rows); return rows
    except Exception as e:
        checks['gap_csv_readable'] = False; details['gap_csv_error'] = str(e); return []

def structural_checks(artifacts, facts=None):
    root=Path(artifacts);hashes=artifact_hashes(root);checks={};details={}
    book=root/BOOK;gap=root/GAPCSV
    checks['named_workbook_present']=book.is_file()
    checks['gap_register_csv_present']=gap.is_file()
    rows=_read_csv(gap,checks,details) if gap.is_file() else []
    checks['gap_csv_schema']=bool(rows) and all(f in rows[0] for f in GAP_FIELDS)
    if book.is_file():
        try:
            wb=openpyxl.load_workbook(book,data_only=False)
            checks['required_sheets']=set(REQUIRED_SHEETS)<=set(wb.sheetnames)
            checks['substantive_sheets']=checks['required_sheets'] and all(any(c.value is not None for row in wb[s] for c in row) for s in REQUIRED_SHEETS)
            details['sheets']=wb.sheetnames;wb.close()
        except Exception as error:
            checks['workbook_readable']=False;details['error']=str(error)
    return dict(status='pass' if checks and all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=hashes,scope='Format only; layout, wording, numerical semantics and conditional formatting are evaluated against source evidence separately')

CRITERIA = [
'Deliver both named artifacts: gap_register.csv with the required seven fields and Q4_Infrastructure_Rationalization.xlsx with Reconciliation, Migration_Plan, Gap_Register, and Executive_Summary sheets. The workbook must be readable, internally consistent with the CSV gap register, and usable by a board reviewer without relying on hidden reasoning.',
'Reconciliation must cross-reference the Q4 ITSM incidents to inventory assets despite naming convention differences, include at least the top 10 incident-driving assets, quantify incident volume, annotate unmatched or discrepant identifiers, explain health/utilization/age/criticality factors, and surface reassignment behavior by incident category as evidence of process gaps.',
'Migration_Plan must rank underutilized or aging on-premise candidates using risk-weighted logic, treat Critical assets as generally excluded unless incident frequency justifies migration, compare current on-premise spend to estimated cloud costs using the AWS legacy EC2 Cost Comparison Calculator revised February 1 2010 as the fixed benchmark, identify cases where cloud cost exceeds current spend, and provide action recommendations.',
'For PRJ-2024-041, compute available funding from the approved budget and existing cloud operations in the budget data. Judge the figure against the visible file or clarified world value; do not prefer the original default over a supplied alternative-world clarification.',
'For SRV-007, carry the current on-premise cost from the inventory or clarification into the migration plan and annualize it correctly. Conflicting or missing variants must not silently substitute either value without support.',
'Sequence migration around PRJ-2024-042 Zero Trust segmentation using the visible file or clarified world timeline. Explain dependencies without implying segmentation alone removes all operational or security constraints.',
'Gap register must map worst reassignment categories to official NIST CSF 2.0 subcategory identifiers, relate each gap to a CI category, cross-reference pending projects including PRJ-2024-042 where applicable, estimate positive costs for unbudgeted gaps, flag high-severity unbudgeted items, and apply red conditional formatting or red highlighting in the workbook.',
'Executive_Summary must contain 5 to 7 prioritized board-level recommendations, each tied to quantified financial impact and an implementation quarter, covering operational risk, security/process gaps, migration sequencing, budget constraints, and cost-exceed decisions.'
]

def _facts_for_evidence(variant, clarification_records):
    oracle = json.loads((RELEASE/'private/oracle.json').read_text())
    facts = {k: atom['default'] for k, atom in oracle['atoms'].items()}
    spec = oracle['variants'][variant]
    unresolved = set(spec['missing'] + spec['conflict'])
    for record in clarification_records or []:
        for item in record.get('provided', []):
            if item['fact_id'] in unresolved:
                facts[item['fact_id']] = item['value']
    return facts, oracle

def completion_rubrics(evidence):
    """Business modules score separately; complete acceptance still requires all."""
    names = ['Workbook and gap-register coverage', 'Asset and incident reconciliation', 'Risk-weighted migration and TCO', 'Approved funding and actual operations', 'SRV-007 annualized costs', 'Segmentation dependencies', 'NIST gap mapping and remediation', 'Board recommendations']
    context = "Private source evidence for independent verification, not required output wording: " + json.dumps(evidence, default=str)
    return [dict(rubric=name, weight=1, criterion=[criterion, context]) for name, criterion in zip(names, CRITERIA)]


def check(artifacts, private_root, variant='full', world=None, clarification_records=None, **config):
    root = Path(private_root); root.mkdir(parents=True, exist_ok=True)
    facts, oracle = _facts_for_evidence(variant, clarification_records)
    structure = structural_checks(artifacts, facts)
    if structure['status'] != 'pass':
        return dict(case='JB17', variant=variant, status='fail', structural=structure, original=dict(status='not_run'), completion=dict(status='not_run'))
    source, _, original = load_task('JB17')
    spec = oracle['variants'][variant]
    provided = {x['fact_id'] for r in (clarification_records or []) for x in r.get('provided', [])}
    unconfirmed = set(spec['missing'] + spec['conflict']) - provided
    ev = dict(facts=facts, expected_world_values=dict(funding_gap=max(0, 850000-facts['budget']), headroom=max(0, facts['budget']-850000), annual_on_premise_cost=str(Decimal(str(facts['monthly_cost']))*12), segmentation_planned_finish=facts['network_timeline'].split(' - ')[1]), clarification_audit=dict(records=clarification_records or [], unconfirmed_alternatives={k:[oracle['atoms'][k]['default'], oracle['atoms'][k]['alternative']] for k in unconfirmed}, instruction='Assess only facts visible in artifacts or supplied through clarification; hidden values cannot justify unsupported confirmed figures.'))
    ev['complete_source_controls']=source_evidence(variant)
    ev['facts']={k:v for k,v in facts.items() if k not in unconfirmed}
    for field,derived in {'budget':['funding_gap','headroom'],'monthly_cost':['annual_on_premise_cost'],'network_timeline':['segmentation_planned_finish']}.items():
        if field in unconfirmed:
            for key in derived:ev['expected_world_values'].pop(key,None)
    ev['comparison_note']='Funding gap/headroom against estimated project cost is not the remaining approved funding after actual cloud operations. Distinguish these quantities and justify period/provider/project scope. Do not invent cross-source identity mappings or fill blank costs as observed zero.'
    (root/'source_evidence.json').write_text(json.dumps(ev, indent=2, default=str)+'\n')
    completion = completion_rubrics(ev)
    _, original_path, _ = load_task('JB17')
    original_judge=OfficialJudge(original_path,root/'original_judge',**config)
    native=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,original,original_judge)({}, {})
    rp=root/'authored_completion_rubrics.json'
    rp.write_text(json.dumps(dict(rubrics=completion),indent=2)+'\n')
    judge=OfficialJudge(rp,root/'completion_judge',**config)
    active=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,completion,judge)({}, {})
    return dict(case='JB17',variant=variant,status='pass' if active.status=='passed' else 'fail',structural=structure,original=asdict(native),completion=asdict(active),unconfirmed_fields=sorted(unconfirmed),original_judge_run=str(original_judge.last_run),completion_judge_run=str(judge.last_run),scope='Separate unchanged original diagnostic and source-grounded active business judgment; no native replay')
