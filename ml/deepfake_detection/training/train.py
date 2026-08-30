"""Phase 2: train the XGBoost DSP-anomaly classifier once you have a labeled
genuine/synthetic dataset (e.g. ASVspoof2021 + your own collected samples).

Expected input: a CSV/manifest with columns [filepath, label] where
label = 0 (genuine) / 1 (synthetic).
"""
from __future__ import annotations
import argparse
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

from ml.common.audio_utils import load_audio
from ml.deepfake_detection.preprocessing.feature_extraction import extract_all_features


def build_dataset(manifest_csv: str):
    df = pd.read_csv(manifest_csv)
    X, y = [], []
    for _, row in df.iterrows():
        audio = load_audio(row["filepath"])
        X.append(extract_all_features(audio))
        y.append(int(row["label"]))
    return np.stack(X), np.array(y)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, help="CSV with filepath,label columns")
    parser.add_argument("--out", default="models/dsp_xgb.json")
    args = parser.parse_args()

    X, y = build_dataset(args.manifest)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    # Also save genuine-only reference stats for the rule-based fallback / normalization.
    genuine_mask = y_train == 0
    np.save("models/dsp_ref_mean.npy", X_train[genuine_mask].mean(axis=0))
    np.save("models/dsp_ref_std.npy", X_train[genuine_mask].std(axis=0) + 1e-6)

    clf = xgb.XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, eval_metric="logloss",
    )
    clf.fit(X_train, y_train)

    preds = clf.predict(X_test)
    probs = clf.predict_proba(X_test)[:, 1]
    print(classification_report(y_test, preds, target_names=["genuine", "synthetic"]))
    print("ROC-AUC:", roc_auc_score(y_test, probs))

    clf.save_model(args.out)
    print("Saved model to", args.out)


if __name__ == "__main__":
    main()
