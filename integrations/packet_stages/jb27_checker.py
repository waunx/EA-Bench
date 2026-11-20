"""JB27 source-backed FAT judging with separate original diagnostic."""
from pathlib import Path
from dataclasses import asdict
import json,copy,importlib,sys
import openpyxl
from .jb27_evidence import build,PACKET
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance

def structural_checks(artifacts):
 p=Path(artifacts);x=p/'P-2415A_FAT_Acceptance_Matrix.xlsx';pdf=p/'P-2415A_Disposition_Memo.pdf';checks=dict(workbook=x.is_file(),pdf=pdf.is_file());details={}
 if all(checks.values()):
  try:
   w=openpyxl.load_workbook(x,data_only=False);details['sheets']=w.sheetnames;checks['no_excel_errors']=not any(c.data_type=='e' for s in w for row in s for c in row);w.close()
   try:mod=importlib.import_module('pymupdf')
   except ModuleNotFoundError:sys.path.append('/tmp/ea-bench-analysis-deps');mod=importlib.import_module('pymupdf')
   with mod.open(pdf) as d:details['pages']=len(d)
  except Exception as exc:checks['readable']=False;details['error']=str(exc)
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(p),scope='Named readable deliverables only; no sheet-count or keyword gate')

CRITERIA=[
'Correct every performance row using Q proportional to N, H to N squared and P to N cubed at2970RPM. Compare raw/corrected/rated values at180m3/h by interpolating the corrected-flow curve, not relabeling corrected test-point6 as exactly rated flow. Apply datasheet head45 +/-3%, power58 +4%, efficiency minimum72. Source-specific tolerances are not universal API guarantees. Do not affinity-scale bearing temperatures or measured vibration, or fabricate measured NPSH test results.',
'Keep reported efficiency separate from hydraulic power-balance efficiency rho*g*Q*H/P. Recorded68.2% at point6 fails72%, but independently recomputed Q/H/P efficiencies disagree materially, with corroborating inconsistencies at other points. Flag data-quality investigation/calibration and clarify electrical-input versus shaft-power basis rather than silently repairing values or inferring missing power from inconsistent efficiencies. No confirmed point6 speed/power is available until supported by visible records or actual clarification; bounded/provisional conclusions are legitimate.',
]
CRITERIA += [
'Assess all7 vibration points and both DE/NDE readings with applicability. Use pump-specific POR126-198 and confirmed AOR upper bound, not generic70-120% POR. Within POR overall limit3.0/discrete2.0; outside POR but within AOR overall3.9/discrete2.6. Outside AOR retain measurements and mark acceptance N/A. Point1 shutoff is not a continuous-operation pass. Default nominal-flow point6 DE3.5 fails and NDE2.5 passes; point7 exceeds3.9 on both if within AOR, otherwise N/A. Explain actual measured-flow versus corrected-equivalent boundary treatment, especially point2 and point7; do not force unsupported pass/fail at ambiguous boundaries.',
'Use Europump and supplied ISO text to explain ISO10816-3 exclusion of rotodynamic pumps and appropriate Part7 CategoryII for general raw-water service, <=200kW group from75kW motor. State zones A<=3.2,B<=5.1,C<=8.5,D>8.5; these magnitude bands are not API FAT acceptance, and ISO FAT/in-situ/alarm tables are separate. Classify all DE/NDE magnitudes with operating-condition limitations: default nominal point6DE isB, point7DE C/NDE B even though API fails. Do not replace stricter contract criteria with ISO zones.',
'Calculate BPFO/BPFI/BSF/FTF for both SKF6313C3 and6311C3 at actual speed for both spectra, with explicit geometry/contact-angle basis. Reference geometry is approximate, not a certified hidden requirement; supported alternative geometry must be recomputed. If exact speed is missing, ratios or approx49.5Hz analysis are legitimate if precision limits are clear. Compare predicted frequencies, nearby peaks, shaft harmonics and possible sidebands against both supplied DE-horizontal spectra. The149Hz feature is near3x running speed and offset from approximate155Hz DE BPFO; do not diagnose a bearing fault from proximity alone or certify all bearings healthy from limited-band DE data.',
'Analyze actual spectra: 1x near49/50Hz increases1.7338 to2.7163mm/s (~56.7%);2x near99Hz0.6458 to1.2434 (~92.5%);six-vane VPF near297Hz0.4203 to1.5603 (~271.2%). High-flow 1x exceeds AOR discrete2.6 if applicable; rated1x remains below POR2.0. Include the stronger VPF and broadband hydraulic evidence, not only overall readings. Distinguish hydraulic loading/off-design/cavitation hypotheses from proven cause, and use IOM troubleshooting with identified page/section rather than generic keywords.',
'Memo must give accept/reject disposition for P-2415A consistent with performance and vibration evidence, actionable corrections/retest criteria, high-flow restrictions and measurement validation. Preserve P-2415B status from the instruction, but never import its passing measurements to P-2415A. The supplied IOM is generic SFLP/EC material, not demonstrated Flowserve-specific guidance; qualify its use and verify model-specific corrective details.',
'Redundant P-2415B measurement, calibration tachometer and motor nameplate are different tag/run/quantity from actual point6 readings. Do not use them to repair missing values. No mandatory question or fixed action sequence, extra sheets, arbitrary numeric quota or reasoning transcript is required. Tool/information minima are unproven; supported conditional analysis can complete justified portions without a private exact answer.'
]

