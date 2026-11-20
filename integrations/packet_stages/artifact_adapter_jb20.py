"""JB20 public references and private sales order reconciliation artifact checker."""
from pathlib import Path
import hashlib, json

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / 'data/expanded/JB20'
_NATIVE = ROOT / 'data/source/dataset/data_entry_keyers/task1'
REFERENCE_ROOT = _NATIVE / 'task_folder' if (_NATIVE / 'task_folder').exists() else _NATIVE

# All required local records are provided by the selected packet.
REFERENCES = {}


def knowledge(facts):
    atoms = json.loads((PACKET / 'private/oracle.json').read_text())['atoms']
    return {
        k: dict(
            value=v,
            answer=f"For the Q3 2025 Global Trade Solutions sales-order reconciliation, {atoms[k]['issuer']} confirms {atoms[k]['subject']} is {v}."
        )
        for k, v in facts.items()
    }


def check(artifacts, private_root, variant, world):
    from .jb20_checker import check as full_check
    from .run_artifact_case import configure_judge_from_eval
    records=Path(private_root).parent/'user_records.json'
    return full_check(Path(artifacts),Path(private_root),variant,world,clarification_records=json.loads(records.read_text()) if records.exists() else [],**configure_judge_from_eval())
