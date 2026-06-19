"""Generate the clearcote-profile library from the public chrome-fingerprints dataset.

    pip install chrome-fingerprints
    python generate.py                       # -> profiles/*.json  (every real-GPU capture)
    python generate.py --samples 80 --out samples   # a small, GPU-diverse curated set

Each output file is a clearcote-profile usable directly:

    # Python SDK
    browser = clearcote.launch(fingerprint="user-1", fingerprint_profile="samples/vinyzu-00042.json")
    # or the engine switch (the SDK gzip+base64-encodes it for you)
"""
import argparse
import json
import os
import sys

from convert import convert

try:
    from chrome_fingerprints import FingerprintGenerator
    from chrome_fingerprints.fingerprints import index_fingerprint
except ImportError:
    raise SystemExit("This needs the dataset: pip install chrome-fingerprints")

# GPU families used to spread a --samples selection across diverse hardware.
_FAMILIES = ("RTX", "GTX", "GeForce", "NVIDIA", "Radeon", "AMD", "Arc", "Iris", "UHD", "Intel",
             "Apple", "Adreno", "Mali", "Quadro")


def all_records():
    gen = FingerprintGenerator()
    gen.fingerprint_loading_feature.result()  # block until the lzma dataset is loaded
    for index, raw in enumerate(gen.fingerprints):
        if not isinstance(raw["navigator"]["user_agent"], str):
            index_fingerprint(raw)  # resolve interned string refs in place
        yield index, raw


def gpu_family(profile):
    renderer = profile["webgl"]["webgl1"]["debug"]["UNMASKED_RENDERER_WEBGL"].lower()
    for fam in _FAMILIES:
        if fam.lower() in renderer:
            return fam
    return "other"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="profiles", help="output directory")
    parser.add_argument("--samples", type=int, default=0,
                        help="if >0, write a GPU-diverse sample of N profiles instead of all")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    kept, skipped = 0, 0
    by_family = {}
    for index, raw in all_records():
        try:
            profile = convert(raw, "vinyzu-%05d" % index)
        except Exception as exc:  # noqa: BLE001 - keep generation going, but surface the cause
            print("skip index %d: %s" % (index, exc), file=sys.stderr)
            skipped += 1
            continue
        if profile is None:
            skipped += 1
            continue
        kept += 1
        by_family.setdefault(gpu_family(profile), []).append(profile)

    if args.samples > 0:
        # round-robin across GPU families (most-common first) for a diverse sample
        selected, families = [], sorted(by_family, key=lambda k: -len(by_family[k]))
        while len(selected) < args.samples and any(by_family.values()):
            progressed = False
            for fam in families:
                if by_family[fam]:
                    selected.append(by_family[fam].pop())
                    progressed = True
                    if len(selected) >= args.samples:
                        break
            if not progressed:
                break
        to_write = selected
    else:
        to_write = [p for bucket in by_family.values() for p in bucket]

    for profile in to_write:
        path = os.path.join(args.out, "%s.json" % profile["meta"]["id"])
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(profile, handle, indent=1)

    print("kept=%d  skipped(non-real-GPU/err)=%d  written=%d -> %s/" % (kept, skipped, len(to_write), args.out))
    print("GPU families:", {k: len(v) for k, v in sorted(by_family.items(), key=lambda kv: -len(kv[1]))})


if __name__ == "__main__":
    main()
