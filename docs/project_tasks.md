# Projektaufgaben und Ausbaupfade

Diese Datei buendelt die offene Arbeitsliste des Projekts. Sie ersetzt die fruehere Mischung aus Lang-README und `README_TASK4.md`.

## 1. Projektweit offene Aufgaben

### Datengewinnung und Datenhaltung

- Fetch- und Build-Workflows weiter robust halten und bei SessionNet-Aenderungen anpassen
- inkrementelle Download-Strategie fuer geaenderte oder fehlende Dokumente weiter verbessern
- Datenqualitaet und Metadatenkonsistenz ueber Regressionstests absichern

### Analyse und KI

- Analyseziele, Ausgabeformate und Qualitaetskriterien verbindlich machen
- mehrere Analysemodi fuer Dokumente, TOPs und ganze Sitzungen umsetzen
- Volltext- oder PDF-Uebergabe an KI-Provider pro TOP vervollstaendigen
- Quellenbezug, Review und Reproduzierbarkeit in der Analyseoberflaeche sichtbar machen

### Oberflaechen

- Django-Hauptoberflaeche unter `web/` modular nach dem Grundkonzept ausbauen
- `scripts/run_web.py` als primaeren UI-Startpunkt stabil halten
- Streamlit und Legacy-Desktop-GUI nur noch als deprecated Kompatibilitaet mitfuehren

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

- Volltext- oder PDF-Uebergabe im produktiven Analysepfad
- gemeinsame Antwortstruktur fuer spaetere UI- und API-Nutzung

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

- Django-Oberflaeche in einzelne Seiten und Apps aufteilen
- Restliche aktive Dokumentation von deprecated UI-Pfaden bereinigen
- TOP-basierte KI-Analyse als ersten belastbaren End-to-End-Pfad fertigstellen
- Aufgabenliste regelmaessig bereinigen und erledigte Punkte streichen oder verschieben
