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
MODEL = "mistral:7b"

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

def build_player_index(data: dict) -> dict:
    """Dizionario nome_lower → {nome, squadra, ruolo, quotazione, fvm}"""
    import re
    index = {}
    pattern = re.compile(r'^(.+?) gioca nel (.+?), ruolo .+?, quotazione (\d+) crediti, FVM (\d+)\.')
    for ruolo, content in data.items():
        for line in content.splitlines():
            m = pattern.match(line.strip())
            if m:
                nome = m.group(1)
                index[nome.lower()] = {
                    "nome": nome, "squadra": m.group(2),
                    "ruolo": ruolo, "quotazione": int(m.group(3)), "fvm": int(m.group(4))
                }
    return index

def verify_names(text: str, index: dict) -> list[dict]:
    """Cerca parole con iniziale maiuscola nel testo e verifica se sono nel listone."""
    import re
    # Parole con maiuscola che non siano inizio frase (precedute da spazio)
    candidates = re.findall(r'(?<= )([A-Z][a-zàèéìòùA-Z]+(?:\s+[A-Z][a-z]+)?)', text)
    # Aggiungi anche prima parola se è un nome
    first = re.match(r'^([A-Z][a-zàèéìòùA-Z]+)', text)
    if first:
        candidates.append(first.group(1))
    
    results = []
    seen = set()
    for c in candidates:
        key = c.lower()
        key_nospace = key.replace(" ", "")

        # Cerca corrispondenza: esatta, senza spazi, o parziale (min 4 char)
        found = index.get(key) or index.get(key_nospace)
        if not found:
            for k, v in index.items():
                if (len(key) >= 4 and key in k) or (len(key_nospace) >= 4 and key_nospace in k):
                    found = v
                    break
        if found and found["nome"] not in seen:
            seen.add(found["nome"])
            results.append({"cercato": c, "trovato": True, "dati": found})
        elif len(c) >= 4 and c not in seen:
            seen.add(c)
            results.append({"cercato": c, "trovato": False, "dati": None})
    return results

def count_players(data: dict) -> int:
    return sum(line.count("gioca nel") for d in data.values() for line in d.splitlines())

# ── Rileva il ruolo dalla domanda ─────────────────────────────────────────────

def find_player_by_name(query: str, index: dict) -> dict | None:
    """Cerca un giocatore nell'indice per nome (esatto, senza spazi, parziale ≥4 char)."""
    key = query.lower()
    key_nospace = key.replace(" ", "")
    found = index.get(key) or index.get(key_nospace)
    if not found:
        for k, v in index.items():
            if (len(key) >= 4 and key in k) or (len(key_nospace) >= 4 and key_nospace in k):
                return v
    return found

# Pattern per relazioni tipo "secondo di X", "panchinaro di X", "riserva di X"
import re as _re
_REL_PATTERN = _re.compile(
    r'\b(?:secondo|panchinaro|riserva|backup|dodicesimo|dodic)\b[^.!?]*?\bdi\s+([A-Z][a-zàèéìòùA-Z]+(?:\s+[A-Z][a-zàèéìòùA-Z]+)?)',
    _re.IGNORECASE
)

def _extract_rel_name(text: str) -> str | None:
    """Estrae il nome del giocatore da frasi relazionali; gestisce cognomi composti."""
    m = _REL_PATTERN.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    tokens = raw.split()
    if len(tokens) == 2:
        # Tieni entrambe solo se la seconda parola inizia davvero con maiuscola nel testo originale
        if not tokens[1][0].isupper():
            raw = tokens[0]
    return raw

def expand_relational_query(text: str, index: dict, data: dict) -> tuple[str, list[str]]:
    """
    Se la domanda contiene 'panchinaro/secondo/riserva di X', restituisce:
    - testo arricchito con il contesto esplicito da aggiungere alla domanda
    - lista di ruoli da caricare
    Altrimenti restituisce ('', []).
    """
    ref_name = _extract_rel_name(text)
    if not ref_name:
        return "", []
    player = find_player_by_name(ref_name, index)
    if not player:
        return "", []

    squadra = player["squadra"]
    ruolo   = player["ruolo"]

    # Tutti i giocatori dello stesso ruolo e squadra (escluso il titolare stesso)
    teammates = [
        v for v in index.values()
        if v["squadra"] == squadra and v["ruolo"] == ruolo and v["nome"] != player["nome"]
    ]

    if not teammates:
        note = (
            f"\n\n[CONTESTO AUTOMATICO] {player['nome']} ({squadra}, {ruolo}) "
            f"non ha compagni di squadra dello stesso ruolo nel listone."
        )
    else:
        lines = "\n".join(
            f"- {t['nome']} ({squadra}, {ruolo}, Q:{t['quotazione']}, FVM:{t['fvm']})"
            for t in sorted(teammates, key=lambda x: -x["fvm"])
        )
        note = (
            f"\n\n[CONTESTO AUTOMATICO] Stai cercando le riserve di {player['nome']} "
            f"({squadra}, {ruolo}, Q:{player['quotazione']}, FVM:{player['fvm']}).\n"
            f"Giocatori dello stesso ruolo e squadra nel listone:\n{lines}\n"
            f"Consiglia tra questi."
        )

    return note, [ruolo]

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

