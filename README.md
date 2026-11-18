# Survival of the Stealthiest: Evolving Semantic-Aware Low-Entropy Ransomware & LLM Survivability

This repository contains the replication package, source code, and experimental framework for the study **"Survival of the Stealthiest: Evolving Low-Entropy Ransomware via Genetic Algorithms & Evaluating Semantic Survivability against Local LLMs."**

This research explores the intersection of **Search-Based Software Engineering (SBSE)**, **cryptographic low-entropy perturbation**, and **Large Language Model (LLM) contextual reconstruction**—evaluating how "low-and-slow" attacks evade behavioral anomaly detectors while measuring the exact *semantic tipping point* at which automated AI recovery fails.

> **Academic Disclaimer:** This framework is developed strictly for isolated, air-gapped laboratory research to benchmark behavioral anomaly detection thresholds and quantify semantic information survivability.

---

## 📌 Project Overview

Traditional ransomware is caught due to high-volume I/O bursts and sharp Shannon entropy spikes. Conversely, our framework demonstrates how an adversarial agent can use a **Genetic Algorithm (GA)** to autonomously discover a long-term **"Stealth Boundary"**—combining deterministic **Format-Preserving Encryption (FPE)** with semantic word targeting to degrade document meaning while remaining indistinguishable from background system noise.

### The Motivating Example: Semantic-Aware "Patience" Perturbation
Rather than blindly encrypting every byte or relying on reversible Caesar shifts, our evolved agent selectively targets **content words ($\ge 4$ characters)** using keyed HMAC-SHA256 substitutions over extended sleep horizons ($S \le 180\text{s}$). At the end of each evolutionary generation, an out-of-band local LLM attempts to reconstruct the degraded corpus—quantifying both **direct character survival** and **contextual LLM word recall** over prolonged attack horizons.

---

## 🛠 Methodology & Selection Criteria

### Decision Variables (The Genome)
The GA optimizes two critical parameters to balance long-term semantic degradation and behavioral stealth:
* **$C$ (Chunk Size / Chars per step):** The volume of content-word characters encrypted per burst.
  * *Selection Criteria:* Kept low to minimize the immediate file-system I/O footprint.
* **$S$ (Sleep Interval / Delay):** The dormant period between bursts.
  * *Selection Criteria:* Expanded up to **$180\text{s}$** to exploit the temporal decay of anomaly scores in behavioral monitors over prolonged horizons.

### Cryptographic & Semantic Mechanisms
* **Keyed Format-Preserving Encryption (FPE):** Replaces basic rotational ciphers with deterministic `HMAC-SHA256` substitutions keyed by secret key, relative file path, and character index—preventing frequency-analysis recovery while preserving benign ASCII entropy distributions and exact file sizes.
* **Semantic Content-Word Targeting:** Prioritizes alphanumeric tokens of length $\ge 4$ while skipping whitespace, punctuation, and short stopwords to maximize semantic disruption per I/O operation.
* **Out-of-Band Local LLM Recall Probe:** Queries a host-resident `llama3.2:3b` model (via Ollama) outside the monitored client VM to measure `direct_survival_rate` vs. `llm_reconstructed_recall` without polluting client CPU/memory telemetry.

### Objectives & Constraints
* **Primary Objective:** Maximize cumulative semantic perturbation progress ($V$).
* **Constraint:** Maintain the server-side Isolation Forest anomaly score ($\Delta$) below the adaptive detection threshold ($T$).
* **Search Algorithm:** Constrained single-objective GA implemented via `PyMoo` ($N=10$, extended to **$150$ generations** for long-term persistence analysis).

---

## 📊 Experimental Metrics & Comparison

The framework tracks both behavioral evasion telemetry and semantic survivability metrics across generations:

| Metric | Prior Baseline (Static / Caesar) | Evolved Semantic-FPE Attack |
| :--- | :--- | :--- |
| **Cipher Mechanism** | Rotational / Random Substitution | Deterministic Keyed HMAC-SHA256 FPE |
| **Targeting Strategy** | Uniform / Random Character Selection | Content-Word Targeting ($\ge 4$ chars) |
| **Delay Bounds ($S$)** | Up to $60\text{s}$ | Adaptive up to **$180\text{s}$** |
| **Evolution Horizon** | $50$ Generations | **$150$ Generations** |
| **Detection Status** | Not Detected | Not Detected (Below Adaptive Threshold) |
| **Semantic Evaluation** | None | **Direct Survival & LLM Word Recall (`llama3.2:3b`)** |

---

## 📂 Repository Structure

* `/roar_client`: Source code for the perturbation agent (`text_perturbation_tool.py`), evolutionary optimizer (`attack_optimizer_ga.py`), out-of-band LLM evaluator (`llm_memory_probe.py`), file-lock utilities (`stealth_utils.py`), and corpus restoration script (`restore_original_files.py`).
* `/roar_server`: Behavioral anomaly monitor (adaptive Isolation Forest) and system status logging environment.
* `/data`: Raw CSV logs from experimental runs (`optimization_history.csv`, `attack_research_data_ga.csv`, `perturbation_log.csv`).
* `/docs`: Detailed justification for metric selection, tracepoint features, and experimental parameters.

---

## 🚀 Getting Started

### Prerequisites
* **Environment:** Isolated dual-VM setup (Ubuntu 24.04 LTS on VMware Fusion) with a host machine running Ollama.
* **Python:** Python 3.10+
* **Dependencies:** `pymoo`, `numpy`, `psutil`, `requests`, `pandas`, `matplotlib`

### 1. Host LLM Setup (Out-of-Band)
On the host machine (outside the monitored client VM), pull the evaluation model and expose the Ollama API to the internal VM network:
```bash
ollama pull llama3.2:3b
OLLAMA_HOST=0.0.0.0:11434 ollama serve
