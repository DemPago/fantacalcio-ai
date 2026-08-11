#!/usr/bin/env python3
"""
aggiorna_rosa.py — Aggiornamento stats_stagione in rosa.json

Legge voti_giornata.json di una giornata e aggiorna le statistiche
cumulative di ogni giocatore in rosa.json.

Uso:
    python aggiorna_rosa.py --lega mantra --giornata 1
    python aggiorna_rosa.py --lega classic --giornata 1
    python aggiorna_rosa.py --lega mantra --giornata 1 --dry-run
"""

import json
import sys
from pathlib import Path
from copy import deepcopy

try:
    import typer
    from rich.console import Console
    from rich.table import Table
    from rich import box
except ImportError:
    print("Installa le dipendenze: pip install -r requirements.txt")
    sys.exit(1)

app = typer.Typer()
console = Console()

BASE_DIR = Path(__file__).parent.parent


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def calcola_fantamedia(rosa_player: dict) -> float | None:
    """Ricalcola la fantamedia da stats_stagione."""
    stats = rosa_player.get("stats_stagione", {})
    presenze = stats.get("presenze", 0)
    if presenze == 0:
        return None
    # Fantamedia = somma fantavoti / presenze (presenze = partite con voto)
    # Viene ricalcolata in modo incrementale: qui la aggiorniamo solo se
    # abbiamo il totale punteggio. Per semplicità la lasciamo a None
    # e la calcoliamo dal riepilogo_stagione se disponibile.
    return None


def aggiorna_stats(player: dict, voto_entry: dict, bonus_attivi: dict) -> dict:
    """
    Aggiorna le stats_stagione di un giocatore con i dati di una giornata.
    Restituisce il player aggiornato.
    """
    stats = player.setdefault("stats_stagione", {})
    ha_giocato = voto_entry.get("ha_giocato", False)
    sv = voto_entry.get("sv", False)

    if ha_giocato and not sv:
        stats["presenze"] = stats.get("presenze", 0) + 1

    if sv:
        stats["sv_count"] = stats.get("sv_count", 0) + 1

    bonus = voto_entry.get("bonus", {})
    malus = voto_entry.get("malus", {})

    stats["gol_segnati"]    = stats.get("gol_segnati", 0)    + bonus.get("gol_segnati", 0)
    stats["assist"]         = stats.get("assist", 0)          + bonus.get("assist", 0)
    stats["gol_subiti"]     = stats.get("gol_subiti", 0)     + abs(malus.get("gol_subiti", 0))
    stats["rigori_parati"]  = stats.get("rigori_parati", 0)  + bonus.get("rigori_parati", 0)
    stats["rigori_sbagliati"] = stats.get("rigori_sbagliati", 0) + (
        1 if malus.get("rigori_sbagliati", 0) < 0 else 0
    )
    stats["autogol"]        = stats.get("autogol", 0) + (
        1 if malus.get("autogol", 0) < 0 else 0
    )
    stats["ammonizioni"]    = stats.get("ammonizioni", 0) + (
        1 if malus.get("ammonizione", 0) < 0 else 0
    )
    stats["espulsioni"]     = stats.get("espulsioni", 0) + (
        1 if malus.get("espulsione", 0) < 0 else 0
    )

    # Aggiorna media voto (media mobile)
    voto_base = voto_entry.get("voto_base")
    if voto_base and not sv:
        presenze = stats.get("presenze", 1)
        media_attuale = stats.get("media_voto") or 0.0
        # Media mobile: (media_old * (n-1) + nuovo_voto) / n
        stats["media_voto"] = round(
            (media_attuale * (presenze - 1) + voto_base) / presenze, 3
        )

    # Aggiorna fantamedia (media mobile)
    fantavoto = voto_entry.get("fantavoto")
    if fantavoto and not sv:
        presenze = stats.get("presenze", 1)
        fm_attuale = stats.get("fantamedia") or 0.0
        stats["fantamedia"] = round(
            (fm_attuale * (presenze - 1) + fantavoto) / presenze, 3
        )

    return player


def aggiorna_riepilogo(riepilogo: dict, voti_data: dict) -> dict:
    """Aggiunge la giornata al riepilogo stagione."""
    giornata = voti_data.get("giornata")
    punteggio = voti_data.get("punteggio_finale", 0)
    avversario = voti_data.get("avversario", "?")
    risultato = voti_data.get("risultato")
    punteggio_avv = voti_data.get("punteggio_avversario", 0)

    riepilogo["giornate_giocate"] = riepilogo.get("giornate_giocate", 0) + 1

    # Aggiorna punti totali e media
    tot = riepilogo.get("punti_totali", 0.0) + punteggio
    gn = riepilogo["giornate_giocate"]
    riepilogo["punti_totali"] = round(tot, 2)
    riepilogo["punti_medi"] = round(tot / gn, 2)

    # Record
    rec = riepilogo.setdefault("record", {})
    if rec.get("punteggio_massimo") is None or punteggio > rec["punteggio_massimo"]:
        rec["punteggio_massimo"] = punteggio
        rec["punteggio_massimo_giornata"] = giornata
    if rec.get("punteggio_minimo") is None or punteggio < rec["punteggio_minimo"]:
        rec["punteggio_minimo"] = punteggio
        rec["punteggio_minimo_giornata"] = giornata

    # Bilancio
    bilancio = riepilogo.setdefault("bilancio", {"vittorie": 0, "pareggi": 0, "sconfitte": 0})
    if risultato == "W":
        bilancio["vittorie"] += 1
    elif risultato == "D":
        bilancio["pareggi"] += 1
    elif risultato == "L":
        bilancio["sconfitte"] += 1

    # Log giornate (evita duplicati)
    log = riepilogo.setdefault("log_giornate", [])
    if not any(g.get("giornata") == giornata for g in log):
        log.append({
            "giornata": giornata,
            "punteggio": punteggio,
            "avversario": avversario,
            "punteggio_avversario": punteggio_avv,
            "risultato": risultato,
        })
        log.sort(key=lambda x: x["giornata"])

    return riepilogo


