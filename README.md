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

Records captured under software rendering (SwiftShader / llvmpipe) are filtered out — only real
desktop GPUs are kept (~9k of the 10k).

## Generate the full library

```bash
pip install -r requirements.txt      # the dataset + clearcote-browser's canonical converter
python generate.py                   # -> profiles/*.json   (~8.5k curated real-GPU profiles)
python generate.py --samples 80 --out samples   # regenerate the curated sample set
```

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
- **`curate.py`** — the library's quality opinion: `is_real_gpu` + `is_plausible` filters,
  `gpu_family` bucketing, and small engine-readiness fix-ups.
- **`generate.py`** — runs the canonical converter over the dataset, applies curation, and writes
  the profiles (all, or a GPU-diverse `--samples` set).
- **`samples/`** — 80 curated, validated, ready-to-use profiles.

The profile schema (and a collector to capture your *own* machine) also live under
[`tools/fingerprint-collect`](https://github.com/clearcotelabs/clearcote-browser/tree/main/tools/fingerprint-collect).

## Licence & attribution

The profiles are derived from [chrome-fingerprints](https://github.com/Vinyzu/chrome-fingerprints)
© [Vinyzu](https://github.com/Vinyzu/), licensed **GNU GPL-3.0**. As a derivative dataset, **this
repository is also GPL-3.0** (see [`LICENSE`](LICENSE)) — note this differs from the clearcote
*browser*, which is BSD-3-Clause. Keep the attribution and licence if you redistribute.

Use clearcote for lawful automation and privacy. It does not guarantee evasion of any particular
service, and you are responsible for complying with the terms of the sites you visit.
