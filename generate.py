"""Generate the curated clearcote-profile library.

The dataset->profile mapping is done by clearcote-browser's canonical converter
(`convert_dataset`, installed via requirements.txt — this library does NOT fork it). This script
adds the curation layer: quality filtering (real-GPU + plausible hardware) and GPU-diverse
sampling, then writes the profiles.

    pip install -r requirements.txt
    python generate.py                       # -> profiles/*.json   (all curated, ~8.5k)
    python generate.py --samples 80 --out samples   # regenerate the curated sample set
"""
import argparse
import json
import os
import sys

try:
    from convert_dataset import convert, find_dataset, load_records, load_tables
except ImportError:
    raise SystemExit("Install deps first:  pip install -r requirements.txt")

from curate import gpu_family, gpu_vendor, is_curated, normalize, summary

ATTRIBUTION = "chrome-fingerprints (https://github.com/Vinyzu/chrome-fingerprints, GPL-3.0)"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="profiles", help="output directory")
    parser.add_argument("--samples", type=int, default=0,
                        help="if >0, write a GPU-diverse sample of N profiles instead of all")
    parser.add_argument("--dataset", help="path to a chrome_fingerprints checkout (auto-detected if pip-installed)")
    args = parser.parse_args()

    pkg = find_dataset(args.dataset)
    tables = load_tables(pkg)
    records = load_records(pkg)
    print("dataset: %s (%d records)" % (pkg, len(records)), file=sys.stderr)

    os.makedirs(args.out, exist_ok=True)
    kept, skipped, by_family = 0, 0, {}
    for index, rec in enumerate(records):
        try:
            profile = convert(rec, tables)            # canonical mapping (clearcote-browser)
        except Exception as exc:                       # noqa: BLE001 - keep going, surface the cause
            print("skip %d: %s" % (index, exc), file=sys.stderr)
            skipped += 1
            continue
        if not is_curated(profile):                    # curation: real GPU + plausible hardware
            skipped += 1
            continue
        normalize(profile)
        profile["meta"]["id"] = "vinyzu-%05d" % index
        profile["meta"]["source"] = ATTRIBUTION
        profile["meta"]["gpu_vendor"] = gpu_vendor(profile)
        profile["meta"]["gpu_family"] = gpu_family(profile)
        kept += 1
        by_family.setdefault(gpu_family(profile), []).append(profile)

    if args.samples > 0:
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
            json.dump(profile, handle, indent=1, ensure_ascii=False)

    write_index(args.out, to_write)
    print("kept=%d  skipped=%d  written=%d -> %s/" % (kept, skipped, len(to_write), args.out), file=sys.stderr)
    print("GPU families:", {k: len(v) for k, v in sorted(by_family.items(), key=lambda kv: -len(kv[1]))}, file=sys.stderr)


def write_index(out_dir, profiles):
    """Write index.json: a manifest of the written profiles so a consumer can pick one whose GPU
    vendor/family matches the host. Grouped counts + one summary row per profile."""
    by_vendor = {}
    for profile in profiles:
        by_vendor[gpu_vendor(profile)] = by_vendor.get(gpu_vendor(profile), 0) + 1
    index = {
        "count": len(profiles),
        "source": ATTRIBUTION,
        "by_vendor": dict(sorted(by_vendor.items(), key=lambda kv: -kv[1])),
        "profiles": sorted((summary(p) for p in profiles), key=lambda s: (s["gpu_vendor"], s["id"])),
    }
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
