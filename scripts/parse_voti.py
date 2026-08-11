#!/usr/bin/env python3
"""
parse_voti.py — Parsing CSV voti da Fantacalcio.it

Uso:
    python parse_voti.py --lega mantra --giornata 1 --input voti_gn1.csv
    python parse_voti.py --lega classic --giornata 1 --input voti_gn1.csv

Il CSV di Fantacalcio.it ha tipicamente le colonne:
    Nome, Squadra, Voto, Gf, Gs, Rp, Rs, Ass, Amm, Esp, Au
"""

import json
import csv
import sys
from pathlib import Path
from datetime import date

try:
    import typer
    from rich.console import Console
    from rich.table import Table
except ImportError:
    print("Installa le dipendenze: pip install -r requirements.txt")
    sys.exit(1)

app = typer.Typer()
console = Console()

BASE_DIR = Path(__file__).parent.parent


def calcola_fantavoto(row: dict, bonus_attivi: dict) -> float:
    """Calcola il fantavoto da una riga del CSV voti."""
    try:
        voto = float(row.get("Voto", 0) or 0)
        if voto == 0:
            return 0.0

        gf  = int(row.get("Gf", 0) or 0)
        gs  = int(row.get("Gs", 0) or 0)
        rp  = int(row.get("Rp", 0) or 0)
        rs  = int(row.get("Rs", 0) or 0)
        ass = int(row.get("Ass", 0) or 0)
        amm = int(row.get("Amm", 0) or 0)
        esp = int(row.get("Esp", 0) or 0)
        au  = int(row.get("Au", 0) or 0)

        bonus = gf * 3
        bonus += rp * 3
        if bonus_attivi.get("assist"):
            bonus += ass * 1

        malus = 0.0
        malus += gs * -1  # gol subiti portiere (da gestire per ruolo)
        malus += rs * -3
        malus += amm * -0.5
        malus += esp * -1
        malus += au * -2

        return round(voto + bonus + malus, 2)

    except (ValueError, TypeError):
        return 0.0


@app.command()
def parse(
    lega: str = typer.Option(..., help="Lega: mantra o classic"),
    giornata: int = typer.Option(..., help="Numero giornata"),
    input_csv: Path = typer.Option(..., "--input", help="Percorso del CSV voti scaricato da Fantacalcio.it"),
):
    """
    Legge il CSV voti di Fantacalcio.it e genera voti_giornata.json
    nella cartella weekly_logs/GN_XX/ della lega selezionata.
    """
    if lega not in ("mantra", "classic"):
        console.print("[red]--lega deve essere 'mantra' o 'classic'[/red]")
        raise typer.Exit(1)

    # Carica configurazione lega
    config_path = BASE_DIR / "leghe" / lega / "config.json"
    if not config_path.exists():
        console.print(f"[red]config.json non trovato in {config_path}[/red]")
        raise typer.Exit(1)

    with open(config_path) as f:
        config = json.load(f)
    bonus_attivi = config["lega"].get("bonus_attivi", {})

    # Carica rosa per filtrare solo i giocatori della propria squadra
    rosa_path = BASE_DIR / "leghe" / lega / "my_team" / "rosa.json"
    rosa_ids = {}
    if rosa_path.exists():
        with open(rosa_path) as f:
            rosa_data = json.load(f)
        for p in rosa_data.get("rosa", []):
            rosa_ids[p["nome"].lower()] = p["id"]

    # Leggi CSV
    if not input_csv.exists():
        console.print(f"[red]File CSV non trovato: {input_csv}[/red]")
        raise typer.Exit(1)

    voti = []
    with open(input_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            nome = row.get("Nome", "").strip()
            if not nome:
                continue

            player_id = rosa_ids.get(nome.lower(), f"unknown_{nome.lower().replace(' ', '_')}")
            voto_base = float(row.get("Voto", 0) or 0)
            sv = voto_base == 0

            fantavoto = calcola_fantavoto(row, bonus_attivi) if not sv else 0.0

            voti.append({
                "id": player_id,
                "nome": nome,
                "ha_giocato": not sv,
                "voto_base": voto_base if not sv else None,
                "bonus": {
                    "porta_inviolata": 0,
                    "gol_segnati": int(row.get("Gf", 0) or 0),
                    "assist": int(row.get("Ass", 0) or 0),
                    "rigori_parati": int(row.get("Rp", 0) or 0),
                },
                "malus": {
                    "gol_subiti": int(row.get("Gs", 0) or 0),
                    "ammonizione": -0.5 * int(row.get("Amm", 0) or 0),
                    "espulsione": -1.0 * int(row.get("Esp", 0) or 0),
                    "rigori_sbagliati": -3.0 * int(row.get("Rs", 0) or 0),
                    "autogol": -2.0 * int(row.get("Au", 0) or 0),
                },
                "fantavoto": fantavoto,
                "sv": sv,
                "sostituito_al_minuto": None,
                "entrato_dalla_panchina": False,
                "note": "",
            })

    # Crea directory output
    output_dir = BASE_DIR / "leghe" / lega / "weekly_logs" / f"GN_{giornata:02d}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "voti_giornata.json"

    output = {
        "giornata": giornata,
        "modalita": lega.capitalize(),
        "data": str(date.today()),
        "punteggio_finale": 0,
        "punteggio_avversario": 0,
        "risultato": None,
        "voti": voti,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Output a schermo
    table = Table(title=f"Voti Giornata {giornata} — {lega.upper()}")
    table.add_column("Nome", style="cyan")
    table.add_column("Voto Base", justify="right")
    table.add_column("FantaVoto", justify="right", style="green")
    table.add_column("SV", justify="center")

    for v in sorted(voti, key=lambda x: x["fantavoto"], reverse=True):
        table.add_row(
            v["nome"],
            str(v["voto_base"] or "S.V."),
            str(v["fantavoto"]) if not v["sv"] else "—",
            "✓" if v["sv"] else "",
        )

    console.print(table)
    console.print(f"\n[green]Salvato in: {output_path}[/green]")
    console.print("[yellow]Ricorda di aggiornare manualmente: punteggio_finale, punteggio_avversario, risultato[/yellow]")


if __name__ == "__main__":
    app()
