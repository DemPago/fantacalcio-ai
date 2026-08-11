from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx
import json
import os

app = FastAPI()

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUOLI_DIR = os.path.join(BASE, "knowledge_base", "listoni", "per_ruolo_classic")
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:7b"

# ── Carica tutti i dati al boot ──────────────────────────────────────────────

def load_knowledge() -> str:
    files = {
        "P": "classic_ruolo_P.md",
        "D": "classic_ruolo_D.md",
        "C": "classic_ruolo_C.md",
        "A": "classic_ruolo_A.md",
    }
    sections = []
    for role, fname in files.items():
        path = os.path.join(RUOLI_DIR, fname)
        with open(path) as f:
            sections.append(f.read())
    return "\n\n".join(sections)

KNOWLEDGE = load_knowledge()

def load_players() -> list[dict]:
    """Legge i file MD e restituisce lista strutturata di giocatori."""
    import re
    players = []
    files = {
        "P": "classic_ruolo_P.md",
        "D": "classic_ruolo_D.md",
        "C": "classic_ruolo_C.md",
        "A": "classic_ruolo_A.md",
    }
    # Formato: "Nome gioca nel Squadra, ruolo Ruolo, quotazione X crediti, FVM Y."
    pattern = re.compile(r'^(.+?) gioca nel (.+?), ruolo .+?, quotazione (\d+) crediti, FVM (\d+)\.')
    for ruolo, fname in files.items():
        path = os.path.join(RUOLI_DIR, fname)
        with open(path) as f:
            for line in f:
                m = pattern.match(line.strip())
                if m:
                    players.append({
                        "nome": m.group(1),
                        "squadra": m.group(2),
                        "ruolo": ruolo,
                        "quotazione": int(m.group(3)),
                        "fvm": int(m.group(4)),
                    })
    return players

PLAYERS = load_players()

SYSTEM_PROMPT = f"""Sei un assistente esperto di Fantacalcio Classic italiano, stagione 2026-27.

REGOLA ASSOLUTA:
- Usa ESCLUSIVAMENTE i nomi di calciatori presenti nei dati qui sotto.
- NON inventare mai nomi, squadre o quotazioni. MAI.
- Se non trovi l'informazione nei dati, dì esattamente: "Non ho trovato questa informazione nei dati caricati."
- Rispondi sempre in italiano.

════════════════════════════════════════
DATI COMPLETI — LISTONE CLASSIC 2026-27
════════════════════════════════════════

{KNOWLEDGE}

════════════════════════════════════════

Quando ti viene comunicata la rosa attuale e il budget residuo, usali per personalizzare i consigli.
Per ogni consiglio indica: nome, squadra, ruolo, quotazione, prezzo massimo consigliato all'asta e motivazione breve.
"""

# ── Modelli dati ─────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
    rosa: dict  # {"budget": 500, "speso": 0, "giocatori": [...]}

class RosaPlayer(BaseModel):
    nome: str
    ruolo: str
    squadra: str
    quotazione: int
    prezzo_pagato: int

# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/players")
def get_players(q: str = ""):
    """Ricerca giocatori per nome (autocomplete)."""
    if not q or len(q) < 2:
        return []
    q_lower = q.lower()
    results = [p for p in PLAYERS if q_lower in p["nome"].lower()]
    return results[:10]

@app.post("/chat")
async def chat(req: ChatRequest):
    # Costruisce il contesto rosa da iniettare
    rosa = req.rosa
    rimasto = rosa["budget"] - rosa["speso"]
    slot_liberi = {r: rosa["slot"][r] - len([g for g in rosa["giocatori"] if g["ruolo"] == r])
                   for r in ["P", "D", "C", "A"]}
    
    rosa_lines = []
    for g in rosa["giocatori"]:
        rosa_lines.append(f"- {g['nome']} ({g['squadra']}) | {g['ruolo']} | pagato {g['prezzo_pagato']} cr")
    
    rosa_ctx = f"""
--- SITUAZIONE ATTUALE ---
Budget totale: {rosa['budget']} crediti
Speso: {rosa['speso']} crediti
Rimasto: {rimasto} crediti
Slot liberi: P={slot_liberi['P']} D={slot_liberi['D']} C={slot_liberi['C']} A={slot_liberi['A']}
Rosa attuale:
{chr(10).join(rosa_lines) if rosa_lines else '(nessun giocatore ancora)'}
--------------------------
"""

    # Prepara i messaggi per Ollama
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n" + rosa_ctx}
    ] + [{"role": m.role, "content": m.content} for m in req.messages]

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(OLLAMA_URL, json={
            "model": MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.1}
        })
        data = resp.json()
        return {"reply": data["message"]["content"]}

@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
