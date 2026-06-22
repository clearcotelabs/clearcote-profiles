"""Re-apply the curation opinion to an already-written profile directory — no upstream dataset
needed. Use this after curate.py's opinion changes (e.g. a new VM/software filter) to bring an
existing set into line without regenerating from source.

For each ``<dir>/*.json`` it:
  * moves any profile that is no longer curated (software/VM GPU, implausible hardware) into
    ``excluded/`` (kept for transparency, out of the default ``samples/*.json`` glob);
  * tags ``meta.gpu_vendor`` / ``meta.gpu_family`` on the kept profiles;
  * (re)writes ``<dir>/index.json`` — the pick-by-host-GPU manifest.

    python reindex.py samples
"""
import argparse
import json
import os
import sys
from glob import glob

import curate


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dir", nargs="?", default="samples", help="profile directory to re-curate")
    parser.add_argument("--excluded", default="excluded", help="quarantine directory for dropped captures")
    args = parser.parse_args()

    kept, moved = [], []
    for path in sorted(glob(os.path.join(args.dir, "*.json"))):
        if os.path.basename(path) == "index.json":
            continue
        with open(path, encoding="utf-8") as handle:
            profile = json.load(handle)
        if not curate.is_curated(profile):
            os.makedirs(args.excluded, exist_ok=True)
            os.replace(path, os.path.join(args.excluded, os.path.basename(path)))
            moved.append((os.path.basename(path), curate.renderer(profile)))
            continue
        meta = profile.setdefault("meta", {})
        meta["gpu_vendor"] = curate.gpu_vendor(profile)
        meta["gpu_family"] = curate.gpu_family(profile)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(profile, handle, indent=1, ensure_ascii=False)
        kept.append(profile)

    by_vendor = {}
    for profile in kept:
        vendor = curate.gpu_vendor(profile)
        by_vendor[vendor] = by_vendor.get(vendor, 0) + 1
    index = {
        "count": len(kept),
        "by_vendor": dict(sorted(by_vendor.items(), key=lambda kv: -kv[1])),
        "profiles": sorted((curate.summary(p) for p in kept), key=lambda s: (s["gpu_vendor"], s["id"])),
    }
    with open(os.path.join(args.dir, "index.json"), "w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=1, ensure_ascii=False)

    print("kept=%d  excluded=%d -> %s/" % (len(kept), len(moved), args.excluded), file=sys.stderr)
    print("by vendor:", by_vendor, file=sys.stderr)
    for name, renderer in moved:
        print("  excluded %s  (%s)" % (name, renderer[:56]), file=sys.stderr)


if __name__ == "__main__":
    main()