# ── Quick picks ──────────────────────────────────────────────────────────────

# Ogni quick pick ha: label (da mostrare), ruoli da caricare, prompt ottimizzato.
# I pick con ruoli=None sono gestiti in modo speciale (rosa sequenziale).
QUICK_PICKS = [
    {
        "label": "Miglior portiere assoluto",
        "roles": ["P"],
        "prompt": "Qual è il miglior portiere da acquistare all'asta? Scegli UN solo nome. Indica: nome, squadra, quotazione ufficiale, prezzo massimo consigliato, motivazione in 2 righe.",
    },
    {
        "label": "Miglior portiere low-cost (quotazione ≤ 5)",
        "roles": ["P"],
        "prompt": "Qual è il miglior portiere con quotazione ufficiale uguale o minore di 5 crediti? UN solo nome. Indica: nome, squadra, quotazione, prezzo massimo consigliato, motivazione in 2 righe.",
    },
    {
        "label": "Difesa più forte possibile",
        "roles": ["D"],
        "prompt": "Costruisci la difesa più forte possibile per il Fantacalcio Classic. Scegli esattamente 8 difensori. Per ognuno: nome, squadra, quotazione ufficiale, prezzo massimo consigliato. Niente testo extra.",
    },
    {
        "label": "Difesa economica (budget ≤ 60 crediti totali)",
        "roles": ["D"],
        "prompt": "Scegli 8 difensori con un budget totale massimo di 60 crediti (somma delle quotazioni ufficiali ≤ 60). Per ognuno: nome, squadra, quotazione. Mostra il totale alla fine.",
    },
    {
        "label": "Centrocampo più forte (modulo 3-5-2)",
        "roles": ["C"],
        "prompt": "Scegli i 5 migliori centrocampisti per un modulo 3-5-2 al Fantacalcio Classic. Per ognuno: nome, squadra, quotazione ufficiale, prezzo massimo consigliato. Niente testo extra.",
    },
    {
        "label": "Top 3 attaccanti da non perdere",
        "roles": ["A"],
        "prompt": "Quali sono i 3 attaccanti assolutamente da avere all'asta? Per ognuno: nome, squadra, quotazione ufficiale, prezzo massimo consigliato, motivazione in 1 riga.",
    },
    {
        "label": "Attaccante sorpresa (FVM alto, quotazione bassa)",
        "roles": ["A"],
        "prompt": "Trova l'attaccante con il miglior rapporto FVM/quotazione — il 'bidone d'oro' dell'asta. UN solo nome. Mostra il calcolo: FVM ÷ quotazione. Indica prezzo massimo consigliato.",
    },
    {
        "label": "Rosa competitiva completa (3-4-3)",
        "roles": None,   # gestione speciale: sequenziale per ruolo
        "modulo": {"P": 1, "D": 4, "C": 4, "A": 3},
        "prompts": {
            "P": "Scegli 2 portieri (1 titolare + 1 riserva) per una rosa 3-4-3 competitiva. Per ognuno: nome, squadra, quotazione, prezzo max consigliato.",
            "D": "Scegli 5 difensori (4 titolari + 1 riserva) per una rosa 3-4-3 competitiva. Per ognuno: nome, squadra, quotazione, prezzo max consigliato.",
            "C": "Scegli 5 centrocampisti (4 titolari + 1 riserva) per una rosa 3-4-3 competitiva. Per ognuno: nome, squadra, quotazione, prezzo max consigliato.",
            "A": "Scegli 4 attaccanti (3 titolari + 1 riserva) per una rosa 3-4-3 competitiva. Per ognuno: nome, squadra, quotazione, prezzo max consigliato.",
        },
    },
    {
        "label": "Rosa low-cost (budget totale ≤ 250 crediti)",
        "roles": None,   # gestione speciale: sequenziale per ruolo
        "prompts": {
            "P": "Scegli 2 portieri con budget massimo 20 crediti totali. Per ognuno: nome, squadra, quotazione.",
            "D": "Scegli 5 difensori con budget massimo 70 crediti totali. Per ognuno: nome, squadra, quotazione.",
            "C": "Scegli 5 centrocampisti con budget massimo 80 crediti totali. Per ognuno: nome, squadra, quotazione.",
            "A": "Scegli 4 attaccanti con budget massimo 80 crediti totali. Per ognuno: nome, squadra, quotazione.",
        },
    },
]

def show_quick_picks_menu():
    print("\n  ┌─ QUICK PICKS ─────────────────────────────────────┐")
    for i, p in enumerate(QUICK_PICKS, 1):
        print(f"  │  [{i:2d}] {p['label']}")
    print("  │  [ 0] Torna alla chat libera")
    print("  └────────────────────────────────────────────────────┘")