@app.command()
def aggiorna(
    lega: str = typer.Option(..., help="Lega: mantra o classic"),
    giornata: int = typer.Option(..., help="Numero giornata da processare"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Mostra le modifiche senza salvare"),
):
    """
    Legge voti_giornata.json della giornata specificata e aggiorna:
    - stats_stagione in rosa.json per ogni giocatore
    - riepilogo_stagione.json con punteggio e bilancio
    """
    if lega not in ("mantra", "classic"):
        console.print("[red]--lega deve essere 'mantra' o 'classic'[/red]")
        raise typer.Exit(1)

    lega_dir = BASE_DIR / "leghe" / lega
    rosa_path = lega_dir / "my_team" / "rosa.json"
    voti_path = lega_dir / "weekly_logs" / f"GN_{giornata:02d}" / "voti_giornata.json"
    riepilogo_path = lega_dir / "weekly_logs" / "riepilogo_stagione.json"
    config_path = lega_dir / "config.json"

    # Verifica file
    for p in [rosa_path, voti_path, config_path]:
        if not p.exists():
            console.print(f"[red]File non trovato: {p}[/red]")
            raise typer.Exit(1)

    rosa_data = load_json(rosa_path)
    voti_data = load_json(voti_path)
    config = load_json(config_path)
    bonus_attivi = config["lega"].get("bonus_attivi", {})

    riepilogo_data = load_json(riepilogo_path) if riepilogo_path.exists() else {
        "stagione": config["lega"].get("stagione", "2026-27"),
        "modalita": lega.capitalize(),
        "giornate_giocate": 0,
        "punti_totali": 0.0,
        "punti_medi": 0.0,
        "classifica_posizione": None,
        "record": {},
        "bilancio": {"vittorie": 0, "pareggi": 0, "sconfitte": 0},
        "log_giornate": [],
    }

    # Verifica se giornata già processata
    log = riepilogo_data.get("log_giornate", [])
    if any(g.get("giornata") == giornata for g in log):
        console.print(f"[yellow]Attenzione: giornata {giornata} già presente nel riepilogo.[/yellow]")
        if not typer.confirm("Vuoi rielaborarla comunque?"):
            raise typer.Exit(0)

    # Costruisci indice voti per ID
    voti_by_id: dict[str, dict] = {}
    for v in voti_data.get("voti", []):
        voti_by_id[v["id"]] = v

    # Aggiorna rosa
    rosa_aggiornata = deepcopy(rosa_data)
    modifiche = []

    for player in rosa_aggiornata.get("rosa", []):
        pid = player["id"]
        if pid not in voti_by_id:
            continue

        stats_prima = deepcopy(player.get("stats_stagione", {}))
        player = aggiorna_stats(player, voti_by_id[pid], bonus_attivi)

        modifiche.append({
            "nome": player["nome"],
            "ha_giocato": voti_by_id[pid].get("ha_giocato"),
            "fantavoto": voti_by_id[pid].get("fantavoto"),
            "sv": voti_by_id[pid].get("sv"),
            "nuova_fm": player["stats_stagione"].get("fantamedia"),
            "nuova_media_voto": player["stats_stagione"].get("media_voto"),
        })

        # Aggiorna il player nell'array originale
        for i, p in enumerate(rosa_aggiornata["rosa"]):
            if p["id"] == pid:
                rosa_aggiornata["rosa"][i] = player
                break

    # Aggiorna riepilogo
    riepilogo_aggiornato = aggiorna_riepilogo(deepcopy(riepilogo_data), voti_data)

    # Tabella riepilogativa
    table = Table(
        title=f"Aggiornamento GN {giornata} — {lega.upper()}",
        box=box.ROUNDED,
    )
    table.add_column("Giocatore", style="cyan")
    table.add_column("FantaVoto", justify="right")
    table.add_column("FM stagione", justify="right", style="green")
    table.add_column("Media voto", justify="right")
    table.add_column("SV", justify="center")

    for m in sorted(modifiche, key=lambda x: x["fantavoto"] or 0, reverse=True):
        table.add_row(
            m["nome"],
            str(m["fantavoto"]) if not m["sv"] else "—",
            str(m["nuova_fm"]) if m["nuova_fm"] else "—",
            str(m["nuova_media_voto"]) if m["nuova_media_voto"] else "—",
            "S.V." if m["sv"] else "",
        )

    console.print(table)

    # Riepilogo stagione
    console.print(
        f"\n[bold]Stagione aggiornata[/bold]: "
        f"GN giocate: {riepilogo_aggiornato['giornate_giocate']} | "
        f"Punti totali: {riepilogo_aggiornato['punti_totali']} | "
        f"Media: {riepilogo_aggiornato['punti_medi']} | "
        f"W/D/L: {riepilogo_aggiornato['bilancio']['vittorie']}/"
        f"{riepilogo_aggiornato['bilancio']['pareggi']}/"
        f"{riepilogo_aggiornato['bilancio']['sconfitte']}"
    )

    if dry_run:
        console.print("\n[yellow]DRY-RUN: nessun file modificato.[/yellow]")
        return

    save_json(rosa_path, rosa_aggiornata)
    save_json(riepilogo_path, riepilogo_aggiornato)

    console.print(f"\n[green]Salvato: {rosa_path}[/green]")
    console.print(f"[green]Salvato: {riepilogo_path}[/green]")


if __name__ == "__main__":
    app()
