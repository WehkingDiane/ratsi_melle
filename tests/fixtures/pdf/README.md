# PDF-Fixtures aus echten lokalen Daten

Die sechs Original-PDFs sind **unveraenderte, bytegleiche Kopien** aus
`data/raw/`. Sie liegen dauerhaft unter `tests/fixtures/pdf/` und werden direkt
von pytest gelesen. Die Tests brauchen weder den urspruenglichen Rohdatenbestand
noch einen Download. Die Originale unter `data/raw/` bleiben erhalten.

| Datei | Umfang | Testzweck |
| --- | --- | --- |
| `budget_proposal.pdf` | 5 Seiten | Beschlussvorschlag, Umlaute, Eurobetraege, Abschnittsueberschriften und kurze Schlussseite |
| `council_public_notice.pdf` | 2 Seiten | Amtliche Bekanntmachung, Tagesordnung und Seitenfolge |
| `budget_tables.pdf` | 2 Seiten | Tabellen, Spalten, Zahlen und Zeilenumbrueche |
| `municipal_statute.pdf` | 7 Seiten | Paragraphen, eingebettete Schriften, Umlaute und Wappenabbildungen |
| `council_rules.pdf` | 10 Seiten | Laengerer Text, Passage-Aufteilung, spaete Seiten und Textbegrenzung |
| `scanned_price_table.pdf` | 1 Seite | Echte Scan-PDF ohne durchsuchbare Textschicht |

Zwei weitere Dateien sind ausdruecklich abgeleitete Testfaelle:

- `mixed_text_scan.pdf`: erste Seite der Haushaltsvorlage und die echte
  Scan-Seite, zu einem Dokument zusammengefuegt. Dokumentmetadaten und
  Annotationen werden dabei nicht uebernommen.
- `truncated_proposal.pdf`: erste 16 Bytes der Haushaltsvorlage fuer einen
  kontrollierten Fehler bei unlesbarer PDF-Struktur.

Das [Manifest](manifest.json) dokumentiert Originalpfad, oeffentliche Quell-URL,
SHA-256 des Originals und der Kopie, Dateigroesse, Seitenzahl und gezielte
Textbelege pro Seite. Bei Originalkopien muessen beide Pruefsummen gleich sein.
Die Quelle dient als Herkunftsnachweis; Tests rufen die URLs nicht auf.
Die Auswahl enthaelt amtliche Sachtexte und eine oeffentlich bereitgestellte
Preistabelle. Vollstaendige Sitzungsprotokolle mit Einwohnerbeiträgen wurden
fuer diesen Testbestand nicht uebernommen.

## Pflege

Neue Originale als Kopie aufnehmen und Herkunft, Pruefsumme sowie fachlich
gepruefte Erwartungen im Manifest ergaenzen. Textbelege pruefen gezielte Inhalte
statt einen vollstaendigen, bibliotheksabhaengigen Textdump. Ersetzen einer
Fixture erfordert eine erneute Pruefung ihrer Erwartungen.

Die abgeleitete Mischdatei wurde mit `pypdf` 6.9.2 ueber `PdfWriter.add_page`
und `write` erstellt; `/Annots`, `/B` und `/Metadata` wurden ausgeschlossen.
Die Bibliotheksfunktionen sind in der
[pypdf-Dokumentation](https://pypdf.readthedocs.io/en/stable/modules/PdfWriter.html)
beschrieben. Die abgeschnittene Datei besteht exakt aus `original_bytes[:16]`.

Groessere Testdateien werden temporaer erzeugt. Die regulaeren Groessenpruefungen
verwenden Sparse-Dateien an den echten 25-/100-MiB-Grenzen. Ein optionaler
Belastungstest wiederholt die Originalseiten der Geschaeftsordnung zu einem
300-seitigen PDF unter pytest `tmp_path`; der Aufruf steht in der Projekt-README.
