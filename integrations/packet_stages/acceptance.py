"""Host-side verdicts. Agent JSON is never evidence of execution."""
from dataclasses import dataclass, field
from copy import deepcopy
from .session import BindingError, canonical


@dataclass(frozen=True)
class CheckResult:
    layer: str
    status: str
    checks: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.status not in {"passed", "failed", "unavailable", "error"}:
            raise ValueError("Unknown acceptance status")
        if any(type(v) is not bool for v in self.checks.values()):
            raise ValueError("Checks must be booleans")
        if self.status == "passed" and (not self.checks or not all(self.checks.values())):
            raise ValueError("Empty or failing checks cannot pass")
        if self.status == "failed" and (not self.checks or all(self.checks.values())):
            raise ValueError("A failed result must identify a failing check")
        canonical(self.to_dict())

    @classmethod
    def evaluated(cls, layer, checks, **details):
        if not checks:
            raise BindingError("Empty acceptance checks: " + layer)
        return cls(layer, "passed" if all(checks.values()) else "failed", checks, details)

    def to_dict(self):
        return deepcopy(dict(layer=self.layer, status=self.status,
                             checks=self.checks, details=self.details))


class Acceptance:
    def __init__(self, checks, *, required=("original", "supplemental")):
        self.checks, self.required = dict(checks), tuple(required)
        if not self.required or any(not callable(self.checks.get(k)) for k in self.required):
            raise BindingError("Missing original or supplemental acceptance")
        self.results = {}

    def __call__(self, outputs, report):
        self.results = {}
        for layer in self.required:
            try:
                result = self.checks[layer](deepcopy(outputs), deepcopy(report))
                if not isinstance(result, CheckResult) or result.layer != layer:
                    raise TypeError("Wrong result type or layer")
            except Exception as error:
                result = CheckResult(layer, "error", details={"error": str(error)})
            self.results[layer] = result.to_dict()
        if any(r["status"] in {"unavailable", "error"} for r in self.results.values()):
            raise BindingError("Task acceptance unavailable or failed to execute")
        return all(r["status"] == "passed" for r in self.results.values())
