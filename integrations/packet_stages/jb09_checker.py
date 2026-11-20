"""JB09 host-owned migration artifact validation and separate original scoring."""
from pathlib import Path
from dataclasses import asdict
import csv,json,re,zipfile,xml.etree.ElementTree as ET
from .jobbench import load_task,OfficialJudge
from .native import artifact_hashes,JobBenchAcceptance
ROOT=Path(__file__).resolve().parents[2];PACKET=ROOT/'data/expanded/JB09'
EXTRA=[dict(rubric='Complete migration plan and manager constraints',weight=1,criterion=[
'Migration plan assigns every one of the 75 inventory assets exactly one Ready/Remediable/Replace/Decommission category, a justified per-device cost and conditional eligibility checks where needed. Department and overall totals reconcile; unknown workstation quotes are explicit allowances, not silently priced as desktops.',
'Provide January–June 2026 two-week sprints with departmental milestones, procurement order/arrival dependencies, test/pilot/rollback and acceptance work. Finance and Legal migrate or decommission before March 31; Sales avoids disruptive February–March work with protected interim risk controls; verify Executive status rather than assume completion.',
'Plans distinguish OS edition licensing, BIOS/TPM/Secure Boot/RAM remediation, no-cost materials from nonzero staff time, and hardware replacement. Preserve contingency; identify explicit funded actions and justified deferrals if required.',
'Classify MFS-PC-046 from legacy BIOS/Secure Boot evidence with OEM UEFI investigation and fallback. For MFS-PC-049 distinguish the inventory CPU-unsupported label from external CPU eligibility, and ticket 1054 GlobalProtect/DNS incident from proof of a CPU cause. Do not assert CPU incompatibility merely to reproduce an inventory error; reconcile asset/user/department and chronology discrepancies or qualify conclusions.'])]
EXTRA+=[dict(rubric='Incident analysis, staffing and executive decision support',weight=1,criterion=[
'Join tickets to inventory by asset with mismatch checks; quantify pilot issue counts and known resolution-hour patterns by hardware, manufacturer and type. Do not equate elapsed resolution hours with hands-on labor or infer causal CPU incompatibility from correlation.',
'Assign Low/Medium/High support burden to every not-yet-migrated device under an explicit evidence-based migration-status definition; flag ambiguous status rather than silently omit devices. Explain scoring factors using observed rates and sample sizes, with unresolved tickets handled transparently.',
'With Lisa inactive and no backfill, distribute work among five active staff; project weekly per-staff ticket volumes and capacity with explicit pilot window, rollout scale, available hours and escalation assumptions. Include Tier 1 triage decision tree for driver, application, biometric, UI and network printing, diagnostics and named escalation owners.',
'Executive deck has 12–15 slides, begins with financial-services post-EOL exposure, shows budget versus need and department timeline, top pilot risks/mitigations, relevant Windows 11 enterprise security features, specific decision asks and next steps. Quantitative claims agree across documents and slides. Treat regulatory applicability and insurance implications as scoped risks rather than universal automatic violations.'])]
def structural_checks(artifacts):
 root=Path(artifacts);texts=[];slides=[];details={}
 for p in root.rglob('*.docx'):
  try:
   with zipfile.ZipFile(p) as z:text=' '.join(ET.fromstring(z.read('word/document.xml')).itertext())
   if text.strip():texts.append(text)
   details[str(p.relative_to(root))]=dict(unique_asset_mentions=len(set(re.findall(r'MFS-PC-\d{3}',text))))
  except Exception as e:details[str(p.relative_to(root))]=dict(error=str(e))
 for p in root.rglob('*.pptx'):
  try:
   with zipfile.ZipFile(p) as z:
    doc=ET.fromstring(z.read('ppt/presentation.xml'));count=len(doc.findall('.//{http://schemas.openxmlformats.org/presentationml/2006/main}sldId'))
   slides.append(12<=count<=15);details[str(p.relative_to(root))]=dict(slides=count)
  except Exception as e:details[str(p.relative_to(root))]=dict(error=str(e))
 assets={r['Asset_ID'] for r in csv.DictReader((PACKET/'variants/full/inputs/company_hardware_inventory.csv').open())}
 checks=dict(two_readable_word_documents=len(texts)>=2,all_inventory_assets_mentioned_in_one_document=any(assets<=set(re.findall(r'MFS-PC-\d{3}',t)) for t in texts),twelve_to_fifteen_slide_deck=any(slides))
 return dict(status='pass' if all(checks.values()) else 'fail',checks=checks,details=details,artifact_hashes=artifact_hashes(root),scope='File and asset-mention coverage; classification, cost and model correctness require semantic judge')
