# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json
import typing


class SourceWatch(gl.Contract):
    """Stable-field extraction from live web pages, for use as oracle evidence.

    Pattern: web pages change between validator requests (counts tick, ads rotate,
    timestamps drift). Instead of asking validators to agree on a whole page, the
    caller names the fields it needs and the non-deterministic block returns only
    those fields. The validator checks the *shape* of the result (every requested
    field present, scalar, short), so consensus survives cosmetic page churn while
    still refusing malformed extractions.
    """

    snapshots: TreeMap[str, str]
    urls: TreeMap[str, str]
    rounds: TreeMap[str, str]
    total: str

    def __init__(self):
        self.snapshots = TreeMap()
        self.urls = TreeMap()
        self.rounds = TreeMap()
        self.total = "0"

    @gl.public.write
    def watch(self, watch_id: str, source_url: str, fields: str) -> typing.Any:
        if not watch_id or not source_url.startswith("http") or not fields:
            return "invalid input"
        wanted = [f.strip() for f in fields.split(",") if f.strip()]
        if not wanted:
            return "invalid input"

        def leader_fn():
            page = gl.nondet.web.render(source_url, mode="text", wait_after_loaded="3s")
            prompt = f"""Extract the requested fields from the page text below.

Fields: {", ".join(wanted)}

SOURCE ({source_url}) text:
{page[:8000]}

Reply with JSON only: one key per requested field. Each value must be a short scalar
(string or number). If a field is absent from the page use the string "NOT_FOUND"."""
            out = gl.nondet.exec_prompt(prompt, response_format="json")
            if isinstance(out, str):
                out = json.loads(out)
            clean = {}
            for key in wanted:
                value = out.get(key, "NOT_FOUND")
                if isinstance(value, (int, str)):
                    clean[key] = str(value)[:120]
                else:
                    clean[key] = "NOT_FOUND"
            return clean

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            data = leader_result.calldata
            if not isinstance(data, dict):
                return False
            for key in wanted:
                if key not in data:
                    return False
                value = data[key]
                if not isinstance(value, str) or len(value) > 120:
                    return False
            return True

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        self.total = str(int(self.total) + 1)
        previous = int(self.rounds.get(watch_id, "0"))
        self.rounds[watch_id] = str(previous + 1)
        self.urls[watch_id] = source_url
        self.snapshots[watch_id] = json.dumps(result, sort_keys=True)
        return json.dumps(
            {"watch_id": watch_id, "round": previous + 1, "fields": result}, sort_keys=True
        )

    @gl.public.view
    def latest(self, watch_id: str) -> str:
        return json.dumps(
            {
                "watch_id": watch_id,
                "source": self.urls.get(watch_id, ""),
                "round": int(self.rounds.get(watch_id, "0")),
                "fields": json.loads(self.snapshots.get(watch_id, "{}")),
            },
            sort_keys=True,
        )

    @gl.public.view
    def count(self) -> str:
        return self.total
