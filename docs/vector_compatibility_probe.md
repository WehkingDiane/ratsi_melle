# Bibliothekswechsel ohne vollständigen Indexneuaufbau prüfen

`scripts/probe_bi_vector_compatibility.py` prüft den bestehenden Ratsinfo-Passagenindex gegen separat vorbereitete Modelle mit den installierten Bibliotheken. Die Berechnung soll wie der bisherige Indexaufbau direkt unter Windows in `.venv` laufen. Die vorhandene Geräteerkennung bevorzugt Intel XPU, sonst CPU. Ein Performancevorteil gegenüber WSL wird nicht vorausgesetzt oder durch diesen Test gemessen.

## Vorbereitung unter Windows

Qdrant muss mit dem bisherigen Bestand laufen. Während der Prüfung keine Indexaufbauten, Migrationen oder direkten Qdrant-Schreibzugriffe starten. Die Diagnose nutzt dieselbe Collection-Sperre wie die Projekt-Builds. Die Sperren legen lokale Lockdateien an; Indexpunkte und Freigabemarker werden nicht verändert. Lokaler Qdrant-Dateimodus wird bewusst nicht geöffnet.

In PowerShell im Repository-Stamm die gewünschte Windows-Umgebung nutzen. Die neueren Bibliotheken müssen bereits installiert sein. Die Vorbereitung kann Modelle herunterladen und zusätzlichen Speicherplatz benötigen. Ein neues Kandidatenverzeichnis verwenden und den alten Bestand `data/models` beibehalten:

```powershell
$previousModelsDir = $env:RATSI_MODELS_DIR
try {
    $env:RATSI_MODELS_DIR = Join-Path $PWD 'data\models_candidate'
    & .\.venv\Scripts\python.exe .\scripts\prepare_embedding_models.py --download
    if ($LASTEXITCODE -ne 0) { throw 'Modellvorbereitung fehlgeschlagen' }
} finally {
    if ($null -eq $previousModelsDir) {
        Remove-Item Env:RATSI_MODELS_DIR -ErrorAction SilentlyContinue
    } else {
        $env:RATSI_MODELS_DIR = $previousModelsDir
    }
}
```

Damit entsteht ein eigener Manifestvertrag für die aktuellen Bibliotheken. Die bestehenden Vektoren bleiben die Referenz; die alte Bibliotheksumgebung wird für diesen ersten Vergleich nicht benötigt. Modellrevisionen, Dimension und Pipeline müssen identisch bleiben; die Diagnose erlaubt nur einen abweichenden Manifesthash. Sie umgeht keine Modellbereitschaftsprüfung.

## Diagnose starten

Für den bisherigen Standardserver:

```powershell
$env:RATSI_QDRANT_MODE = 'server'
$env:RATSI_QDRANT_URL = 'http://127.0.0.1:6333'
& .\.venv\Scripts\python.exe .\scripts\probe_bi_vector_compatibility.py `
    --models-dir .\data\models_candidate `
    --sample-size 128 --batch-size 4 --top-k 10 `
    --report .\data\processed\vector_compatibility_windows_01.json
```

Bei einem anderen bisherigen Server dessen URL und gegebenenfalls `RATSI_QDRANT_STATE_DIR` beibehalten. Der passende lokale Freigabemarker muss vorhanden und freigegeben sein. Vorhandene Berichte werden nicht überschrieben. Ein neuer Dateiname ermöglicht Wiederholungen.

Optional `--queries .\data\private\compatibility_queries.txt` ergänzen: UTF-8, eine Suchanfrage pro Zeile. Ohne Datei werden „Schulsanierung“, „Bebauungsplan“ und „Haushalt und Straßenbau“ geprüft. Der Bericht enthält die Suchanfragen, Punkt-IDs und Messwerte, aber keine vollständigen Dokumenttexte oder Vektoren. Sinnvoll sind zusätzlich eigene typische Suchanfragen.

## Bericht auswerten

- Exit-Code **0**, `sample_matches`: Alle Stichprobenvektoren stimmen innerhalb der bestehenden Migrationstoleranzen überein und die geprüften Stichprobenrangfolgen bleiben gleich.
- Exit-Code **1**, `differences_found`: Mindestens ein Vektorvergleich oder eine Rangfolge weicht ab. Das bedeutet Prüfbedarf, nicht automatisch Unbrauchbarkeit.
- Exit-Code **2**, `aborted`: Die Prüfung konnte nicht abgeschlossen werden, etwa wegen ungültigem Modellbestand, fehlendem Marker, falschem Vektorschema oder erkannten Änderungen während des Tests. Argumentfehler verwenden ebenfalls Exit-Code 2 und erzeugen keinen Bericht.

`summary` enthält Anzahl strenger Übereinstimmungen, minimale Dense-Kosinusähnlichkeit, maximale Dense-Abweichung und Zahl gleicher Rangfolgen. `sample` enthält die Einzelergebnisse für Harrier und BM25; `contract_differences` nennt die Vertragsabweichungen. Die strenge Vektorprüfung verwendet die vorhandenen absoluten und relativen Toleranzen von jeweils `1e-4`. Neue Dense-Vektoren werden wie in einer Qdrant-Cosine-Collection normalisiert.

Die Auswahl ist bei gleichem Bestand deterministisch: Hashauswahl mit abwechselnder Berücksichtigung kurzer/langer Texte, OCR, Zahlen, Umlauten und übrigen Texten. Kategorien können sich überschneiden; es besteht keine Garantie für jedes Sonderformat oder jedes Dokument. Alle Payloads werden zweimal gelesen, Vektoren nur für die Stichprobe. Der Scan und die tiefe Modellprüfung können Zeit beanspruchen. Kleinere `--batch-size`, etwa 1, reduziert den Speicherbedarf der Neuberechnung.

Die Suchprüfung berechnet Kandidaten-Anfragevektoren gegen alte und neu berechnete Stichprobenvektoren, mit Dense-/Sparse-Rängen und lokalem RRF (Konstante 60). Sie prüft den geplanten Mischbetrieb näherungsweise. Sie bildet weder die vollständige Produktionssuche noch deren Laufzeit ab. Ohne alte Bibliotheksumgebung fehlt außerdem die alte Anfragevektor-Baseline. Auch ein fehlerfreier Stichprobentest beweist keine vollständige Gleichheit; externe Schreibzugriffe lassen sich nicht atomar ausschließen.

**Der Bericht gibt keinen Index frei.** `migration_authorized` bleibt immer `false`. Indexvertrag, Suchfreigabe und Unterstützung mehrerer Bibliotheksstände bleiben unverändert. Erst nach Auswertung entscheiden, ob eine kontrollierte Weiterverwendung und schrittweise Dokumentaktualisierung umgesetzt werden kann.
