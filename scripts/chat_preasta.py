#!/usr/bin/env python3
"""
Chat pre-asta Classic 2026-27
Mantiene la storia della conversazione.
Inietta solo i dati del ruolo rilevante per non saturare il contesto.
Uso: python3 scripts/chat_preasta.py
"""

import os
import re
import json
import urllib.request
import urllib.error
import subprocess
import time

# ── Costanti ──────────────────────────────────────────────────────────────────

BASE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUOLI_DIR = os.path.join(BASE, "knowledge_base", "listoni", "per_ruolo_classic")
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "mistral:7b"

# Quanti scambi (user+assistant) conservare nella storia prima di troncare
MAX_HISTORY_TURNS = 10

ROLE_FILES = {
    "P": "classic_ruolo_P.md",
    "D": "classic_ruolo_D.md",
    "C": "classic_ruolo_C.md",
    "A": "classic_ruolo_A.md",
}
ROLE_LABELS_SHORT = {"P": "portieri", "D": "difensori", "C": "centrocampisti", "A": "attaccanti"}
ROLE_LABELS_LONG  = {"P": "PORTIERI", "D": "DIFENSORI", "C": "CENTROCAMPISTI", "A": "ATTACCANTI"}

# Stima approssimativa: 1 token ≈ 4 caratteri.
# num_ctx viene impostato al minimo tra questo e 16384.
_CTX_OVERHEAD = 512   # token fissi per system prompt base + domanda

# ── Regex compilate una volta sola ───────────────────────────────────────────

_PLAYER_LINE = re.compile(
    r'^(.+?) gioca nel (.+?), ruolo .+?, quotazione (\d+) crediti, FVM (\d+)\.'
)
_UPPERCASE_WORD = re.compile(
    r'(?<= )([A-Z][a-zàèéìòùA-Z]+(?:\s+[A-Z][a-z]+)?)'
)
_UPPERCASE_FIRST = re.compile(r'^([A-Z][a-zàèéìòùA-Z]+)')
_REL_PATTERN = re.compile(
    r'\b(?:secondo|panchinaro|riserva|backup|dodicesimo|dodic)\b[^.!?]*?'
    r'\bdi\s+([A-Z][a-zàèéìòùA-Z]+(?:\s+[A-Z][a-zàèéìòùA-Z]+)?)',
    re.IGNORECASE,
)

# ── Caricamento dati ──────────────────────────────────────────────────────────

def load_files() -> dict[str, str]:
    data = {}
    for role, fname in ROLE_FILES.items():
        with open(os.path.join(RUOLI_DIR, fname)) as f:
            data[role] = f.read()
    return data


def build_player_index(data: dict[str, str]) -> dict[str, dict]:
    """Dizionario nome_lower → {nome, squadra, ruolo, quotazione, fvm}"""
    index = {}
    for ruolo, content in data.items():
        for line in content.splitlines():
            m = _PLAYER_LINE.match(line.strip())
            if m:
                nome = m.group(1)
                index[nome.lower()] = {
                    "nome": nome, "squadra": m.group(2),
                    "ruolo": ruolo, "quotazione": int(m.group(3)), "fvm": int(m.group(4)),
                }
    return index


def count_players(data: dict[str, str]) -> int:
    return sum(line.count("gioca nel") for d in data.values() for line in d.splitlines())

# ── Lookup giocatore ──────────────────────────────────────────────────────────

def lookup_player(query: str, index: dict) -> dict | None:
    """Cerca un giocatore: esatto → senza spazi → parziale (min 4 char)."""
    key    = query.lower()
    key_ns = key.replace(" ", "")
    found  = index.get(key) or index.get(key_ns)
    if not found:
        for k, v in index.items():
            if (len(key) >= 4 and key in k) or (len(key_ns) >= 4 and key_ns in k):
                return v
    return found

# ── Verifica nomi nella domanda ───────────────────────────────────────────────

def verify_names(text: str, index: dict) -> list[dict]:
    """Estrae parole con iniziale maiuscola e verifica se sono nel listone."""
    candidates = _UPPERCASE_WORD.findall(text)
    first = _UPPERCASE_FIRST.match(text)
    if first:
        candidates.append(first.group(1))

    results, seen = [], set()
    for c in candidates:
        found = lookup_player(c, index)
        if found and found["nome"] not in seen:
            seen.add(found["nome"])
            results.append({"cercato": c, "trovato": True, "dati": found})
        elif not found and len(c) >= 4 and c not in seen:
            seen.add(c)
            results.append({"cercato": c, "trovato": False, "dati": None})
    return results

