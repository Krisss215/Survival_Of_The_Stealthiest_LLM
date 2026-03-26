# Project Goal: SSBSE 2026 Challenge - "Creeping Attack"

## 1. Context
You are currently looking at the **CLIENT SIDE** codebase of a Client-Server architecture. This code runs on an isolated Virtual Machine (VM). 

## 2. The Objective
We are building a "creeping attack" (stealthy ransomware) for an academic challenge. The goal is to slowly mutate text files on this VM without the Server's fingerprinting defense detecting the anomaly. Also, the server needs to be able to learn what "normal" user behavior looks like on this VM before the attack starts.

## 3. Your Task (Gap Analysis)
Please scan my entire current codebase in this workspace. Based on the project objective above and the code you currently see:
1. Briefly summarize what is currently implemented and working on this Client machine.
2. Analyze the gaps: What specific scripts, functionalities, or components are completely missing from this Client VM to achieve the project's goals? (Think about the attack itself and the baseline generation).
3. Provide a step-by-step development plan to build these missing parts, and ask me if we should start writing the first missing script.