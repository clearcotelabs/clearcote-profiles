"""Convert a public chrome-fingerprints (Vinyzu) record into a clearcote-profile.

clearcote (https://github.com/clearcotelabs/clearcote-browser) drives its persona from a
``--fingerprint-profile=<json>`` switch (see the browser repo's ``tools/fingerprint-collect``).
This converter turns the open chrome-fingerprints dataset into that profile schema.

Design choices that keep imported identities *coherent*:

* **Device characteristics only.** We import GPU / screen / fonts / speech voices /
  WebGL driver parameters / audio metadata / hardware counts / display gamut — everything that
  varies per *machine*. We deliberately do NOT import the browser-version identity (User-Agent,
  Chrome version, UA-CH brands): the dataset is Chrome 117, while clearcote ships a newer engine,
  so importing the old version would create a version-vs-behaviour mismatch that is itself a tell.
  clearcote keeps its own (current) browser version; only the device is borrowed.
* **Real-GPU captures only.** Some dataset records were collected in software-rendering
  environments (SwiftShader / llvmpipe). Importing a software renderer is counter-productive, so
  those records are filtered out — only real desktop ANGLE GPUs are kept.

The dataset interns strings; the ``chrome_fingerprints`` package resolves them for us, so this
module operates on the fully-resolved record (a dict / dataclass-asdict).
"""

SCHEMA_VERSION = 1

# Vinyzu webgl.properties camelCase key -> the GL pname key clearcote's engine reads.
# (The dataset stores WebGL2-context values under a trailing "2"; bare keys are the WebGL1 context.)
WEBGL1_INT = {
    "MAX_TEXTURE_SIZE": "maxTextureSize",
    "MAX_CUBE_MAP_TEXTURE_SIZE": "maxCubeMapTextureSize",
    "MAX_RENDERBUFFER_SIZE": "maxRenderBufferSize",
    "MAX_VARYING_VECTORS": "maxVaryingVectors",
    "MAX_VERTEX_UNIFORM_VECTORS": "maxVertexUniformVectors",
    "MAX_FRAGMENT_UNIFORM_VECTORS": "maxFragmentUniformVectors",
    "MAX_COMBINED_TEXTURE_IMAGE_UNITS": "maxCombinedTextureImageUnits",
    "RED_BITS": "redBits",
    "GREEN_BITS": "greenBits",
    "BLUE_BITS": "blueBits",
    "ALPHA_BITS": "alphaBits",
    "DEPTH_BITS": "depthBits",
    "STENCIL_BITS": "stencilBits",
    "SUBPIXEL_BITS": "subpixelBits",
    "SAMPLE_BUFFERS": "sampleBuffers",
    "SAMPLES": "samples",
}
WEBGL2_INT = {
    "MAX_3D_TEXTURE_SIZE": "max3DTextureSize2",
    "MAX_ARRAY_TEXTURE_LAYERS": "maxArrayTextureLayers2",
    "MAX_DRAW_BUFFERS": "maxDrawBuffers2",
    "MAX_COLOR_ATTACHMENTS": "maxColorAttachments2",
    "MAX_SAMPLES": "maxSamples2",
    "MAX_VERTEX_UNIFORM_BLOCKS": "maxVertexUniformBlocks2",
    "MAX_FRAGMENT_UNIFORM_BLOCKS": "maxFragmentUniformBlocks2",
    "MAX_COMBINED_UNIFORM_BLOCKS": "maxCombinedUniformBlocks2",
    "MAX_UNIFORM_BUFFER_BINDINGS": "maxUniformBufferBindings2",
    "MAX_VERTEX_UNIFORM_COMPONENTS": "maxVertexUniformComponents2",
    "MAX_FRAGMENT_UNIFORM_COMPONENTS": "maxFragmentUniformComponents2",
}
WEBGL2_FLOAT = {"MAX_TEXTURE_LOD_BIAS": "maxTextureLodBias2"}

# Renderers we refuse to import (software/headless captures, not a real desktop GPU).
_SOFTWARE_MARKERS = ("swiftshader", "llvmpipe", "software", "microsoft basic", "subzero")


