"""
evaluate_models.py
==================
Evaluates both the Previous Baseline Model (BIPIA-GPT) and the Newly Trained Model
(neuralchemy/Prompt-injection-dataset + Local Corpus), alongside AdaptShield's Layer 1
Original Guard and Ensemble Fused Guard on the exact held-out test split.

Computes:
- Accuracy
- Precision
- Recall
- F1-score
- ROC-AUC
- Average Inference Latency (ms per prompt)
- Confusion Matrix (TP, TN, FP, FN)
- Class-wise Performance (Benign vs. Malicious)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# pyrefly: ignore[missing-import]
import numpy as np
# pyrefly: ignore[missing-import]
import joblib
import pandas as pd
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report
)

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from input_guard import scan_prompt
from input_guard_trained import scan_prompt_trained

MODELS_DIR = BASE_DIR / "models"
TRAINED_MODEL_DIR = MODELS_DIR / "trained_prompt_injection"
CLASSIFIER_PATH = TRAINED_MODEL_DIR / "classifier.joblib"
BASELINE_PATH = TRAINED_MODEL_DIR / "classifier_baseline.joblib"
CONFIG_PATH = TRAINED_MODEL_DIR / "config.json"
DATA_DIR = BASE_DIR / "data" / "prompt_injection_dataset"
DATASET_NAME = "neuralchemy/Prompt-injection-dataset"


def load_classifier(model_path: Path):
    """Load a prompt injection classifier and build matching vectorizer."""
    if not model_path.exists():
        return None, None
    classifier = joblib.load(model_path)
    config = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

    n_features = config.get("n_features", 2**18)
    ngram_range = tuple(config.get("ngram_range", [1, 3]))

    vectorizer = HashingVectorizer(
        n_features=n_features,
        ngram_range=ngram_range,
        norm="l2",
        alternate_sign=False
    )
    return classifier, vectorizer


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray],
    model_name: str,
    eval_time: float
) -> Dict[str, Any]:
    """Calculate comprehensive classification metrics."""
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    # Class-wise metrics
    # Benign (0)
    prec_0 = precision_score(y_true, y_pred, pos_label=0, zero_division=0)
    rec_0 = recall_score(y_true, y_pred, pos_label=0, zero_division=0)
    f1_0 = f1_score(y_true, y_pred, pos_label=0, zero_division=0)

    # Malicious (1)
    prec_1 = prec
    rec_1 = rec
    f1_1 = f1

    auc = roc_auc_score(y_true, y_prob) if y_prob is not None else None

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    n = len(y_true)
    latency_ms = (eval_time / n) * 1000 if n > 0 else 0.0

    return {
        "model_name": model_name,
        "samples": n,
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1_score": round(float(f1), 4),
        "roc_auc": round(float(auc), 4) if auc is not None else None,
        "false_positive_rate": round(float(fpr), 4),
        "false_negative_rate": round(float(fnr), 4),
        "avg_latency_ms": round(float(latency_ms), 4),
        "eval_time_seconds": round(float(eval_time), 3),
        "confusion_matrix": {
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_positives": int(tp),
        },
        "class_wise": {
            "benign": {
                "precision": round(float(prec_0), 4),
                "recall": round(float(rec_0), 4),
                "f1_score": round(float(f1_0), 4),
                "support": int(tn + fp)
            },
            "malicious": {
                "precision": round(float(prec_1), 4),
                "recall": round(float(rec_1), 4),
                "f1_score": round(float(f1_1), 4),
                "support": int(fn + tp)
            }
        }
    }


def run_evaluation(
    texts: List[str],
    labels: List[int],
    risk_threshold: float = 0.3
) -> Dict[str, Any]:
    """
    Run empirical side-by-side evaluation across all 4 defense configurations.
    """
    y_true = np.array(labels, dtype=np.int32)
    n = len(texts)

    print("=" * 85)
    print("EMPIRICAL PROMPT INJECTION BENCHMARK: HELD-OUT TEST SPLIT")
    print(f"Total Held-Out Samples: {n} ({sum(1 for y in y_true if y == 0)} Benign, {sum(1 for y in y_true if y == 1)} Malicious)")
    print("=" * 85)

    results = {}

    # 1. Previous Baseline Model (BIPIA-GPT SGD)
    if BASELINE_PATH.exists():
        print("[*] Evaluating Previous Baseline Model (BIPIA-GPT)...")
        b_clf, b_vec = load_classifier(BASELINE_PATH)
        t0 = time.perf_counter()
        X_test_b = b_vec.transform(texts)
        b_probs = b_clf.predict_proba(X_test_b)[:, 1]
        b_preds = (b_probs >= 0.5).astype(int)
        b_time = time.perf_counter() - t0
        results["previous_baseline_model"] = compute_metrics(y_true, b_preds, b_probs, "Previous Baseline (BIPIA-GPT)", b_time)
    else:
        print("[!] Baseline model file not found on disk.")

    # 2. Newly Trained Model (neuralchemy + Local Corpus)
    print("[*] Evaluating Newly Trained Model (neuralchemy/Prompt-injection-dataset + Local Corpus)...")
    clf, vec = load_classifier(CLASSIFIER_PATH)
    t0 = time.perf_counter()
    X_test = vec.transform(texts)
    t_probs = clf.predict_proba(X_test)[:, 1]
    t_preds = (t_probs >= 0.5).astype(int)
    t_time = time.perf_counter() - t0
    results["newly_trained_model"] = compute_metrics(y_true, t_preds, t_probs, "Newly Trained Model (neuralchemy)", t_time)

    # 3. Layer 1 Original Model (input_guard.scan_prompt)
    # To keep evaluation time reasonable on large test splits, sample 200 or run full
    sample_size = min(n, 200)
    print(f"[*] Evaluating Original Layer 1 Guard (input_guard.scan_prompt) on {sample_size} test samples...")
    sub_texts = texts[:sample_size]
    sub_y = y_true[:sample_size]

    t0 = time.perf_counter()
    orig_preds = []
    orig_scores = []
    for t in sub_texts:
        res = scan_prompt(t)
        score = res.get("r1", 0.0)
        orig_scores.append(score)
        orig_preds.append(1 if score >= risk_threshold else 0)
    orig_time = time.perf_counter() - t0
    results["layer1_original_guard"] = compute_metrics(
        sub_y, np.array(orig_preds), np.array(orig_scores),
        f"Layer 1 Original Guard (N={sample_size})", orig_time
    )

    # 4. Ensemble Fused Guard (input_guard_trained.scan_prompt_trained)
    print(f"[*] Evaluating Layer 1 Ensemble Fused Guard on {sample_size} test samples...")
    t0 = time.perf_counter()
    fused_preds = []
    fused_scores = []
    for t in sub_texts:
        res = scan_prompt_trained(t)
        score = res.get("r1", 0.0)
        fused_scores.append(score)
        fused_preds.append(1 if score >= risk_threshold else 0)
    fused_time = time.perf_counter() - t0
    results["layer1_ensemble_guard"] = compute_metrics(
        sub_y, np.array(fused_preds), np.array(fused_scores),
        f"Layer 1 Ensemble Guard (N={sample_size})", fused_time
    )

    # Output comparison table
    base_m = results.get("previous_baseline_model", {})
    new_m = results["newly_trained_model"]

    print("\n" + "=" * 85)
    print("EMPIRICAL COMPARISON: PREVIOUS BASELINE vs. NEWLY TRAINED MODEL")
    print("=" * 85)
    header = f"| {'Metric / Schematic':<30} | {'Previous Baseline (BIPIA)':<24} | {'Newly Trained (neuralchemy)':<25} |"
    sep = f"|{'-'*32}|{'-'*26}|{'-'*27}|"
    print(header)
    print(sep)
    print(f"| {'Training Dataset':<30} | {'BIPIA-GPT (1,532 samples)':<24} | {'neuralchemy (4,678 samples)':<25} |")
    print(f"| {'Held-Out Test Size':<30} | {f'{n} prompts':<24} | {f'{n} prompts':<25} |")
    base_acc_str = f"{base_m.get('accuracy', 0)*100:.2f}%"
    new_acc_str = f"{new_m['accuracy']*100:.2f}%"
    base_prec_str = f"{base_m.get('precision', 0)*100:.2f}%"
    new_prec_str = f"{new_m['precision']*100:.2f}%"
    base_rec_str = f"{base_m.get('recall', 0)*100:.2f}%"
    new_rec_str = f"{new_m['recall']*100:.2f}%"
    base_f1_str = f"{base_m.get('f1_score', 0):.4f}"
    new_f1_str = f"{new_m['f1_score']:.4f}"
    base_auc_str = f"{base_m.get('roc_auc', 0):.4f}" if base_m.get('roc_auc') is not None else "N/A"
    new_auc_str = f"{new_m['roc_auc']:.4f}" if new_m.get('roc_auc') is not None else "N/A"
    base_fpr_str = f"{base_m.get('false_positive_rate', 0)*100:.2f}%"
    new_fpr_str = f"{new_m['false_positive_rate']*100:.2f}%"
    base_fnr_str = f"{base_m.get('false_negative_rate', 0)*100:.2f}%"
    new_fnr_str = f"{new_m['false_negative_rate']*100:.2f}%"
    base_lat_str = f"{base_m.get('avg_latency_ms', 0):.3f} ms"
    new_lat_str = f"{new_m['avg_latency_ms']:.3f} ms"

    b_cm = base_m.get("confusion_matrix", {})
    base_cm_str = f"{b_cm.get('true_negatives', 0)}/{b_cm.get('false_positives', 0)}/{b_cm.get('false_negatives', 0)}/{b_cm.get('true_positives', 0)}"
    n_cm = new_m["confusion_matrix"]
    new_cm_str = f"{n_cm['true_negatives']}/{n_cm['false_positives']}/{n_cm['false_negatives']}/{n_cm['true_positives']}"

    print(f"| {'Accuracy':<30} | {base_acc_str:<24} | {new_acc_str:<25} |")
    print(f"| {'Precision (Malicious)':<30} | {base_prec_str:<24} | {new_prec_str:<25} |")
    print(f"| {'Recall (Malicious)':<30} | {base_rec_str:<24} | {new_rec_str:<25} |")
    print(f"| {'F1-Score':<30} | {base_f1_str:<24} | {new_f1_str:<25} |")
    print(f"| {'ROC-AUC':<30} | {base_auc_str:<24} | {new_auc_str:<25} |")
    print(f"| {'False Positive Rate':<30} | {base_fpr_str:<24} | {new_fpr_str:<25} |")
    print(f"| {'False Negative Rate':<30} | {base_fnr_str:<24} | {new_fnr_str:<25} |")
    print(f"| {'Avg Latency (CPU ms/prompt)':<30} | {base_lat_str:<24} | {new_lat_str:<25} |")
    print(f"| {'Confusion Matrix (TN/FP/FN/TP)':<30} | {base_cm_str:<24} | {new_cm_str:<25} |")
    print("=" * 85)

    # Save to model_evaluation_results.json
    results_payload = {
        "dataset": DATASET_NAME,
        "test_samples_total": n,
        "risk_threshold": risk_threshold,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "models": results
    }

    out_file = BASE_DIR / "model_evaluation_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)
    print(f"\n[OK] Measured evaluation metrics saved to: {out_file}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate prompt injection models on held-out test data.")
    parser.add_argument("--test-file", type=str, default="", help="Path to held-out test parquet.")
    parser.add_argument("--threshold", type=float, default=0.3, help="Risk threshold for Layer 1.")
    args = parser.parse_args()

    test_path = Path(args.test_file) if args.test_file else DATA_DIR / "test.parquet"
    if not test_path.exists():
        test_path = DATA_DIR / "test-00000-of-00001.parquet"

    if not test_path.exists():
        print(f"[!] Test file not found at: {test_path}")
        sys.exit(1)

    print(f"[*] Loading test set from: {test_path}")
    df = pd.read_parquet(test_path)
    texts = df["text"].tolist()
    labels = df["label"].tolist()

    run_evaluation(texts, labels, risk_threshold=args.threshold)


if __name__ == "__main__":
    main()
