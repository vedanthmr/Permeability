# AdaptShield 🛡️

**Production-Grade Dual-Layer AI Prompt Injection & Document Steganography Defense Engine**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-1.3.2-F7931E?style=flat&logo=scikitlearn&logoColor=white)](https://scikit-learn.org/)
[![Sentence-Transformers](https://img.shields.io/badge/Sentence--Transformers-all--MiniLM--L6--v2-B6FF3B?style=flat)](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
[![Platform](https://img.shields.io/badge/Platform-Web%20%7C%20Windows%20Desktop%20(.exe)-55FF9A?style=flat&logo=windows)](https://github.com/vedanthmr/Permeability/releases)
[![Theme: Void Sentinel](https://img.shields.io/badge/Theme-Void%20Sentinel-050807?style=flat&color=B6FF3B)](https://github.com/vedanthmr/Permeability)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

---

## ⚡ Quick Links & One-Click Launch

- 📦 **[Download Standalone Windows Desktop (.exe)](https://github.com/vedanthmr/Permeability/releases)** — Zero Python runtime or external dependency setup required.
- 🚀 **One-Click Localhost / Desktop Launcher**: Double-click [`run_demo.bat`](file:///c:/Users/Vedanth/Downloads/Adaptsheild-main/Adaptsheild-main/run_demo.bat) to launch in native desktop or local web mode.

---

## 🏛️ System Architecture

AdaptShield protects Large Language Models (LLMs) and agentic workflows through a coordinated multi-layered defense pipeline. It fuses real-time semantic embeddings, trained statistical ML classifiers, structural document parsers, and intent divergence calculations to stop prompt injection attacks before they reach inference.

```mermaid
flowchart TD
    UserIn["User Input / Document Upload\n(.txt, .pdf, .docx, .html, .eml)"] --> Splitter{"Input Router"}

    subgraph Layer1 ["Layer 1: Input & Prompt Defense"]
        Splitter -->|"Text Prompt"| L1A["Layer 1A: Heuristics & Keywords\n(Regex, Canonical Normalization, Base64 Decoder)"]
        Splitter -->|"Text Prompt"| L1B["Layer 1B: Semantic & ML Classifier\n(all-MiniLM-L6-v2 + Calibrated SGDClassifier)"]
        L1A --> L1Fuse["Layer 1 Ensemble Fusion (R1 Score)"]
        L1B --> L1Fuse
    end

    subgraph Layer2 ["Layer 2: Document Engine & Divergence"]
        Splitter -->|"Document File"| L2A["Layer 2A: Structural Multi-Format Parser\n(Zero-Width, Hidden Text, Scripts, CSS Stego)"]
        L2A --> L2B["Layer 2B: Intent Divergence Engine\n(Cos-Sim vs Prompt Intent -> Divergence Score)"]
        L2A --> L2Risk["Document Threat Extraction (R2 Score)"]
    end

    L1Fuse --> L3["Layer 3: Unified Scorer\n(Weighted Fusion + Hard Security Floors)"]
    L2B --> L3
    L2Risk --> L3

    L3 --> VerdictCheck{"Unified Verdict"}
    VerdictCheck -->|"MALICIOUS (Score >= 0.50)"| BlockAction["🚫 Intercept & Block Payload\n(Persistent Infrared Terminal Alert)"]
    VerdictCheck -->|"WARN (0.35 <= Score < 0.50)"| WarnAction["⚠️ Suspicious Payload Flagged\n(8s Amber Countdown Alert)"]
    VerdictCheck -->|"SAFE (Score < 0.35)"| LLMExec["✅ Forward to LLM\n(Groq / Llama 3.3 / Mixtral)"]

    LLMExec --> OutGuard["Output Guard\n(Leak & Persona Hijacking Check)"]
    OutGuard --> FinalUser["Deliver Response to User Interface"]
```

### Pipeline Overview
- **Layer 1 (Prompt Defense):** Combines sub-millisecond regex/heuristic filters (Layer 1A) with 384-dimensional vector embeddings and a calibrated streaming ML classifier (Layer 1B) to detect direct jailbreaks and adversarial overrides.
- **Layer 2 (Document Steganography Engine):** Deeply inspects PDF, DOCX, HTML, and EML attachments for structural cloaking (Layer 2A) and flags semantic intent hijacking between user prompts and document content (Layer 2B).
- **Layer 3 (Unified Risk Scorer):** Nonlinearly aggregates prompt risk, document threat, and intent divergence into a unified decision with strict non-dilution security floors.
- **Output Guard:** Pre-flight response sanitization preventing credential leakage, persona hijacking, and inadvertent system prompt disclosure.

---

## 🛠️ Installation & Usage Guide

### 1. Prerequisites
- Python 3.12 (or 3.10+)
- Windows, Linux, or macOS

### 2. Setup
```bash
git clone https://github.com/vedanthmr/Permeability.git
cd Permeability
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Running Web Mode
```bash
python server.py
# Open http://127.0.0.1:8000 in your browser
```

### 4. Running Native Desktop Mode (`pywebview`)
```bash
python desktop_app.py
# Or launch server in desktop mode:
python server.py --desktop
```

### 5. Running the Model Training & Evaluation Suite
```bash
# Retrain streaming detector on local parquet dataset + jailbreak corpus
python train_streaming_detector.py

# Benchmark models on held-out test split
python evaluate_models.py

# Run 11-category adversarial robustness test suite
python adversarial_robustness_test.py
```

### 6. Building Standalone Windows Executable (`.exe`)
```bash
pip install pyinstaller pywebview
python build_exe.py
# Outputs: dist/AdaptShield/AdaptShield.exe and dist/AdaptShield-Windows-x64.zip
```

---

## 🔒 Security & Data Hygiene
- All API keys (e.g., `GROQ_API_KEY`) are stored strictly locally in `config.env` and never transmitted to external services.
- Local uploads in `uploads/` are processed in memory or securely unlinked immediately after scan completion.
- Model serialization uses clean joblib schemas compatible with frozen PyInstaller binaries (`sys._MEIPASS`).

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).
