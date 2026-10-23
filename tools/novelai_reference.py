#!/usr/bin/env python3
"""One V4.5 reference generation with a 150-Anlas project trial budget."""
import argparse
import base64
import datetime as dt
import fcntl
import hashlib
import json
from pathlib import Path
import struct
import sys

from novelai import (REPO, SUBSCRIPTION_URL, GENERATION_URL, NovelAIError,
                     decode_png, load_token, request_json, require, validate_payload)

LIMIT = 150
RESERVE = 50
LEDGER = REPO / "reviews/novelai-costs.json"


def balance(token):
    data = request_json(SUBSCRIPTION_URL, token)
    require(data.get("active") is True and data.get("tier") == 3,
            "Active Opus was not confirmed.")
    credits = data.get("trainingStepsLeft", {}).get("fixedTrainingStepsLeft")
    require(type(credits) is int and credits >= 0, "Subscription Anlas balance is unavailable.")
    return credits


def save_ledger(data):
    temporary = LEDGER.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(LEDGER)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--fidelity", type=float, default=0.6)
    parser.add_argument("--strength", type=float, default=1.0)
    args = parser.parse_args()
    try:
        require(0 <= args.fidelity <= 1 and 0 <= args.strength <= 1,
                "Strength and fidelity must be 0–1.")
        payload = validate_payload(json.loads(args.payload.read_text()))
        require(not args.output.exists() and not args.output.with_suffix(".json").exists(),
                "Output exists; use a new version.")
        require(args.output.suffix == ".png", "Output must be a PNG path.")
        reference = args.reference.read_bytes()
        require(reference[:8] == b"\x89PNG\r\n\x1a\n", "Reference must be PNG.")
        require(struct.unpack(">II", reference[16:24]) in {(1024, 1536), (1536, 1024), (1472, 1472)},
                "Use a reference already at a documented Precise Reference resolution.")
        source_hash = hashlib.sha256(reference).hexdigest()
        original = json.loads(json.dumps(payload))
        payload["parameters"].update({
            "director_reference_images": [base64.b64encode(reference).decode("ascii")],
            "director_reference_descriptions": [{"caption": {"base_caption": "character", "char_captions": []}, "use_coords": False, "use_order": True}],
            "director_reference_information_extracted": [1.0],
            "director_reference_strength_values": [args.strength],
            "director_reference_secondary_strength_values": [args.fidelity],
        })
        token = load_token(args.credentials_file)
        require(bool(token), "NovelAI token is not configured.")
        LEDGER.parent.mkdir(exist_ok=True)
        with LEDGER.with_suffix(".lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"trial_limit_anlas": LIMIT, "requests": []}
            require(all(r.get("observed_anlas") is not None for r in ledger["requests"]),
                    "A prior request has unresolved cost; reconcile it before another generation.")
            used = sum(r["observed_anlas"] for r in ledger["requests"])
            require(used + RESERVE <= LIMIT, "Trial budget cannot reserve another request.")
            before = balance(token)
            require(before >= RESERVE, "Insufficient subscription Anlas; purchased credits will not be used.")
            record = {"output": args.output.name, "reference_sha256": source_hash,
                      "started_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                      "observed_anlas": None, "status": "request_pending"}
            ledger["requests"].append(record)
            save_ledger(ledger)
            try:
                response = request_json(GENERATION_URL, token, "POST", payload)
            except NovelAIError:
                record["status"] = "request_failed_cost_unconfirmed"
                save_ledger(ledger)
                raise
            after = balance(token)
            cost = before - after
            require(cost >= 0, "Balance increased during request; cost needs manual reconciliation.")
            record.update({"observed_anlas": cost, "status": "response_received"})
            save_ledger(ledger)
            p = payload["parameters"]
            raw = decode_png(response, p["width"], p["height"])
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("xb") as stream:
                stream.write(raw)
            metadata = {"provider": "NovelAI", "request": original,
                        "reference": {"file": args.reference.name, "sha256": source_hash,
                                      "type": "character", "strength": args.strength, "fidelity": args.fidelity},
                        "sha256": hashlib.sha256(raw).hexdigest(), "observed_anlas": cost,
                        "client_approval": "pending", "visual_review": "pending"}
            with args.output.with_suffix(".json").open("x") as stream:
                json.dump(metadata, stream, ensure_ascii=False, indent=2)
            record["status"] = "saved_pending_visual_review"
            save_ledger(ledger)
            print(json.dumps({"output": str(args.output), "observed_anlas": cost,
                              "trial_spent_anlas": used + cost, "trial_limit_anlas": LIMIT}))
        return 0
    except (NovelAIError, OSError, ValueError, struct.error) as exc:
        print(str(exc) if isinstance(exc, NovelAIError) else "Local file/response validation failed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