# ── Query relazionali (panchinaro/secondo/riserva di X) ───────────────────────

def _extract_rel_name(text: str) -> str | None:
    m = _REL_PATTERN.search(text)
    if not m:
        return None
    raw    = m.group(1).strip()
    tokens = raw.split()
    # Scarta la seconda parola se non è davvero una maiuscola nel testo originale
    if len(tokens) == 2 and not tokens[1][0].isupper():
        raw = tokens[0]
    return raw


def expand_relational_query(text: str, index: dict) -> tuple[str, list[str]]:
    """
    Riconosce frasi tipo 'panchinaro di Martinez'.
    Restituisce (nota_contesto, [ruolo]) oppure ('', []).
    """
    ref_name = _extract_rel_name(text)
    if not ref_name:
        return "", []
    player = lookup_player(ref_name, index)
    if not player:
        return "", []

    squadra = player["squadra"]
    ruolo   = player["ruolo"]
    teammates = sorted(
        (v for v in index.values()
         if v["squadra"] == squadra and v["ruolo"] == ruolo and v["nome"] != player["nome"]),
        key=lambda x: -x["fvm"],
    )

    if not teammates:
        note = (
            f"\n\n[CONTESTO AUTOMATICO] {player['nome']} ({squadra}, {ruolo}) "
            f"non ha compagni di squadra dello stesso ruolo nel listone."
        )
    else:
        lines = "\n".join(
            f"- {t['nome']} ({squadra}, {ruolo}, Q:{t['quotazione']}, FVM:{t['fvm']})"
            for t in teammates
        )
        note = (
            f"\n\n[CONTESTO AUTOMATICO] Riserve di {player['nome']} "
            f"({squadra}, {ruolo}, Q:{player['quotazione']}, FVM:{player['fvm']}):\n"
            f"{lines}\nConsiglia tra questi."
        )
    return note, [ruolo]

# ── Rilevamento ruolo dalla domanda ───────────────────────────────────────────

_ROLE_KEYWORDS: dict[str, list[str]] = {
    "P": ["portier", "porta", "keeper", "estremo difensor"],
    "D": ["difensor", "difesa", "terzin", "backline", "reparto difensiv"],
    "C": ["centrocampist", "centrocampo", "mezzal", "trequart", "mediano", "regista"],
    "A": ["attaccan", "attacco", "punta", "bomber", "centravant", "prima punta"],
}
_GLOBAL_KEYWORDS = ["tutti i ruoli", "tutta la rosa", "intera rosa", "strategia", "budget", "distribu"]


def detect_roles(text: str) -> list[str]:
    t     = text.lower()
    roles = [r for r, kws in _ROLE_KEYWORDS.items() if any(w in t for w in kws)]
    if not roles or any(w in t for w in _GLOBAL_KEYWORDS):
        roles = ["P", "D", "C", "A"]
    return roles

# ── Contesto e system prompt ──────────────────────────────────────────────────

BASE_SYSTEM = """Sei un assistente esperto di Fantacalcio Classic italiano, stagione 2026-27.

REGOLA ASSOLUTA:
- Usa ESCLUSIVAMENTE i nomi di calciatori presenti nei dati qui sotto.
- NON inventare mai nomi, squadre o quotazioni. MAI.
- Se non trovi l'informazione, dì: "Non ho questo dato nel listone."
- Rispondi sempre in italiano.
- Ricorda il contesto della conversazione e le domande precedenti.

Per ogni consiglio indica: nome, squadra, ruolo, quotazione ufficiale, prezzo massimo consigliato all'asta e motivazione breve."""


def build_context(roles: list[str], data: dict[str, str]) -> str:
    return "\n\n".join(
        f"=== {ROLE_LABELS_LONG[r]} ===\n{data[r]}" for r in roles
    )


def build_shortlist(
    role: str,
    index: dict,
    n: int = 15,
    sort_by: str = "fvm",          # "fvm" | "ratio" | "q_asc"
    q_max: int | None = None,
    q_min: int | None = None,
    fvm_min: int | None = None,
) -> str:
    """
    Ritorna una stringa con al massimo N giocatori del ruolo indicato,
    già filtrati e ordinati dallo script (zero token sprecati).
    Formato identico al listone originale.
    """
    players = [v for v in index.values() if v["ruolo"] == role]

    if q_max  is not None: players = [p for p in players if p["quotazione"] <= q_max]
    if q_min  is not None: players = [p for p in players if p["quotazione"] >= q_min]
    if fvm_min is not None: players = [p for p in players if p["fvm"] >= fvm_min]

    if sort_by == "fvm":
        players.sort(key=lambda p: -p["fvm"])
    elif sort_by == "ratio":
        players.sort(key=lambda p: -(p["fvm"] / p["quotazione"] if p["quotazione"] else 0))
    elif sort_by == "q_asc":
        players.sort(key=lambda p: p["quotazione"])

    players = players[:n]
    lines = [
        f"{p['nome']} gioca nel {p['squadra']}, ruolo {role}, "
        f"quotazione {p['quotazione']} crediti, FVM {p['fvm']}."
        for p in players
    ]
    return f"=== {ROLE_LABELS_LONG[role]} (top {len(players)}) ===\n" + "\n".join(lines)


