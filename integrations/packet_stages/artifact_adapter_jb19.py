"""JB19 public references and private SOCI 201 early-alert artifact checker."""
from pathlib import Path
import hashlib, json

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / 'data/expanded/JB19'
_NATIVE = ROOT / 'data/source/dataset/sociology_teachers_postsecondary/task1'
REFERENCE_ROOT = _NATIVE / 'task_folder' if (_NATIVE / 'task_folder').exists() else _NATIVE

REFERENCES = {}
for name in ['Effective_Advising_Practice_Guide.pdf', 'student-por.csv']:
    p = REFERENCE_ROOT / name
    if not p.is_file():
        raise FileNotFoundError('Missing required JB19 public reference: '+str(p))
    REFERENCES[name] = dict(path=p, sha256=hashlib.sha256(p.read_bytes()).hexdigest(), url=None)


def knowledge(facts):
    atoms = json.loads((PACKET / 'private/oracle.json').read_text())['atoms']
    return {
        k: dict(
            value=v,
            answer=f"For SOCI 201 Fall 2024 early-alert reporting, {atoms[k]['issuer']} confirms {atoms[k]['subject']} is {v}."
        )
        for k, v in facts.items()
    }


def check(artifacts, private_root, variant, world):
    from .jb19_checker import check as full_check
    from .run_artifact_case import configure_judge_from_eval
    records=Path(private_root).parent/'user_records.json'
    return full_check(Path(artifacts),Path(private_root),variant,world,clarification_records=json.loads(records.read_text()) if records.exists() else [],**configure_judge_from_eval())
