# TODO.md – Ratsinformations-Analysetool Melle

## Phase 1: Projektgrundlage & Setup

- [ ] Projektverzeichnis `ratsi_melle/` anlegen  
- [ ] `requirements.txt` erstellen  
  - [ ] beautifulsoup4  
  - [ ] requests  
  - [ ] pandas  
  - [ ] streamlit  
  - [ ] openai (oder ollama)  
  - [ ] schedule  
  - [ ] python-dotenv (für API-Keys)
- [ ] `config.json` anlegen (Gremien, Themen, Analyseparameter)  
- [ ] Python-Virtualenv einrichten  
- [ ] `.gitignore` anlegen (data/, __pycache__/, env/, .streamlit/)  
- [ ] README.md ergänzen (Installations- und Startanleitung)

---

## Phase 2: Sitzungskalender auslesen (`fetch_sessions.py`)

- [ ] Zielseite analysieren: `https://session.melle.info/bi/si010.asp`
- [ ] HTML-Struktur prüfen (Tabellenaufbau, Spalten, Links)
- [ ] Erste Requests-Abfrage mit `requests.get()`
- [ ] Encoding auf UTF-8 setzen
- [ ] Parsing mit `BeautifulSoup`
- [ ] Relevante Datenfelder extrahieren:
  - [ ] Sitzungsdatum  
  - [ ] Gremium  
  - [ ] Sitzungstitel  
  - [ ] Link zur Detailseite (`SILFDNR`)
- [ ] Daten in DataFrame oder Dictionary speichern
- [ ] Lokale Speicherung als `sessions.json` oder SQLite-Tabelle
- [ ] Logging einbauen (neue / bereits bekannte Sitzungen)
- [ ] Funktion zur inkrementellen Aktualisierung

---

## Phase 3: Vorlagenübersicht auslesen (`fetch_documents.py`)

- [ ] URL-Muster analysieren (z. B. `/bi/vo020.asp` oder `/bi/to010.asp?SILFDNR=xxxx`)
- [ ] HTML-Struktur der Vorlagentabelle untersuchen  
- [ ] Schleife: für jede Sitzung → zugehörige Vorlagen laden  
- [ ] Extraktion:
  - [ ] Titel  
  - [ ] Nummer  
  - [ ] Status  
  - [ ] Antragsteller  
  - [ ] Link zur Vorlage (`VOLFDNR`)
- [ ] Detailseiten abrufen und Textinhalt extrahieren  
  - [ ] ggf. PDF-Links identifizieren und speichern  
- [ ] Datenstruktur aufbauen:
  ```
  data/YYYY-MM-DD_Gremium/
      Sitzung.json
      01_Titel_der_Vorlage/
          Vorlage.html
  ```
- [ ] Plausibilitätsprüfung (leere Tabellen / Fehlerseiten)
- [ ] Fortschrittsausgabe im Terminal

---

## Phase 4: Datenorganisation (`file_utils.py`)

- [ ] Funktionen zum Erstellen von Ordnerstrukturen:
  - [ ] `create_session_folder(gremium, datum)`
  - [ ] `create_document_folder(session_path, title)`
- [ ] JSON-Schreib- und Lesefunktionen
- [ ] automatische Dateinamen-Säuberung (Sonderzeichen entfernen)
- [ ] Funktion: `get_all_sessions()`
- [ ] Funktion: `get_documents_for_session(session_path)`
- [ ] Fehlerhandling bei bereits existierenden Dateien

---

## Phase 5: KI-Analyse & Zusammenfassung (`llm_analyzer.py`)

- [ ] LLM-API vorbereiten (OpenAI, Ollama oder lokales Modell)
- [ ] Prompt-Template für journalistische Zusammenfassung:
  - [ ] „Fasse folgenden Ratsantrag neutral und sachlich zusammen …“
- [ ] Text aus Vorlagen extrahieren
- [ ] Aufruf an KI-Modell mit Titel, Text, Metadaten
- [ ] Ergebnis speichern als `Analyse.json`
- [ ] Struktur:
  ```json
  {
    "titel": "",
    "kurzfassung": "",
    "bewertung": "",
    "themenfelder": [],
    "datum": "",
    "quelle": ""
  }
  ```
