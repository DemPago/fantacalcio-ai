# Logica Sostituzioni Mantra — Guida Completa

Fonte: https://www.fantacalcio.it/regolamenti/sistema-mantra

---

## Principio Base

Quando uno o più titolari risultano **assenti o senza voto**, il sistema sostituisce
automaticamente con calciatori dalla panchina, rispettando l'ordine schierato dal fantallenatore.

**REGOLA CRITICA**: la panchina si schiera in **ordine di preferenza assoluta**,
non per ruolo. Il sistema trova lo schema possibile. NON usare l'ordine P→D→C→A.

---

## Sostituzione del Portiere

Il portiere è **sempre il primo** ad essere sostituito se il titolare è assente.
L'ingresso di un portiere di riserva **riduce di 1** il numero di sostituzioni disponibili
(nelle leghe con limite massimo di sostituzioni).

---

## 3 Modalità di Sostituzioni (scelta di lega)

### BASIC (default)

Gerarchia di ricerca:

**1. Soluzione OTTIMALE**
Stesso schema schierato dal fantallenatore, nessun calciatore fuori posizione, nessun malus.

**2. Soluzione EFFICIENTE** (se non trovata l'ottimale)
Cambio modulo automatico verso uno degli altri 10 schemi disponibili, senza malus.
(Se più schemi alternativi sono validi con la stessa combinazione di panchinari, la scelta è indifferente — i giocatori conteggiati sarebbero gli stessi.)

**3. Soluzione ADATTATA** (se non trovata l'efficiente)
Uno o più calciatori fuori posizione con malus -1 ciascuno.
Nessuna priorità del modulo base rispetto agli altri in questa fase.
Priorità tra soluzioni con stesso numero di malus: comanda l'ordine panchina.

Se neanche la soluzione adattata è possibile → si gioca **in inferiorità numerica** (10, 9...).

### EASY

Elimina completamente il cambio modulo. La squadra nasce e muore con il modulo scelto.

**1. Soluzione OTTIMALE** — stesso modulo, nessun malus
**2. Soluzione ADATTATA** — stesso modulo, fuori posizione con malus

### MASTER

La modalità più "spinta". Cade la priorità del modulo base.
Sin dall'inizio tutto si fonda sull'ordine panchina.

**1. Soluzione OTTIMALE/EFFICIENTE** — qualsiasi schema, nessun malus
(Il sistema prova sempre a far entrare prima i calciatori schierati in cima alla panchina)
**2. Soluzione ADATTATA** — qualsiasi schema, fuori posizione con malus

---

## Algoritmo di Selezione dei Panchinari (valido per tutti i modi)

Le sostituzioni avvengono **in blocco**, non una per volta.

### Esempio con 5 panchinari (A-B-C-D-E) e 3 da inserire:

L'ordine di priorità delle combinazioni è:
```
ABC → ABD → ABE → ACD → ACE → ADE → BCD → BCE → BDE → CDE
```

Il sistema scorre nell'ordine finché trova una combinazione che permette di ricostruire
uno schema valido (ottimale → efficiente → adattato).

**Conseguenza pratica**: mettere in panchina prima i calciatori più "flessibili" (multiruolo)
aumenta le chance di trovare soluzioni ottimali.

---

## Nota sul Malus Fuori Posizione in Sostituzione

Il sistema alloca i calciatori in modo random tra quelli dello stesso ruolo.
Il malus -1 viene assegnato a **uno** dei calciatori coinvolti, non necessariamente
al più recente entrato. La sostanza non cambia: 1 malus = 1 malus.

---

## Schieramento Fuori Posizione (scelta consapevole)

Si può schierare un calciatore fuori posizione in formazione (con malus -1) SOLO per emergenze reali.
Non è una strategia: alla prima sostituzione il sistema destruttura lo schema.

**Inibiti in fase di schieramento** (non sostituzioni):
- B/Dd/Ds non possono coprire Dc
- Dd non può coprire Ds (e viceversa)
- E non può coprire M (solo slot M/C)
- M non può coprire E (solo slot E/W)
- W non può coprire T (solo slot T/A)
- **4-1-4-1**: W e T non sono intercambiabili nemmeno con malus

---

## Checklist Prima di Schierare la Panchina

- [ ] Ho messo il portiere di riserva per primo (se voglio che entri in caso di SV del titolare)
- [ ] Ho ordinato i restanti per preferenza, non per ruolo
- [ ] Ho considerato quali calciatori sono multiruolo e li ho posizionati strategicamente
- [ ] Se uso MASTER, so che il sistema ignora il mio modulo e ottimizza sulla panchina
- [ ] Ho verificato che non ci siano infortunati/squalificati nascosti in panchina
