# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json
import typing


class ClaimCourt(gl.Contract):
    """Web-grounded adjudication of a plain-English claim.

    Pattern: fetch a live page inside a non-deterministic block, ask an LLM for a
    structured verdict plus the verbatim quote that decides it, and reach consensus
    with a *structural* validator (not exact match on LLM prose). Every adjudication
    is stored append-only and addressable by id, so other contracts and frontends can
    consume the result instead of trusting an off-chain party.
    """

    claims: TreeMap[str, str]
    verdicts: TreeMap[str, str]
    evidence: TreeMap[str, str]
    sources: TreeMap[str, str]
    total: str

    def __init__(self):
        self.claims = TreeMap()
        self.verdicts = TreeMap()
        self.evidence = TreeMap()
        self.sources = TreeMap()
        self.total = "0"

    @gl.public.write
    def resolve(self, claim: str, source_url: str) -> typing.Any:
        if not claim or not source_url.startswith("http"):
            return "invalid input"

        def leader_fn():
            page = gl.nondet.web.render(source_url, mode="text", wait_after_loaded="3s")
            prompt = f"""You are a neutral fact-checker. Decide whether the CLAIM is supported by the SOURCE page below.

CLAIM: {claim}

SOURCE ({source_url}) text:
{page[:8000]}

Reply with JSON only, no prose:
{{"verdict": "TRUE" | "FALSE" | "UNCLEAR", "quote": "<short verbatim quote from the source that decides it, max 200 chars>"}}
Use UNCLEAR when the source never mentions the claim."""
            out = gl.nondet.exec_prompt(prompt, response_format="json")
            if isinstance(out, str):
                out = json.loads(out)
            verdict = str(out.get("verdict", "UNCLEAR")).upper().strip()
            if verdict not in ("TRUE", "FALSE", "UNCLEAR"):
                verdict = "UNCLEAR"
            return {"verdict": verdict, "quote": str(out.get("quote", ""))[:200]}

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            data = leader_result.calldata
            if not isinstance(data, dict):
                return False
            if data.get("verdict") not in ("TRUE", "FALSE", "UNCLEAR"):
                return False
            quote = data.get("quote")
            return isinstance(quote, str) and len(quote) <= 200

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        self.total = str(int(self.total) + 1)
        claim_id = self.total
        self.claims[claim_id] = claim
        self.verdicts[claim_id] = result["verdict"]
        self.evidence[claim_id] = result["quote"]
        self.sources[claim_id] = source_url
        return json.dumps({"id": claim_id, "verdict": result["verdict"]}, sort_keys=True)

    @gl.public.view
    def get(self, claim_id: str) -> str:
        return json.dumps(
            {
                "claim_id": claim_id,
                "claim": self.claims.get(claim_id, ""),
                "verdict": self.verdicts.get(claim_id, ""),
                "evidence": self.evidence.get(claim_id, ""),
                "source": self.sources.get(claim_id, ""),
            },
            sort_keys=True,
        )

    @gl.public.view
    def last(self) -> str:
        latest = self.total
        if latest == "0":
            return "{}"
        return self.get(latest)

    @gl.public.view
    def count(self) -> str:
        return self.total