def _int(value):
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def _float(value):
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def _plausible_hardware(hardware_concurrency, device_memory):
    """Drop junk/outlier records. A real-GPU desktop reports an even logical-core count (or 1)
    and 2/4/8 GB; the dataset has a few implausible values (e.g. 11 cores, 0.5 GB)."""
    hc_ok = hardware_concurrency == 1 or (
        isinstance(hardware_concurrency, int) and hardware_concurrency % 2 == 0
        and 2 <= hardware_concurrency <= 128)
    return hc_ok and device_memory in (2, 4, 8)


def is_real_gpu(renderer):
    """True only for a real desktop ANGLE GPU renderer string."""
    r = (renderer or "").lower()
    if "angle" not in r:
        return False
    return not any(marker in r for marker in _SOFTWARE_MARKERS)


def convert(fp, source_id):
    """Convert a resolved chrome-fingerprints record (dict) to a clearcote-profile dict.

    Returns ``None`` if the record is not a real-GPU desktop capture (filtered out).
    """
    webgl = fp.get("webgl") or {}
    renderer = webgl.get("unmasked_renderer") or ""
    if not is_real_gpu(renderer):
        return None
    if not _plausible_hardware(fp.get("hardware_concurrency"), fp.get("device_memory")):
        return None

    props = webgl.get("properties") or {}
    screen = fp.get("screen") or {}

    p1 = {}
    for engine_key, vinyzu_key in WEBGL1_INT.items():
        value = _int(props.get(vinyzu_key))
        if value is not None:
            p1[engine_key] = value
    for engine_key, vinyzu_key in (("ALIASED_LINE_WIDTH_RANGE", "aliasedLineWidthRange"),
                                   ("ALIASED_POINT_SIZE_RANGE", "aliasedPointSizeRange")):
        rng = props.get(vinyzu_key)
        if isinstance(rng, dict) and "0" in rng and "1" in rng:
            p1[engine_key] = [rng["0"], rng["1"]]
    anisotropy = _int(webgl.get("max_anisotropy"))
    if anisotropy is not None:
        p1["MAX_TEXTURE_MAX_ANISOTROPY_EXT"] = float(anisotropy)  # engine reads this via FindDouble

    p2 = {}
    for engine_key, vinyzu_key in WEBGL2_INT.items():
        value = _int(props.get(vinyzu_key))
        if value is not None:
            p2[engine_key] = value
    for engine_key, vinyzu_key in WEBGL2_FLOAT.items():
        value = _float(props.get(vinyzu_key))
        if value is not None:
            p2[engine_key] = value
    if not p2:
        return None  # require a WebGL2-capable GPU (skip pre-WebGL2 cards -> empty webgl2 params)

    audio_src = fp.get("audio") or {}
    audio = {k: audio_src[k] for k in
             ("BaseAudioContextSampleRate", "AudioContextBaseLatency", "AudioContextOutputLatency")
             if audio_src.get(k) is not None}

    profile = {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "source": "chrome-fingerprints (https://github.com/Vinyzu/chrome-fingerprints, GPL-3.0)",
            "id": source_id,
            "note": "device characteristics only; clearcote keeps its own browser version",
        },
        "hardware_concurrency": fp.get("hardware_concurrency"),
        "device_memory": fp.get("device_memory"),
        "screen": {k: screen[k] for k in
                   ("width", "height", "avail_width", "avail_height", "color_depth", "device_pixel_ratio")
                   if screen.get(k) is not None},
        "webgl": {
            "webgl1": {
                "debug": {
                    "UNMASKED_VENDOR_WEBGL": webgl.get("unmasked_vendor") or "",
                    "UNMASKED_RENDERER_WEBGL": renderer,
                },
                "parameters": p1,
                "extensions": list(webgl.get("extensions") or []),
            },
            "webgl2": {"parameters": p2},
        },
        "audio": audio,
        "speech": [
            {"voice_uri": v.get("voice_uri"), "name": v.get("name"), "lang": v.get("lang"),
             "local_service": v.get("local_service"), "default": v.get("default")}
            for v in (fp.get("speech") or [])
            if v.get("voice_uri") and v.get("name")
        ],
        "fonts": {"detected": [f for f in (fp.get("fonts") or []) if isinstance(f, str)]},
    }
    gamut = (fp.get("css") or {}).get("color-gamut")
    if gamut in ("srgb", "p3", "rec2020"):
        profile["css"] = {"color-gamut:%s" % gamut: True}
    return profile
