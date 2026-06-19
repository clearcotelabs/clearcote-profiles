"""Quality curation for the clearcote-profiles library.

The dataset->profile *mapping* lives in clearcote-browser (`convert_dataset`, installed via
requirements.txt) — this module adds only the library's curation opinion on top of a converted
clearcote-profile dict:

* **`is_real_gpu`** — keep real desktop ANGLE GPUs; drop software/headless captures
  (SwiftShader / llvmpipe / "Microsoft Basic Render").
* **`is_plausible`** — drop junk/outlier records: a real desktop reports an even logical-core
  count (or 1), 2/4/8 GB, and a WebGL2-capable GPU.
* **`gpu_family`** — bucket by GPU line so a sample can be spread across diverse hardware.
"""

_SOFTWARE = ("swiftshader", "llvmpipe", "software", "microsoft basic", "subzero")
_FAMILIES = ("RTX", "GTX", "GeForce", "NVIDIA", "Quadro", "Radeon", "AMD", "Arc",
             "Iris", "UHD", "Intel", "Apple", "Adreno", "Mali")


def renderer(profile):
    webgl1 = (profile.get("webgl") or {}).get("webgl1") or {}
    return (webgl1.get("debug") or {}).get("UNMASKED_RENDERER_WEBGL") or ""


def is_real_gpu(profile):
    r = renderer(profile).lower()
    return "angle" in r and not any(marker in r for marker in _SOFTWARE)


def is_plausible(profile):
    hc = profile.get("hardware_concurrency")
    dm = profile.get("device_memory")
    hc_ok = hc == 1 or (isinstance(hc, int) and hc % 2 == 0 and 2 <= hc <= 128)
    webgl2 = ((profile.get("webgl") or {}).get("webgl2") or {}).get("parameters") or {}
    return hc_ok and dm in (2, 4, 8) and bool(webgl2)


def is_curated(profile):
    return is_real_gpu(profile) and is_plausible(profile)


def gpu_family(profile):
    r = renderer(profile).lower()
    for fam in _FAMILIES:
        if fam.lower() in r:
            return fam
    return "other"


def normalize(profile):
    """Small fix-ups so every converted profile is fully engine-ready. The engine reads CSS
    color-gamut as boolean media-query keys (``color-gamut:srgb``); the dataset stores a single
    ``color-gamut`` string — mirror it into the boolean key the engine expects."""
    css = profile.get("css")
    if isinstance(css, dict):
        gamut = css.get("color-gamut")
        if gamut in ("srgb", "p3", "rec2020"):
            css["color-gamut:%s" % gamut] = True
    return profile
