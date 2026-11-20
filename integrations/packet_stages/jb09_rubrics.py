"""Complete original business coverage, corrected for source defects and current facts."""
from copy import deepcopy
import json

def compatible_rubrics(original, evidence):
 rubrics=deepcopy(original)
 # Original CPU criterion contradicts the supplied Microsoft reference.
 rubrics[0]['rubric']='Does the plan investigate MFS-PC-049 using supported-CPU evidence and qualified incident linkage?'
 rubrics[0]['criterion']=[
  'Identify MFS-PC-049 as Dell OptiPlex 3070 with i5-9500, TPM 2.0, Secure Boot and UEFI. The supplied Microsoft reference supports the ninth-generation i5; distinguish the incorrect inventory CPU-unsupported label from actual eligibility, and investigate the reported failed upgrade without inventing a CPU incompatibility.',
  'Discuss ticket 1054 and its GlobalProtect split-tunnel/DNS network issue and documented Marcus Thompson resolution. Check asset, user, department and dates before linking it to MFS-PC-049; a mismatch must be disclosed rather than treated as confirmed identity.',
  'Retain conditional hardware/firmware and migration-status verification, pilot/rollback and incident follow-up. CPU support alone does not prove migration completion or explain a network incident.',
  'Respect the December 6, 2025 package deadline: later tickets/resolutions may be analyzed as a clearly labeled supplied retrospective snapshot, or excluded with a justified as-of cutoff. Do not claim future resolution was known at deadline.'
 ]
 # Sales inventory has a second ninth-generation i5 false negative (074).
 rubrics[2]['criterion'][0]="Acknowledge Sales has 11 devices, with 4 Yes and 7 No labels in the inventory, and February–March downtime freeze. Reconcile labels with actual specifications: MFS-PC-074 has a supported i5-9500; MFS-PC-036 has no TPM detected and MFS-PC-067 has TPM 1.2. Distinguish these investigation/remediation candidates from the four genuinely older unsupported CPUs; do not force five CPU replacements to reproduce an inventory error."
 # Exact ticket figures remain useful for the full supplied snapshot; scoped as-of analysis is valid.
 temporal=' These figures describe the entire supplied 61-ticket snapshot, not necessarily knowledge available by December 6, 2025. Accept an explicitly dated as-of subset with correctly recomputed counts/means and transparent exclusions; retain the same analysis and staffing/triage coverage.'
 for index in (3,4,6):
  rubrics[index]['criterion']=[criterion+temporal for criterion in rubrics[index]['criterion']]
 rubrics[5]['criterion'][1]='Discuss PCI DSS exposure where applicable to payment-card systems, and distinguish framework applicability and risk from automatic universal noncompliance. Address the supplied guide with appropriate scope; mentioning ISO 27001/HIPAA does not establish they apply to MFS.'
 rubrics[5]['criterion'][3]='Contextualize unsupported Windows 10 security exposure for financial services, including ransomware/malware and absence of ordinary support after EOL. Do not reject a properly scoped ESU or other documented interim protection; residual risk and deadline obligations remain.'
 rubrics[7]['rubric']='Does the funded plan respect the established current cap and reserve, reconcile every device cost and justify specific deferrals?'
 rubrics[7]['criterion']=[
  'Use the current established budget and preserve the contingency reserve. Source/confirmation evidence: '+json.dumps(evidence)+'. When budget is unconfirmed, label assumptions and provide a feasible conditional or conservative plan; never award factual confirmation for a lucky private-world guess.',
  'Itemize all required desktop/laptop replacements and RAM, TPM, Secure Boot and OS licensing work with per-device costs. Current allowances are $1,100 desktop, $1,400 laptop, $85 for 4-to-8 GB RAM and $130 Home-to-Pro license; distinguish zero material cost from staff time. Recompute counts and totals after correcting eligibility labels; historical 16 desktops/7 laptops/$27,785 are not mandatory minima.',
  'Address MFS-PC-023 (IT) and MFS-PC-033 (Marketing) workstation costs with explicit justified allowances or sourced quotes; do not silently price them as standard desktops.',
  'Reconcile funded totals against cap minus reserve, with no double counting. If necessary name devices/departments deferred and business reasons, preserving Finance/Legal audit and Sales freeze constraints. A plan above the established spendable cap without feasible funded alternatives fails.'
 ]
 return rubrics