- [ ] Fehlerhandling (Timeout, leere Antworten)
- [ ] Option für Batch-Analyse mehrerer Sitzungen
- [ ] Parameter für Token-Limit und Temperatur

---

## Phase 6: Streamlit-Dashboard (`main.py`)

- [ ] Grundgerüst erstellen:
  - [ ] Titel: "Ratsinformations-Analysetool Melle"
  - [ ] Menüleiste: Start | Sitzungen | Analysen | Verwaltung
- [ ] **Startseite**
  - [ ] Begrüßung und kurze Projektbeschreibung
  - [ ] Button: „Sitzungen aktualisieren“
  - [ ] Button: „Analysen starten“
- [ ] **Sitzungen**
  - [ ] Liste aller vorhandenen Sitzungen
  - [ ] Filter nach Gremium, Datum
  - [ ] Anzeige der zugehörigen Vorlagen
  - [ ] Vorschau der Anträge (Titel, Status)
- [ ] **Analysen**
  - [ ] Darstellung der KI-Zusammenfassungen
  - [ ] Filter nach Themenfeldern
  - [ ] Download als JSON / Markdown
- [ ] **Verwaltung**
  - [ ] Anzeige Speichergröße
  - [ ] Button: „Alte Daten löschen“
  - [ ] Eingabe: Datum oder Gremium
- [ ] Erfolgsmeldungen / Logs im UI anzeigen

---

## Phase 7: Lösch-Skript (`cleanup.py`)

- [ ] CLI-Tool erstellen:
  ```bash
  python utils/cleanup.py --before 2024-01-01
  ```
- [ ] Argumente parsen mit `argparse`
- [ ] Ziel:
  - [ ] Sitzungen vor Datum löschen  
  - [ ] Optional: nach Gremium filtern  
- [ ] Sicherheitsabfrage vor Löschung
- [ ] Logging: Welche Ordner gelöscht wurden
- [ ] Rückgabewert für automatisierte Jobs

---

## Phase 8: Logging & Fehlermanagement

- [ ] Zentrale Logging-Funktion (`logger.py`)
  - [ ] Ausgabe in Konsole + Logdatei (`logs/app.log`)
- [ ] Fehlermeldungen bei fehlendem Internet / HTTP-Fehler
- [ ] Retry-Mechanismus bei Netzwerkproblemen
- [ ] Validierung der HTML-Struktur (Fallback bei Änderungen)
- [ ] Fortschrittsbalken (z. B. `tqdm`)

---

## Phase 9: Automatisierung

- [ ] Geplante Tasks mit `schedule`
  - [ ] Tägliches Abrufen neuer Sitzungen (z. B. 6 Uhr)
  - [ ] Wöchentliche Löschung alter Daten
- [ ] Optional: GitHub Action oder Cronjob vorbereiten
- [ ] Logging automatischer Läufe speichern

---

## Phase 10: Tests & Qualitätssicherung

- [ ] Unit-Tests für:
  - [ ] `fetch_sessions.py`  
  - [ ] `fetch_documents.py`  
  - [ ] `file_utils.py`
- [ ] Integrationstest: Crawl → Speicherung → Analyse
- [ ] Manuelle Tests:
  - [ ] Funktioniert Dashboard lokal?
  - [ ] Werden alle Sitzungen korrekt erkannt?
- [ ] Code-Review & Dokumentation
- [ ] Optionale HTML-Validierung

---

## Phase 11: Erweiterungen (optional)

- [ ] Mehrsprachige Analyseausgabe (Deutsch / Englisch)
- [ ] Vergleich ähnlicher Anträge (z. B. gleiche Themen)
- [ ] Export für Newsletter oder CSV-Report
- [ ] Zeitreihenanalyse (Themenhäufigkeit)
- [ ] Wordcloud der Schlagwörter
- [ ] Erweiterung auf andere Kommunen mit SessionNet-System
