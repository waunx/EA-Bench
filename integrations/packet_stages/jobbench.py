"""Bind original JobBench task/rubric files and invoke the official judge."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from .authored import SOURCE, read_json
from .native import JobBenchAcceptance
from .session import BindingError

ROOT = SOURCE.parent.parent
JUDGE = ROOT / "vendor/jobbench/eval/judge.py"
DEFAULT_JUDGE_MODEL = "gpt-5.5"


def load_task(case):
    if case not in {"JB" + str(i).zfill(2) for i in range(1, 31)}:
        raise BindingError("Unknown JobBench case")
    source = read_json(SOURCE / case / "SOURCE.json")
    task = ROOT / "data/source/dataset" / source["original_id"]
    instruction = task / "task_folder/TASK_INSTRUCTIONS.txt"
    if instruction.read_text().strip() != source["original_text"].strip():
        raise BindingError("Original JobBench task text mismatch: " + case)
    path = task / "RUBRICS.json"
    raw = read_json(path)
    rubrics = raw.get("rubrics", raw.get("evaluation_rubrics", []))
    if not rubrics:
        raise BindingError("Missing original JobBench rubrics")
    for row in rubrics:
        criteria = row.get("criterion", [])
        if isinstance(criteria, str):
            criteria = [criteria]
        if not criteria or not all(isinstance(c, str) and c.strip() for c in criteria):
            raise BindingError("Missing original rubric criteria")
        weight = row["weight"]
        if type(weight) not in (int, float) or not math.isfinite(weight) or weight < 0:
            raise BindingError("Invalid rubric weight")
    return source, path, rubrics


class OfficialJudge:
    """Fresh private report directory on every invocation; no stale score reuse."""
    def __init__(self, rubric_file, private_root, *, model=DEFAULT_JUDGE_MODEL, api_base=None,
                 python=sys.executable, timeout=3600):
        if not model:
            raise BindingError("Explicit JobBench judge model required")
        self.rubric_file, self.private_root = Path(rubric_file).resolve(), Path(private_root).resolve()
        self.model, self.python, self.timeout = model, python, timeout
        self.api_base = (api_base or os.environ.get("JUDGE_API_BASE")
                         or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1")
        self.rubric_hash = hashlib.sha256(self.rubric_file.read_bytes()).hexdigest()
        self.last_run = None

    def __call__(self, artifacts):
        if hashlib.sha256(self.rubric_file.read_bytes()).hexdigest() != self.rubric_hash:
            raise BindingError("Rubrics changed after binding")
        if self.private_root.is_relative_to(Path(artifacts).resolve()):
            raise BindingError("Judge results must be outside submitted artifacts")
        self.private_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        run = Path(tempfile.mkdtemp(prefix="judge-", dir=self.private_root))
        self.last_run = run
        from .judge_visual_evidence import prepare
        judge_artifacts=prepare(artifacts,run)
        args = [self.python, str(JUDGE), "--output-dir", str(judge_artifacts.resolve()),
                "--rubrics-file", str(self.rubric_file), "--judge-model", self.model,
                "--details-file", str(run / "details.json"),
                "--extraction-file", str(run / "extraction.json"),
                "--detail-log-dir", str(run / "debug"), "--detail-log-prefix", "original",
                "--result-file", str(run / "reward.json")]
        from .calc_runtime import VALIDATION
        if VALIDATION.exists():
            runtime=read_json(VALIDATION)
            if runtime.get('status')=='passed':
                args[1]=str(ROOT/'integrations/packet_stages/jobbench_judge_entry.py')
                (run/'calc_runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
        if self.api_base:
            args += ["--api-base", self.api_base]
        # Credentials are read by the original judge from its environment.
        with ExitStack() as stack:
            from .judge_environment import judge_environment
            env=judge_environment()
            dependencies=['/tmp/ea-bench-notebook-compat','/tmp/ea-bench-judge-deps','/tmp/ea-bench-analysis-deps']
            env['PYTHONPATH']=os.pathsep.join([p for p in dependencies if Path(p).is_dir()]+([env['PYTHONPATH']] if env.get('PYTHONPATH') else []))
            with (run / "judge.log").open("w") as log:
                process = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, timeout=self.timeout,env=env)
        if process.returncode or not (run / "details.json").is_file():
            raise BindingError("Original JobBench judge failed; inspect private judge.log")
        extraction = read_json(run / "extraction.json")
        if extraction.get("status") != "complete":
            raise BindingError("JobBench extraction did not complete")
        details = read_json(run / "details.json")
        if details.get("error"):
            raise BindingError("Original JobBench judge returned an error")
        for row in details.get("rubrics", []):
            log = run / "debug" / ("original_rubric_" + str(row["index"]) + ".log")
            if not log.is_file():
                raise BindingError("Missing original judge execution evidence")
            header = log.read_text().split("\n\n", 1)[0].splitlines()
            if "API Exit Code: 0" not in header:
                raise BindingError("Judge API failure is not a model task failure")
        return details


def create_original_checker(case, artifacts, private_root, **judge_config):
    source, path, rubrics = load_task(case)
    judge = OfficialJudge(path, private_root, **judge_config)
    return JobBenchAcceptance(source["original_id"], source["original_id"], artifacts, rubrics, judge)
