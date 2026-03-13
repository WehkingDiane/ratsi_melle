# Task 4: Analysemodul entwickeln

Diese Datei konkretisiert Task 4 aus [README.md](/mnt/c/users/diane/git/ratsi_melle/README.md). Sie beschreibt den inhaltlichen Rahmen fuer das Analysemodul, ohne sich auf die aktuelle Developer-GUI zu beschraenken.

Wichtiger Grundsatz:
Die spaetere vollstaendige inhaltliche Analyse soll ueber KI laufen. Regelbasierte Verfahren bleiben wichtig fuer Vorstrukturierung, Qualitaetspruefung, Quellenbezug und Reproduzierbarkeit, aber nicht als alleinige Endanalyse fuer komplexe PDF-Dokumente.

## Ausgangspunkt

Das Projektziel aus `README.md` bleibt unveraendert:

- kommunalpolitische Informationen automatisch einsammeln
- Dokumente und Sitzungen strukturiert aufbereiten
- nachvollziehbare und verstaendliche Analysen erzeugen
- spaetere Recherche, Auswertung und Darstellung unterstuetzen

Fuer Task 4 bedeutet das:
Es braucht ein Analysemodul, das Dokumente, Tagesordnungspunkte und ganze Sitzungen verarbeiten kann, dabei aber klar zwischen vorbereitender Logik und eigentlicher KI-Analyse trennt.

## 1. Analyseziele, Qualitaetskriterien und Ausgabeformate

### Analyseziele

Das Analysemodul soll mindestens diese Ziele unterstuetzen:

- Kernaussagen aus Dokumenten und TOPs erfassen
- Beschlusslagen und moegliche Verfahrensschritte sichtbar machen
- finanzielle Hinweise und politische Relevanz erkennbar machen
- Unterschiede zwischen Dokumenten, Vorlagen und spaeteren Staenden festhalten
- sitzungsweite Uebersichten aus einzelnen TOP-Analysen ableiten

### Qualitaetskriterien

Jede Analyse muss sich an klaren Kriterien messen lassen:

- Faktentreue
- Quellenbezug
- Nachvollziehbarkeit
- klare Trennung zwischen belegter Aussage und Unsicherheit
- reproduzierbare Eingaben und Ausgaben
- menschlich pruefbare Ergebnisse

Wichtige Konsequenz:
Wenn Dokumente nur schlecht extrahierbar sind oder die Quellenlage duenn ist, darf die Analyse keine Sicherheit vortaeuschen. In solchen Faellen muss die Ausgabe Unsicherheit explizit markieren.

### Ausgabeformate

Das Modul sollte mehrere Ausgabeschichten beherrschen:

- lesbarer Markdown-Bericht fuer Sichtung und Review
- strukturierte JSON-Ausgabe fuer Weiterverarbeitung
- Quellenliste mit Dokumentreferenzen
- spaeter optional exportierbare Artefakte fuer GUI, API oder Redaktion

## 2. Mehrere Analysemodi fuer Dokumente, TOPs und ganze Sitzungen

Task 4 soll nicht nur eine einzige Analyseform liefern. Stattdessen braucht es mehrere Modi und Analyseebenen.

### Dokumentebene

Moegliche Ziele:

- kurzes Inhaltsprofil eines einzelnen Dokuments
- Hinweise auf Beschluss, Finanzierung, Zustaendigkeit oder offene Fragen
- Qualitaetseinschaetzung der Extraktion

### TOP-Ebene

Diese Ebene ist fuer die spaetere KI-Analyse besonders wichtig.

Empfohlener Standardfall:

- genau ein TOP wird analysiert
- alle zugeordneten Dokumente werden gebuendelt
- die KI erstellt daraus eine inhaltliche Zusammenfassung des TOPs

Typische Ausgabe fuer einen TOP:

- `top_summary`
- `decision_signal`
- `financial_signal`
- `public_relevance`
- `open_questions`
- `source_citations`
- `confidence`

### Sitzungsebene

Eine Sitzungsanalyse sollte nicht direkt aus allen Rohdokumenten auf einmal entstehen.
Sinnvoller ist:

1. einzelne TOPs analysieren
2. die Ergebnisse pruefen
3. daraus eine uebergeordnete Sitzungsverdichtung bauen

Das reduziert Halluzinationsrisiken und erhoeht die Nachvollziehbarkeit.

