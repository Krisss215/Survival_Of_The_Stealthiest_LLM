# Project Goal: SSBSE 2026 Challenge - Defense System

## 1. Context
You are currently looking at the **SERVER SIDE** codebase of a Client-Server architecture. This code runs on an isolated Virtual Machine (VM) and receives sensor data from the Client VM.

## 2. The Objective
We are building a defense mechanism against a "creeping attack" (stealthy ransomware) for an academic challenge. The Server's job is to analyze the incoming client CSV data and perform "Fingerprinting" to detect slow, stealthy anomalies (mutations) happening on the client's file system, while ignoring normal background noise.

## 3. Your Task (Gap Analysis)
Please scan my entire current codebase in this workspace. Based on the project objective above and the code you currently see:
1. Briefly summarize what infrastructure is currently implemented on this Server (e.g., data receiving, basic reward logic).
2. Analyze the gaps: What specific logics, anomaly detection algorithms, or fingerprinting mechanisms are missing or need to be improved here to achieve the project's goal?
3. Provide a step-by-step development plan to build or upgrade these missing defense mechanisms, and ask me if we should start with the first step.