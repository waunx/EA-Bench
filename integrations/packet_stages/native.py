"""Adapters for host-owned original evaluators, never agent-reported scores.

Callers bind frozen native task IDs/state and provide the original evaluator.
These adapters do not claim to create the currently missing native task worlds.
"""
from .acceptance import CheckResult
from .session import BindingError
from pathlib import Path
import hashlib
import math


def artifact_hashes(directory):
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise BindingError("Missing artifact directory or symlink")
    hashes = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise BindingError("Artifact symlink")
        if path.is_file():
            hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif not path.is_dir():
            raise BindingError("Artifact is not a regular file")
    return hashes


class JobBenchAcceptance:
    """Complete acceptance requires all criteria; retain the native weighted score."""
    def __init__(self, task_id, expected_task_id, artifacts, rubrics, judge):
        require_identity(task_id, expected_task_id)
        if not callable(judge) or not rubrics:
            raise BindingError("Missing JobBench judge or rubrics")
        self.task_id, self.artifacts = task_id, Path(artifacts)
        self.rubrics, self.judge = rubrics, judge

    def __call__(self, outputs, report):
        before = artifact_hashes(self.artifacts)
        if not before:
            return CheckResult.evaluated("original", {"delivered_files": False}, backend="jobbench")
        raw = self.judge(self.artifacts)
        if artifact_hashes(self.artifacts) != before:
            raise BindingError("Artifacts changed during judging")
        if raw.get("error"):
            raise BindingError("JobBench judge error")
        results = raw["rubrics"]
        if len(results) != len(self.rubrics) or {r["index"] for r in results} != set(range(len(self.rubrics))):
            raise BindingError("Incomplete or duplicate rubric results")
        return self._score(results, before)

    def _score(self, results, hashes):
        checks, total, maximum = {}, 0, 0
        for row in results:
            index = row["index"]
            rubric, result = self.rubrics[index], row["result"]
            criteria = rubric.get("criterion", [])
            if isinstance(criteria, str):
                criteria = [criteria]
            if not isinstance(criteria, list) or not criteria or not all(isinstance(c, str) and c.strip() for c in criteria):
                raise BindingError("Empty or malformed original rubric criteria")
            items = result["criteria_results"]
            if len(items) != len(criteria) or {r["index"] for r in items} != set(range(len(criteria))):
                raise BindingError("Incomplete criterion results")
            if any(type(r["passed"]) is not bool for r in items) or type(result["passed"]) is not bool:
                raise BindingError("Non-boolean judge verdict")
            passed = all(r["passed"] for r in items)
            weight = rubric["weight"]
            if type(weight) not in (int, float) or not math.isfinite(weight) or weight < 0:
                raise BindingError("Invalid rubric weight")
            if result["passed"] != passed or row["weight"] != weight or result["score"] != (weight if passed else 0):
                raise BindingError("Inconsistent judge score")
            checks["rubric_" + str(index)] = passed
            total += result["score"]
            maximum += weight
        if maximum <= 0:
            raise BindingError("Empty rubric weight")
        return CheckResult.evaluated("original", checks, backend="jobbench",
                                     task_id=self.task_id, total_score=total,
                                     max_score=maximum, normalized_score=total / maximum,
                                     artifact_hashes=hashes)


def require_identity(actual, expected):
    if not actual or actual != expected:
        raise BindingError("Native task ID does not match the packet")


class AppWorldAcceptance:
    """evaluate_tasks must return the official aggregate/individual report."""
    def __init__(self, task_id, expected_task_id, evaluate_tasks):
        require_identity(task_id, expected_task_id)
        if not callable(evaluate_tasks):
            raise BindingError("Missing AppWorld evaluator")
        self.task_id, self.evaluate_tasks = task_id, evaluate_tasks

    def __call__(self, outputs, report):
        raw = self.evaluate_tasks([self.task_id])
        result = raw["individual"][self.task_id]
        success, passes, fails = result["success"], result["passes"], result["fails"]
        if type(success) is not bool or not isinstance(passes, list) or not isinstance(fails, list):
            raise BindingError("Malformed AppWorld result")
        if not passes and not fails:
            raise BindingError("AppWorld ran no task tests")
        if success != (not fails):
            raise BindingError("Inconsistent AppWorld verdict")
        return CheckResult.evaluated("original", {"native_tests": success},
                                     backend="appworld", task_id=self.task_id,
                                     passes=passes, fails=fails)


class WorkBenchAcceptance:
    """Replay the HOST trace with the original is_correct evaluator.

Use an isolated native worker: the original evaluator resets global state.
Supplemental state must be captured before this callback is invoked.
"""
    def __init__(self, task_id, expected_task_id, ground_truth, read_trace, is_correct):
        require_identity(task_id, expected_task_id)
        if not callable(read_trace) or not callable(is_correct) or not isinstance(ground_truth, list):
            raise BindingError("Incomplete WorkBench binding")
        self.task_id, self.ground_truth = task_id, list(ground_truth)
        self.read_trace, self.is_correct = read_trace, is_correct

    def __call__(self, outputs, report):
        trace = self.read_trace()
        actions, error = trace["actions"], trace["error"]
        if not isinstance(actions, list) or not all(isinstance(a, str) for a in actions):
            raise BindingError("Invalid host action trace")
        result = self.is_correct(actions, self.ground_truth, error)
        if type(result) is not bool:
            raise BindingError("WorkBench supplied no boolean verdict")
        return CheckResult.evaluated("original", {"native_state_match": result},
                                     backend="workbench", task_id=self.task_id)