## 3. KI- und regelbasierte Verfahren kombinierbar machen

Task 4 soll einen echten Hybridansatz festlegen.

### Regelbasierte Aufgaben

Regeln sind sinnvoll fuer:

- Einlesen und Strukturieren von Metadaten
- Dokumenttyp-Erkennung
- Extraktionsqualitaet
- Maskierung sensibler Daten
- Vorfilterung unbrauchbarer Dokumente
- Hashing, Logging und Artefaktablage

### KI-basierte Aufgaben

Die eigentliche inhaltliche Analyse soll ueber KI laufen, insbesondere fuer:

- Zusammenfassung von PDF-Inhalten
- Zusammenfuehrung mehrerer Dokumente zu einem TOP
- Erkennen politischer Relevanz
- Formulierung verstaendlicher Ausgaben fuer unterschiedliche Zielgruppen
- spaetere sitzungsweite Verdichtung

### Austauschbare Schnittstellen

Die KI-Anbindung darf nicht direkt in GUI oder Einzelskripte verdrahtet werden.
Noetig ist eine austauschbare Schnittstelle mit klaren Ein- und Ausgaben.

Empfohlen wird eine Trennung in:

- lokale Vorbereitung des Analyse-Pakets
- Modell-Client oder Provider-Adapter
- standardisierte Antwortstruktur
- nachgelagerte Qualitaets- und Review-Schicht

### Empfohlene KI-Uebergabe pro TOP

Der wichtigste Zielpfad fuer Task 4 ist eine KI-Analyse pro TOP.

Ein geeignetes Eingabepaket sollte enthalten:

- `session_id`
- Datum
- Gremium
- `top_number`
- `top_title`
- Dokumentliste mit Titel, Typ, URL, Pfad und Qualitaetsstatus
- extrahierte Texte oder direkt uebergebene PDFs, sofern die Schnittstelle dies erlaubt

Die KI soll daraus fuer genau einen TOP eine belastbare Inhaltszusammenfassung erzeugen.

## 4. Reproduzierbarkeit, Quellenbezug und menschliche Nachpruefung

Task 4 ist nur sinnvoll, wenn Analyseergebnisse spaeter nachvollzogen werden koennen.

### Reproduzierbarkeit

Zu jeder Analyse sollen mindestens gespeichert werden:

- Analysemodus
- Eingabekontext
- verwendete Dokumente
- Dokument-Hashes
- Prompt oder Prompt-Version
- Modellname oder Provider
- Parameter der Ausfuehrung
- Zeitstempel

### Quellenbezug

Jede belastbare Aussage soll auf konkrete Quellen zurueckfuehrbar sein.
Das gilt besonders fuer spaetere KI-Ausgaben.

Mindesterwartung:

- Quelle pro Aussage oder Abschnitt nachvollziehbar
- Dokumentreferenzen sichtbar
- unklare oder unbelegte Aussagen markiert

### Menschliche Nachpruefung

Analyseergebnisse duerfen nicht als ungepruefte Endwahrheit behandelt werden.

Deshalb braucht Task 4:

- Draft-Status fuer neue Analysen
- sichtbare Unsicherheitsmarker
- Review-Moeglichkeit durch Menschen
- Freigabe oder Ablehnung mit Notizen

## Zielbild fuer den ersten sinnvollen Ausbau

Ein brauchbarer erster Ausbau von Task 4 waere erreicht, wenn:

- Analyseziele, Qualitaetskriterien und Ausgabeformate klar definiert sind
- mehrere Analysemodi fuer Dokument, TOP und Sitzung konzeptionell festgelegt sind
- eine austauschbare KI-Schnittstelle vorgesehen ist
- der Standardpfad fuer echte Inhaltsanalyse ueber KI pro TOP definiert ist
- Quellenbezug, Reproduzierbarkeit und Review verbindlich vorgesehen sind

## Offene Punkte

- Welche KI-Schnittstelle soll spaeter konkret angebunden werden?
- Soll die KI Texte, PDFs oder beides pro TOP erhalten?
- Welche Antwortstruktur ist fuer GUI und API gleichermassen tragfaehig?
- Welche Teile der Analyse bleiben lokal regelbasiert, welche gehen verpflichtend an die KI?
- Wie streng muessen Quellen- und Review-Regeln fuer spaetere Endnutzer-Ausgaben sein?
