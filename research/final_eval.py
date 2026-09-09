"""Refit the chosen configurations on FULL dev, then score test+external exactly once.

Phases 16, 17, 33, 49, 52, 53. Nothing here is selected using these numbers: the
candidate list was fixed by the CV inside dev (research/fusion_cv.json).
"""
from __future__ import annotations
import json, sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibrate_fuse import (load_scores, eer, auc, cllr, Identity, Platt, Isotonic,
                            Temperature, MeanProb, EqualLLR, LogRegFusion, MODELS, EPS)
from math import comb

L4={"Hindi","Tamil","Telugu","Malayalam"}
CAL={"indic":Isotonic,"dhwani":Isotonic,"customDeepfake":Isotonic,"prosody":Platt,
     "iv15":Isotonic,"spectra":Platt,"stageA":Temperature}      # chosen by dev CV

def ci_diff(pa,na,pb,nb,B=1000,seed=0):
    rng=np.random.default_rng(seed)
    d=[eer(rng.choice(pb,len(pb)),rng.choice(nb,len(nb)))[0]-
       eer(rng.choice(pa,len(pa)),rng.choice(na,len(na)))[0] for _ in range(B)]
    return np.percentile(d,2.5),np.percentile(d,97.5)

def mcnemar(b,c):
    n=b+c
    if n==0: return 1.0
    k=min(b,c); return min(1.0,2*sum(comb(n,i) for i in range(k+1))/2**n)

def main():
    tabs=load_scores(None); rows=list(tabs.values())
    have=[m for m in MODELS if sum(r.get(m) is not None for r in rows)>1000]
    rows=[r for r in rows if all(r.get(m) is not None for m in have)]
    dev=[r for r in rows if r.get("split")=="dev"]
    Xd=np.array([[r[m] for m in have] for r in dev],float)
    yd=np.array([r["label"] for r in dev])
    cal={m:CAL[m]().fit(Xd[:,j],yd) for j,m in enumerate(have)}
    def L(rs,sub):
        X=np.array([[r[m] for m in sub] for r in rs],float)
        return np.column_stack([cal[m].llr(X[:,k]) for k,m in enumerate(sub)])
    def RAW(rs,sub): return np.array([[r[m] for m in sub] for r in rs],float)

    ib=[r for r in rows if r["language"] in L4 and r["set"]=="internal" and r.get("split")=="test" and r["label"]==0]
    isp=[r for r in rows if r["language"] in L4 and r["set"]=="internal" and r.get("split")=="test" and r["label"]==1]
    eb=[r for r in rows if r["language"] in L4 and r["set"]=="external" and r["label"]==0]
    esp=[r for r in rows if r["language"] in L4 and r["set"]=="external" and r["label"]==1]
    fv=[r for r in esp if r["generator"]=="freevc24"]
    fl=[r for r in rows if r["source"]=="google/fleurs"]
    print(f"test sets: ib {len(ib)} isp {len(isp)} eb {len(eb)} esp {len(esp)} freevc24 {len(fv)} fleurs {len(fl)}\n")

    CANDS=[("stageA alone",["stageA"],None),
           ("spectra alone",["spectra"],None),
           ("iv15 alone",["iv15"],None),
           ("CURRENT pipeline (mean raw prob)",["indic","dhwani","customDeepfake","prosody"],"raw"),
           ("equal-LLR, 4 pipeline models",["indic","dhwani","customDeepfake","prosody"],EqualLLR),
           ("logistic-L2, 4 pipeline models",["indic","dhwani","customDeepfake","prosody"],LogRegFusion),
           ("logistic-L2 iv15+stageA",["iv15","stageA"],LogRegFusion),
           ("logistic-L2 indic+stageA",["indic","stageA"],LogRegFusion),
           ("logistic-L2 iv15+spectra",["iv15","spectra"],LogRegFusion),
           ("logistic-L2 all 7",have,LogRegFusion)]
    out={}
    print(f"{'configuration':36}{'A':>13}{'B':>13}{'C':>13}{'D':>13}{'FreeVC24 D':>13}{'FLEURS FPR':>12}")
    for name,sub,M in CANDS:
        if M is None:
            f=lambda rs: L(rs,sub)[:,0]
        elif M=="raw":
            w=np.array([0.45,0.20,0.20,0.15]); w=w/w.sum()
            f=lambda rs: RAW(rs,sub)@w
        else:
            fit=M().fit(L(dev,sub),yd); f=lambda rs: fit.score(L(rs,sub))
        S={k:f(v) for k,v in (("ib",ib),("isp",isp),("eb",eb),("esp",esp),("fv",fv),("fl",fl))}
        # threshold fitted on dev with the same pipeline
        sd=f(dev); _,thr=eer(-sd[yd==0],-sd[yd==1]); thr=-thr
        cell=lambda b,s: eer(-S[b],-S[s])[0]
        row=(f"{cell('ib','isp'):>13.2f}{cell('ib','esp'):>13.2f}{cell('eb','isp'):>13.2f}"
             f"{cell('eb','esp'):>13.2f}{eer(-S['eb'],-S['fv'])[0]:>13.2f}"
             f"{100*(S['fl']>=thr).mean():>11.2f}%")
        print(f"{name:36}{row}")
        out[name]={"A":cell('ib','isp'),"B":cell('ib','esp'),"C":cell('eb','isp'),
                   "D":cell('eb','esp'),"freevc24_D":eer(-S['eb'],-S['fv'])[0],
                   "fleurs_fpr":100*float((S['fl']>=thr).mean()),"subset":sub,
                   "threshold":float(thr)}
    json.dump(out,open(Path(__file__).parent/"final_eval.json","w"),indent=1)
    print("\nwrote research/final_eval.json")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
