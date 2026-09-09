"""Audio-only features for a DEPLOYABLE gate. No labels, no generator, no dataset id.

Phase 13/15/20. Everything here is computable at inference from the waveform alone.
Deliberately excluded: ground truth, generator identity, benchmark cell, corpus name.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, soundfile as sf

REPO = Path(__file__).resolve().parents[1]
WT = Path("/home/aayushdwivedi/Projects/voiceguard-wt/voiceshield")
SR = 16_000
FEATS = ["rms_db","peak","crest_db","dyn_range_db","noise_floor_db","silence_frac",
         "zcr","hf_share","lf_share","centroid_hz","rolloff95_hz","flatness",
         "duration_s","band_edge_hz","spec_slope"]

def feats(y, sr):
    y = y.astype(np.float64)
    if y.size < 512: return None
    rms = float(np.sqrt(np.mean(y**2)))+1e-12
    peak = float(np.max(np.abs(y)))+1e-12
    n=len(y); frame=int(sr*0.03) or 1
    fr=np.array([np.sqrt(np.mean(y[i:i+frame]**2)) for i in range(0,max(1,n-frame+1),frame)])+1e-12
    w=np.hanning(n); spec=np.abs(np.fft.rfft(y*w)); freq=np.fft.rfftfreq(n,1/sr)
    p=spec**2; tot=p.sum()+1e-20; cum=np.cumsum(p)/tot
    # highest frequency holding real energy -- a codec/bandwidth proxy
    band_edge=float(freq[np.searchsorted(cum,0.995)])
    lo=(freq>50)&(freq<8000)
    slope=float(np.polyfit(np.log10(freq[lo]+1),10*np.log10(p[lo]+1e-20),1)[0]) if lo.sum()>10 else 0.0
    return {"rms_db":20*np.log10(rms),"peak":peak,"crest_db":20*np.log10(peak/rms),
            "dyn_range_db":20*np.log10(np.percentile(fr,95)/np.percentile(fr,5)),
            "noise_floor_db":20*np.log10(float(np.percentile(fr,5))),
            "silence_frac":float(np.mean(fr<peak*10**(-35/20))),
            "zcr":float(np.mean(np.abs(np.diff(np.sign(y)))>0)),
            "hf_share":float(p[freq>4000].sum()/tot),"lf_share":float(p[freq<300].sum()/tot),
            "centroid_hz":float((freq*p).sum()/tot),
            "rolloff95_hz":float(freq[np.searchsorted(cum,0.95)]),
            "flatness":float(np.exp(np.mean(np.log(p+1e-20)))/(p.mean()+1e-20)),
            "duration_s":n/sr,"band_edge_hz":band_edge,"spec_slope":slope}

def main():
    rows=[]
    for f,tag in ((WT/"data/mixed_f5_iv15/manifest.jsonl","internal"),
                  (WT/"data/external2/manifest.jsonl","external")):
        for l in open(f):
            r=json.loads(l); r["_root"]=tag; rows.append(r)
    ext=WT/"data/external2"
    res=lambda r:(ext/r["path"]) if r["_root"]=="external" else (WT/r["path"])
    rows=[r for r in rows if res(r).exists()]
    out={}
    for i,r in enumerate(rows):
        y,sr=sf.read(res(r),dtype="float32",always_2d=False)
        if y.ndim>1: y=y.mean(axis=1)
        if sr!=SR and y.size:
            import soxr; y=soxr.resample(y,sr,SR).astype(np.float32); sr=SR
        f=feats(y,sr)
        if f: out[r["path"]]=f
        if i%500==0: print(f"  {i}/{len(rows)}",flush=True)
    np.savez_compressed(REPO/"research/gate_features.npz",
                        paths=np.array(list(out)),
                        X=np.array([[v[k] for k in FEATS] for v in out.values()]),
                        names=np.array(FEATS))
    print(f"wrote gate_features.npz  {len(out)} clips x {len(FEATS)} features")

if __name__=="__main__": raise SystemExit(main())
