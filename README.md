# Survival of the Stealthiest: Evolving Low-Entropy Ransomware

[cite_start]This repository contains the implementation and experimental data for **"Survival of the Stealthiest: Evolving Low-Entropy Ransomware via Genetic Algorithms,"** a study exploring Search-Based Software Engineering (SBSE) techniques to generate evasive, low-noise cryptographic attacks[cite: 420, 424].

## 📌 Project Overview
Traditional ransomware often triggers defense systems due to high-volume encryption spikes. [cite_start]This project introduces a "low-and-slow" attack vector that uses a **Genetic Algorithm (GA)** to optimize encryption frequency ($C$) and dormant intervals ($S$)[cite: 423, 425, 457]. [cite_start]By treating detection thresholds as dynamic constraints, the evolved ransomware masquerades as legitimate system behavior while maintaining 100% encryption progress over extended periods[cite: 436, 456, 483].

## 🛠 Methodology
* [cite_start]**Attacker Model**: A discretized, time-slotted strategy $(C, S)$ that balances data encryption volume ($V$) against system-level anomaly scores ($\Delta$)[cite: 457, 461, 463].
* [cite_start]**Search Algorithm**: A constrained Genetic Algorithm (GA) implemented via the **PyMoo** library[cite: 462, 464, 468].
* [cite_start]**Fitness Function**: Maximizes negated encryption volume $f(x) = -V$, subject to the environmental constraint $g(x) = D$ (where $D=1$ indicates detection)[cite: 464, 465].
* [cite_start]**Environment**: A closed-loop system where the server acts as an automated oracle, providing real-time feedback from system status logs[cite: 468, 470].

## 📊 Key Results
[cite_start]The GA-evolved attack successfully identified a "stealth boundary" that bypassed modern behavioral monitors[cite: 474, 476]:
* [cite_start]**Zero Detection Events**: Achieved 100% final encryption progress without triggering alerts[cite: 474, 483].
* [cite_start]**Optimized Throughput**: Converged to a rhythmic pace of approximately 1 character every 60 seconds[cite: 475, 485].
* [cite_start]**Reliability**: Outperformed baseline high-volume attacks in high-security environments where detection leads to immediate process termination[cite: 486].

| Metric | Baseline Attack | GA-Evolved Attack |
| :--- | :--- | :--- |
| **Total Time** | ~3,000s | [cite_start]~30,000s [cite: 483] |
| **Detection Events** | 0 | [cite_start]0 [cite: 483] |
| **Encryption Progress**| 100% | [cite_start]100% [cite: 483] |

## 🚀 Getting Started
### Prerequisites
* Python 3.8+
* [cite_start]`pymoo` library [cite: 468]
* Target environment with system status logging enabled

### Running the Optimizer
```bash
python evolve_attack.py --pop_size 40 --generations 50
```
[cite_start]*The default configuration uses Simulated Binary Crossover (SBX) and Polynomial Mutation as detailed in the methodology[cite: 469, 470].*

## 📂 Repository Structure
* [cite_start]`/roar_client`: Implementation of the client+attacker.
* [cite_start]`/roar_server`: Implementation of the server.

---

**Disclaimer**: This project is for research and educational purposes only within the scope of the SSBSE 2026 Challenge. Use responsibly.
