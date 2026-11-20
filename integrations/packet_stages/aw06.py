"""AW06 contracts. The fixture backend is authored data, not native Amazon."""
from copy import deepcopy
from functools import partial
from .authored import DecisionChecker, read_json, SOURCE
from .acceptance import Acceptance, CheckResult
from .session import BindingError, StageSession, canonical
from .native import AppWorldAcceptance


def same(a, b):
    return canonical(a) == canonical(b)


def object_schema(properties):
    return dict(type="object", properties=properties, required=list(properties),
                additionalProperties=False)


def schemas():
    text = {"type": "string"}
    cents = {"type": "integer", "minimum": 0}
    order = object_schema({k: {"type": "integer", "minimum": 1} for k in ("PS5", "SCALE", "XBOX")})
    row = object_schema({k: text for k in ("line", "sku", "qty", "selected", "seller", "gift")})
    cart = object_schema({"rows": {"type": "array", "items": row},
                          "metadata": object_schema({k: text for k in ("coupon", "address", "note")})})
    result = {"n7": cart}
    result["n2"] = object_schema({"order": order, "prices": object_schema({k: cents for k in ("PS5", "SCALE", "XBOX")})})
    result["n3"] = object_schema({"card": text})
    result["n4"] = object_schema({"card": text, "total_cents": cents, "budget_cents": cents})
    result["n5"] = object_schema({"order": order, "address": text})
    result["n6"] = object_schema({"order": order, "address": text, "card": text, "total_cents": cents})
    return result


class AW06Checker:
    def __init__(self, variant, answers, backend, *, input_directory=None):
        self.decision = DecisionChecker("AW06", variant, answers, input_directory=input_directory)
        self.backend = backend
        self.target = deepcopy(self.decision.expected)
        self.initial = deepcopy(backend.snapshot())
        t, d = self.target, self.decision.data
        if not same(self.initial["cart_rows"], t["restore_rows"]) or not same(self.initial["cart_metadata"], t["restore_metadata"]):
            raise BindingError("Backend initial cart does not match selected world")
        price = {r["sku"]: int(r["price_cents"]) for r in d["catalog"]
                 if r["sku"] in t["order"] and r["sku"] != "PS5"}
        price["PS5"] = t["total_cents"] - sum(price.values())
        self.plans = {
            "n2": dict(order=t["order"], prices=price),
            "n3": dict(card=t["card"]),
            "n4": dict(card=t["card"], total_cents=t["total_cents"], budget_cents=100000),
            "n5": dict(order=t["order"], address="HOME"),
            "n6": dict(order=t["order"], address="HOME", card=t["card"], total_cents=t["total_cents"]),
            "n7": dict(rows=t["restore_rows"], metadata=t["restore_metadata"]),
        }

    def read_cart(self, parents):
        # Preserve missing facts in the public attachment. Do not expose the
        # host's resolved coupon to the model in missing/conflict variants.
        return deepcopy(dict(rows=self.decision.data["before"], metadata=self.decision.data["meta"]))

    def check_plan(self, identity, data, parents):
        if not same(data, self.plans[identity]):
            return False
        if identity in {"n5", "n7"}:
            visible = self.read_cart({})
            if not same(parents["n1"], visible):
                return False
        return True

    @staticmethod
    def unchanged(before, after, allowed):
        return set(before) == set(after) and all(same(before[k], after[k]) for k in before if k not in allowed)

    def check_effect(self, identity, data, parents, evidence):
        before, after = evidence["before"], evidence["after"]
        if identity == "n5":
            allowed = {"checkout", "cart_rows", "cart_metadata"}
            selected = {}
            for row in after["cart_rows"]:
                if row["selected"] == "1":
                    try:
                        qty = int(row["qty"])
                    except (ValueError, TypeError):
                        return False
                    if qty <= 0:
                        return False
                    selected[row["sku"]] = selected.get(row["sku"], 0) + qty
            return (same(after["checkout"], self.plans["n5"]) and same(selected, self.target["order"])
                    and self.unchanged(before, after, allowed))
        if identity == "n6":
            allowed = {"orders", "payments", "checkout", "cart_rows", "cart_metadata"}
            return (self.order_created(before, after) and after["checkout"] is None
                    and self.unchanged(before, after, allowed))
        if identity == "n7":
            return (same(after["cart_rows"], self.target["restore_rows"]) and
                    same(after["cart_metadata"], self.target["restore_metadata"]) and
                    self.unchanged(before, after, {"cart_rows", "cart_metadata"}))
        raise BindingError("Unknown AW06 write node")

    def order_created(self, before, after):
        orders, payments = after["orders"], after["payments"]
        if len(orders) != len(before["orders"]) + 1 or len(payments) != len(before["payments"]) + 1:
            return False
        if not same(orders[:-1], before["orders"]) or not same(payments[:-1], before["payments"]):
            return False
        order = orders[-1]
        if set(order) != set(self.plans["n6"]) | {"id"} or not isinstance(order["id"], str) or not order["id"]:
            return False
        if order["id"] in {r["id"] for r in before["orders"]}:
            return False
        expected_payment = dict(order_id=order["id"], card=self.target["card"],
                                total_cents=self.target["total_cents"])
        return (same({k: v for k, v in order.items() if k != "id"}, self.plans["n6"])
                and same(payments[-1], expected_payment))

    def final(self, outputs, report, layer="supplemental"):
        state = self.backend.snapshot()
        return CheckResult.evaluated(layer, {
            "one_correct_order_and_payment": self.order_created(self.initial, state),
            "cart_rows_restored": same(state["cart_rows"], self.initial["cart_rows"]),
            "cart_metadata_restored": same(state["cart_metadata"], self.initial["cart_metadata"]),
            "checkout_consumed": state["checkout"] is None,
            "protected_state_preserved": self.unchanged(self.initial, state, {"orders", "payments", "checkout"}),
            "report": same(report, {"completed": True}),
        }, backend=self.backend.validation_layer)


