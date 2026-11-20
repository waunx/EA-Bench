"""Per-case existing decision checks, explicitly below full task acceptance."""
from copy import deepcopy
import hashlib
import json
from integrations.packet_eval.reference_paths.kernel import SOURCE, environment, read_data, decide
from integrations.packet_eval.reference_paths.validate import author_worlds, normal
from integrations.packet_eval.scoring import equal
from .acceptance import CheckResult
from .session import BindingError, canonical


def read_json(path):
    return json.loads(path.read_text())


def packet_inputs(case, variant):
    # Validate names through the frozen manifest before constructing paths.
    release = SOURCE.parent.parent / "data/authored"
    manifest = read_json(release / "manifest.json")
    if case + "--" + variant not in manifest["packets"]:
        raise BindingError("Unknown case or variant")
    folder = SOURCE / case / "variants" / variant
    expected = read_json(SOURCE / case / "MANIFEST.json")[variant]
    paths = {str(p.relative_to(folder)): p for p in folder.rglob("*") if p.is_file()}
    if set(paths) != set(expected) or any(p.is_symlink() for p in folder.rglob("*")):
        raise BindingError("Packet file set changed")
    if any(hashlib.sha256(paths[k].read_bytes()).hexdigest() != v for k, v in expected.items()):
        raise BindingError("Packet bytes changed")
    return folder / "inputs"


def reviewed_worlds(case, variant):
    packet_inputs(case, variant)
    directory = SOURCE / case / "private"
    return author_worlds(case, variant, read_json(directory / "oracle.json"),
                         read_json(directory / "check_result.json"))


class DecisionChecker:
    """Host selects an already reviewed world; never takes truth from the agent."""
    def __init__(self, case, variant, answers, *, input_directory=None):
        self.case, self.variant = case, variant
        worlds = reviewed_worlds(case, variant)
        matches = [expected for a, expected in worlds if canonical(a) == canonical(answers)]
        if len(matches) != 1:
            raise BindingError("World is missing, unreviewed, or ambiguous")
        env = environment(case, input_directory if input_directory is not None else packet_inputs(case, variant))
        self.data = read_data(case, env)
        self.expected = normal(decide(case, env, deepcopy(self.data), deepcopy(answers)))
        if not equal(self.expected, normal(matches[0])):
            raise BindingError("Reference disagrees with per-case reviewed result")
        self.answers = deepcopy(answers)

    def check(self, actual):
        checks = {key: isinstance(actual, dict) and key in actual and equal(actual[key], value)
                  for key, value in self.expected.items()}
        checks["exact_field_set"] = isinstance(actual, dict) and set(actual) == set(self.expected)
        return CheckResult.evaluated("diagnostic", checks, case=self.case, variant=self.variant,
                                     native_evaluator_run=False, full_task_acceptance=False)
