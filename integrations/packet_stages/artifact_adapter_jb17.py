"""JB17 public references, clarification facts, and private artifact checker."""
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / 'data/expanded/JB17'
NATIVE = ROOT / 'data/source/dataset/computer_and_information_systems_managers/task2'
REFERENCE_ROOT = NATIVE / 'files_required_to_search'

REFERENCES = {}
for p in REFERENCE_ROOT.iterdir():
    if p.is_file():
        REFERENCES[p.name] = dict(path=p, sha256=hashlib.sha256(p.read_bytes()).hexdigest(), url=None)


def knowledge(facts):
    atoms = json.loads((PACKET / 'private/oracle.json').read_text())['atoms']
    answers = {
        'budget': 'For Cloud Migration Phase 2 (PRJ-2024-041), the PMO November 15 2024 portfolio confirms the approved budget is {value} USD.',
        'monthly_cost': 'For SRV-007, the IT infrastructure inventory confirms the current monthly on-premise operating cost is {value} USD.',
        'network_timeline': 'For Zero Trust Network Architecture rollout (PRJ-2024-042), the PMO November 15 2024 portfolio confirms the planned timeline is {value}.',
    }
    return {k: dict(value=v, answer=answers.get(k, atoms[k]['issuer'] + ' confirms ' + atoms[k]['subject'] + ' is {value}.').format(value=v)) for k, v in facts.items()}


def check(artifacts, private_root, variant, world):
    from .run_artifact_case import configure_judge_from_eval
    from .jb17_checker import check as full_check
    p = Path(private_root).parent / 'user_records.json'
    clarification_records = json.loads(p.read_text()) if p.exists() else []
    return full_check(artifacts, private_root, variant, world, clarification_records=clarification_records, **configure_judge_from_eval())
