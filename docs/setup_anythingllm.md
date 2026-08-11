# Setup Locale — Guida Completa (Ollama + AnythingLLM)

Tutto gira in locale sul tuo Mac. Nessun dato viene inviato online.

---

## PASSO 1 — Installa Ollama (il motore LLM)

1. Vai su **https://ollama.com** → clicca **Download for Mac**
2. Apri il `.zip` scaricato → trascina `Ollama.app` nella cartella Applicazioni
3. Avvia Ollama dalla cartella Applicazioni
   - Comparirà un'icona nella barra menu in alto a destra (la lama)
   - Ollama gira in background, non ha finestra

4. Apri il **Terminale** e scarica il modello consigliato:
   ```bash
   ollama pull qwen2.5
   ```
   > Scarica ~4.5 GB. Ci vorrà qualche minuto.

5. Verifica che funzioni:
   ```bash
   ollama list
   ```
   Devi vedere `qwen2.5` nella lista.

> **Ollama deve essere avviato ogni volta che usi AnythingLLM.**  
> Se hai l'icona nella barra menu, è già attivo.

---

## PASSO 2 — Installa AnythingLLM (l'interfaccia)

1. Vai su **https://anythingllm.com/download**
2. Clicca **Download for macOS**
3. Apri il `.dmg` scaricato → trascina `AnythingLLM.app` nelle Applicazioni
4. Avvia AnythingLLM
5. Al primo avvio ti chiede di configurare un LLM:
   - Seleziona **Ollama**
   - Base URL: `http://localhost:11434`
   - Seleziona il modello: `qwen2.5`
   - Clicca **Save**

---

## PASSO 3 — Connetti Ollama in AnythingLLM

Se hai saltato la configurazione iniziale, puoi farlo anche dopo:

1. Clicca l'icona **ingranaggio** (Settings) in basso a sinistra
2. Vai su **LLM Preference**
3. Seleziona **Ollama**
4. Base URL: `http://localhost:11434`
5. Modello: scegli `qwen2.5` dal dropdown
6. Clicca **Save changes**

---

## PASSO 4 — Crea i due Workspace

### Workspace Mantra

1. Nella sidebar sinistra clicca **+ New Workspace**
2. Nome: `FC-MANTRA-2026`
3. Clicca sull'ingranaggio del workspace → **Settings**
4. Campo **System Prompt**: copia e incolla il contenuto di:
   ```
   prompts/mantra/system_prompt_A_formazione.md
   ```
5. **Chat Mode**: seleziona **Query** (non Chat — serve per usare i documenti)
6. Imposta i parametri:
   | Parametro | Valore |
   |---|---|
   | Temperature | 0.3 |
   | Similarity Threshold | 0.25 |
   | Max Chunks | 10 |
7. Salva

### Workspace Classic

1. Clicca **+ New Workspace**
2. Nome: `FC-CLASSIC-2026`
3. System Prompt → copia da `prompts/classic/system_prompt_A_formazione.md`
4. Stessi parametri del workspace Mantra

---

## PASSO 5 — Carica i Documenti

Questo è il passaggio che rende il modello "intelligente" sul tuo fantacalcio.

### Nel workspace FC-MANTRA-2026

1. Clicca l'icona **Upload Documents** (freccia in su) nel workspace
2. Carica questi file dalla cartella del progetto:

   ```
   knowledge_base/regolamento/tabella_bonus_malus.md
   knowledge_base/regolamento/ruoli_mantra_definizioni.md
   knowledge_base/regolamento/schemi_mantra_11moduli.md
   knowledge_base/regolamento/sostituzioni_mantra_logica.md
   knowledge_base/listoni/listone_mantra_2026_27.csv
   knowledge_base/schede_squadre/*.md   ← tutte e 20
   ```
   > Dopo l'asta aggiungi anche: `leghe/mantra/my_team/rosa.json`

3. Dopo il caricamento clicca **Save and Embed** — AnythingLLM indicizza i file

### Nel workspace FC-CLASSIC-2026

   ```
   knowledge_base/regolamento/tabella_bonus_malus.md
   knowledge_base/regolamento/regolamento_classic.md
   knowledge_base/listoni/listone_classic_2026_27.csv
   knowledge_base/schede_squadre/*.md   ← tutte e 20
   ```
   > Dopo l'asta aggiungi anche: `leghe/classic/my_team/rosa.json`

---

## PASSO 6 — Prima Chat di Prova

Nel workspace `FC-MANTRA-2026` prova a scrivere:

```
Quali attaccanti hanno la quotazione più alta nel listone Mantra?
```

Se risponde con dati reali dal CSV → tutto funziona correttamente.

Se risponde in modo generico senza usare i dati → verifica che i documenti siano stati indicizzati (Step 5) e che la Chat Mode sia **Query**.

---

## PASSO 7 — Usare i 4 Prompt (A/B/C/D)

Hai 4 system prompt per ogni lega. Cambiali prima di ogni sessione:

| Prompt | Quando usarlo |
|--------|--------------|
| **A** — Formazione | Ogni giornata: scegliere chi schierare e panchina |
| **B** — Report | Dopo la giornata: analizzare sostituzioni e punti |
| **C** — Scambi | Prima del mercato: valutare scambi e svincolati |
| **D** — Asta | Prima dell'asta: strategia, prezzi, obiettivi |

Per cambiare prompt:
1. Workspace Settings → System Prompt
2. Cancella il contenuto attuale
3. Incolla il nuovo prompt dal file corrispondente
4. Salva
5. **Apri una nuova chat** (importante: il contesto vecchio non deve influenzare)

---

## PASSO 8 — Aggiornamento Settimanale

Ogni settimana dopo la giornata:

```bash
cd ~/Progetti_Personale/Progetto_AI/Fantacalcio-ai

# 1. Aggiorna i voti
python3 scripts/parse_voti.py --giornata GN_02 --input /path/voti.csv

# 2. Aggiorna le statistiche rosa
python3 scripts/aggiorna_rosa.py --lega mantra --giornata GN_02

# 3. Salva su GitHub
git add . && git commit -m "GN_02: aggiornamento voti e rosa" && git push
```

Poi in AnythingLLM:
1. Workspace → Manage Documents
2. Rimuovi `rosa.json` vecchio
3. Carica `rosa.json` aggiornato
4. Clicca **Save and Embed**

> AnythingLLM **non aggiorna automaticamente** i file: devi ricaricarli manualmente dopo ogni modifica.

---

## Troubleshooting

| Problema | Soluzione |
|----------|-----------|
| AnythingLLM non trova Ollama | Verifica che Ollama sia avviato (icona nella barra menu) |
| Risposte lente | Normale per modelli 7B su Mac senza GPU dedicata. Prova `llama3.2:3b` per risposte più veloci |
| Il modello non usa i documenti | Controlla che Chat Mode sia **Query** e che i file siano stati indicizzati (verde = ok) |
| Risposte in inglese | Aggiungi `Rispondi sempre in italiano.` alla fine del system prompt |
| Errore "context length exceeded" | Riduci Max Chunks a 6 o usa un modello con context window più grande |
