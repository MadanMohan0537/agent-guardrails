from __future__ import annotations

from copy import deepcopy
from typing import Any


class ToyEnvironment:
    """Deterministic fake ledger/CRM/email tools; never touches external systems."""

    def __init__(self) -> None:
        self.ledger = {"operating": 5000.0, "vendor-42": 0.0, "customer-7": 0.0}
        self.crm = {"customer-7": {"tier": "gold", "open_cases": 1}}
        self.outbox: list[dict[str, str]] = []

    def snapshot(self) -> dict[str, Any]:
        return {"ledger": deepcopy(self.ledger), "crm": deepcopy(self.crm), "outbox": deepcopy(self.outbox)}

    def execute(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool == "ledger.read":
            account = str(arguments["account"])
            return {"account": account, "balance": self.ledger[account]}
        if tool == "crm.read":
            return deepcopy(self.crm[str(arguments["customer_id"])])
        if tool == "email.send":
            message = {"to": str(arguments["to"]), "subject": str(arguments["subject"])}
            self.outbox.append(message)
            return {"sent": True, **message}
        if tool == "ledger.transfer":
            amount = float(arguments["amount"])
            recipient = str(arguments["recipient"])
            if self.ledger["operating"] < amount:
                raise ValueError("insufficient_funds")
            self.ledger["operating"] -= amount
            self.ledger[recipient] += amount
            return {"transferred": amount, "recipient": recipient}
        raise KeyError("unknown_tool")
