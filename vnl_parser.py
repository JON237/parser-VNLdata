"""Parser für VNL‑Screenshots.

Dieses Modul extrahiert Spielstatistiken aus Screenshot‑Anzeigen der Volleyball
Nations League (VNL). Jedes Spiel besteht aus 14 Screenshots – sieben für Team A
und sieben für Team B. Die Reihenfolge bzw. Struktur der Screenshots wird für
jedes Team wie folgt erwartet:

    scoring.png
    attack.png
    block.png
    serve.png
    reception.png
    dig.png
    set.png

Für jedes Spiel wird eine einzelne Zeile mit den im Projekt geforderten
Spalten erzeugt:

    attack_diff
    block_diff
    serve_diff
    opp_error_diff
    total_points_diff
    dig_diff
    reception_diff
    set_diff
    top_scorer_1_diff
    top_scorer_2_diff
    label

`label` ist `1`, wenn Team A gewinnt, und `0`, wenn Team B gewinnt.

Das Skript verwendet `pytesseract` für die optische Zeichenerkennung. Die
Heuristiken sind auf die Screenshots der VNL‑Webseite zugeschnitten. Wenn die
OCR einen Wert nicht erkennt, wird ein `ValueError` ausgelöst, sodass keine
fehlenden Daten in die resultierende CSV-Datei gelangen.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import cv2  # type: ignore
import pandas as pd  # type: ignore
import pytesseract  # type: ignore

# ---------------------------------------------------------------------------
# Datenstrukturen
# ---------------------------------------------------------------------------

# Reihenfolge der erwarteten Screenshots pro Team
TEAM_SCREENS = [
    "scoring",
    "attack",
    "block",
    "serve",
    "reception",
    "dig",
    "set",
]


@dataclass
class TeamStats:
    """Speichert aggregierte Statistiken für ein Team."""

    attack: int
    block: int
    serve: int
    opp_error: int
    total_points: int
    dig: int
    reception: int
    set: int
    top_scorer_1: int
    top_scorer_2: int


# ---------------------------------------------------------------------------
# OCR-Hilfsfunktionen
# ---------------------------------------------------------------------------

_number_re = re.compile(r"\d+")


def _ocr_lines(image_path: Path) -> List[List[str]]:
    """Führt OCR auf einem Bild aus und liefert eine Liste tokenisierter Zeilen.

    Jede Zeile wird an Leerzeichen getrennt; leere Zeilen und Tokens werden entfernt.
    """

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Bild {image_path} konnte nicht gelesen werden")
    text = pytesseract.image_to_string(img)
    lines: List[List[str]] = []
    for raw in text.splitlines():
        tokens = [t for t in raw.strip().split() if t]
        if tokens:
            lines.append(tokens)  # nur nicht-leere Zeilen übernehmen
    return lines


def _extract_numbers(tokens: Iterable[str]) -> List[int]:
    """Liefert alle Ganzzahlen, die in `tokens` gefunden werden."""

    numbers: List[int] = []
    for tok in tokens:
        m = _number_re.search(tok)
        if m:
            numbers.append(int(m.group()))  # erkannte Zahl speichern
    return numbers


# ---------------------------------------------------------------------------
# Parser für einzelne Statistiken
# ---------------------------------------------------------------------------


def _parse_scoring(image: Path) -> Dict[str, int]:
    """Parst den *scoring*-Screenshot eines Teams.

    Der Screenshot enthält pro Spieler eine Zeile mit den Spalten
    (Total Attempts, Attack Points, Block Points, Serve Points, Opp Errors).
    Wir summieren die Spalten über alle Spieler, berechnen die Gesamtpunkte und
    ermitteln die Punkte der zwei besten Scorer.
    """

    totals = {
        "attack": 0,
        "block": 0,
        "serve": 0,
        "opp_error": 0,
        "top_scorers": [],  # type: ignore[list-item]
    }
    for tokens in _ocr_lines(image):
        numbers = _extract_numbers(tokens)
        # Mindestens erwartet: Total, Attack, Block, Serve, Opp error
        if len(numbers) >= 5:
            attack, block, serve, opp_error = numbers[1:5]
            totals["attack"] += attack
            totals["block"] += block
            totals["serve"] += serve
            totals["opp_error"] += opp_error
            # Punkte des Spielers als Summe aller Aktionen speichern
            totals["top_scorers"].append(attack + block + serve + opp_error)
    top = sorted(totals["top_scorers"], reverse=True)
    top1 = top[0] if top else 0
    top2 = top[1] if len(top) > 1 else 0
    total_points = (
        totals["attack"] + totals["block"] + totals["serve"] + totals["opp_error"]
    )
    return {
        "attack": totals["attack"],
        "block": totals["block"],
        "serve": totals["serve"],
        "opp_error": totals["opp_error"],
        "total_points": total_points,
        "top_scorer_1": top1,
        "top_scorer_2": top2,
    }


def _parse_simple_total(image: Path) -> int:
    """Parst Screenshots, in denen pro Spieler eine Zahl genügt.

    Die Funktion summiert die erste Zahl jeder Zeile. Sie wird für die
    Screenshots `dig`, `reception` und `set` verwendet, bei denen sich die
    Spaltennamen leicht unterscheiden können, die Gesamtanzahl der Aktionen aber
    als erster Wert erscheint.
    """

    total = 0
    for tokens in _ocr_lines(image):
        numbers = _extract_numbers(tokens)
        if numbers:
            total += numbers[0]  # ersten Wert der Zeile addieren
    return total


def _parse_team(images: Dict[str, Path]) -> TeamStats:
    """Extrahiert Statistiken für ein Team anhand seiner Screenshots."""

    scoring = _parse_scoring(images["scoring"])
    dig = _parse_simple_total(images["dig"])
    reception = _parse_simple_total(images["reception"])
    set_total = _parse_simple_total(images["set"])

    return TeamStats(
        attack=scoring["attack"],
        block=scoring["block"],
        serve=scoring["serve"],
        opp_error=scoring["opp_error"],
        total_points=scoring["total_points"],
        dig=dig,
        reception=reception,
        set=set_total,
        top_scorer_1=scoring["top_scorer_1"],
        top_scorer_2=scoring["top_scorer_2"],
    )


# ---------------------------------------------------------------------------
# Verarbeitung auf Spiel-Ebene
# ---------------------------------------------------------------------------


def _parse_match(match_dir: Path, label: int) -> Dict[str, int]:
    """Parst ein Spielverzeichnis und berechnet die Merkmalsdifferenzen."""

    # Screenshots für Team A und Team B sammeln
    team_a_images = {name: match_dir / f"teamA_{name}.png" for name in TEAM_SCREENS}
    team_b_images = {name: match_dir / f"teamB_{name}.png" for name in TEAM_SCREENS}

    # Statistiken der beiden Teams aus den Bildern extrahieren
    team_a = _parse_team(team_a_images)
    team_b = _parse_team(team_b_images)

    # Differenzen zwischen den Teams berechnen und Label hinzufügen
    row = {
        "attack_diff": team_a.attack - team_b.attack,
        "block_diff": team_a.block - team_b.block,
        "serve_diff": team_a.serve - team_b.serve,
        "opp_error_diff": team_a.opp_error - team_b.opp_error,
        "total_points_diff": team_a.total_points - team_b.total_points,
        "dig_diff": team_a.dig - team_b.dig,
        "reception_diff": team_a.reception - team_b.reception,
        "set_diff": team_a.set - team_b.set,
        "top_scorer_1_diff": team_a.top_scorer_1 - team_b.top_scorer_1,
        "top_scorer_2_diff": team_a.top_scorer_2 - team_b.top_scorer_2,
        "label": label,
    }

    # Sicherheitscheck: keine fehlenden Werte zulassen
    if any(v is None for v in row.values()):
        raise ValueError(f"Fehlender Wert beim Parsen von {match_dir} entdeckt")
    return row


# ---------------------------------------------------------------------------
# Kommandozeilen-Schnittstelle
# ---------------------------------------------------------------------------


def build_dataset(match_specs: Iterable[str], output_file: Path) -> None:
    """Erstellt aus den angegebenen Spielen einen CSV-Datensatz.

    Parameter
    ---------
    match_specs:
        Iterable von Zeichenketten im Format ``"/pfad/zu/spiel:label"``.
    output_file:
        Pfad, unter dem die resultierende CSV-Datei geschrieben wird.
    """

    rows = []
    for spec in match_specs:  # jede Spielspezifikation verarbeiten
        try:
            dir_name, label_str = spec.split(":", 1)
        except ValueError as exc:  # pragma: no cover - defensiv
            raise ValueError(
                "Match-Spezifikation muss die Form 'verzeichnis:label' haben"
            ) from exc
        match_dir = Path(dir_name)
        label = int(label_str)
        rows.append(_parse_match(match_dir, label))
    df = pd.DataFrame(rows)
    if df.isna().any().any():
        raise ValueError("Fehlende Werte im finalen DataFrame entdeckt")
    df.to_csv(output_file, index=False)


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="VNL-Screenshots auswerten")
    parser.add_argument(
        "output",
        type=Path,
        help="Pfad zur zu erstellenden CSV-Datei",
    )
    parser.add_argument(
        "matches",
        nargs="+",
        help="Spiel-Spezifikationen im Format '/pfad/zu/spiel:label'",
    )
    args = parser.parse_args()
    build_dataset(args.matches, args.output)


if __name__ == "__main__":  # pragma: no cover - Startpunkt der CLI
    main()
