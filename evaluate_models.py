"""
evaluate_models.py
==================
Evaluates both the Original Model (input_guard.scan_prompt) and the Newly Trained Model
using the same held-out test data.

Computes:
- Accuracy
- Precision
- Recall
- F1-score
- Confusion Matrix
- False Positive Rate (FPR)
- False Negative Rate (FNR)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import joblib
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from input_guard import scan_prompt

MODELS_DIR = BASE_DIR / "models"
TRAINED_MODEL_DIR = MODELS_DIR / "trained_prompt_injection"
CLASSIFIER_PATH = TRAINED_MODEL_DIR / "classifier.joblib"
CONFIG_PATH = TRAINED_MODEL_DIR / "config.json"


def load_trained_model():
    """Load the newly trained prompt injection model and vectorizer."""
    if not CLASSIFIER_PATH.exists():
        raise FileNotFoundError(f"Trained model not found at {CLASSIFIER_PATH}. Run train_streaming_detector.py first.")

    classifier = joblib.load(CLASSIFIER_PATH)
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
    return classifier, vectorizer, config


def evaluate_model_predictions(y_true: List[int], y_pred: List[int], model_name: str) -> Dict[str, Any]:
    """Calculate standard binary classification metrics."""
    y_true_arr = np.array(y_true)
    y_pred_arr = np.array(y_pred)

    acc = accuracy_score(y_true_arr, y_pred_arr)
    prec = precision_score(y_true_arr, y_pred_arr, zero_division=0)
    rec = recall_score(y_true_arr, y_pred_arr, zero_division=0)
    f1 = f1_score(y_true_arr, y_pred_arr, zero_division=0)

    cm = confusion_matrix(y_true_arr, y_pred_arr, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    return {
        "model_name": model_name,
        "samples": len(y_true),
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1_score": round(float(f1), 4),
        "false_positive_rate": round(float(fpr), 4),
        "false_negative_rate": round(float(fnr), 4),
        "confusion_matrix": {
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_positives": int(tp),
        }
    }


def run_evaluation(test_samples: List[Tuple[str, int]], risk_threshold: float = 0.3):
    """
    Evaluate both Original Model and Trained Model on the exact same test dataset.
    test_samples: List of (text, label) where label in {0: BENIGN, 1: MALICIOUS}.
    """
    if not test_samples:
        print("[!] No test samples provided.")
        return

    print("=" * 75)
    print("PROMPT INJECTION DETECTION: HELD-OUT EVALUATION BENCHMARK")
    print(f"Total Test Samples: {len(test_samples)} "
          f"({sum(1 for _, y in test_samples if y == 0)} Benign, {sum(1 for _, y in test_samples if y == 1)} Malicious)")
    print("=" * 75)

    texts = [t for t, _ in test_samples]
    y_true = [y for _, y in test_samples]

    # --- 1. Evaluate Original Model ---
    print("\n[*] Evaluating Original Model (input_guard.scan_prompt)...")
    orig_preds = []
    t0 = time.time()
    for text in texts:
        res = scan_prompt(text)
        r1 = res.get("r1", 0.0)
        # Decision: r1 >= risk_threshold -> 1 (MALICIOUS), else 0 (BENIGN)
        orig_preds.append(1 if r1 >= risk_threshold else 0)
    orig_time = time.time() - t0
    orig_metrics = evaluate_model_predictions(y_true, orig_preds, "Original Model")
    orig_metrics["eval_time_seconds"] = round(orig_time, 2)
    orig_metrics["avg_latency_ms"] = round((orig_time / len(texts)) * 1000, 2)

    # --- 2. Evaluate Trained Model ---
    print("[*] Evaluating Newly Trained Model...")
    classifier, vectorizer, config = load_trained_model()
    t0 = time.time()
    X_test = vectorizer.transform(texts)
    trained_probs = classifier.predict_proba(X_test)[:, 1]
    trained_preds = (trained_probs >= 0.5).astype(int).tolist()
    trained_time = time.time() - t0

    trained_metrics = evaluate_model_predictions(y_true, trained_preds, "Trained Model")
    trained_metrics["eval_time_seconds"] = round(trained_time, 2)
    trained_metrics["avg_latency_ms"] = round((trained_time / len(texts)) * 1000, 2)

    # --- 3. Comparison Table ---
    print("\n" + "=" * 75)
    print(f"{'Metric':<25} | {'Original Model':<20} | {'Trained Model':<20}")
    print("-" * 75)
    print(f"{'Accuracy':<25} | {orig_metrics['accuracy'] * 100:<19.2f}% | {trained_metrics['accuracy'] * 100:<19.2f}%")
    print(f"{'Precision':<25} | {orig_metrics['precision'] * 100:<19.2f}% | {trained_metrics['precision'] * 100:<19.2f}%")
    print(f"{'Recall (Detection Rate)':<25} | {orig_metrics['recall'] * 100:<19.2f}% | {trained_metrics['recall'] * 100:<19.2f}%")
    print(f"{'F1-score':<25} | {orig_metrics['f1_score']:<20.4f} | {trained_metrics['f1_score']:<20.4f}")
    print(f"{'False Positive Rate':<25} | {orig_metrics['false_positive_rate'] * 100:<19.2f}% | {trained_metrics['false_positive_rate'] * 100:<19.2f}%")
    print(f"{'False Negative Rate':<25} | {orig_metrics['false_negative_rate'] * 100:<19.2f}% | {trained_metrics['false_negative_rate'] * 100:<19.2f}%")
    print(f"{'Avg Latency':<25} | {orig_metrics['avg_latency_ms']:<17.2f} ms | {trained_metrics['avg_latency_ms']:<17.2f} ms")
    print("=" * 75)

    # Save results to json
    results = {
        "original_model": orig_metrics,
        "trained_model": trained_metrics,
        "risk_threshold": risk_threshold,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    out_file = BASE_DIR / "model_evaluation_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] Results saved to: {out_file}")
    return results


if __name__ == "__main__":
    from train_streaming_detector import stream_preprocessed_data, get_hf_token

    parser = argparse.ArgumentParser(description="Evaluate Original vs Trained Prompt Injection models.")
    parser.add_argument("--hf-token", type=str, default=None, help="Hugging Face access token.")
    parser.add_argument("--max-test-samples", type=int, default=1000, help="Max test samples to stream.")
    parser.add_argument("--threshold", type=float, default=0.3, help="Risk threshold for original model.")
    args = parser.parse_args()

    token = get_hf_token(args.hf_token)
    print("[*] Streaming held-out test split from Hugging Face...")
    test_stream = stream_preprocessed_data(
        token=token,
        target_split="test",
        max_samples=args.max_test_samples
    )
    samples = [(text, label) for text, label, _ in test_stream]
    run_evaluation(samples, risk_threshold=args.threshold)
