import sys
import logging

logging.basicConfig(level=logging.INFO)

from ml.adapters import dhwani, deepfake, prosody, speaker

print("Loading Dhwani...")
try:
    if dhwani.load_dhwani():
        print("Dhwani OK")
    else:
        print("Dhwani FAILED")
except Exception as e:
    print(f"Dhwani Error: {e}")

print("\nLoading Deepfake...")
try:
    if deepfake.load_deepfake():
        print("Deepfake OK")
    else:
        print("Deepfake FAILED")
except Exception as e:
    print(f"Deepfake Error: {e}")

print("\nLoading Prosody...")
try:
    if prosody.load_prosody():
        print("Prosody OK")
    else:
        print("Prosody FAILED")
except Exception as e:
    print(f"Prosody Error: {e}")

print("\nLoading Speaker...")
try:
    if speaker.load_speaker():
        print("Speaker OK")
    else:
        print("Speaker FAILED")
except Exception as e:
    print(f"Speaker Error: {e}")
