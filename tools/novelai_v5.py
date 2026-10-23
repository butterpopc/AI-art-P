#!/usr/bin/env python3
"""Single controlled V5 Full comparison, sharing the 150-Anlas trial ledger."""
import argparse
import copy
import datetime as dt
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import struct

from novelai import (REPO, SUBSCRIPTION_URL, GENERATION_URL, NovelAIError,
                     load_token, request_json, require, validate_payload, decode_png)
from novelai_reference import balance, save_ledger, LEDGER, LIMIT, RESERVE

ARTISTS = {"baseline": "", "puuzaki": "artist:puuzaki puuna, ", "saitom": "artist:saitom, "}


def payload_for(variant, seed, quality="original", prompt_file=None, scale=7):
    text = (prompt_file or REPO / "prompts/v5-baseline-draft.txt").read_text()
    positive = text.split("POSITIVE:\n", 1)[1].split("\n\nUNDESIRED:", 1)[0].strip()
    negative = text.split("UNDESIRED:\n", 1)[1].split("\n\nCONTROLLED", 1)[0].strip()
    prompt = ARTISTS[variant] + positive
    require(quality in ("original", "standard"), "Unknown quality preset.")
    if quality == "standard":
        prompt = prompt.removesuffix("best quality, high complexity") + "high complexity, very aesthetic, masterpiece, no text"
    p = {"params_version": 4, "width": 832, "height": 1216, "steps": 23,
         "n_samples": 1, "seed": seed, "sampler": "k_euler_ancestral",
         "noise_schedule": "karras", "scale": scale, "cfg_rescale": 0,
         "negative_prompt": negative}
    for key, value in [("v4_prompt", prompt), ("v4_negative_prompt", negative)]:
        p[key] = {"caption": {"base_caption": value, "char_captions": []},
                  "use_coords": False, "use_order": True, "legacy_uc": False}
    payload = {"model": "nai-diffusion-5-full", "action": "generate", "input": prompt, "parameters": p}
    # Reuse the existing bounds/structure validation without weakening legacy behavior.
    validation = copy.deepcopy(payload)
    validation["model"] = "nai-diffusion-4-5-full"
    validation["parameters"]["params_version"] = 3
    validate_payload(validation)
    return payload


def png_source(raw):
    offset = 8
    while offset + 12 <= len(raw):
        length = struct.unpack(">I", raw[offset:offset+4])[0]
        kind = raw[offset+4:offset+8]
        data = raw[offset+8:offset+8+length]
        if kind == b"tEXt" and data.startswith(b"Source\0"):
            return data.split(b"\0", 1)[1].decode("utf-8", "replace")
        offset += length + 12
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=ARTISTS, required=True)
    parser.add_argument("--seed", type=int, default=271025)
    parser.add_argument("--quality", choices=("original", "standard"), default="original")
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--scale", type=float, default=7)
    args = parser.parse_args()
    try:
        payload = payload_for(args.variant, args.seed, args.quality, args.prompt_file, args.scale)
        stem = f"v5-{args.variant}-{args.seed}"
        if args.prompt_file:
            require(args.prompt_file.stem.replace('-', '').replace('_', '').isalnum(), "Invalid prompt filename.")
            stem += "-" + args.prompt_file.stem
        if args.quality != "original":
            stem += "-" + args.quality
        if args.scale != 7:
            stem += f"-cfg{args.scale:g}"
        output = REPO / "artwork" / (stem + ".png")
        metadata = output.with_suffix(".json")
        if args.dry_run:
            print(json.dumps({"valid": True, "model": payload["model"], "variant": args.variant,
                              "seed": args.seed, "network_used": False}))
            return 0
        require(not output.exists() and not metadata.exists(), "Output already exists.")
        token = load_token(args.credentials_file)
        require(bool(token), "Token is unavailable.")
        with LEDGER.with_suffix(".lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            ledger = json.loads(LEDGER.read_text())
            require(all(r.get("observed_anlas") is not None for r in ledger["requests"]),
                    "Unresolved prior cost requires reconciliation.")
            used = sum(r["observed_anlas"] for r in ledger["requests"])
            require(used + RESERVE <= LIMIT, "Trial budget cannot reserve another request.")
            before = balance(token)
            require(before >= RESERVE, "Insufficient subscription Anlas.")
            record = {"output": output.name, "model": payload["model"], "variant": args.variant,
                      "started_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                      "observed_anlas": None, "status": "request_pending"}
            ledger["requests"].append(record)
            save_ledger(ledger)
            try:
                response = request_json(GENERATION_URL, token, "POST", payload)
            except NovelAIError:
                record["status"] = "failed_no_retry"
                try:
                    after = balance(token)
                    if after <= before: record["observed_anlas"] = before - after
                finally:
                    save_ledger(ledger)
                raise
            after = balance(token)
            require(after <= before, "Balance changed unexpectedly; reconcile cost.")
            record["observed_anlas"] = before - after
            record["status"] = "response_received"
            save_ledger(ledger)
            raw = decode_png(response, 832, 1216)
            with output.open("xb") as stream: stream.write(raw)
            data = {"provider": "NovelAI", "request": payload, "variant": args.variant,
                    "png_source": png_source(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                    "quality": args.quality,
                    "observed_anlas": before-after, "visual_review": "pending", "client_approval": "pending"}
            metadata.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            (REPO / "prompts" / (stem + ".json")).write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n")
            record["status"] = "saved_pending_visual_review"
            save_ledger(ledger)
            print(json.dumps({"image": str(output), "png_source": data["png_source"],
                              "observed_anlas": before-after, "trial_spent_anlas": used+before-after}))
        return 0
    except (NovelAIError, OSError, ValueError) as exc:
        print(str(exc) if isinstance(exc, NovelAIError) else "Local data validation failed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
