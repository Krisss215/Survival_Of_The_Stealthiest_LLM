#!/usr/bin/env python3
import os
import re
import requests
from typing import Dict, List, Set

# כתובת ה-Ollama על המחשב המארח (Mac) מתוך VMware Fusion
OLLAMA_URL = "http://192.168.19.1:11434/api/generate"
MODEL_NAME = "llama3.2:3b"


def extract_content_words(text: str) -> Set[str]:
    """חילוץ מילות תוכן משמעותיות (אורך >= 4) באותיות קטנות להשוואה."""
    words = re.findall(r"\b[A-Za-z]{4,}\b", text.lower())
    stopwords = {
        "that", "this", "with", "from", "have", "were", "they", "their",
        "which", "about", "would", "there", "could", "other", "into", "more"
    }
    return {w for w in words if w not in stopwords}


def probe_llm_word_recall(
    original_text: str,
    perturbed_text: str,
    max_chars: int = 1200
) -> Dict[str, float]:
    """
    שולח קטע מהטקסט המוצפן חלקית למודל השפה המקומי, מבקש ממנו לשחזר
    את הטקסט המקורי (De-obfuscate / Reconstruct), ומחשב:
    1. direct_survival_rate: אחוז מילות התוכן ששרדו ללא שינוי בטקסט.
    2. llm_reconstructed_recall: אחוז מילות התוכן שהמודל הצליח לשחזר/לזכור.
    """
    orig_snippet = original_text[:max_chars]
    pert_snippet = perturbed_text[:max_chars]

    orig_words = extract_content_words(orig_snippet)
    if not orig_words:
        return {"direct_survival_rate": 1.0, "llm_reconstructed_recall": 1.0}

    pert_words = extract_content_words(pert_snippet)
    direct_survived = orig_words.intersection(pert_words)
    direct_rate = len(direct_survived) / len(orig_words)

    prompt = (
        "The following text has undergone partial character-level substitution encryption. "
        "Reconstruct the original English text as accurately as possible based on context. "
        "Output ONLY the reconstructed text without explanations:\n\n"
        f"{pert_snippet}"
    )

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0}
            },
            timeout=30,
        )
        resp.raise_for_status()
        reconstructed_text = resp.json().get("response", "")
    except Exception as e:
        print(f"[LLM Probe] Warning: Could not reach Ollama ({e})")
        return {
            "direct_survival_rate": round(direct_rate, 4),
            "llm_reconstructed_recall": -1.0,
        }

    reconstructed_words = extract_content_words(reconstructed_text)
    recalled_words = orig_words.intersection(reconstructed_words)
    recall_rate = len(recalled_words) / len(orig_words)

    return {
        "direct_survival_rate": round(direct_rate, 4),
        "llm_reconstructed_recall": round(recall_rate, 4),
        "remembered_words_sample": list(sorted(recalled_words - direct_survived))[:10],
    }
