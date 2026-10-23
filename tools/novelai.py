#!/usr/bin/env python3
"""One-request NovelAI client. Credentials stay in the environment or a private file."""
import argparse
import base64
import binascii
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys
import urllib.error
import urllib.request

SUBSCRIPTION_URL = "https://image.novelai.net/user/subscription"
GENERATION_URL = "https://image.novelai.net/ai/generate-image"
REPO = Path(__file__).resolve().parents[1]
DEFAULT_PAYLOAD = REPO / "prompts/novelai-seorin-v1.json"
MAX_RESPONSE = 32 * 1024 * 1024
ALLOWED_PARAMETERS = {
    "width", "height", "steps", "n_samples", "seed", "sampler", "scale",
    "noise_schedule", "cfg_rescale", "params_version", "negative_prompt",
    "v4_prompt", "v4_negative_prompt", "qualityToggle", "ucPreset",
}


class NovelAIError(Exception):
    """Safe, non-secret diagnostic intended for display."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise NovelAIError("Redirect refused; credentials were not forwarded.")


def request_json(url, token, method="GET", payload=None):
    if url not in {SUBSCRIPTION_URL, GENERATION_URL}:
        raise NovelAIError("Destination is not an approved NovelAI endpoint.")
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method=method, headers={
        "User-Agent": "AI-art-P/0.1",
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    # Default HTTPSHandler retains Python's CA and hostname verification.
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=180) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise NovelAIError("Response exceeded the 32 MiB limit.")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise NovelAIError("Unexpected API response structure.")
        return result
    except urllib.error.HTTPError as exc:
        # Do not print response bodies, request objects, headers, or tokens.
        raise NovelAIError(f"NovelAI returned HTTP {exc.code}; no automatic retry was made.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise NovelAIError("Network/TLS request failed; no automatic retry was made.") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise NovelAIError("NovelAI did not return valid JSON; no automatic retry was made.") from None


def require(condition, message):
    if not condition:
        raise NovelAIError(message)


def load_token(credentials_file=None):
    """Prefer the environment; otherwise read only the private file's api_token."""
    token = os.environ.get("NOVELAI_API_TOKEN", "")
    if token:
        require("\r" not in token and "\n" not in token, "API token contains an invalid line break.")
        return token.strip()
    if credentials_file is None:
        return ""
    try:
        path = Path(credentials_file).resolve()
        require(not path.is_relative_to(REPO.resolve()), "Credentials files must be outside the repository.")
        parent_status = path.parent.stat()
        require(parent_status.st_mode & 0o077 == 0, "Credentials directory must deny group/other access (use mode 700).")
        require(parent_status.st_uid == os.geteuid(), "Credentials directory must belong to the current user.")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            status = os.fstat(stream.fileno())
            require(stat.S_ISREG(status.st_mode), "Credentials must be a regular file.")
            require(status.st_mode & 0o077 == 0, "Credentials file must deny group/other access (use mode 600).")
            require(status.st_uid == os.geteuid(), "Credentials file must belong to the current user.")
            contents = stream.read(65537)
            require(len(contents) <= 65536, "Credentials file exceeds the size limit.")
            document = json.loads(contents)
            require(isinstance(document, dict), "Credentials file must be a JSON object.")
            token = document.get("api_token")
            require(isinstance(token, str) and bool(token.strip()), "Credentials file needs a nonempty api_token string.")
            require("\r" not in token and "\n" not in token, "API token contains an invalid line break.")
            return token.strip()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise NovelAIError("Private credentials file could not be read or was not valid JSON.") from None


def validate_condition(value, expected):
    require(isinstance(value, dict), "Invalid V4 conditioning structure.")
    require(set(value) <= {"caption", "use_coords", "use_order", "legacy_uc"}, "Unknown V4 conditioning field.")
    caption = value.get("caption")
    require(isinstance(caption, dict), "V4 caption is required.")
    require(set(caption) == {"base_caption", "char_captions"}, "Use one base caption without character positioning.")
    require(caption["base_caption"] == expected and caption["char_captions"] == [], "V4 caption must match the main prompt.")
    for key in set(value) - {"caption"}:
        require(type(value[key]) is bool, "V4 conditioning flags must be boolean.")


