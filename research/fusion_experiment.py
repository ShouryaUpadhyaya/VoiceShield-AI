"""Calibration + fusion, selected by cross-validation INSIDE dev, tested once.

Phases 8, 21, 23, 24, 27, 30, 32, 46-48, 51-53.

Protocol, and the reason for it:
  * calibrators and fusion weights see ONLY the internal dev split (1,485 clips);
  * candidate methods are ranked by 5-fold CV *within* dev, so the choice of method
    is not made on test either;
  * the winning configuration is refit on all of dev and applied ONCE to test and the
    external held-out sets. FLEURS, XTTS-v2 and FreeVC24 never touch a fitted parameter.
"""
from __future__ import annotations
import json, sys, numpy as np
from pathlib import Path
from itertools import combinations
sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibrate_fuse import (load_scores, eer, auc, cllr, min_cllr, brier, ece,
                            Identity, Platt, Isotonic, Temperature,
                            MeanProb, EqualLLR, LogRegFusion, MLPFusion, GBFusion,
                            MODELS, EPS)
from sklearn.model_selection import StratifiedKFold

L4 = {"Hindi", "Tamil", "Telugu", "Malayalam"}

def cells(rows):
    ib = [r for r in rows if r["language"] in L4 and r["set"]=="internal" and r.get("split")=="test" and r["label"]==0]
    isp= [r for r in rows if r["language"] in L4 and r["set"]=="internal" and r.get("split")=="test" and r["label"]==1]
    eb = [r for r in rows if r["language"] in L4 and r["set"]=="external" and r["label"]==0]
    esp= [r for r in rows if r["language"] in L4 and r["set"]=="external" and r["label"]==1]
    return {"A":(ib,isp),"B":(ib,esp),"C":(eb,isp),"D":(eb,esp)}

def main():
    tabs = load_scores(None); rows=list(tabs.values())
    have=[m for m in MODELS if sum(r.get(m) is not None for r in rows)>1000]
    rows=[r for r in rows if all(r.get(m) is not None for m in have)]
    dev=[r for r in rows if r.get("split")=="dev"]
    X_dev=np.array([[r[m] for m in have] for r in dev],float)
    y_dev=np.array([r["label"] for r in dev])
    print(f"dev {len(dev)}  models {have}\n")

    # ---- Phase 21: which calibrator, per model, by 5-fold CV inside dev ----------
    print("=== PHASE 21: calibrator selection per model (5-fold CV inside dev, C_llr) ===")
    print(f"  {'model':16}" + "".join(f"{c.name:>22}" for c in (Identity,Platt,Isotonic,Temperature)))
    best_cal={}
    skf=StratifiedKFold(5,shuffle=True,random_state=0)
    for j,m in enumerate(have):
        line=f"  {m:16}"; scores={}
        for C in (Identity,Platt,Isotonic,Temperature):
            vals=[]
            for tr,te in skf.split(X_dev,y_dev):
                c=C().fit(X_dev[tr,j], y_dev[tr])
                l=c.llr(X_dev[te,j]); yy=y_dev[te]
                vals.append(cllr(-l[yy==0], -l[yy==1]))
            scores[C]=float(np.mean(vals)); line+=f"{scores[C]:>22.3f}"
        best_cal[m]=min(scores,key=scores.get)
        print(line+f"   -> {best_cal[m].name}")
    print()

    # ---- calibrate every column on full dev, using the CV-chosen calibrator ------
    cal={m:best_cal[m]().fit(X_dev[:,j], y_dev) for j,m in enumerate(have)}
    def LLR(rs):
        X=np.array([[r[m] for m in have] for r in rs],float)
        return np.column_stack([cal[m].llr(X[:,j]) for j,m in enumerate(have)])
    Ldev=LLR(dev)

    # ---- Phase 30: subset x method, ranked by 5-fold CV inside dev ---------------
    print("=== PHASE 27/30/47: fusion method x subset, 5-fold CV INSIDE dev ===")
    subsets=[]
    for k in range(1,len(have)+1):
        for c in combinations(have,k):
            subsets.append(list(c))
    methods=[("mean-raw-prob(current)",MeanProb),("equal-LLR",EqualLLR),
             ("logistic-L2",LogRegFusion),("MLP",MLPFusion),("GB",GBFusion)]
    res=[]
    for sub in subsets:
        idx=[have.index(m) for m in sub]
        for mname,M in methods:
            if mname=="mean-raw-prob(current)":
                Xs=np.array([[r[m] for m in sub] for r in dev],float)   # RAW probs
            else:
                Xs=Ldev[:,idx]
            ee=[]
            for tr,te in skf.split(Xs,y_dev):
                try:
                    f=M().fit(Xs[tr],y_dev[tr]); s=f.score(Xs[te]); yy=y_dev[te]
                    ee.append(eer(-s[yy==0],-s[yy==1])[0])
                except Exception:
                    ee.append(float("nan"))
            res.append({"subset":sub,"method":mname,"cv_eer":float(np.nanmean(ee))})
    res.sort(key=lambda r:r["cv_eer"])
    print(f"  {'rank':>5}{'cv EER':>9}  {'method':24}subset")
    for i,r in enumerate(res[:15],1):
        print(f"  {i:>5}{r['cv_eer']:>9.3f}  {r['method']:24}{'+'.join(r['subset'])}")
    print("\n  --- how the CURRENT pipeline configuration ranks ---")
    cur=[r for r in res if r["method"]=="mean-raw-prob(current)"
         and set(r["subset"])=={"indic","dhwani","customDeepfake","prosody"}]
    for r in cur:
        print(f"    mean-raw-prob on indic+dhwani+customDeepfake+prosody: "
              f"cv EER {r['cv_eer']:.3f}  (rank {res.index(r)+1} of {len(res)})")
    best_single=min([r for r in res if len(r['subset'])==1], key=lambda r:r['cv_eer'])
    print(f"    best single model: {best_single['subset'][0]} cv EER {best_single['cv_eer']:.3f}")
    json.dump(res, open(Path(__file__).parent/"fusion_cv.json","w"), indent=1)
    print(f"\nwrote research/fusion_cv.json ({len(res)} configurations)")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
