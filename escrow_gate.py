# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json
import typing


class EscrowGate(gl.Contract):
    """Deterministic settlement of a two-party deal against an adjudicated verdict.

    Pattern: keep the money logic fully deterministic and let the *verdict* be the
    only non-deterministic input. A deal is opened with a named beneficiary for each
    outcome, then settled exactly once with a TRUE/FALSE verdict plus an evidence
    reference (a ClaimCourt claim id, a SourceWatch round, or any URI). Rejected
    settlements do not consume the deal, so a bad verdict can be retried with better
    evidence instead of bricking the escrow.

    On a network with native value transfer, settlement would also call
    emit_transfer; it is omitted here because StudioNet does not move value.
    """

    status: TreeMap[str, str]
    buyer: TreeMap[str, str]
    seller: TreeMap[str, str]
    amount: TreeMap[str, str]
    terms: TreeMap[str, str]
    evidence_ref: TreeMap[str, str]
    total: str

    def __init__(self):
        self.status = TreeMap()
        self.buyer = TreeMap()
        self.seller = TreeMap()
        self.amount = TreeMap()
        self.terms = TreeMap()
        self.evidence_ref = TreeMap()
        self.total = "0"

    @gl.public.write
    def open_deal(self, deal_id: str, buyer: str, seller: str, amount: int, terms_url: str) -> typing.Any:
        if not deal_id or not buyer or not seller:
            return "invalid input"
        if amount <= 0:
            return "invalid amount"
        if self.status.get(deal_id, ""):
            return "deal exists"
        self.status[deal_id] = "OPEN"
        self.buyer[deal_id] = buyer
        self.seller[deal_id] = seller
        self.amount[deal_id] = str(amount)
        self.terms[deal_id] = terms_url
        self.total = str(int(self.total) + 1)
        return json.dumps({"deal_id": deal_id, "status": "OPEN", "amount": amount}, sort_keys=True)

    @gl.public.write
    def settle(self, deal_id: str, verdict: str, evidence_ref_id: str) -> typing.Any:
        current = self.status.get(deal_id, "")
        if current != "OPEN":
            return "deal not open"
        normalized = verdict.upper().strip()
        if normalized not in ("TRUE", "FALSE"):
            return "verdict must be TRUE or FALSE"
        if not evidence_ref_id:
            return "evidence reference required"
        beneficiary = self.seller.get(deal_id, "") if normalized == "TRUE" else self.buyer.get(deal_id, "")
        self.status[deal_id] = "SETTLED_TRUE" if normalized == "TRUE" else "SETTLED_FALSE"
        self.evidence_ref[deal_id] = evidence_ref_id
        return json.dumps(
            {
                "deal_id": deal_id,
                "verdict": normalized,
                "paid_to": beneficiary,
                "amount": self.amount.get(deal_id, "0"),
                "evidence": evidence_ref_id,
            },
            sort_keys=True,
        )

    @gl.public.view
    def get(self, deal_id: str) -> str:
        return json.dumps(
            {
                "deal_id": deal_id,
                "status": self.status.get(deal_id, ""),
                "buyer": self.buyer.get(deal_id, ""),
                "seller": self.seller.get(deal_id, ""),
                "amount": self.amount.get(deal_id, "0"),
                "terms": self.terms.get(deal_id, ""),
                "evidence": self.evidence_ref.get(deal_id, ""),
            },
            sort_keys=True,
        )

    @gl.public.view
    def count(self) -> str:
        return self.total