def run_quick_pick(pick: dict, data: dict, history: list) -> list[dict]:
    """
    Esegue un quick pick e restituisce i messaggi da aggiungere alla storia.
    Per le rose sequenziali stampa ruolo per ruolo.
    """
    new_history = []

    if pick["roles"] is not None:
        # Pick singolo ruolo
        context = build_context(pick["roles"], data)
        role_labels = {"P":"portieri","D":"difensori","C":"centrocampisti","A":"attaccanti"}
        loaded = " + ".join(role_labels[r] for r in pick["roles"])
        print(f"  [contesto: {loaded}]")
        messages = [
            {"role": "system", "content": BASE_SYSTEM + "\n\n" + context}
        ] + history + [
            {"role": "user", "content": pick["prompt"]}
        ]
        print("AI: ", end="", flush=True)
        reply = ollama_chat(messages)
        print(reply + "\n")
        new_history.append({"role": "user",      "content": pick["prompt"]})
        new_history.append({"role": "assistant",  "content": reply})

    else:
        # Rosa sequenziale: una chiamata per ruolo
        role_order = ["P", "D", "C", "A"]
        role_labels = {"P": "PORTIERI", "D": "DIFENSORI", "C": "CENTROCAMPISTI", "A": "ATTACCANTI"}
        print(f"\n  [rosa sequenziale: 4 chiamate separate]\n")
        for role in role_order:
            prompt_r = pick["prompts"][role]
            context  = build_context([role], data)
            print(f"  ── {role_labels[role]} ──────────────────────────────")
            messages = [
                {"role": "system", "content": BASE_SYSTEM + "\n\n" + context}
            ] + history + new_history + [
                {"role": "user", "content": prompt_r}
            ]
            print("AI: ", end="", flush=True)
            reply = ollama_chat(messages)
            print(reply + "\n")
            new_history.append({"role": "user",      "content": prompt_r})
            new_history.append({"role": "assistant",  "content": reply})

    return new_history

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
    index = build_player_index(data)
    total = count_players(data)
    print(f" {total} calciatori pronti.")
    print(f"  Modello: {MODEL}")
    print("─"*55)
    print("  Comandi: /esci  /reset  /storia  /picks")
    print("═"*55)

    show_quick_picks_menu()
    print()

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

        if user_input == "/picks":
            show_quick_picks_menu()
            print()
            continue

        # ── Selezione quick pick numerica ──
        if user_input.isdigit():
            n = int(user_input)
            if n == 0:
                print("→ Chat libera.\n")
                continue
            if 1 <= n <= len(QUICK_PICKS):
                pick = QUICK_PICKS[n - 1]
                print(f"\n  → {pick['label']}\n")
                new_msgs = run_quick_pick(pick, data, history)
                history.extend(new_msgs)
                continue
            else:
                print(f"  → Numero non valido. Scegli tra 1 e {len(QUICK_PICKS)}, oppure 0.\n")
                continue

        # ── Verifica nomi propri nella domanda ──
        checks = verify_names(user_input, index)
        nomi_ok = [c for c in checks if c["trovato"]]
        nomi_ko = [c for c in checks if not c["trovato"]]

        if nomi_ok:
            for c in nomi_ok:
                d = c["dati"]
                print(f"  ✓ {d['nome']} ({d['squadra']}, {d['ruolo']}, Q:{d['quotazione']}, FVM:{d['fvm']})")
        if nomi_ko:
            for c in nomi_ko:
                print(f"  ✗ '{c['cercato']}' non trovato nel listone — potrebbe essere un nome inventato")
            # Se TUTTI i nomi sono inventati, blocca prima di chiamare il modello
            if not nomi_ok and nomi_ko:
                print("  → Nessun nome valido trovato. Correggi il nome e riprova.\n")
                continue

        # ── Espandi query relazionali (panchinaro/secondo/riserva di X) ──
        rel_note, rel_roles = expand_relational_query(user_input, index, data)
        if rel_note:
            print(f"  [relazione rilevata → compagni di ruolo iniettati]")

        # Rileva i ruoli rilevanti per questa domanda
        # Considera anche il testo delle ultime domande per il contesto
        recent_text = user_input + " ".join(m["content"] for m in history[-4:])
        roles = rel_roles if rel_roles else detect_roles(recent_text)
        context = build_context(roles, data)

        role_labels = {"P":"portieri","D":"difensori","C":"centrocampisti","A":"attaccanti"}
        loaded = " + ".join(role_labels[r] for r in roles)
        print(f"  [contesto: {loaded}]")

        # Costruisce i messaggi: system con dati freschi + storia + domanda attuale
        user_msg = user_input + rel_note  # rel_note è "" se non c'è relazione
        messages = [
            {"role": "system", "content": BASE_SYSTEM + "\n\n" + context}
        ] + history + [
            {"role": "user", "content": user_msg}
        ]

        print("AI: ", end="", flush=True)
        reply = ollama_chat(messages)
        print(reply)
        print()

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    main()
