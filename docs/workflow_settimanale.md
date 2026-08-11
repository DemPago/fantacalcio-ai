# Workflow Settimanale — Checklist 4 Step

---

## STEP 1 — Aggiornamento Post-Giornata (Lunedì/Martedì)

**Dopo la fine dell'ultima giornata:**

- [ ] Scarica il CSV voti da `fantacalcio.it/voti-fantacalcio-serie-a`
- [ ] Esegui lo script di parsing per la lega Mantra:
  ```bash
  python scripts/parse_voti.py --lega mantra --giornata N --input ~/Downloads/voti_gnN.csv
  ```
- [ ] Esegui lo script per la lega Classic:
  ```bash
  python scripts/parse_voti.py --lega classic --giornata N --input ~/Downloads/voti_gnN.csv
  ```
- [ ] Apri `leghe/mantra/weekly_logs/GN_N/voti_giornata.json` e compila manualmente:
  - `punteggio_finale`
  - `punteggio_avversario`
  - `risultato` (W / D / L)
- [ ] Fai lo stesso per `leghe/classic/weekly_logs/GN_N/voti_giornata.json`
- [ ] Aggiorna `riepilogo_stagione.json` di entrambe le leghe con i dati della giornata
- [ ] Aggiorna `stats_stagione` in `rosa.json` per i giocatori scesi in campo
- [ ] Controlla e aggiorna lo stato `infortunato / squalificato / diffidato` in `rosa.json`

---

## STEP 2 — Report Post-Giornata (Martedì)

**Apri AnythingLLM:**

Per la **lega Mantra**:
- Workspace: `FC-MANTRA-2026`
- Carica (se non già presente): `voti_giornata.json` + `formazione_schierata.json`
- System Prompt: `prompts/mantra/system_prompt_B_report.md`
- Query: *"Analizza la giornata N appena conclusa per la mia lega Mantra"*
- Salva il report generato in `leghe/mantra/weekly_logs/GN_N/report.md`

Per la **lega Classic**:
- Workspace: `FC-CLASSIC-2026`
- System Prompt: `prompts/classic/system_prompt_B_report.md`
- Query: *"Analizza la giornata N appena conclusa per la mia lega Classic"*
- Salva in `leghe/classic/weekly_logs/GN_N/report.md`

---

## STEP 3 — Aggiornamento Knowledge Base (Giovedì)

**Scarica e aggiorna:**

- [ ] Scarica le probabili formazioni aggiornate da `fantacalcio.it/probabili-formazioni-serie-a`
- [ ] Aggiorna i file rilevanti in `knowledge_base/schede_squadre/` (almeno le squadre dei tuoi giocatori)
- [ ] Controlla `fantacalcio.it/infortunati-serie-a` → aggiorna `stato` in `rosa.json`
- [ ] Controlla `fantacalcio.it/squalificati-e-diffidati-campionato-serie-a`
- [ ] Scarica le quotazioni aggiornate (se disponibili) e salva in `knowledge_base/listoni/quotazioni_aggiornate/`
- [ ] **Ricarica i file aggiornati su AnythingLLM** nei rispettivi workspace

---

## STEP 4 — Scelta Formazione (Venerdì/Sabato — entro la deadline)

**Apri AnythingLLM:**

Per la **lega Mantra**:
- Workspace: `FC-MANTRA-2026`
- Assicurati che `rosa.json` aggiornato sia caricato
- System Prompt: `prompts/mantra/system_prompt_A_formazione.md`
- Query: *"Suggerisci la formazione ottimale per la giornata N+1 della mia lega Mantra"*
- Verifica manualmente i ballottaggi segnalati (Twitter/Telegram/app ufficiale)
- Compila `leghe/mantra/weekly_logs/GN_N+1/formazione_schierata.json`
- Inserisci su Fantacalcio.it **entro la deadline**

Per la **lega Classic**:
- Workspace: `FC-CLASSIC-2026`
- System Prompt: `prompts/classic/system_prompt_A_formazione.md`
- Query: *"Suggerisci la formazione ottimale per la giornata N+1 della mia lega Classic"*
- Compila `leghe/classic/weekly_logs/GN_N+1/formazione_schierata.json`
- Inserisci su Fantacalcio.it **entro la deadline**

---

## STEP EXTRA — Valutazione Scambi (quando necessario)

- Workspace: `FC-MANTRA-2026` o `FC-CLASSIC-2026`
- System Prompt: `system_prompt_C_scambi.md` della lega corrispondente
- Query: *"Valuta lo scambio: cedo [NOME A] per [NOME B]"*

---

## Deadline Tipiche Fantacalcio.it

| Giorno | Orario | Evento |
|---|---|---|
| Venerdì | 12:00 | Apertura inserimento formazioni |
| Sabato | 12:45 | Deadline formazioni (anticipo sabato) |
| Domenica | 12:30 | Deadline formazioni (partite domenicali) |
| Lunedì | 20:30 | Deadline formazioni (posticipo lunedì) |

> Verifica sempre la deadline esatta per la tua giornata su Fantacalcio.it.
> In caso di dubbio, inserisci la formazione **entro venerdì sera**.
