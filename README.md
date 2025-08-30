# parser-VNLdata

This repository contains a Python script for converting Volleyball Nations League
(VNL) statistics screenshots into a machine readable CSV dataset.  Each match
is represented by 14 screenshots – seven for each team.  The script aggregates
statistics for both teams and writes a single row with the following columns:

- `attack_diff`
- `block_diff`
- `serve_diff`
- `opp_error_diff`
- `total_points_diff`
- `dig_diff`
- `reception_diff`
- `set_diff`
- `top_scorer_1_diff`
- `top_scorer_2_diff`
- `label` (`1` if team A wins, `0` otherwise)

## Usage

Prepare a directory for every match containing the screenshots named according
to the following convention for team A and team B:

```
teamA_scoring.png   teamB_scoring.png
teamA_attack.png    teamB_attack.png
teamA_block.png     teamB_block.png
teamA_serve.png     teamB_serve.png
teamA_reception.png teamB_reception.png
teamA_dig.png       teamB_dig.png
teamA_set.png       teamB_set.png
```

With the directories in place run:

```
python vnl_parser.py output.csv path/to/match1:1 path/to/match2:0 ...
```

Each `path:label` pair points to a match directory and provides the match
label (`1` if team A wins, `0` if team B wins).  The script uses OCR through
`pytesseract`; ensure the Tesseract binary is installed and available in your
`PATH`.
