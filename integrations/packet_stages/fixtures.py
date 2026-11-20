"""Authored offline state machine for checking AW06 predicates, not native replay."""
from copy import deepcopy


class AW06FixtureBackend:
    validation_layer = "authored_fixture"

    def __init__(self, expected):
        self.state = dict(cart_rows=deepcopy(expected["restore_rows"]),
                          cart_metadata=deepcopy(expected["restore_metadata"]),
                          checkout=None, orders=[{"id": "existing", "protected": True}],
                          payments=[{"order_id": "existing", "protected": True}],
                          unrelated={"wishlist": ["keep"], "profile": {"name": "keep"}})
        self.calls = []

    def snapshot(self):
        return deepcopy(self.state)

    def prepare(self, data, parents):
        self.calls.append("n5")
        self.state["checkout"] = deepcopy(data)
        self.state["cart_rows"] = [
            dict(line="new-" + sku, sku=sku, qty=str(qty), selected="1", seller="fixture", gift="0")
            for sku, qty in data["order"].items()]
        return {"prepared": True}

    def checkout(self, data, parents):
        self.calls.append("n6")
        if self.state["checkout"] != {k: data[k] for k in ("order", "address")}:
            raise ValueError("No matching prepared checkout")
        identity = "order-" + str(len(self.state["orders"]))
        self.state["orders"].append(dict(deepcopy(data), id=identity))
        self.state["payments"].append(dict(order_id=identity, card=data["card"], total_cents=data["total_cents"]))
        self.state["checkout"] = None
        self.state["cart_rows"] = []
        return {"order_id": identity}

    def restore(self, data, parents):
        self.calls.append("n7")
        self.state["cart_rows"] = deepcopy(data["rows"])
        self.state["cart_metadata"] = deepcopy(data["metadata"])
        return {"restored": True}
