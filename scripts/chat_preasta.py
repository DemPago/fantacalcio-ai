#!/usr/bin/env python3
"""
Chat pre-asta Classic 2026-27
Mantiene la storia della conversazione.
Inietta solo i dati del ruolo rilevante per non saturare il contesto.
Uso: python3 scripts/chat_preasta.py
"""

import os
import json
import urllib.request
import urllib.error
import subprocess
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUOLI_DIR = os.path.join(BASE, "knowledge_base", "listoni", "per_ruolo_classic")
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:7b"

# ── Carica i file per ruolo ───────────────────────────────────────────────────

def load_files() -> dict:
    files = {
        "P": "classic_ruolo_P.md",
        "D": "classic_ruolo_D.md",
        "C": "classic_ruolo_C.md",
        "A": "classic_ruolo_A.md",
    }
    data = {}
    for role, fname in files.items():
        with open(os.path.join(RUOLI_DIR, fname)) as f:
            data[role] = f.read()
    return data

def count_players(data: dict) -> int:
    return sum(line.count("gioca nel") for d in data.values() for line in d.splitlines())

# ── Rileva il ruolo dalla domanda ─────────────────────────────────────────────

def detect_roles(text: str) -> list[str]:
    t = text.lower()
    roles = []
    if any(w in t for w in ["portier", "porta", "keeper", "estremo difensor"]):
        roles.append("P")
    if any(w in t for w in ["difensor", "difesa", "terzin", "backline", "reparto difensiv"]):
        roles.append("D")
    if any(w in t for w in ["centrocampist", "centrocampo", "mezzal", "trequart", "mediano", "regista"]):
        roles.append("C")
    if any(w in t for w in ["attaccan", "attacco", "punta", "bomber", "centravant", "prima punta"]):
        roles.append("A")
    # Solo per domande esplicitamente globali → tutti i ruoli
    if not roles or any(w in t for w in ["tutti i ruoli", "tutta la rosa", "intera rosa", "strategia", "budget", "distribu"]):
        roles = ["P", "D", "C", "A"]
    return roles

# ── Costruisce il system prompt con solo i dati rilevanti ─────────────────────

BASE_SYSTEM = """Sei un assistente esperto di Fantacalcio Classic italiano, stagione 2026-27.

REGOLA ASSOLUTA:
- Usa ESCLUSIVAMENTE i nomi di calciatori presenti nei dati qui sotto.
- NON inventare mai nomi, squadre o quotazioni. MAI.
- Se non trovi l'informazione, dì: "Non ho questo dato nel listone."
- Rispondi sempre in italiano.
- Ricorda il contesto della conversazione e le domande precedenti.

Per ogni consiglio indica: nome, squadra, ruolo, quotazione ufficiale, prezzo massimo consigliato all'asta e motivazione breve."""

def build_context(roles: list[str], data: dict) -> str:
    sections = []
    labels = {"P": "PORTIERI", "D": "DIFENSORI", "C": "CENTROCAMPISTI", "A": "ATTACCANTI"}
    for r in roles:
        sections.append(f"=== {labels[r]} ===\n{data[r]}")
    return "\n\n".join(sections)

# ── Chat con Ollama ───────────────────────────────────────────────────────────

def restart_ollama():
    """Riavvia Ollama silenziosamente e attende che sia pronto."""
    print("  [riavvio Ollama...]", end="", flush=True)
    subprocess.run(["pkill", "ollama"], capture_output=True)
    time.sleep(3)
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Aspetta fino a 15 secondi che risponda
    for _ in range(15):
        try:
            urllib.request.urlopen("http://localhost:11434", timeout=1)
            print(" pronto.")
            return True
        except:
            time.sleep(1)
    print(" fallito.")
    return False

def ollama_chat(messages: list, retry: bool = True) -> str:
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 16384}
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["message"]["content"]
    except (urllib.error.URLError, TimeoutError):
        if retry:
            if restart_ollama():
                return ollama_chat(messages, retry=False)
        return "Ollama non risponde anche dopo il riavvio. Prova a rilanciare lo script."

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "═"*55)
    print("  ⚽  FANTACALCIO AI — PRE-ASTA CLASSIC 2026-27")
    print("═"*55)
    print("  Caricamento listone...", end="", flush=True)

    data = load_files()
    total = count_players(data)
    print(f" {total} calciatori pronti.")
    print(f"  Modello: {MODEL}")
    print("─"*55)
    print("  Comandi: /esci  /reset  /storia")
    print("═"*55 + "\n")

    # La storia non include il system prompt (viene ricostruito ad ogni turno)
    history: list[dict] = []

    while True:
        try:
            user_input = input("Tu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nA presto!")
            break

        if not user_input:
            continue

        if user_input == "/esci":
            print("A presto!")
            break

        if user_input == "/reset":
            history = []
            print("→ Conversazione resettata.\n")
            continue

        if user_input == "/storia":
            if not history:
                print("→ Nessuna domanda ancora.\n")
            else:
                print(f"\n→ {len(history)//2} scambi nella sessione:")
                for m in history:
                    label = "Tu" if m["role"] == "user" else "AI"
                    preview = m["content"][:80].replace("\n", " ")
                    print(f"  [{label}] {preview}...")
                print()
            continue

        # Rileva i ruoli rilevanti per questa domanda
        # Considera anche il testo delle ultime domande per il contesto
        recent_text = user_input + " ".join(m["content"] for m in history[-4:])
        roles = detect_roles(recent_text)
        context = build_context(roles, data)

        role_labels = {"P":"portieri","D":"difensori","C":"centrocampisti","A":"attaccanti"}
        loaded = " + ".join(role_labels[r] for r in roles)
        print(f"  [contesto: {loaded}]")

        # Costruisce i messaggi: system con dati freschi + storia + domanda attuale
        messages = [
            {"role": "system", "content": BASE_SYSTEM + "\n\n" + context}
        ] + history + [
            {"role": "user", "content": user_input}
        ]

        print("AI: ", end="", flush=True)
        reply = ollama_chat(messages)
        print(reply)
        print()

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    main()
