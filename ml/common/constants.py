"""Fixed constants for the VoiceShield audio pipeline.

These values are contract, not preference: training and inference must agree on
every one of them or the model sees a different distribution at serve time than
it saw at train time.
"""

from pathlib import Path

# --- Audio contract -------------------------------------------------------
SAMPLE_RATE = 16_000

# 64600 samples ~= 4.0375 s. This is the ASVspoof/AASIST convention; keeping it
# means published EER numbers are comparable to ours.
SEGMENT_SAMPLES = 64_600
SEGMENT_SECONDS = SEGMENT_SAMPLES / SAMPLE_RATE

# Target level for RMS normalisation. Upload loudness varies by orders of
# magnitude; the model must never learn to use gain as a cue.
TARGET_DBFS = -26.0

# Below this the clip is treated as silence/garbage rather than speech.
MIN_RMS_DBFS = -60.0

# --- Labels ---------------------------------------------------------------
# 1 = spoof (synthetic), 0 = bonafide (genuine human).
# Chosen so the model's positive-class probability is directly the
# "deepfake_probability" the API already returns.
LABEL_BONAFIDE = 0
LABEL_SPOOF = 1
LABEL_NAMES = {LABEL_BONAFIDE: "bonafide", LABEL_SPOOF: "spoof"}

# --- Silence handling -----------------------------------------------------
# ASVspoof 2019 LA has a documented shortcut: leading/trailing silence length
# differs systematically between bonafide and spoofed clips, so a model can
# reach a low EER by measuring silence instead of detecting synthesis.
# Whatever policy we pick must be applied identically to both classes, and we
# report EER under both "keep" and "trim_edges" so the number is honest.
SILENCE_POLICIES = ("keep", "trim_edges")
DEFAULT_SILENCE_POLICY = "trim_edges"
SILENCE_TOP_DB = 40.0

# --- Paths ----------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
METADATA_DIR = DATA_DIR / "metadata"
ARTIFACT_DIR = REPO_ROOT / "ml" / "artifacts"

# Audio containers the API accepts. Anything not natively readable by
# libsndfile is routed through ffmpeg.
SOUNDFILE_SUFFIXES = {".wav", ".flac", ".ogg", ".aiff", ".au"}
SUPPORTED_SUFFIXES = SOUNDFILE_SUFFIXES | {".mp3", ".m4a", ".aac", ".webm", ".opus", ".amr", ".3gp"}
