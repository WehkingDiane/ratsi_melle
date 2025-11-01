# Konzept für die Datenerfassung

Dieses Dokument beschreibt die Ergebnisse aus Task 2 der Projekt-Roadmap. Es fasst die recherchierten Strukturen des Ratsinformationssystems der Stadt Melle zusammen, leitet daraus eine Abruflogik ab und definiert das Speicherkonzept für die Rohdaten.

## 1. Quellen und HTML-Strukturen

Die Stadt Melle nutzt das **SessionNet**-System des Kommunalen Rechenzentrums Minden-Ravensberg/Lippe (KRZ). Der relevante Basis-Pfad lautet `https://sessionnet.krz.de/melle/bi/`. Wichtige Seiten:

| Seite | Zweck | Parameter |
| --- | --- | --- |
| `si010.asp` | Monatsübersicht mit allen Sitzungen. Tabelle enthält je Zeile `Gremium`, `Sitzung` (Detail-Link), `Datum`, `Zeit`, `Ort` sowie Verweise auf Tagesordnung (`to010.asp`) und Dokumente (`do010.asp`). | `MM` (Monat, zweistellig), `YY` (Jahr, vierstellig) |
| `si0050.asp` / `si0051.asp` | Detailansicht einer Sitzung, inkl. Meta-Informationen und Tagesordnungstabelle. Der Schlüsselparameter ist `SILFDNR`. | `SILFDNR`, optional `__ksinr` |
| `to010.asp` | Öffentliche Tagesordnung als eigenständige Seite (Redundanz zur Detailseite). | `SILFDNR` |
| `do010.asp` | Übersicht aller anhängigen Dokumente. | `SILFDNR` |
| `vo0050.asp` | Detailansicht zu Vorlagen/Beschlussvorlagen. Liefert Links zu weiteren Dokumenten. | `VOLFDNR` |
| `do0050.asp` | Download der eigentlichen Dateien (PDF, DOCX etc.). | `__ksinr`, `__kagnr`, `__kvonr` |

### HTML-Merkmale

- **Übersicht (`si010.asp`)**: `<table class="tliste">` mit `<tr>`-Zeilen; Detail-Link ist ein `<a>`-Tag mit `href` `si0050.asp?...`. Agenda- und Dokument-Links enthalten `to010` bzw. `do010` im `href`.
- **Tagesordnung**: In der Detailseite existiert eine Tabelle mit der Beschriftung/Titel „Tagesordnung“. Die Spalten umfassen TOP-Nummer, Betreff, Status und eine Zelle mit verlinkten Dokumenten (`do0050.asp`).
- **Dokumente**: Links enden auf `do0050.asp?` und liefern die eigentliche Datei. Der Linktext entspricht dem Dokumenttitel; Dateiendungen sind nicht im Link ersichtlich und müssen aus dem HTTP-Header bestimmt werden.

## 2. Abruflogik

1. **Monatsweise Abfrage**: Für jeden Monat wird `si010.asp?MM=..&YY=..` geladen und unverändert abgespeichert. Daraus werden Sitzungsreferenzen extrahiert (Gremium, Sitzungstitel, Datum, Detail-Link, optionale Agenda-/Dokument-Links).
2. **Detailabfrage**: Für jede Sitzung wird die Detailseite (`si0050.asp`) geladen. Die Tagesordnungstabelle wird geparst und zu einer strukturierten Liste von TOPs transformiert, inklusive der dort verlinkten Dokumente.
3. **Dokumentdownloads**: Alle aus Tagesordnung oder Dokumentübersicht gefundenen `do0050.asp`-Links werden mit denselben Sitzungsschlüsseln heruntergeladen. Fehler (z. B. 404) werden geloggt, aber führen nicht zum Abbruch der gesamten Sitzungserfassung.
4. **Wiederholungsstrategien**: HTTP-Fehler werden durch Exception-Handling abgefangen; der Client kann erneut aufgerufen werden. Die CLI unterstützt Wiederholungen über erneutes Ausführen.

## 3. Speicherkonzept für Rohdaten

- **Verzeichnisstruktur**: `data/raw/<Jahr>/<Datum>_<Gremium>_<Sitzungs-ID>/`.
  - Beispiel: `data/raw/2024/2024-05-14_Ausschuss-fuer-Umwelt_12345/`.
  - Sonderzeichen werden bei der Ablage in Dateinamen durch Bindestriche ersetzt.
- **Gespeicherte Artefakte**:
  - `YYYY-MM_overview.html` pro Monat im Jahresordner.
  - `session_detail.html` innerhalb des Sitzungsordners.
  - Heruntergeladene Dokumente als `*.bin`. Die binäre Endung wird beibehalten, bis Metadaten (z. B. `Content-Type`) für eine genaue Dateiendung ausgewertet werden können.
- **Metadaten**: Agenda und Dokumente werden programmatisch zu Python-Objekten (`SessionDetail`, `AgendaItem`, `DocumentReference`) verarbeitet. Persistente Serialisierung (z. B. JSON) erfolgt erst in späteren Tasks.
- **Versionierung**: Alle Rohdaten liegen innerhalb des Git-Repositories, werden aber über `.gitignore` von produktiven Downloads ausgeschlossen. Tests können mit Mock-Daten arbeiten.

## 4. Offene Punkte

- Authentifizierung ist aktuell nicht erforderlich, jedoch sollte mittelfristig ein Request-Rate-Limit implementiert werden (z. B. 1 Anfrage/Sekunde), um die Server zu schonen.
- Für Dokumentdownloads muss der finale Dateiname zukünftig über die HTTP-Header (`Content-Disposition`) bestimmt werden.
- Bei dauerhaft nicht erreichbaren Seiten (z. B. Wartung) sollte die CLI einen non-zero Exit-Code liefern, um Scheduler-Läufe sichtbar scheitern zu lassen.

