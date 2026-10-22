"""Probe the hosted model of the model-size study (NVIDIA NIM) before any run.

    python scripts/probe_hosted.py --capabilities        # reasoning on/off, structured output, served id
    python scripts/probe_hosted.py --rate-limit --burst 50   # how many requests per minute this key gets

Writes outputs/model_size/probes/<UTC timestamp>_<what>.json (no API key in it: the key is
read by trafficsense.llm.hosted.load_api_key and only goes into the Authorization header).

Capabilities: the same short decision prompt (two phases, JSON answer) is sent with
  default         no reasoning parameter
  thinking_off    chat_template_kwargs {"enable_thinking": false} (NVIDIA's documented switch)
  json_schema     thinking off + OpenAI response_format json_schema
  guided_json     thinking off + nvext.guided_json
  seed            thinking off + seed 0
and each records: HTTP status, latency, the model id the API returned, finish reason, token
usage, reasoning characters returned, the raw content and whether prompt.parse_response
accepts it.
Rate limit: first 5 sequential calls (latency and every response header), then `--burst`
tiny calls (max_tokens 1) sent as fast as 8 threads allow; it records when the first 429
arrived and how many calls succeeded in the first 60 s. NIM sends no rate-limit headers
(checked), so this is the only way to see the limit of a key. The burst is sent once.
Paced (--paced RPM --seconds S): after a 60 s pause, tiny calls one after another at RPM per
minute for S seconds; shows whether a sustained rate (the runs' pattern: one call at a time)
gets 429s.
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

from trafficsense.config import load_config, repo_root
from trafficsense.llm import prompt
from trafficsense.llm.hosted import load_api_key

OUT = Path("outputs/model_size/probes")
SCHEMA = prompt.response_schema([1, 3], "guided_v3")
MSG = [{"role": "system", "content": 'Reply JSON: {"phase": <allowed id>, "reason": "<at most 15 words>"}'},
       {"role": "user", "content": "Allowed phases: 1 (pressure 12, queue 14), 3 (pressure 2, queue 5). "
                                   "HIGHER pressure = the phase needs green MORE. Which phase next?"}]
OFF = {"chat_template_kwargs": {"enable_thinking": False}}
VARIANTS = {"default": {}, "thinking_off": OFF,
            "json_schema": {**OFF, "response_format": {"type": "json_schema",
                                                        "json_schema": {"name": "decision", "schema": SCHEMA}}},
            "guided_json": {**OFF, "nvext": {"guided_json": SCHEMA}},
            "seed": {**OFF, "seed": 0}}


def post(h: dict, url: str, body: dict, timeout: float) -> dict:
    t0 = time.perf_counter()
    t_sent = time.time()
    try:
        r = requests.post(url, json=body, headers=h, timeout=(10, timeout))
    except requests.exceptions.RequestException as e:
        return {"sent_unix": t_sent, "status": type(e).__name__, "latency_s": time.perf_counter() - t0}
    out = {"sent_unix": t_sent, "status": r.status_code, "latency_s": time.perf_counter() - t0,
           "headers": dict(r.headers)}
    try:
        d = r.json()
    except ValueError:
        return out | {"body": r.text[:300]}
    if r.status_code != 200:
        return out | {"body": d}
    ch = d["choices"][0]
    m = ch["message"]
    rc = m.get("reasoning_content") or m.get("reasoning") or ""
    out.update(model_returned=d.get("model"), finish_reason=ch.get("finish_reason"), usage=d.get("usage"),
               reasoning_chars=len(rc), reasoning_head=rc[:200], content=m.get("content"))
    try:
        out["parsed"] = list(prompt.parse_response(m.get("content") or "", [1, 3], 15))
    except prompt.InvalidResponse as e:
        out["parse_error"] = f"{e.failure_type}: {e}"
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--capabilities", action="store_true")
    ap.add_argument("--rate-limit", action="store_true")
    ap.add_argument("--burst", type=int, default=0)
    ap.add_argument("--paced", type=float, default=0, help="sequential calls at this many per minute")
    ap.add_argument("--seconds", type=float, default=90)
    ap.add_argument("--timeout", type=float, default=120)
    args = ap.parse_args()
    hc = load_config(args.config)["llm_hosted"]["nvidia_nim"]
    root = repo_root()
    key = load_api_key(hc["api_key_env"], root / hc["env_file"])
    h = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    url = hc["base_url"].rstrip("/") + hc["endpoint"]
    base = {"model": hc["model"], "messages": MSG, "temperature": 0, "max_tokens": hc["max_tokens"], "stream": False}
    started = datetime.now(timezone.utc)
    rec = {"script": "scripts/probe_hosted.py", "model_requested": hc["model"], "endpoint": url,
           "started_utc": started.isoformat(timespec="seconds"), "note": "API key not recorded"}
    if args.capabilities:
        rec["capabilities"] = {}
        for name, extra in VARIANTS.items():
            rec["capabilities"][name] = r = post(h, url, base | extra, args.timeout)
            print(f"{name:<13} HTTP {r['status']} {r['latency_s']:.2f} s  model={r.get('model_returned')}  "
                  f"reasoning={r.get('reasoning_chars')}  tokens={r.get('usage')}  "
                  f"parsed={r.get('parsed', r.get('parse_error'))}", flush=True)
    if args.rate_limit:
        seq = [post(h, url, base | OFF, args.timeout) for _ in range(5)]
        rec["sequential"] = seq
        print("sequential:", [(s["status"], round(s["latency_s"], 2)) for s in seq], flush=True)
        names = sorted({k for s in seq for k in s.get("headers", {})})
        print("response header names:", names, flush=True)
        if args.burst:
            tiny = base | OFF | {"max_tokens": 1}
            with ThreadPoolExecutor(8) as ex:
                burst = list(ex.map(lambda _: post(h, url, tiny, args.timeout), range(args.burst)))
            t0 = min(b["sent_unix"] for b in burst)
            for b in burst:
                b.pop("headers", None) if b["status"] == 200 else None
            ok60 = sum(1 for b in burst if b["status"] == 200 and b["sent_unix"] - t0 < 60)
            first429 = sorted((b["sent_unix"] - t0, i) for i, b in enumerate(burst) if b["status"] == 429)
            rec["burst"] = {"n": args.burst, "threads": 8, "calls": burst,
                            "status_counts": {str(s): sum(1 for b in burst if b["status"] == s)
                                              for s in {b["status"] for b in burst}},
                            "ok_within_60s_of_first": ok60,
                            "first_429_after_s": first429[0][0] if first429 else None,
                            "ok_before_first_429": (sum(1 for b in burst if b["status"] == 200 and
                                                        b["sent_unix"] < t0 + first429[0][0])
                                                    if first429 else None)}
            print("burst:", {k: v for k, v in rec["burst"].items() if k != "calls"}, flush=True)
    if args.paced:
        time.sleep(60)          # let any earlier burst leave the window first
        tiny = base | OFF | {"max_tokens": 1}
        calls, t_start = [], time.perf_counter()
        while time.perf_counter() - t_start < args.seconds:
            t_next = t_start + len(calls) * 60 / args.paced
            time.sleep(max(0.0, t_next - time.perf_counter()))
            c = post(h, url, tiny, args.timeout)
            c.pop("headers", None)
            calls.append(c)
        n = {str(s): sum(1 for c in calls if c["status"] == s) for s in {c["status"] for c in calls}}
        rec["paced"] = {"rpm": args.paced, "seconds": args.seconds, "calls": calls, "status_counts": n}
        print(f"paced {args.paced}/min for {args.seconds} s: {n}", flush=True)
    what = "_".join(w for w, on in (("capabilities", args.capabilities), ("ratelimit", args.rate_limit),
                                    ("paced", bool(args.paced))) if on)
    out = root / OUT / f"{started:%Y%m%dT%H%M%SZ}_{what}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(rec, indent=1, default=str)
    if key in text:
        raise SystemExit("Refusing to write: the API key appears in the record")
    out.write_text(text)
    print(f"Wrote {out.relative_to(root)}")


if __name__ == "__main__":
    main()