def create_aw06(variant, answers, backend, *, original=None, ask_handler=None):
    fixture = backend.validation_layer == "authored_fixture"
    if not fixture:
        if backend.validation_layer != "native" or not isinstance(original, AppWorldAcceptance):
            raise BindingError("AW06 requires the original AppWorld evaluator")
        source = read_json(SOURCE / "AW06/SOURCE.json")
        if original.task_id != source["original_id"] or backend.task_id != original.task_id:
            raise BindingError("AW06 native ID mismatch")
        if not getattr(backend, "information_isolation_reviewed", False):
            raise BindingError("Native API information-leak review is required")
    elif original is not None:
        raise BindingError("Fixture results cannot be presented as native acceptance")
    checker = AW06Checker(variant, answers, backend)
    release = SOURCE.parent.parent / "data/authored"
    nodes = read_json(release / "cases/AW06/workflow.json")["nodes"]
    for node in nodes:
        if node["kind"] != "read":
            node["schema"] = schemas()[node["id"]]
    checks = {n["id"]: partial(checker.check_plan, n["id"]) for n in nodes if n["kind"] != "read"}
    if fixture:
        acceptance = Acceptance({"authored_state": partial(checker.final, layer="authored_state")},
                                required=("authored_state",))
    else:
        acceptance = Acceptance({"original": original, "supplemental": checker.final},
                                required=("supplemental", "original"))
    session = StageSession(nodes, {"n1": checker.read_cart}, checks, acceptance,
        writers={"n5": backend.prepare, "n6": backend.checkout, "n7": backend.restore},
        observers={n: backend.snapshot for n in ("n5", "n6", "n7")},
        effect_checkers={n: partial(checker.check_effect, n) for n in ("n5", "n6", "n7")},
        ask_handler=ask_handler)
    session.acceptance, session.case_checker = acceptance, checker
    session.validation_layer = "authored_fixture" if fixture else "native_plus_supplemental"
    return session
