import os
import sys
import urllib.request
import numpy as np
import librosa

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from ml.adapters.dhwani import load_dhwani, run as run_dhwani

def main():
    urls = [
        "https://www.signalogic.com/melp/EngSamples/Orig/trev.wav",
        "https://www.signalogic.com/melp/EngSamples/Orig/steve.wav",
        "https://www.signalogic.com/melp/EngSamples/Orig/marc.wav",
        "https://www.signalogic.com/melp/EngSamples/Orig/david.wav",
        "https://www.signalogic.com/melp/EngSamples/Orig/john.wav",
        "https://www.signalogic.com/melp/EngSamples/Orig/mary.wav",
        "https://www.signalogic.com/melp/EngSamples/Orig/peggy.wav",
        "https://www.signalogic.com/melp/EngSamples/Orig/linda.wav",
        "https://www.signalogic.com/melp/EngSamples/Orig/pam.wav",
        "https://www.signalogic.com/melp/EngSamples/Orig/kathy.wav",
    ]
    
    out_dir = "/home/shouryaupadhyaya/Programming/VoiceShield-AI/data/wavs/fake/easy"
    load_dhwani()
    
    saved = 0
    for i, url in enumerate(urls):
        try:
            name = url.split('/')[-1]
            tmp_path = os.path.join(out_dir, f"temp_{name}")
            urllib.request.urlretrieve(url, tmp_path)
            
            # test
            audio, sr = librosa.load(tmp_path, sr=16000, mono=True)
            chunk = audio[:48000]
            if len(chunk) < 48000:
                chunk = np.pad(chunk, (0, 48000 - len(chunk)))
            
            res = run_dhwani(chunk)
            if res and res.get('synthetic_probability', 0) > 0.90:
                final_path = os.path.join(out_dir, f"fake_sample_{saved+3}.wav")
                os.rename(tmp_path, final_path)
                print(f"Saved {final_path} - score: {res['synthetic_probability']}")
                saved += 1
            else:
                os.remove(tmp_path)
                print(f"Skipped {url} - score: {res.get('synthetic_probability') if res else None}")
                
            if saved >= 10:
                break
        except Exception as e:
            print(f"Failed {url}: {e}")
            
    print(f"Total newly saved: {saved}")

if __name__ == '__main__':
    main()
