"""Shared constants for the VoiceShield ML pipeline.

These values are contract, not preference: training and inference must agree on
every one of them or the model sees a different distribution at serve time than
it saw at train time.
"""

from pathlib import Path

# --- Paths ----------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = _PROJECT_ROOT
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
METADATA_DIR = DATA_DIR / "metadata"
# Note: real-time Gateway uses artifacts directly from project root, training used ml/artifacts
ARTIFACT_DIR = _PROJECT_ROOT / "artifacts"

# --- Audio contract -------------------------------------------------------
SAMPLE_RATE = 16000

# 64600 samples ~= 4.0375 s. This is the ASVspoof/AASIST convention; keeping it
# means published EER numbers are comparable to ours.
SEGMENT_SAMPLES = 64_600
SEGMENT_SECONDS = SEGMENT_SAMPLES / SAMPLE_RATE

# Target level for RMS normalisation. Upload loudness varies by orders of
# magnitude; the model must never learn to use gain as a cue.
TARGET_DBFS = -26.0

# Below this the clip is treated as silence/garbage rather than speech.
MIN_RMS_DBFS = -60.0

# --- Gateway Real-Time Constants ------------------------------------------
WINDOW_SECONDS = 3.0
WINDOW_SAMPLES = int(SAMPLE_RATE * WINDOW_SECONDS)
HOP_SECONDS = 1.0
HOP_SAMPLES = int(SAMPLE_RATE * HOP_SECONDS)

# Gateway sends 48 kHz PCM16; ML models need 16 kHz
GATEWAY_SAMPLE_RATE = 48000
GATEWAY_CHUNK_BYTES = GATEWAY_SAMPLE_RATE * 1 * 2 * 3  # 48k * mono * 2bytes * 3sec = 288,000

# --- Labels ---------------------------------------------------------------
LABEL_BONAFIDE = 0
LABEL_SPOOF = 1
LABEL_NAMES = {LABEL_BONAFIDE: "bonafide", LABEL_SPOOF: "spoof"}

# --- Silence handling -----------------------------------------------------
SILENCE_POLICIES = ("keep", "trim_edges")
DEFAULT_SILENCE_POLICY = "trim_edges"
SILENCE_TOP_DB = 40.0

# --- Containers -----------------------------------------------------------
SOUNDFILE_SUFFIXES = {".wav", ".flac", ".ogg", ".aiff", ".au"}
SUPPORTED_SUFFIXES = SOUNDFILE_SUFFIXES | {".mp3", ".m4a", ".aac", ".webm", ".opus", ".amr", ".3gp"}

# --- Inference Config -----------------------------------------------------
SUPPORTED_LANGS = ["en", "hi", "ta", "te", "ml"]

# Phase-1 weighted-fusion weights. Tune against your eval set later.
FUSION_WEIGHTS = {
    "dhwani": 0.45,    # D: synthetic-speech probability
    "speaker": 0.20,   # S: speaker mismatch (0 if no enrolled ref)
    "dsp": 0.15,       # A: DSP anomaly score
    "prosody": 0.10,   # P: prosodic anomaly score
    "context": 0.10,   # C: call/transaction context risk
}

RISK_THRESHOLDS = {
    "low": 0.35,
    "high": 0.65,   # >= high -> critical
}

MODEL_PATHS = {
    "silero_vad_repo": "snakers4/silero-vad",
    "dhwani_onnx": str(_PROJECT_ROOT / "models" / "dhwani" / "dhwani.onnx"),
    "ecapa_source": "speechbrain/spkrec-ecapa-voxceleb",
    "ecapa_savedir": str(_PROJECT_ROOT / "models" / "ecapa"),
}

# ML service version string embedded in every response
ML_SERVICE_VERSION = "voiceshield-ml-v1"
