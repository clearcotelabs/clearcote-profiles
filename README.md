# clearcote-profiles

A library of **ready-to-use device profiles** for the
[clearcote](https://github.com/clearcotelabs/clearcote-browser) anti-detect browser, built from
the open [chrome-fingerprints](https://github.com/Vinyzu/chrome-fingerprints) dataset of ~10k real
Windows-Chrome fingerprints.

clearcote can present a *real machine's* identity instead of a synthetic seed-derived one via its
`--fingerprint-profile` switch (`fingerprint_profile=` / `fingerprintProfile:` in the SDKs). This
repo's converter turns the public dataset into that profile format, so you get thousands of
coherent, real-hardware personas without capturing your own.

```python
import clearcote
browser = clearcote.launch(
    fingerprint="user-1",
    fingerprint_profile="samples/vinyzu-04201.json",   # an Intel Arc A770 desktop
)
```

`samples/` ships a small, GPU-diverse, validated set you can use immediately. Run the generator to
produce the full library (see below).

## What gets imported — and what doesn't

Profiles carry only **device characteristics**, which vary per machine:

- GPU: WebGL unmasked vendor/renderer, the driver `getParameter` table (bit depths, aliased
  ranges, anisotropy, MAX_* limits), and the supported-extension list
- Screen: resolution, available area, colour depth, device-pixel-ratio, colour gamut
- Hardware: `hardwareConcurrency`, `deviceMemory`
- Fonts (the installed set), speech-synthesis voices, audio context sample-rate/latency

They deliberately **do not** carry the browser-version identity (User-Agent, Chrome version, UA-CH
brands). The source dataset is Chrome 117; clearcote ships a newer engine. Importing the old
version would make the browser *claim* 117 while *behaving* like its real version — a mismatch that
is itself detectable. clearcote keeps its own current browser version; only the device is borrowed.

Records captured under software rendering (SwiftShader / llvmpipe) **or inside a virtual machine**
(Parallels / VMware / VirtualBox / SVGA) are filtered out — only real desktop GPUs are kept. A VM
adapter is its own tell to virtualization checks and renders incoherently against a desktop
persona, so those captures score worst against strict tampering classifiers. The 8 VM/software
records in the sample set are preserved under [`excluded/`](excluded/) for transparency, leaving
**72 curated** profiles in `samples/`.

## Picking a profile (coherence beats noise)

Strict browser-tampering / anti-detect classifiers don't just read individual values — they check
whether the whole device is *internally coherent*, and whether its canvas/WebGL/audio output lands
inside the cluster of outputs that real machines with that hardware produce. Two rules follow, both
validated to drop the tampering score sharply:

**1. Match the host GPU vendor.** clearcote renders canvas/WebGL on the *real* host GPU, so the
imported `UNMASKED_RENDERER` string should come from the **same vendor** as the machine running the
browser (Intel host → an Intel profile, etc.). A cross-vendor profile — e.g. an NVIDIA string on an
Intel iGPU — makes the claimed GPU contradict the actual render, a detectable mismatch.
[`samples/index.json`](samples/index.json) is the manifest for this: every profile tagged with
`gpu_vendor` / `gpu_family` / `screen` / `hardware_concurrency`, plus `by_vendor` counts
(currently Intel 29, NVIDIA 34, AMD 9).

```python
import json, random, clearcote
index = json.load(open("samples/index.json"))
pool = [p for p in index["profiles"] if p["gpu_vendor"] == "Intel"]   # match YOUR host GPU vendor
choice = random.choice(pool)
browser = clearcote.launch(
    fingerprint="user-1",
    fingerprint_profile=f"samples/{choice['id']}.json",
    fingerprint_noise=False,            # see rule 2
)
```

**2. Turn the farbling noise off for these sites.** The per-site canvas/WebGL/audio *noise* is an
added perturbation layer on top of the real render; strict ML classifiers recognise that layer
itself. With a coherent imported profile you don't need it — the profile already supplies the
identity, and per-profile uniqueness still comes from the differing device characteristics. Set
`fingerprint_noise=False` (`fingerprintNoise: false`). The noise stays on by default for sites that
don't score it.

## Generate the full library

```bash
pip install -r requirements.txt      # the dataset + clearcote-browser's canonical converter
python generate.py                   # -> profiles/*.json   (~8.5k curated real-GPU profiles)
python generate.py --samples 80 --out samples   # regenerate the curated sample set + index.json
```

Both write an `index.json` manifest alongside the profiles. To re-apply the curation opinion to an
existing set *without* the upstream dataset (e.g. after the VM/software filter changed), run
`python reindex.py samples` — it quarantines newly-excluded captures into `excluded/`, tags
`meta.gpu_vendor` / `meta.gpu_family`, and rewrites `index.json`.

`profiles/` is git-ignored (large + fully regenerable); commit only `samples/`.

## How it connects to clearcote-browser

The dataset→profile **mapping is not forked here** — it lives in clearcote-browser at
[`tools/fingerprint-collect/convert_dataset.py`](https://github.com/clearcotelabs/clearcote-browser/tree/main/tools/fingerprint-collect)
(the single source of truth, kept in sync with the engine's profile reader). This repo installs it
as a **pinned dependency** (`requirements.txt`, via `pip install … git+…#subdirectory=…`) and adds
only its **curation** on top. Bump the pinned commit to track a newer converter.

## Files

- **`requirements.txt`** — the dataset (`chrome-fingerprints`) + the canonical converter
  (`clearcote-fingerprint`, pinned from the browser repo's subdirectory).
- **`curate.py`** — the library's quality opinion: `is_real_gpu` + `is_vm` + `is_plausible`
  filters, `gpu_vendor` / `gpu_family` bucketing, a `summary` row for the manifest, and small
  engine-readiness fix-ups.
- **`generate.py`** — runs the canonical converter over the dataset, applies curation, writes the
  profiles (all, or a GPU-diverse `--samples` set) and an `index.json` manifest.
- **`reindex.py`** — re-curates an existing profile directory in place (no dataset needed):
  quarantines excluded captures, tags meta, rewrites `index.json`.
- **`samples/`** — 72 curated, validated, ready-to-use profiles + `index.json`.
- **`samples/index.json`** — the pick-by-host-GPU manifest (`by_vendor` counts + one tagged row per
  profile).
- **`excluded/`** — the VM/software captures filtered out of the curated set, kept for transparency.

The profile schema (and a collector to capture your *own* machine) also live under
[`tools/fingerprint-collect`](https://github.com/clearcotelabs/clearcote-browser/tree/main/tools/fingerprint-collect).

## Licence & attribution

The profiles are derived from [chrome-fingerprints](https://github.com/Vinyzu/chrome-fingerprints)
© [Vinyzu](https://github.com/Vinyzu/), licensed **GNU GPL-3.0**. As a derivative dataset, **this
repository is also GPL-3.0** (see [`LICENSE`](LICENSE)) — note this differs from the clearcote
*browser*, which is BSD-3-Clause. Keep the attribution and licence if you redistribute.

Use clearcote for lawful automation and privacy. It does not guarantee evasion of any particular
service, and you are responsible for complying with the terms of the sites you visit.