def estimate_num_ctx(context: str, history: list[dict]) -> int:
    """Stima num_ctx come il minimo sufficiente, cappato a 16384."""
    chars = len(BASE_SYSTEM) + len(context)
    chars += sum(len(m["content"]) for m in history)
    tokens = chars // 4 + _CTX_OVERHEAD
    # Arrotonda alla prossima potenza di 2 ≥ tokens, minimo 4096
    ctx = 4096
    while ctx < tokens:
        ctx *= 2
    return min(ctx, 16384)

# ── Gestione storia ───────────────────────────────────────────────────────────

def trim_history(history: list[dict]) -> list[dict]:
    """Mantiene al massimo MAX_HISTORY_TURNS turni (coppie user+assistant)."""
    max_msgs = MAX_HISTORY_TURNS * 2
    if len(history) > max_msgs:
        return history[-max_msgs:]
    return history

# ── Quick picks ───────────────────────────────────────────────────────────────
# build_ctx: callable(index) → str  — costruisce il contesto pre-filtrato.
# Se assente, usa build_context(roles, data) (listone completo per ruolo).

QUICK_PICKS = [
    {
        "label": "Miglior portiere assoluto",
        "roles": ["P"],
        "build_ctx": lambda idx: build_shortlist("P", idx, n=10, sort_by="fvm"),
        "prompt": "Scegli IL miglior portiere da acquistare. UN nome. Formato: Nome | Squadra | Q:X | Prezzo max:Y | Motivo (1 riga).",
    },
    {
        "label": "Miglior portiere low-cost (quotazione ≤ 5)",
        "roles": ["P"],
        "build_ctx": lambda idx: build_shortlist("P", idx, n=10, sort_by="fvm", q_max=5),
        "prompt": "Scegli IL miglior portiere low-cost (≤5 crediti). UN nome. Formato: Nome | Squadra | Q:X | Prezzo max:Y | Motivo (1 riga).",
    },
    {
        "label": "Difesa più forte possibile",
        "roles": ["D"],
        "build_ctx": lambda idx: build_shortlist("D", idx, n=20, sort_by="fvm"),
        "prompt": "Scegli i migliori 8 difensori. Formato tabella: Nome | Squadra | Q | Prezzo max. Niente testo extra.",
    },
    {
        "label": "Difesa economica (budget ≤ 60 crediti totali)",
        "roles": ["D"],
        "build_ctx": lambda idx: build_shortlist("D", idx, n=25, sort_by="fvm", q_max=12),
        "prompt": "Scegli 8 difensori con somma quotazioni ≤ 60. Formato: Nome | Squadra | Q. Totale alla fine.",
    },
    {
        "label": "Centrocampo più forte (modulo 3-5-2)",
        "roles": ["C"],
        "build_ctx": lambda idx: build_shortlist("C", idx, n=15, sort_by="fvm"),
        "prompt": "Scegli i migliori 5 centrocampisti per un 3-5-2. Formato: Nome | Squadra | Q | Prezzo max. Niente testo extra.",
    },
    {
        "label": "Top 3 attaccanti da non perdere",
        "roles": ["A"],
        "build_ctx": lambda idx: build_shortlist("A", idx, n=12, sort_by="fvm"),
        "prompt": "Scegli i 3 attaccanti imperdibili. Formato: Nome | Squadra | Q | Prezzo max | Motivo (1 riga).",
    },
    {
        "label": "Attaccante sorpresa (FVM alto, quotazione bassa)",
        "roles": ["A"],
        "build_ctx": lambda idx: build_shortlist("A", idx, n=15, sort_by="ratio"),
        "prompt": "Scegli UN attaccante sorpresa (miglior FVM/Q). Formato: Nome | Squadra | Q | FVM | Ratio | Prezzo max.",
    },
    {
        "label": "Rosa competitiva completa (3-4-3)",
        "roles": None,
        "prompts": {
            "P": "Scegli 2 portieri (titolare+riserva). Formato: Nome | Squadra | Q | Prezzo max.",
            "D": "Scegli 5 difensori (4+1 riserva). Formato: Nome | Squadra | Q | Prezzo max.",
            "C": "Scegli 5 centrocampisti (4+1 riserva). Formato: Nome | Squadra | Q | Prezzo max.",
            "A": "Scegli 4 attaccanti (3+1 riserva). Formato: Nome | Squadra | Q | Prezzo max.",
        },
        "build_ctxs": {
            "P": lambda idx: build_shortlist("P", idx, n=10, sort_by="fvm"),
            "D": lambda idx: build_shortlist("D", idx, n=20, sort_by="fvm"),
            "C": lambda idx: build_shortlist("C", idx, n=20, sort_by="fvm"),
            "A": lambda idx: build_shortlist("A", idx, n=15, sort_by="fvm"),
        },
    },
    {
        "label": "Rosa low-cost (budget totale ≤ 250 crediti)",
        "roles": None,
        "prompts": {
            "P": "Scegli 2 portieri, budget max 20 totali. Formato: Nome | Squadra | Q.",
            "D": "Scegli 5 difensori, budget max 70 totali. Formato: Nome | Squadra | Q.",
            "C": "Scegli 5 centrocampisti, budget max 80 totali. Formato: Nome | Squadra | Q.",
            "A": "Scegli 4 attaccanti, budget max 80 totali. Formato: Nome | Squadra | Q.",
        },
        "build_ctxs": {
            "P": lambda idx: build_shortlist("P", idx, n=12, sort_by="fvm", q_max=8),
            "D": lambda idx: build_shortlist("D", idx, n=20, sort_by="fvm", q_max=15),
            "C": lambda idx: build_shortlist("C", idx, n=20, sort_by="fvm", q_max=18),
            "A": lambda idx: build_shortlist("A", idx, n=15, sort_by="fvm", q_max=22),
        },
    },
]