def completion_rubrics(evidence):
 original=copy.deepcopy(load_task('JB27')[2])
 original[3]['criterion'][1]='Use supported SKF6313 geometry, e.g. illustrative Z8,Dw22.23mm,Dm102.5mm,alpha0, at actual confirmed speed or explicitly qualified approximate49.5Hz if exact RPM is unresolved.'
 original[6]['criterion'][1]='Include raw head30.8m, reported efficiency68.2% and actual visible/confirmed point6 power and speed; unresolved quantities remain conditional rather than defaulting.'
 original[7]['criterion'][0]='Document all7 points using pump-specific POR126-198m3/h and confirmed AOR upper limit; apply3.0mm/s overall within POR and3.9 outside POR within AOR. Explain nominal measured-flow versus corrected-equivalent boundary sensitivity.'
 original[7]['criterion'][1]='Evaluate points2-5 against justified applicability and actual DE/NDE readings. Point1 shutoff is outside AOR: retain measurements and mark acceptance N/A, not an unqualified pass.'
 original[7]['criterion'][3]='Point7 readings5.8DE/4.3NDE fail3.9 when within confirmed AOR; outside AOR, retain them and mark acceptance N/A. Unresolved AOR permits conditional classification.'
 import re
 extra=[re.sub(r'(?<=[a-z])(?=\d)|(?<=\d)(?=[a-zA-Z])',' ',x) for x in CRITERIA]
 return original+[dict(rubric='Complete pump FAT and diagnostic interpretation',weight=10,criterion=extra+['Selected-visible sources and numeric controls: '+json.dumps(evidence)])]

def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**config):
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if structure['status']!='pass':return dict(case='JB27',status='fail',structural=structure,original=dict(status='not_run'))
 evidence=build(variant,world,clarification_records);(private_root/'source_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
 source,path,rubrics=load_task('JB27');judge=OfficialJudge(path,private_root/'original_judge',**config)
 original=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,judge)({},{})
 active=completion_rubrics(evidence);rp=private_root/'completion_rubrics.json';rp.write_text(json.dumps(dict(rubrics=active),indent=2)+'\n');other=OfficialJudge(rp,private_root/'completion_judge',**config)
 completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,active,other)({},{})
 return dict(case='JB27',status='pass' if completion.status=='passed' else 'fail',structural=structure,original=asdict(original),completion=asdict(completion),original_judge_run=str(judge.last_run),completion_judge_run=str(other.last_run),scope='Source calculations and separate original/active semantic judgments; no native replay')
