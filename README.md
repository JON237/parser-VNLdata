# parser-VNLdata

Dieses Repository enthält ein Python‑Skript, das Screenshots der Volleyball
Nations League (VNL) in einen maschinenlesbaren CSV‑Datensatz umwandelt. Jedes
Spiel besteht aus 14 Screenshots – sieben pro Team. Das Skript aggregiert die
Statistiken beider Teams und schreibt eine einzelne Zeile mit den folgenden
Spalten:

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
- `label` (`1`, wenn Team A gewinnt, sonst `0`)

## Verwendung

Lege für jedes Spiel ein Verzeichnis mit den Screenshots an. Die Dateien müssen
für Team A und Team B nach folgendem Schema benannt sein:

```
teamA_scoring.png   teamB_scoring.png
teamA_attack.png    teamB_attack.png
teamA_block.png     teamB_block.png
teamA_serve.png     teamB_serve.png
teamA_reception.png teamB_reception.png
teamA_dig.png       teamB_dig.png
teamA_set.png       teamB_set.png
```

Sind die Verzeichnisse vorbereitet, führe folgenden Befehl aus:

```
python vnl_parser.py output.csv pfad/zu/spiel1:1 pfad/zu/spiel2:0 ...
```

Jedes `pfad:label`‑Paar verweist auf ein Spielverzeichnis und enthält das Label
(`1`, wenn Team A gewinnt, `0`, wenn Team B gewinnt). Das Skript nutzt OCR über
`pytesseract`; stelle sicher, dass die Tesseract‑Binary installiert und im
`PATH` verfügbar ist.
