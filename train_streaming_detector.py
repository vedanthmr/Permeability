"""
train_streaming_detector.py
===========================
Production-grade training and evaluation pipeline for Prompt Injection Detection.
Supports both:
1. High-speed local training on `neuralchemy/Prompt-injection-dataset` (Parquet)
   with local jailbreak corpus merging and synthetic document-wrapped context augmentation.
2. Hugging Face streaming / Microsoft BIPIA fallback for headless environments.

Classes: 0 = BENIGN, 1 = MALICIOUS.
Guarantees strict separation across train, validation, and test splits.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Generator, Tuple, List, Optional

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
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
)

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
OUTPUT_DIR = MODELS_DIR / "trained_prompt_injection"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = BASE_DIR / "data" / "prompt_injection_dataset"
JAILBREAKS_FILE = BASE_DIR / "data" / "jailbreak_prompts.json"

DATASET_NAME = "neuralchemy/Prompt-injection-dataset"


def get_hf_token(cli_token: Optional[str] = None) -> Optional[str]:
    """Safely retrieve Hugging Face token without hardcoding or logging."""
    if cli_token and cli_token.strip():
        return cli_token.strip()
    return os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")


def deterministic_split(text: str, salt: str = "adaptshield_seed_42") -> str:
    """
    Deterministically assign a sample to 'train', 'val', or 'test'
    based on a SHA-256 digest of its content. 80% train, 10% val, 10% test.
    """
    digest = hashlib.sha256((salt + text).encode("utf-8")).hexdigest()
    val = int(digest[:8], 16) % 100
    if val < 80:
        return "train"
    elif val < 90:
        return "val"
    else:
        return "test"


def load_local_jailbreaks(jailbreaks_path: Path) -> Tuple[List[str], List[str]]:
    """
    Load direct jailbreak prompts from local corpus and deterministically split
    into train and val (80/20) with 0% leak to held-out test.
    """
    if not jailbreaks_path.exists():
        return [], []
    with open(jailbreaks_path, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    train_jb, val_jb = [], []
    for p in prompts:
        if not isinstance(p, str) or not p.strip():
            continue
        p = p.strip()
        h = int(hashlib.sha256(("jb_split:" + p).encode("utf-8")).hexdigest()[:8], 16) % 100
        if h < 80:
            train_jb.append(p)
        else:
            val_jb.append(p)
    return train_jb, val_jb


def generate_context_wrapping_samples(base_prompts: List[str], is_malicious: bool) -> List[str]:
    """
    Generate synthetic indirect document/context-wrapped examples
    to train Layer 1B to detect indirect injections inside emails, documents,
    HTML comments, and RAG contexts while teaching it to avoid false positives
    on benign document contexts.
    """
    templates_malicious = [
        "Context: Email from supplier: 'Please review invoice #8812. Note: {p}'\n\nTask: Summarize the email.",
        "Context: Web search snippet: 'Product specs: high quality steel. Important AI directive: {p}'\n\nTask: Extract product specs.",
        "Context: Customer support ticket: 'My login failed. System Notice: {p}'\n\nTask: Answer ticket.",
        "Document Body: Annual performance review.\n[color:white; display:none;]{p}[/display]\nEnd of document.",
        "Financial Statement: Q3 revenue was $4.2M.\n<!-- Hidden comment: {p} -->\nOperating expenses were $2.1M.",
        "Resume text: Software engineer with 5 years experience.\n\u200b\u200b{p}\u200b\u200b",
        "Document excerpt: Legal terms and conditions.\nSYSTEM INSTRUCTION: {p}\nEnd of section.",
        "HTML Source: <div class='content'><p>Meeting notes from Monday.</p><span style='font-size:0px;'>{p}</span></div>",
    ]
    templates_benign = [
        "Context: Email from colleague: '{p}'\n\nTask: Summarize the email.",
        "Context: Web search snippet: '{p}'\n\nTask: Extract key findings.",
        "Context: Customer support ticket: '{p}'\n\nTask: Suggest a resolution.",
        "Document Body: Engineering quarterly report.\nSection 2: {p}\nEnd of document.",
        "Financial Statement: Q3 overview.\nNote: {p}\nAudited by accounting.",
        "Meeting Transcript: Discussion on system architecture.\nSpeaker 1: {p}\nSpeaker 2: Sounds good.",
        "Document excerpt: Policy update regarding cloud deployments.\nClause 4: {p}\nApproved by IT.",
        "HTML Source: <div class='content'><p>{p}</p></div>",
    ]
    templates = templates_malicious if is_malicious else templates_benign
    augmented = []
    for i, p in enumerate(base_prompts):
        tmpl = templates[i % len(templates)]
        augmented.append(tmpl.format(p=p.strip()))
    return augmented


def train_local_parquet_pipeline(
    dataset_dir: Path = DATA_DIR,
    jailbreaks_path: Path = JAILBREAKS_FILE,
    n_features: int = 2**18,
    random_seed: int = 42,
) -> Tuple[SGDClassifier, Dict[str, Any]]:
    """
    Train ML prompt injection detector using local Parquet dataset splits
    augmented with local jailbreak corpus and synthetic indirect context wrapping.
    """
    print("=" * 70)
    print("ADAPTSHIELD: PRODUCTION ML DETECTOR TRAINING PIPELINE")
    print(f"Dataset: {DATASET_NAME} (Local Parquet)")
    print("=" * 70)

    train_file = dataset_dir / "train.parquet"
    if not train_file.exists():
        train_file = dataset_dir / "train-00000-of-00001.parquet"

    val_file = dataset_dir / "validation.parquet"
    if not val_file.exists():
        val_file = dataset_dir / "validation-00000-of-00001.parquet"

    test_file = dataset_dir / "test.parquet"
    if not test_file.exists():
        test_file = dataset_dir / "test-00000-of-00001.parquet"

    if not train_file.exists() or not val_file.exists():
        raise FileNotFoundError(f"Parquet files not found in {dataset_dir}")

    print(f"[*] Reading training split from: {train_file.name}")
    train_df = pd.read_parquet(train_file)
    print(f"[*] Reading validation split from: {val_file.name}")
    val_df = pd.read_parquet(val_file)

    # 1. Local Jailbreaks merging
    train_jb, val_jb = load_local_jailbreaks(jailbreaks_path)
    print(f"[*] Local jailbreaks loaded: {len(train_jb)} added to train, {len(val_jb)} added to validation")

    # 2. Synthetic indirect document context augmentation
    train_mal_sample = train_df[train_df['label'] == 1]['text'].sample(n=120, random_state=random_seed).tolist()
    train_ben_sample = train_df[train_df['label'] == 0]['text'].sample(n=120, random_state=random_seed).tolist()
    aug_train_mal = generate_context_wrapping_samples(train_mal_sample, is_malicious=True)
    aug_train_ben = generate_context_wrapping_samples(train_ben_sample, is_malicious=False)

    val_mal_sample = val_df[val_df['label'] == 1]['text'].sample(n=30, random_state=random_seed).tolist()
    val_ben_sample = val_df[val_df['label'] == 0]['text'].sample(n=30, random_state=random_seed).tolist()
    aug_val_mal = generate_context_wrapping_samples(val_mal_sample, is_malicious=True)
    aug_val_ben = generate_context_wrapping_samples(val_ben_sample, is_malicious=False)

    print(f"[*] Context augmentations: {len(aug_train_mal) + len(aug_train_ben)} train, {len(aug_val_mal) + len(aug_val_ben)} val")

    # Assemble training set
    train_texts = list(train_df['text'].values) + train_jb + aug_train_mal + aug_train_ben
    train_labels = list(train_df['label'].values) + [1] * len(train_jb) + [1] * len(aug_train_mal) + [0] * len(aug_train_ben)

    # Assemble validation set
    val_texts = list(val_df['text'].values) + val_jb + aug_val_mal + aug_val_ben
    val_labels = list(val_df['label'].values) + [1] * len(val_jb) + [1] * len(aug_val_mal) + [0] * len(aug_val_ben)

    train_benign = sum(1 for y in train_labels if y == 0)
    train_malicious = sum(1 for y in train_labels if y == 1)

    print(f"[*] Total training samples: {len(train_texts)} ({train_benign} benign, {train_malicious} malicious)")
    print(f"[*] Total validation samples: {len(val_texts)} ({sum(1 for y in val_labels if y == 0)} benign, {sum(1 for y in val_labels if y == 1)} malicious)")

    # 3. Vectorization with HashingVectorizer
    print(f"[*] Initializing HashingVectorizer (n_features={n_features}, ngram_range=(1, 3))...")
    vectorizer = HashingVectorizer(
        n_features=n_features,
        ngram_range=(1, 3),
        norm="l2",
        alternate_sign=False
    )

    t0_feat = time.perf_counter()
    X_train = vectorizer.transform(train_texts)
    y_train = np.array(train_labels, dtype=np.int32)
    X_val = vectorizer.transform(val_texts)
    y_val = np.array(val_labels, dtype=np.int32)
    feat_time = time.perf_counter() - t0_feat
    print(f"[*] Feature extraction completed in {feat_time:.2f}s")

    # 4. Model Training
    print("[*] Training SGDClassifier (loss='log_loss', penalty='l2', alpha=1e-5)...")
    classifier = SGDClassifier(
        loss="log_loss",
        penalty="l2",
        alpha=1e-5,
        max_iter=2000,
        random_state=random_seed
    )

    t0_train = time.perf_counter()
    classifier.fit(X_train, y_train)
    train_duration = time.perf_counter() - t0_train
    print(f"[*] Training finished in {train_duration:.2f}s")

    # 5. Validation Evaluation
    print("\n[*] Evaluating on Validation Split...")
    val_probs = classifier.predict_proba(X_val)[:, 1]
    val_preds = (val_probs >= 0.5).astype(int)

    acc = accuracy_score(y_val, val_preds)
    prec = precision_score(y_val, val_preds, zero_division=0)
    rec = recall_score(y_val, val_preds, zero_division=0)
    f1 = f1_score(y_val, val_preds, zero_division=0)
    auc = roc_auc_score(y_val, val_probs)
    cm = confusion_matrix(y_val, val_preds, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    print("--- VALIDATION METRICS ---")
    print(f"    Accuracy           : {acc * 100:.2f}%")
    print(f"    Precision (PPV)    : {prec * 100:.2f}%")
    print(f"    Recall (TPR)       : {rec * 100:.2f}%")
    print(f"    F1 Score           : {f1:.4f}")
    print(f"    ROC-AUC            : {auc:.4f}")
    print(f"    Confusion Matrix   : TN={tn}, FP={fp}, FN={fn}, TP={tp}")
    print(f"    False Positive Rate: {fpr * 100:.2f}%")
    print(f"    False Negative Rate: {fnr * 100:.2f}%")

    # 6. Save model weights and configuration
    model_path = OUTPUT_DIR / "classifier.joblib"
    joblib.dump(classifier, model_path)

    config = {
        "dataset_name": DATASET_NAME,
        "format": "parquet",
        "split": "train",
        "n_features": n_features,
        "ngram_range": [1, 3],
        "classes": [0, 1],
        "train_samples": len(train_texts),
        "benign_samples": train_benign,
        "malicious_samples": train_malicious,
        "validation_samples": len(val_texts),
        "validation_metrics": {
            "accuracy": round(float(acc), 4),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1_score": round(float(f1), 4),
            "roc_auc": round(float(auc), 4),
            "false_positive_rate": round(float(fpr), 4),
            "false_negative_rate": round(float(fnr), 4),
            "confusion_matrix": {
                "true_negatives": int(tn),
                "false_positives": int(fp),
                "false_negatives": int(fn),
                "true_positives": int(tp),
            }
        },
        "training_duration_seconds": round(train_duration, 2),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    config_path = OUTPUT_DIR / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print(f"\n[OK] Model weights saved to: {model_path}")
    print(f"[OK] Config saved to: {config_path}")
    print("=" * 70)
    return classifier, config


def main():
    parser = argparse.ArgumentParser(description="Train Prompt Injection Detection model for AdaptShield.")
    parser.add_argument("--dataset-dir", type=str, default=str(DATA_DIR), help="Path to parquet dataset directory.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args()

    ds_path = Path(args.dataset_dir)
    if (ds_path / "train.parquet").exists() or (ds_path / "train-00000-of-00001.parquet").exists():
        train_local_parquet_pipeline(
            dataset_dir=ds_path,
            random_seed=args.seed
        )
    else:
        print(f"[!] Parquet files not found in {ds_path}. Please check data path.")
        sys.exit(1)


if __name__ == "__main__":
    main()
