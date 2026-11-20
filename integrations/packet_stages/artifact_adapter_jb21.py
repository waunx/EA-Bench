"""JB21 public references and private training deliverable artifact checker."""
from pathlib import Path
import hashlib, json

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / 'data/expanded/JB21'
ORACLE_PATH = PACKET / 'private/oracle.json'
REFERENCE_ROOT = ROOT / 'data/source/dataset/training_and_development_specialists/task2/files_required_to_search'
REFERENCES = {name:dict(path=REFERENCE_ROOT/name,sha256=hashlib.sha256((REFERENCE_ROOT/name).read_bytes()).hexdigest(),url=url) for name,url in {
'kirkpatrick_evaluation_forms.pdf':'https://www.kirkpatrickpartners.com/wp-content/uploads/2024/04/evaluation-form-samples.pdf',
'onboarding_feedback_form.xlsx':'https://www.smartsheet.com/sites/default/files/IC-Strategic-HR-Onboarding-Feedback-Form.xlsx'}.items()}


def knowledge(facts):
    atoms = json.loads(ORACLE_PATH.read_text())['atoms']
    return {
        k: dict(
            value=v,
            answer=f"For the Meridian Health Partners Q4 training plan, {atoms[k]['issuer']} confirms {atoms[k]['subject']} is {v}."
        )
        for k, v in facts.items()
    }


def check(artifacts, private_root, variant, world):
    from .jb21_checker import check as full_check
    from .run_artifact_case import configure_judge_from_eval
    records=Path(private_root).parent/'user_records.json'
    return full_check(Path(artifacts),Path(private_root),variant,world,clarification_records=json.loads(records.read_text()) if records.exists() else [],**configure_judge_from_eval())