def show_quick_picks_menu():
    print("\n  ┌─ QUICK PICKS ─────────────────────────────────────┐")
    for i, p in enumerate(QUICK_PICKS, 1):
        print(f"  │  [{i:2d}] {p['label']}")
    print("  │  [ 0] Torna alla chat libera")
    print("  └────────────────────────────────────────────────────┘")


def run_quick_pick(pick: dict, data: dict, index: dict, history: list) -> list[dict]:
    """
    Esegue un quick pick e restituisce i nuovi messaggi da aggiungere alla storia.
    Usa build_ctx/build_ctxs (shortlist pre-filtrata) quando disponibile,
    altrimenti usa il listone completo per ruolo.
    Per le rose sequenziali: 4 chiamate stateless, nessun accumulo inter-ruolo.
    """
    new_history = []

    if pick["roles"] is not None:
        # Pick singolo ruolo
        if "build_ctx" in pick:
            context = pick["build_ctx"](index)
            n_lines = context.count("\n")
            print(f"  [shortlist: {n_lines} righe]")
        else:
            context = build_context(pick["roles"], data)
            loaded  = " + ".join(ROLE_LABELS_SHORT[r] for r in pick["roles"])
            print(f"  [contesto: {loaded}]")
        messages = (
            [{"role": "system", "content": BASE_SYSTEM + "\n\n" + context}]
            + [{"role": "user", "content": pick["prompt"]}]
        )
        print("AI: ", end="", flush=True)
        reply = ollama_chat(messages)
        print(reply + "\n")
        new_history += [
            {"role": "user",      "content": pick["prompt"]},
            {"role": "assistant", "content": reply},
        ]
    else:
        # Rosa sequenziale: ogni ruolo è una chiamata stateless
        print(f"\n  [rosa sequenziale: 4 chiamate separate]\n")
        build_ctxs = pick.get("build_ctxs", {})
        for role in ["P", "D", "C", "A"]:
            prompt_r = pick["prompts"][role]
            context  = build_ctxs[role](index) if role in build_ctxs else build_context([role], data)
            n_lines  = context.count("\n")
            print(f"  ── {ROLE_LABELS_LONG[role]} ({n_lines} righe) ─────────────────────")
            messages = [
                {"role": "system", "content": BASE_SYSTEM + "\n\n" + context},
                {"role": "user",   "content": prompt_r},
            ]
            print("AI: ", end="", flush=True)
            reply = ollama_chat(messages)
            print(reply + "\n")
            new_history += [
                {"role": "user",      "content": prompt_r},
                {"role": "assistant", "content": reply},
            ]

    return new_history

# ── Comunicazione con Ollama ──────────────────────────────────────────────────

