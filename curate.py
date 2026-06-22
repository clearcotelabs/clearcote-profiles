"""Quality curation for the clearcote-profiles library.

The dataset->profile *mapping* lives in clearcote-browser (`convert_dataset`, installed via
requirements.txt) — this module adds only the library's curation opinion on top of a converted
clearcote-profile dict:

* **`is_real_gpu`** — keep real desktop ANGLE GPUs; drop software/headless captures
  (SwiftShader / llvmpipe / "Microsoft Basic Render").
* **`is_vm`** — drop virtual-machine GPUs (Parallels / VMware / VirtualBox / SVGA). A VM adapter
  is its own tell to virtualization detectors, and presenting a VM GPU on a desktop persona is
  incoherent — these consistently score worst against browser-tampering classifiers.
* **`is_plausible`** — drop junk/outlier records: a real desktop reports an even logical-core
  count (or 1), 2/4/8 GB, and a WebGL2-capable GPU.
* **`gpu_vendor`** — coarse Intel/NVIDIA/AMD bucket; pick a profile whose vendor matches the host
  GPU so the imported GPU string stays coherent with the machine's actual render.
* **`gpu_family`** — finer GPU line, so a sample can be spread across diverse hardware.
"""

_SOFTWARE = ("swiftshader", "llvmpipe", "software", "microsoft basic", "subzero")
_VM = ("parallels", "vmware", "virtualbox", "svga", "qxl", "virgl", "gallium")
_FAMILIES = ("RTX", "GTX", "GeForce", "NVIDIA", "Quadro", "Radeon", "AMD", "Arc",
             "Iris", "UHD", "Intel", "Apple", "Adreno", "Mali")
# coarse vendor -> renderer-string markers (checked in order)
_VENDORS = (
    ("Intel", ("intel", "iris", "uhd")),
    ("NVIDIA", ("nvidia", "geforce", "rtx", "gtx", "quadro", "nvs")),
    ("AMD", ("amd", "radeon")),
    ("Apple", ("apple",)),
    ("Qualcomm", ("adreno",)),
    ("ARM", ("mali",)),
)


def renderer(profile):
    webgl1 = (profile.get("webgl") or {}).get("webgl1") or {}
    return (webgl1.get("debug") or {}).get("UNMASKED_RENDERER_WEBGL") or ""


def is_real_gpu(profile):
    r = renderer(profile).lower()
    return "angle" in r and not any(marker in r for marker in _SOFTWARE)


def is_vm(profile):
    r = renderer(profile).lower()
    return any(marker in r for marker in _VM)


def is_plausible(profile):
    hc = profile.get("hardware_concurrency")
    dm = profile.get("device_memory")
    hc_ok = hc == 1 or (isinstance(hc, int) and hc % 2 == 0 and 2 <= hc <= 128)
    webgl2 = ((profile.get("webgl") or {}).get("webgl2") or {}).get("parameters") or {}
    return hc_ok and dm in (2, 4, 8) and bool(webgl2)


def is_curated(profile):
    return is_real_gpu(profile) and not is_vm(profile) and is_plausible(profile)


def gpu_family(profile):
    r = renderer(profile).lower()
    for fam in _FAMILIES:
        if fam.lower() in r:
            return fam
    return "other"


def gpu_vendor(profile):
    """Coarse Intel/NVIDIA/AMD/... bucket. Match a profile's vendor to the host GPU's vendor so the
    imported UNMASKED_RENDERER string stays coherent with the machine's actual canvas/WebGL render
    (a cross-vendor mismatch — e.g. an NVIDIA string rendered by an Intel iGPU — is detectable)."""
    r = renderer(profile).lower()
    for vendor, markers in _VENDORS:
        if any(m in r for m in markers):
            return vendor
    return "other"


def summary(profile):
    """One manifest row describing a profile, for picking by host hardware (see index.json)."""
    screen = profile.get("screen") or {}
    return {
        "id": (profile.get("meta") or {}).get("id"),
        "gpu_vendor": gpu_vendor(profile),
        "gpu_family": gpu_family(profile),
        "renderer": renderer(profile),
        "screen": "%sx%s" % (screen.get("width"), screen.get("height")),
        "hardware_concurrency": profile.get("hardware_concurrency"),
        "device_memory": profile.get("device_memory"),
    }


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
