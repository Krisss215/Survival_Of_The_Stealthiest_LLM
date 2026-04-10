# Survival of the Stealthiest: Evolving Low-Entropy Ransomware

This repository contains the implementation and experimental data for **"Survival of the Stealthiest: Evolving Low-Entropy Ransomware via Genetic Algorithms,"** a study exploring Search-Based Software Engineering (SBSE) techniques to generate evasive, low-noise cryptographic attacks.

## 📌 Project Overview
Traditional ransomware often triggers defense systems due to high-volume encryption spikes. This project introduces a "low-and-slow" attack vector that uses a **Genetic Algorithm (GA)** to optimize encryption frequency ($C$) and dormant intervals ($S$). By treating detection thresholds as dynamic constraints, the evolved ransomware masquerades as legitimate system behavior while maintaining 100% encryption progress over extended periods.

## 🛠 Methodology
* **Attacker Model**: A discretized, time-slotted strategy $(C, S)$ that balances data encryption volume ($V$) against system-level anomaly scores ($\Delta$).
* **Search Algorithm**: A constrained Genetic Algorithm (GA) implemented via the **PyMoo** library.
* **Fitness Function**: Maximizes negated encryption volume $f(x) = -V$, subject to the environmental constraint $g(x) = D$ (where $D=1$ indicates detection).
* **Environment**: A closed-loop system where the server acts as an automated oracle, providing real-time feedback from system status logs.

## 📊 Key Results
The GA-evolved attack successfully identified a "stealth boundary" that bypassed modern behavioral monitors:
* **Zero Detection Events**: Achieved 100% final encryption progress without triggering alerts.
* **Optimized Throughput**: Converged to a rhythmic pace of approximately 1 character every 60 seconds.
* **Reliability**: Outperformed baseline high-volume attacks in high-security environments where detection leads to immediate process termination.

| Metric | Baseline Attack | GA-Evolved Attack |
| :--- | :--- | :--- |
| **Total Time** | ~3,000s | ~30,000s  |
| **Detection Events** | 0 | 0  |
| **Encryption Progress**| 10% | 100%  |

## 🚀 Getting Started
### Prerequisites
* Python 3.8+
* `pymoo` library 
* Target environment with system status logging enabled

## 📂 Repository Structure
* `/roar_client`: Implementation of the client+attacker.
* `/roar_server`: Implementation of the server.

---

**Disclaimer**: This project is for research and educational purposes only within the scope of the SSBSE 2026 Challenge. Use responsibly.