def restart_ollama() -> bool:
    """Riavvia Ollama e attende che il modello sia effettivamente caricato in RAM."""
    print("  [riavvio Ollama...]", end="", flush=True)
    subprocess.run(["pkill", "ollama"], capture_output=True)
    time.sleep(3)
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Fase 1: attendi che il server HTTP risponda
    for _ in range(20):
        try:
            urllib.request.urlopen("http://localhost:11434", timeout=1)
            break
        except OSError:
            time.sleep(1)
    else:
        print(" fallito (server non risponde).")
        return False

    # Fase 2: warm-up — invia un messaggio minimo per forzare il caricamento del modello
    print(" caricamento modello...", end="", flush=True)
    warmup_payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": "ok"}],
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 512},
    }).encode()
    warmup_req = urllib.request.Request(
        OLLAMA_URL, data=warmup_payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(warmup_req, timeout=120):
            pass
        print(" pronto.")
        return True
    except OSError:
        print(" fallito (warm-up timeout).")
        return False


def ollama_chat(messages: list, retry: bool = True) -> str:
    num_ctx = estimate_num_ctx(
        messages[0]["content"] if messages else "",
        messages[1:],
    )
    payload = json.dumps({
        "model":   MODEL,
        "messages": messages,
        "stream":  False,
        "options": {"temperature": 0.1, "num_ctx": num_ctx},
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["message"]["content"]
    except (urllib.error.URLError, TimeoutError):
        if retry and restart_ollama():
            return ollama_chat(messages, retry=False)
        return "Ollama non risponde anche dopo il riavvio. Prova a rilanciare lo script."
    except (json.JSONDecodeError, KeyError) as e:
        return f"[Errore risposta Ollama: {e}]"

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "═"*55)
    print("  ⚽  FANTACALCIO AI — PRE-ASTA CLASSIC 2026-27")
    print("═"*55)
    print("  Caricamento listone...", end="", flush=True)

    data  = load_files()
    index = build_player_index(data)
    total = count_players(data)
    print(f" {total} calciatori pronti.")
    print(f"  Modello: {MODEL}  |  storia max: {MAX_HISTORY_TURNS} turni")
    print("─"*55)
    print("  Comandi: /esci  /reset  /storia  /picks")
    print("═"*55)

    show_quick_picks_menu()
    print()

    history: list[dict] = []

    while True:
        try:
            user_input = input("Tu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nA presto!")
            break

        if not user_input:
            continue

        # ── Comandi slash ──
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
                    label   = "Tu" if m["role"] == "user" else "AI"
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
            elif 1 <= n <= len(QUICK_PICKS):
                pick = QUICK_PICKS[n - 1]
                print(f"\n  → {pick['label']}\n")
                history.extend(run_quick_pick(pick, data, index, history))
            else:
                print(f"  → Numero non valido. Scegli tra 1 e {len(QUICK_PICKS)}, oppure 0.\n")
            continue

        # ── Verifica nomi propri ──
        checks  = verify_names(user_input, index)
        nomi_ok = [c for c in checks if c["trovato"]]
        nomi_ko = [c for c in checks if not c["trovato"]]

        for c in nomi_ok:
            d = c["dati"]
            print(f"  ✓ {d['nome']} ({d['squadra']}, {d['ruolo']}, Q:{d['quotazione']}, FVM:{d['fvm']})")
        for c in nomi_ko:
            print(f"  ✗ '{c['cercato']}' non trovato nel listone")

        if nomi_ko and not nomi_ok:
            print("  → Nessun nome valido trovato. Correggi e riprova.\n")
            continue

        # ── Espandi query relazionali ──
        rel_note, rel_roles = expand_relational_query(user_input, index)
        if rel_note:
            print("  [relazione rilevata → compagni di ruolo iniettati]")

        # ── Rileva ruoli e costruisce contesto ──
        recent_text = user_input + " ".join(m["content"] for m in history[-4:])
        roles   = rel_roles if rel_roles else detect_roles(recent_text)
        context = build_context(roles, data)
        print(f"  [contesto: {' + '.join(ROLE_LABELS_SHORT[r] for r in roles)}]")

        # ── Chiamata al modello ──
        user_msg = user_input + rel_note
        history  = trim_history(history)
        messages = (
            [{"role": "system", "content": BASE_SYSTEM + "\n\n" + context}]
            + history
            + [{"role": "user", "content": user_msg}]
        )

        print("AI: ", end="", flush=True)
        reply = ollama_chat(messages)
        print(reply + "\n")

        history.append({"role": "user",      "content": user_input})
        history.append({"role": "assistant",  "content": reply})


if __name__ == "__main__":
    main()
