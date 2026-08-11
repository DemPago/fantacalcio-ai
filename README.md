# Fantacalcio AI — Gestione Rosa con LLM Locale

Progetto open-source per gestire e analizzare **una o più rose del Fantacalcio** durante l'intera stagione di Serie A, utilizzando esclusivamente strumenti **locali e gratuiti**.

Supporta sia la modalità **Mantra** che la modalità **Classic** in parallelo.

---

## Stack Tecnologico

| Componente | Strumento | Note |
|---|---|---|
| LLM locale | [Ollama](https://ollama.ai) | Llama 3.2, Qwen 2.5, o equivalenti |
| RAG + Interfaccia | [AnythingLLM](https://anythingllm.com) | Carica i file della `knowledge_base/` |
| Dati / Schemi | JSON + CSV | Standard, editabili a mano o via script |
| Script utility | Python 3.10+ | Opzionale, per automazione parsing CSV |
| Piattaforma Fanta | [Fantacalcio.it](https://leghe.fantacalcio.it) | Fonte ufficiale voti, listoni, quotazioni |

> Tutto gira in locale. Nessun dato viene inviato a server esterni.

---

## Prerequisiti

### 1. Ollama

Scarica e installa da: https://ollama.ai/download

```bash
# Installa un modello (scegli uno)
ollama pull llama3.2
ollama pull qwen2.5
ollama pull mistral

# Verifica che il servizio sia attivo
ollama list
```

Modelli consigliati per questo progetto:

| Modello | RAM richiesta | Qualità ragionamento |
|---|---|---|
| `llama3.2:3b` | 4 GB | Buona per query semplici |
| `llama3.2:8b` | 8 GB | Ottima per analisi e report |
| `qwen2.5:7b` | 8 GB | Eccellente per dati strutturati |
| `qwen2.5:14b` | 16 GB | Top, consigliato se possibile |
| `mistral:7b` | 8 GB | Ottimo bilanciamento velocità/qualità |

### 2. AnythingLLM

Scarica il desktop app da: https://anythingllm.com/download

Configurazione iniziale:
1. Apri AnythingLLM → Settings → LLM Provider → seleziona **Ollama**
2. Inserisci l'URL: `http://localhost:11434`
3. Seleziona il modello installato
4. Crea due workspace: `FC-MANTRA-2026` e `FC-CLASSIC-2026`

### 3. Python (opzionale, per gli script)

```bash
python --version   # richiede 3.10+

cd scripts/
pip install -r ../requirements.txt
```

---

## Struttura del Progetto

```
fantacalcio-ai/
│
├── knowledge_base/              # Documenti per il RAG (carica su AnythingLLM)
│   ├── regolamento/             # Regolamenti ufficiali e tabelle bonus/malus
│   ├── listoni/                 # Listone CSV da Fantacalcio.it (Mantra + Classic)
│   │   └── quotazioni_aggiornate/
│   ├── schede_squadre/          # Una scheda .md per squadra (modulo, titolari, note)
│   └── storici/                 # Fantamedie stagioni precedenti
│
├── leghe/
│   ├── mantra/                  # Lega Mantra
│   │   ├── config.json          # Opzioni lega (budget, bonus attivi, sistema sostituzioni)
│   │   ├── my_team/
│   │   │   ├── rosa.json        # Rosa con ruoli Mantra
│   │   │   ├── crediti.json     # Budget speso/residuo
│   │   │   └── trasferimenti/
│   │   │       └── mercato_log.json
│   │   └── weekly_logs/
│   │       ├── GN_01/
│   │       │   ├── formazione_schierata.json
│   │       │   ├── voti_giornata.json
│   │       │   └── report.md
│   │       └── riepilogo_stagione.json
│   │
│   └── classic/                 # Lega Classic
│       ├── config.json
│       ├── my_team/
│       │   ├── rosa.json        # Rosa con ruoli Classic (P/D/C/A)
│       │   ├── crediti.json
│       │   └── trasferimenti/
│       │       └── mercato_log.json
│       └── weekly_logs/
│           ├── GN_01/
│           │   ├── formazione_schierata.json
│           │   ├── voti_giornata.json
│           │   └── report.md
│           └── riepilogo_stagione.json
│
├── prompts/
│   ├── mantra/
│   │   ├── system_prompt_A_formazione.md
│   │   ├── system_prompt_B_report.md
│   │   └── system_prompt_C_scambi.md
│   └── classic/
│       ├── system_prompt_A_formazione.md
│       ├── system_prompt_B_report.md
│       └── system_prompt_C_scambi.md
│
├── scripts/
│   ├── parse_voti.py            # Parsing CSV voti da Fantacalcio.it
│   ├── aggiorna_rosa.py         # Aggiornamento stats stagionali
│   └── genera_report.py        # Genera report.md da voti_giornata.json
│
├── docs/
│   ├── workflow_settimanale.md  # Checklist 4-step settimanale
│   ├── setup_anythingllm.md     # Guida configurazione AnythingLLM step-by-step
│   └── faq.md                   # Domande frequenti
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Quickstart — Prima Configurazione

### Step 1 — Clona il repo e installa dipendenze

```bash
git clone https://github.com/TUO_USERNAME/fantacalcio-ai.git
cd fantacalcio-ai
pip install -r requirements.txt
```

### Step 2 — Configura la tua lega

Edita i file di configurazione delle leghe a cui partecipi:

```bash
# Lega Mantra
nano leghe/mantra/config.json

# Lega Classic
nano leghe/classic/config.json
```

Imposta `nome`, `budget_iniziale` e attiva i bonus corretti per il tuo regolamento di lega.

### Step 3 — Inserisci la tua rosa

Dopo l'asta, popola il file rosa della tua lega:

```bash
nano leghe/mantra/my_team/rosa.json
nano leghe/classic/my_team/rosa.json
```

Usa i template presenti come base (vedi `docs/`).

### Step 4 — Carica i documenti su AnythingLLM

Nel workspace `FC-MANTRA-2026` carica:
- `knowledge_base/regolamento/*.md`
- `knowledge_base/listoni/listone_mantra_2026_27.csv`
- `leghe/mantra/my_team/rosa.json`
- Le schede squadre rilevanti

Nel workspace `FC-CLASSIC-2026` carica:
- `knowledge_base/regolamento/tabella_bonus_malus.md`
- `knowledge_base/regolamento/regolamento_classic.md`
- `knowledge_base/listoni/listone_classic_2026_27.csv`
- `leghe/classic/my_team/rosa.json`

### Step 5 — Imposta i System Prompt

In ogni workspace AnythingLLM:
`Settings → System Prompt` → incolla il contenuto del file prompt corrispondente.

---

## Workflow Settimanale

Vedi [`docs/workflow_settimanale.md`](docs/workflow_settimanale.md) per la checklist completa in 4 step.

In sintesi:

```
Lunedì/Martedì  → Aggiorna voti_giornata.json + lancia report (Prompt B)
Giovedì         → Aggiorna probabili formazioni + stato infortuni in rosa.json
Venerdì/Sabato  → Chiedi consiglio formazione (Prompt A) → inserisci su Fantacalcio.it
Dopo mercato    → Aggiorna mercato_log.json e rosa.json
```

---

## Dove trovare i dati da scaricare

| Dato | URL | Formato | Frequenza |
|---|---|---|---|
| Voti ufficiali | fantacalcio.it/voti-fantacalcio-serie-a | Web/CSV | Post-giornata |
| Listone calciatori | fantacalcio.it/quotazioni-fantacalcio | CSV scaricabile | Inizio stagione |
| Quotazioni aggiornate | fantacalcio.it/quotazioni-fantacalcio | CSV | Settimanale |
| Probabili formazioni | fantacalcio.it/probabili-formazioni-serie-a | Web | Giovedì-Sabato |
| Infortunati | fantacalcio.it/infortunati-serie-a | Web | Continuo |
| Squalificati/Diffidati | fantacalcio.it/squalificati-e-diffidati-campionato-serie-a | Web | Post-giornata |
| Rigoristi | fantacalcio.it/rigoristi-serie-a | Web | Mensile |
| Statistiche | fantacalcio.it/statistiche-serie-a | Web | Post-giornata |
| Griglia portieri | fantacalcio.it/griglia-portieri | Web | Settimanale |
| Analisi assist | fantacalcio.it/analisi-assist | Web | Settimanale |

---

## Limitazioni Note

- I modelli LLM locali piccoli (3b) possono fare errori su calcoli numerici precisi. Verifica sempre i punteggi manualmente.
- AnythingLLM con documenti CSV molto grandi (listone intero) può avere retrieval impreciso. Considera di filtrare il CSV alla tua rosa prima di caricarlo.
- I ruoli Mantra sono assegnati a fine luglio e non cambiano durante la stagione. Se un giocatore cambia ruolo di fatto ma non ufficialmente, annotalo nelle `note` del giocatore in `rosa.json`.

---

## Contributi

Pull request benvenute. Se trovi errori nel regolamento o vuoi aggiungere nuovi prompt, apri una issue.

---

## Licenza

MIT — uso libero, nessuna responsabilità per decisioni di formazione sbagliate.
