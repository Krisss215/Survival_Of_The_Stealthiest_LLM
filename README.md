Survival of the Stealthiest: Evolving Low-Entropy Ransomware
This repository contains the replication package, source code, and experimental data for the study "Survival of the Stealthiest: Evolving Low-Entropy Ransomware via Genetic Algorithms."

This research explores the application of Search-Based Software Engineering (SBSE) to identify vulnerabilities in behavioral anomaly detection systems by evolving "low-and-slow" cryptographic attack patterns.

📌 Project Overview
Traditional ransomware is often caught due to high-volume I/O spikes. Our framework demonstrates how an adversarial agent can use a Genetic Algorithm (GA) to autonomously discover a "Stealth Boundary"—a specific configuration of encryption throughput and timing that exploits the Tolerance Gap of modern monitors.

The Motivating Example: "Patience" Ransomware

In a landscape where automated defenses (like ReliaQuest's findings) can contain attacks in minutes, our GA-evolved agent adopts the opposite strategy. By encrypting a single character per minute, the malware masquerades as background system noise. This allows it to achieve 100% encryption progress over prolonged horizons without ever crossing the detection threshold.

🛠 Methodology & Selection Criteria
Decision Variables (The Genome)

The GA optimizes two critical parameters to balance impact and stealth:

C (Chunk Size / Chars per step): The volume of data encrypted per burst.

Selection Criteria: Kept low to minimize the immediate I/O footprint.

S (Sleep Interval / Delay): The dormant period between bursts.

Selection Criteria: Calibrated at ~60s to exploit the temporal decay of anomaly scores in behavioral monitors.

Objectives & Constraints

Primary Objective: Maximize total encryption progress (V).

Constraint: Maintain the anomaly score (Δ) below the server's detection threshold (T).

Search Algorithm: Constrained GA implemented via the PyMoo library (N=10, 50 generations).

📊 Experimental Results
Our experiments demonstrate that while a static baseline might "guess" a safe speed, the GA proves the optimal stealth profile.

Metric,Static Baseline,GA-Evolved Attack
Throughput (C),1-2 chars / burst,1 char / burst (Optimized)
Delay (S),60s (Fixed),Variable (Adaptive)
Final Progress,100%,100%
Detection Status,Not Detected*,Not Detected
Avg. Anomaly Score,0.094,0.081 (Reduced)
📂 Repository Structure
/roar_client: Source code for the ransomware agent and GA implementation.

/roar_server: The behavioral monitor and system status logging environment.

/data: Raw CSV logs from experimental runs (including anomaly scores and thresholds).

/docs: Detailed justification for metric selection and experimental parameters.

🚀 Getting Started
Prerequisites

Python 3.8+

Dependencies: pandas, pymoo, matplotlib

Environment: VMware or a similar virtualized Linux environment.
