# Setup AnythingLLM — Guida Step-by-Step

---

## 1. Installazione

Scarica l'app desktop da: https://anythingllm.com/download

Disponibile per: macOS, Windows, Linux

---

## 2. Configurazione LLM (Ollama)

1. Assicurati che Ollama sia in esecuzione: `ollama list`
2. Apri AnythingLLM → **Settings** (icona ingranaggio)
3. Sezione **LLM Provider** → seleziona **Ollama**
4. Base URL: `http://localhost:11434`
5. Seleziona il modello (es. `qwen2.5:7b`)
6. Salva

---

## 3. Crea i due Workspace

### Workspace Mantra
1. Click **+ New Workspace**
2. Nome: `FC-MANTRA-2026`
3. Apri il workspace → **Settings** → **System Prompt**
4. Incolla il contenuto di `prompts/mantra/system_prompt_A_formazione.md`
5. Salva

### Workspace Classic
1. Click **+ New Workspace**
2. Nome: `FC-CLASSIC-2026`
3. System Prompt → incolla `prompts/classic/system_prompt_A_formazione.md`

> Cambia il system prompt manualmente prima di ogni sessione
> (Prompt A per formazione, Prompt B per report, Prompt C per scambi)

---

## 4. Carica i Documenti (Knowledge Base)

### Nel workspace FC-MANTRA-2026

Click **Upload Documents** e carica:

```
knowledge_base/regolamento/tabella_bonus_malus.md
knowledge_base/regolamento/ruoli_mantra_definizioni.md
knowledge_base/regolamento/schemi_mantra_11moduli.md
knowledge_base/regolamento/sostituzioni_mantra_logica.md
knowledge_base/listoni/listone_mantra_2026_27.csv
leghe/mantra/my_team/rosa.json
knowledge_base/schede_squadre/*.md  (quelle rilevanti)
```

### Nel workspace FC-CLASSIC-2026

```
knowledge_base/regolamento/tabella_bonus_malus.md
knowledge_base/regolamento/regolamento_classic.md
knowledge_base/listoni/listone_classic_2026_27.csv
leghe/classic/my_team/rosa.json
knowledge_base/schede_squadre/*.md  (quelle rilevanti)
```

---

## 5. Impostazioni Consigliate per AnythingLLM

In **Workspace Settings**:

| Parametro | Valore consigliato |
|---|---|
| Chat mode | Query (non Chat) per usare il RAG |
| Max Context | 4000 token (aumenta se il modello lo permette) |
| Temperature | 0.3 (risposte più deterministiche) |
| Similarity Threshold | 0.25 (recupera più documenti) |
| Max Chunks | 10 |

---

## 6. Aggiornamento Documenti (ogni settimana)

Quando aggiorni `rosa.json` o aggiungi schede squadre:
1. Apri il workspace
2. **Manage Documents** → rimuovi la versione vecchia
3. Carica la versione aggiornata

> AnythingLLM non aggiorna automaticamente i file: devi ricaricarli manualmente.

---

## 7. Come Cambiare System Prompt tra le Sessioni

Per passare dal Prompt A (formazione) al Prompt B (report):
1. Workspace Settings → System Prompt
2. Cancella il contenuto attuale
3. Incolla il nuovo prompt
4. Salva e avvia nuova conversazione

Crea una nuova chat per ogni sessione (evita che il contesto precedente influenzi le risposte).
