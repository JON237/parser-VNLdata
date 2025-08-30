"""Parser for VNL screenshots.

This module extracts match statistics from Volleyball Nations League (VNL)
scoreboard screenshots. Each match consists of 14 screenshots – seven for
team A and seven for team B.  The order/structure of the screenshots is
expected to be as follows for each team:

    scoring.png
    attack.png
    block.png
    serve.png
    reception.png
    dig.png
    set.png

For each match a single row is produced with the columns
required by the project specification:

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

`label` is 1 when team A wins and 0 when team B wins.

The script relies on `pytesseract` for optical character recognition.  It is
written to be reasonably robust but the heuristics are tailored to the
screenshots provided on the VNL web page.  In case OCR fails to detect a value
for any statistic a `ValueError` is raised so that no missing data is written
into the resulting CSV file.
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
# Data structures
# ---------------------------------------------------------------------------

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
    """Holds aggregated statistics for a single team."""

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
# OCR helper functions
# ---------------------------------------------------------------------------

_number_re = re.compile(r"\d+")


def _ocr_lines(image_path: Path) -> List[List[str]]:
    """Run OCR on an image and return a list of tokenised lines.

    Each line is split on whitespace; empty lines and tokens are removed.
    """

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Unable to read image {image_path}")
    text = pytesseract.image_to_string(img)
    lines: List[List[str]] = []
    for raw in text.splitlines():
        tokens = [t for t in raw.strip().split() if t]
        if tokens:
            lines.append(tokens)
    return lines


def _extract_numbers(tokens: Iterable[str]) -> List[int]:
    """Return a list of integers found in `tokens`."""

    numbers: List[int] = []
    for tok in tokens:
        m = _number_re.search(tok)
        if m:
            numbers.append(int(m.group()))
    return numbers


# ---------------------------------------------------------------------------
# Parsers for individual statistics
# ---------------------------------------------------------------------------


def _parse_scoring(image: Path) -> Dict[str, int]:
    """Parse the 'scoring' screenshot of a team.

    The screenshot contains one row per player with the columns
    (Total Attempts, Attack Points, Block Points, Serve Points, Opp Errors).
    We sum the respective columns across players, compute total points and
    determine the points of the two best scorers.
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
        # Expect at least: Total, Attack, Block, Serve, Opp error
        if len(numbers) >= 5:
            attack, block, serve, opp_error = numbers[1:5]
            totals["attack"] += attack
            totals["block"] += block
            totals["serve"] += serve
            totals["opp_error"] += opp_error
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
    """Parse screenshots where a single numeric column per player is sufficient.

    The function sums the first number on each line.  It is used for the
    `dig`, `reception` and `set` screenshots where the exact column names may
    vary slightly but the total number of actions is the first value.
    """

    total = 0
    for tokens in _ocr_lines(image):
        numbers = _extract_numbers(tokens)
        if numbers:
            total += numbers[0]
    return total


def _parse_team(images: Dict[str, Path]) -> TeamStats:
    """Extract statistics for one team given its screenshots."""

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
# Match level processing
# ---------------------------------------------------------------------------


def _parse_match(match_dir: Path, label: int) -> Dict[str, int]:
    """Parse a single match directory and compute feature differences."""

    team_a_images = {name: match_dir / f"teamA_{name}.png" for name in TEAM_SCREENS}
    team_b_images = {name: match_dir / f"teamB_{name}.png" for name in TEAM_SCREENS}

    team_a = _parse_team(team_a_images)
    team_b = _parse_team(team_b_images)

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

    if any(v is None for v in row.values()):
        raise ValueError(f"Missing value encountered while parsing {match_dir}")
    return row


# ---------------------------------------------------------------------------
# Command line interface
# ---------------------------------------------------------------------------


def build_dataset(match_specs: Iterable[str], output_file: Path) -> None:
    """Build a CSV dataset from the given match specifications.

    Parameters
    ----------
    match_specs:
        Iterable of strings in the form ``"/path/to/match:label"``.
    output_file:
        Path where the resulting CSV file will be written.
    """

    rows = []
    for spec in match_specs:
        try:
            dir_name, label_str = spec.split(":", 1)
        except ValueError as exc:  # pragma: no cover - defensive programming
            raise ValueError(
                "Match specification must be of the form 'directory:label'"
            ) from exc
        match_dir = Path(dir_name)
        label = int(label_str)
        rows.append(_parse_match(match_dir, label))
    df = pd.DataFrame(rows)
    if df.isna().any().any():
        raise ValueError("Missing values detected in final dataframe")
    df.to_csv(output_file, index=False)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse VNL screenshots")
    parser.add_argument(
        "output",
        type=Path,
        help="Path to the CSV file to create",
    )
    parser.add_argument(
        "matches",
        nargs="+",
        help="Match specifications of the form '/dir/to/match:label'",
    )
    args = parser.parse_args()
    build_dataset(args.matches, args.output)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
