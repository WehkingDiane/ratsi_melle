# Projektaufgaben und Ausbaupfade

Diese Datei buendelt die offene Arbeitsliste des Projekts. Sie ersetzt die fruehere Mischung aus Lang-README und `README_TASK4.md`.

## 1. Projektweit offene Aufgaben

### Datengewinnung und Datenhaltung

- Fetch- und Build-Workflows weiter robust halten und bei SessionNet-Aenderungen anpassen
- inkrementelle Download-Strategie fuer geaenderte oder fehlende Dokumente weiter verbessern
- Datenqualitaet und Metadatenkonsistenz ueber Regressionstests absichern

### Analyse und KI

- Analyseziele, Ausgabeformate und Qualitaetskriterien verbindlich machen
- bestehende Sitzungs- und TOP-Analyse um einen dokumentzentrierten UI-Workflow ergaenzen
- Volltext-, PDF- und OCR-Randfaelle im produktiven Analysepfad robuster behandeln
- Quellenbezug, Review und Reproduzierbarkeit in der Analyseoberflaeche sichtbar machen

### Oberflaechen

- Django-Hauptoberflaeche unter `web/` modular nach dem Grundkonzept ausbauen
- `scripts/run_web.py` als primaeren UI-Startpunkt stabil halten

### Betrieb und Qualitaet

- Logging, Monitoring und Fehlerdiagnose ausbauen
- Testabdeckung fuer Datenpipeline, Analysefluesse und Suchpfade erweitern
- Dokumentation regelmaessig gegen den aktuellen Stand pruefen

## 2. Analysemodul

Dieser Abschnitt uebernimmt den Kern aus der frueheren `README_TASK4.md`.

### Zielbild

Das Analysemodul soll:

- Dokumente, TOPs und ganze Sitzungen verarbeiten
- KI fuer die eigentliche Inhaltsanalyse nutzen
- Regeln fuer Vorstrukturierung, Qualitaetskontrolle und Reproduzierbarkeit verwenden
- Ergebnisse als nachvollziehbare, pruefbare Analyseartefakte ausgeben

### Analyseziele

- Kernaussagen aus Dokumenten und TOPs erfassen
- Beschlusslagen und moegliche Verfahrensschritte sichtbar machen
- finanzielle und politische Relevanz kenntlich machen
- sitzungsweite Verdichtungen aus einzelnen TOP-Analysen ableiten

### Qualitaetskriterien

- Faktentreue
- Quellenbezug
- Nachvollziehbarkeit
- sichtbare Unsicherheit statt Scheingenauigkeit
- reproduzierbare Ein- und Ausgaben

### Ausgabeformate

- Markdown-Bericht fuer Sichtung und Review
- strukturierte JSON-Ausgabe
- Quellenliste mit Dokumentreferenzen
- spaeter nutzbare Artefakte fuer UI oder API

### Analyseebenen

#### Dokument

- kurzes Inhaltsprofil
- Hinweise auf Beschluss, Finanzierung, Zustaendigkeit oder offene Fragen
- Einschaetzung der Extraktionsqualitaet

#### Tagesordnungspunkt

Standardpfad fuer die KI-Analyse:

- ein TOP
- alle zugeordneten Dokumente
- eine belastbare Zusammenfassung mit Quellenbezug

Typische Ergebnisfelder:

- `top_summary`
- `decision_signal`
- `financial_signal`
- `public_relevance`
- `open_questions`
- `source_citations`
- `confidence`

#### Sitzung

- zuerst einzelne TOPs analysieren
- danach daraus eine uebergeordnete Sitzungsverdichtung ableiten

### KI- und Regelanteile

#### Regelbasiert

- Metadatenstruktur
- Dokumenttyp-Erkennung
- Qualitaetspruefung der Extraktion
- Hashing, Logging und Artefaktablage

#### KI-basiert

- Inhaltszusammenfassung von Dokumenten
- Zusammenfuehrung mehrerer Dokumente pro TOP
- Erkennen politischer Relevanz
- Formulierung verstaendlicher Ausgaben

### Provider-Infrastruktur

Vorhanden unter `src/analysis/providers/`:

- `claude`
- `codex`
- `ollama`

Offen:

- gemeinsames Antwortschema weiter validieren und bei neuen Analysezwecken versionieren
- Providerfehler, Kontextgrenzen und PDF-/OCR-Randfaelle weiter absichern

### Reproduzierbarkeit und Review

Zu jeder Analyse sollen mindestens gespeichert werden:

- Analysemodus
- Eingabekontext
- verwendete Dokumente
- Dokument-Hashes
- Prompt oder Prompt-Version
- Provider und Modell
- Parameter und Zeitstempel

Zusätzlich benoetigt der Analysepfad:

- Draft-Status fuer neue Analysen
- sichtbare Unsicherheitsmarker
- Review- und Freigabemoeglichkeit

## 3. Naechste sinnvolle Schritte

- Quellenpruefung und Review fuer bestehende Sitzungs- und TOP-Analysen ausbauen
- dokumentzentrierte Analyse und Dokumentvorschau als naechsten End-to-End-Pfad umsetzen
- optionale OCR-Installation und Verhalten bei grossen Dateien betrieblich absichern
- Aufgabenliste regelmaessig bereinigen und erledigte Punkte streichen oder verschieben