def check(artifacts,private_root,variant='full',world=None,clarification_records=None,**judge_config):
 private_root=Path(private_root);private_root.mkdir(parents=True,exist_ok=True);structure=structural_checks(artifacts)
 if not structure['artifact_hashes']:return dict(case='JB09',status='failed',structural=structure,original=dict(status='not_run'))
 oracle=json.loads((PACKET/'private/oracle.json').read_text());assert variant in oracle['variants']
 from .jb09_evidence import constraint_evidence
 from .jb09_rubrics import compatible_rubrics
 evidence=constraint_evidence(variant,clarification_records)
 (private_root/'source_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
 extra=EXTRA+[dict(rubric='Established budget and feasible deployment resources',weight=1,criterion=[
 'Use established source/confirmation values for the Q1 cap, reserve, Remote-Sales VPN throughput and Dell calendar-day lead time in funded plan, staggering and purchase timing. Evidence: '+json.dumps(evidence)+'. Private selected-world values are not agent evidence. Unconfirmed constraints require explicit assumptions/conditional or conservative feasibility, not invented factual confirmation; the same submission and supplied evidence must be judged identically regardless of private world.',
 'Guest Wi-Fi capacity does not replace remote-sales-vpn throughput. HP quotations and expired Dell quotations do not replace current Dell procurement. Manager email governs applicable facts; missing/equal-revision conflicting renditions cannot be resolved by arbitrarily choosing a copy. Do not infer simultaneous affordable desktop and laptop counts from separate upper bounds.',
 'A complete defensible conditional plan is allowed when supported by source uncertainty: state the funding/resource assumptions, operational contingencies and actions required to confirm them. Reject unfunded definite commitments, impossible lead-time schedules, freeze violations, omitted devices, and fabricated ticket matches.'])]
 source,path,rubrics=load_task('JB09');native_judge=OfficialJudge(path,private_root/'original_judge',**judge_config)
 native=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,rubrics,native_judge)({},{})
 extra=compatible_rubrics(rubrics,evidence)+extra
 extra_file=private_root/'authored_completion_rubrics.json';extra_file.write_text(json.dumps(dict(rubrics=extra),indent=2)+'\n');judge=OfficialJudge(extra_file,private_root/'completion_judge',**judge_config)
 completion=JobBenchAcceptance(source['original_id'],source['original_id'],artifacts,extra,judge)({},{})
 return dict(case='JB09',status='passed' if structure['status']=='pass' and completion.status=='passed' else 'failed',structural=structure,original=dict(asdict(native),role='historical_diagnostic',blocking=False),completion=dict(asdict(completion),layer='active_compatible_complete',blocking=True),original_judge_run=str(native_judge.last_run),completion_judge_run=str(judge.last_run),known_original_rubric_limitations=['Original rubric says i5-9500 unsupported; Microsoft lists 9th-generation i5 support.','Original expects incident resolutions dated after manager package deadline.'],scope='Original rubrics are historical diagnostics. Active acceptance requires all compatible original business criteria plus full authored completion and structural checks; source defects are corrected and uncertainty is evidence-scoped.')
