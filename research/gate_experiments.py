"""Four experiments on specialist routing. Research only -- nothing is implemented.

 1. GATE FEASIBILITY  can audio-only features find the region where a weak expert
                      rescues the best model, at the break-even false-route rate?
 2. DISAGREEMENT      does expert disagreement predict difficulty (not which expert)?
 3. PROSODY AS GATE   is prosody worth more as a gating feature than as an expert?
 4. UNCERTAIN BAND    is abstaining on disagreement worth more than routing?

Grouped CV throughout: folds are split by speaker where available, else by
source+language, so near-duplicate clips cannot straddle a fold boundary.
"""
from __future__ import annotations
import json, sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibrate_fuse import load_scores, eer, auc, Isotonic, Platt, Temperature, MODELS
from sklearn.model_selection import GroupKFold
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

REPO = Path(__file__).resolve().parents[1]
CAL={"indic":Isotonic,"dhwani":Isotonic,"customDeepfake":Isotonic,"prosody":Platt,
     "iv15":Isotonic,"spectra":Platt,"stageA":Temperature}

def main():
    z=np.load(REPO/"research/gate_features.npz",allow_pickle=True)
    F={p:x for p,x in zip(z["paths"],z["X"])}; FN=list(z["names"])
    tabs=load_scores(None); rows=[r for r in tabs.values() if r["path"] in F]
    have=[m for m in MODELS if sum(r.get(m) is not None for r in rows)>1000]
    rows=[r for r in rows if all(r.get(m) is not None for m in have)]
    dev=[r for r in rows if r.get("split")=="dev"]
    yd=np.array([r["label"] for r in dev])
    cal={m:CAL[m]().fit(np.array([r[m] for r in dev],float),yd) for m in have}
    THR={}
    for m in have:
        ld=cal[m].llr(np.array([r[m] for r in dev],float))
        _,t=eer(-ld[yd==0],-ld[yd==1]); THR[m]=-t
    ev=[r for r in rows if r.get("split") in ("test","test_iv","test_f5") or r["set"]=="external"]
    y=np.array([r["label"] for r in ev])
    LL={m:cal[m].llr(np.array([r[m] for r in ev],float)) for m in have}
    ok={m:((LL[m]>=THR[m])==(y==1)) for m in have}
    best=max(have,key=lambda m: ok[m].mean())
    X=np.array([F[r["path"]] for r in ev])
    grp=np.array([r.get("speaker_id") or f"{r.get('source')}|{r['language']}" for r in ev])
    print(f"eval pool {len(ev)}   best single = {best} ({(~ok[best]).sum()} errors)\n")

    # ---------------------------------------------------------------- 1 -------
    print("="*78)
    print("1. GATE FEASIBILITY -- can audio-only features find the rescuable region?")
    print("="*78)
    for helper in ("dhwani","iv15","indic","customDeepfake"):
        tgt=(~ok[best] & ok[helper]).astype(int)      # clips worth routing
        harm=(ok[best] & ~ok[helper]).sum()           # clips that must NOT be routed
        if tgt.sum()<3: continue
        be=tgt.sum()/max(harm,1)
        # gate sees audio features + all calibrated scores (all runtime-available)
        Xg=np.hstack([X,np.column_stack([LL[m] for m in have])])
        gkf=GroupKFold(n_splits=5)
        pr=np.zeros(len(ev))
        for tr,te in gkf.split(Xg,tgt,groups=grp):
            if tgt[tr].sum()<2: continue
            clf=make_pipeline(StandardScaler(),
                              LogisticRegression(max_iter=2000,class_weight="balanced"))
            clf.fit(Xg[tr],tgt[tr]); pr[te]=clf.predict_proba(Xg[te])[:,1]
        # sweep the routing threshold; find best NET gain
        best_net=(-999,None)
        for q in np.linspace(0.50,0.9995,120):
            t=np.quantile(pr,q); sel=pr>=t
            gain=int((sel&(tgt==1)).sum()); cost=int((sel&(ok[best]&~ok[helper])).sum())
            if gain-cost>best_net[0]: best_net=(gain-cost,(q,gain,cost,sel.sum()))
        net,(q,gain,cost,nsel)=best_net
        print(f"  route to {helper:14} rescuable {tgt.sum():>3}  harmful {harm:>5}  "
              f"break-even ratio 1:{1/be:,.0f}")
        print(f"    best achievable by the gate: +{gain} rescued  -{cost} broken  "
              f"NET {net:+d}  (routes {nsel} clips)")
    # ---------------------------------------------------------------- 2 -------
    print("\n"+"="*78)
    print("2. DISAGREEMENT -- does it predict difficulty?")
    print("="*78)
    P=np.column_stack([1/(1+np.exp(-LL[m])) for m in have])
    dis=P.std(axis=1)
    strong=np.column_stack([1/(1+np.exp(-LL[m])) for m in ("spectra","stageA","iv15")]).std(axis=1)
    for nm,d in (("all-7 std",dis),("strong-3 std",strong)):
        er=~ok[best]
        a=auc(d[er],d[~er])
        q=np.quantile(d,0.95)
        print(f"  {nm:14} AUC(predicting a {best} error) = {a:.3f}   "
              f"top-5% disagreement holds {int((d>=q)&er)  if False else int(((d>=q)&er).sum())}"
              f"/{er.sum()} of the errors")
    # ---------------------------------------------------------------- 3 -------
    print("\n"+"="*78)
    print("3. PROSODY: expert vs gating feature")
    print("="*78)
    base=np.column_stack([LL[m] for m in ("spectra","stageA","iv15")])
    withp=np.hstack([base,LL["prosody"].reshape(-1,1)])
    gkf=GroupKFold(n_splits=5)
    for nm,Xf in (("without prosody",base),("prosody as EXPERT (extra LLR)",withp),
                  ("prosody as GATE FEATURE (audio+prosody)",np.hstack([base,X,LL["prosody"].reshape(-1,1)]))):
        s=np.zeros(len(ev))
        for tr,te in gkf.split(Xf,y,groups=grp):
            clf=make_pipeline(StandardScaler(),LogisticRegression(max_iter=2000))
            clf.fit(Xf[tr],y[tr]); s[te]=clf.decision_function(Xf[te])
        print(f"  {nm:42} EER {eer(-s[y==0],-s[y==1])[0]:5.2f}")
    # ---------------------------------------------------------------- 4 -------
    print("\n"+"="*78)
    print("4. UNCERTAIN BAND -- abstain instead of routing")
    print("="*78)
    conf=np.abs(LL[best]-THR[best])
    print(f"  {'abstain %':>10}{'clips':>8}{'errors kept':>13}{'error rate on kept':>21}")
    for frac in (0.0,0.005,0.01,0.02,0.05):
        k=int(len(ev)*frac); idx=np.argsort(conf)[k:] if k else np.arange(len(ev))
        e=(~ok[best])[idx].sum()
        print(f"  {100*frac:>9.1f}%{len(ev)-len(idx):>8}{e:>13}{100*e/len(idx):>20.4f}%")
    print(f"\n  ({(~ok[best]).sum()} errors at 0% abstention = {100*(~ok[best]).mean():.3f}%)")
    return 0

if __name__=="__main__": raise SystemExit(main())