def validate_payload(payload):
    require(isinstance(payload, dict), "Payload must be a JSON object.")
    require(set(payload) == {"input", "model", "action", "parameters"}, "Unexpected payload field.")
    require(payload["model"] == "nai-diffusion-4-5-full", "This recipe supports V4.5 Full only.")
    require(payload["action"] == "generate", "Only text-to-image generation is enabled.")
    require(isinstance(payload["input"], str) and 0 < len(payload["input"]) <= 4000, "Prompt must contain 1–4000 characters.")
    p = payload["parameters"]
    require(isinstance(p, dict) and set(p) <= ALLOWED_PARAMETERS, "Unknown/paid generation feature refused.")
    for key in ["width", "height", "steps", "n_samples", "seed"]:
        require(type(p.get(key)) is int, f"{key} must be an integer.")
    w, h = p["width"], p["height"]
    require(64 <= w <= 1536 and 64 <= h <= 1536 and w % 64 == h % 64 == 0, "Dimensions must be multiples of 64 in the supported range.")
    require(w * h <= 1024 * 1024, "Image area exceeds the normal-size Opus limit.")
    require(1 <= p["steps"] <= 28 and p["n_samples"] == 1, "Use at most 28 steps and exactly one image.")
    require(0 <= p["seed"] <= 4294967295, "Seed must be an unsigned 32-bit integer.")
    require(p.get("sampler") == "k_euler_ancestral", "This recipe uses k_euler_ancestral.")
    require(p.get("noise_schedule") == "karras", "This recipe uses the karras schedule.")
    require(type(p.get("scale")) in (int, float) and 1 <= p["scale"] <= 10, "Guidance scale must be 1–10.")
    require(type(p.get("cfg_rescale")) in (int, float) and 0 <= p["cfg_rescale"] <= 1, "CFG rescale must be 0–1.")
    require(p.get("params_version") == 3, "This recipe requires parameters version 3.")
    negative = p.get("negative_prompt")
    require(isinstance(negative, str) and len(negative) <= 4000, "Negative prompt must be at most 4000 characters.")
    validate_condition(p.get("v4_prompt"), payload["input"])
    validate_condition(p.get("v4_negative_prompt"), negative)
    return payload


def subscription(token, transport=request_json):
    require(bool(token), "NOVELAI_API_TOKEN is not configured. Enter it in secure environment settings.")
    data = transport(SUBSCRIPTION_URL, token)
    require(isinstance(data, dict), "Unexpected subscription response.")
    # Return only the fields needed for readiness; omit billing/account data.
    return {"active": data.get("active") is True, "tier": data.get("tier")}


def decode_png(response, width, height):
    require(isinstance(response, dict), "Unexpected generation response.")
    images = response.get("images")
    require(isinstance(images, list) and len(images) == 1, "Expected exactly one generated image.")
    image = images[0]
    require(isinstance(image, dict) and isinstance(image.get("image"), str), "Missing base64 image.")
    try:
        raw = base64.b64decode(image["image"], validate=True)
    except (binascii.Error, ValueError):
        raise NovelAIError("Image was not valid base64.") from None
    require(len(raw) >= 33 and raw[:8] == b"\x89PNG\r\n\x1a\n" and raw[12:16] == b"IHDR", "Output was not a PNG image.")
    require(struct.unpack(">II", raw[16:24]) == (width, height), "Generated image dimensions differ from the request.")
    return raw


def generate(payload, output, token, transport=request_json):
    validate_payload(payload)
    output = Path(output)
    require(output.suffix.lower() == ".png", "Output path must end in .png.")
    metadata_path = output.with_suffix(".json")
    require(not output.exists() and not metadata_path.exists(), "Output already exists; choose a new version filename.")
    status = subscription(token, transport)
    require(status["active"] and type(status["tier"]) is int and status["tier"] == 3,
            "An active Opus subscription was not confirmed; generation was not sent.")
    # A single generation call, never retried automatically, including after timeout.
    response = transport(GENERATION_URL, token, "POST", payload)
    p = payload["parameters"]
    raw = decode_png(response, p["width"], p["height"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(raw)
    metadata = {
        "provider": "NovelAI", "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "request": payload, "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw), "width": p["width"], "height": p["height"],
        "client_approval": "pending", "visual_review": "pending",
        "billing": "No purchase endpoint used. V4.5 normal-size single-image Opus recipe; server billing not independently audited.",
    }
    with metadata_path.open("x", encoding="utf-8") as stream:
        json.dump(metadata, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return {"image": str(output), "metadata": str(metadata_path), "sha256": metadata["sha256"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Read subscription status only.")
    mode.add_argument("--dry-run", action="store_true", help="Validate without network or token.")
    mode.add_argument("--generate", action="store_true", help="Submit exactly one generation after checking Opus.")
    parser.add_argument("--payload", type=Path, default=DEFAULT_PAYLOAD)
    parser.add_argument("--output", type=Path, help="New PNG output path (required for generation).")
    parser.add_argument("--credentials-file", type=Path, help="Private JSON outside the repository; api_token is used only when the environment token is unset.")
    args = parser.parse_args(argv)
    try:
        if args.check:
            result = subscription(load_token(args.credentials_file))
        else:
            payload = validate_payload(json.loads(args.payload.read_text(encoding="utf-8")))
            if args.dry_run:
                result = {"valid": True, "network_used": False, "model": payload["model"], "parameters": {k: payload["parameters"][k] for k in ["width", "height", "steps", "n_samples", "seed"]}}
            else:
                require(args.output is not None, "--output is required for generation.")
                result = generate(payload, args.output, load_token(args.credentials_file))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except NovelAIError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print("A local file could not be read/written or was not valid JSON.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
