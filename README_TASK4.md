# Task 4: Analysemodul entwickeln

Diese Datei beschreibt Task 4 aus `README.md` ausführlich. Das Analysemodul ist ein zentraler Hauptbestandteil des Projekts und soll bewusst so strukturiert werden, dass spaetere Funktionserweiterungen moeglich bleiben.

## Zielbild

Das Analysemodul soll Dokumente, Tagesordnungspunkte und ganze Sitzungen so auswerten, dass daraus nachvollziehbare, reproduzierbare und fuer unterschiedliche Zielgruppen nutzbare Ergebnisse entstehen.

Die Analyse soll nicht nur eine einzige Zusammenfassung erzeugen, sondern mehrere Modi unterstuetzen, die je nach Anwendungsfall aktiviert werden koennen.

## Leitprinzipien

- Faktentreue vor Sprachglanz
- klare Trennung zwischen Quelle, Extraktion, Analyse und Interpretation
- reproduzierbare Ergebnisse durch gespeicherte Parameter
- Kombination aus regelbasierten und KI-gestuetzten Verfahren
- erweiterbare Architektur fuer weitere Analysearten

## Analyseziele

Folgende Ergebnisarten sollten unterstuetzt werden:

- kurze neutrale Zusammenfassung
- ausfuehrliche Zusammenfassung
- strukturierte Extraktion relevanter Inhalte
- Beschlussanalyse
- Finanzanalyse
- Themenklassifikation
- Priorisierung politisch relevanter Dokumente
- Vergleich ueber Sitzungen oder Zeitraeume

## Empfohlene Analyseebenen

### 1. Dokumentanalyse

Ein einzelnes Dokument wird separat analysiert.

Typische Anwendungsfaelle:

- Vorlage zusammenfassen
- Beschlussvorlage in Kernaussagen zerlegen
- Protokoll-Auszug auf Entscheidungen pruefen

Typische Ausgaben:

- Worum geht es?
- Welche Entscheidung ist vorgesehen oder getroffen?
- Welche Kosten oder Risiken werden genannt?
- Welche Stellen oder Gremien sind betroffen?

### 2. TOP-Analyse

Alle Dokumente zu einem Tagesordnungspunkt werden zusammengefuehrt und gemeinsam bewertet.

Typische Anwendungsfaelle:

- Vorlage plus Anlagen plus spaeterer Beschluss
- verschiedene Dokumente zu einem einzigen Sachverhalt

Typische Ausgaben:

- Kernthema des TOP
- Beschlusslage
- offene Fragen
- Finanzbezug
- Unterschiede zwischen Vorlage und Beschluss

### 3. Sitzungsanalyse

Alle relevanten Dokumente einer Sitzung werden zu einer uebergeordneten Analyse verdichtet.

Typische Ausgaben:

- wichtigste Themen der Sitzung
- zentrale Entscheidungen
- oeffentlich relevante Punkte
- wiederkehrende Konfliktlinien
- offene Folgeaufgaben

### 4. Vergleichs- und Monitoringanalyse

Mehrere Sitzungen oder Dokumentstaende werden ueber Zeitraeume hinweg verglichen.

Typische Anwendungsfaelle:

- Thema ueber mehrere Monate verfolgen
- neue Beschluesse gegen fruehere Vorlagen vergleichen
- geaenderte Dokumente erkennen und hervorheben

Typische Ausgaben:

- was ist neu
- was hat sich geaendert
- welche Themen nehmen zu
- welche Entscheidungen wurden fortgeschrieben oder revidiert

## Empfohlene Analysemodi

Die folgenden Modi sind als erster sinnvoller Zielkatalog zu verstehen:

### `summary`

Kurze neutrale Zusammenfassung eines Dokuments, TOPs oder einer Sitzung.

### `decision_brief`

Fokus auf Beschlussinhalt, Entscheidung, Zustaendigkeit und naechste Schritte.

### `financial_impact`

Fokus auf Kosten, Finanzierung, Haushaltsbezug, Foerdermittel und Risiken.

### `citizen_explainer`

Leicht verstaendliche Erklaerung fuer Buergerinnen und Buerger ohne Fachsprache.

### `journalistic_brief`

Arbeitsmodus fuer journalistische Auswertung mit Kernaussagen, Konfliktlinien und offenen Fragen.

### `topic_classifier`

Thematische Einordnung, z. B. Verkehr, Schule, Haushalt, Bau, Soziales, Klima.

### `change_monitor`

Vergleich neuer Dokumente oder Sitzungen mit frueheren Staenden.

## Fachliche Analysearten

Unabhaengig vom Modus sollten folgende fachliche Perspektiven unterstuetzt werden:

- Zusammenfassung
- Beschlussanalyse
- Finanzanalyse
- Akteursanalyse
- Themenklassifikation
- Priorisierung
- Unsicherheits- und Lueckenhinweise

## Kombination von KI und Regeln

Ein rein KI-basiertes System ist fuer diesen Anwendungsfall nicht ideal. Sinnvoller ist ein Hybridansatz.

### Regelbasiert geeignet fuer

- Datum, Gremium, Dokumenttyp
- Beschlussformeln
- Finanzielle Schluesselwoerter
- strukturierte Kernfelder
- technische Vorfilterung

### KI geeignet fuer

- Verdichtung laengerer Inhalte
- Formulierung verschiedener Ausgabeformen
- thematische Einordnung
- Zusammenfuehrung mehrerer Dokumente
- Erkennen indirekter Zusammenhaenge

### Hybridmodus

Empfehlung:

- erst strukturierte Extraktion
- dann KI-Analyse auf basisbereinigtem Kontext
- danach Plausibilitaets- und Qualitaetspruefung

## Modell- und Schnittstellenstrategie

Das Analysemodul sollte mehrere Modelle oder Provider unterstuetzen koennen.

Moegliche Varianten:

- lokale Modelle fuer Datenschutz oder Offline-Betrieb
- API-basierte Modelle fuer hoehere Qualitaet
- kleine schnelle Modelle fuer Vorfilterung
- groessere Modelle fuer Endauswertung

Dafuer braucht es eine einheitliche Schnittstelle fuer:

- Eingabekontext
- Prompting
- Modellname
- Modellversion
- Antwortformat
- Fehlerbehandlung
- Logging

## Reproduzierbarkeit und Nachvollziehbarkeit

Zu jeder Analyse sollten mindestens gespeichert werden:

- Analysemodus
- Modellname
- Modellversion
- Prompt oder Prompt-Version
- Eingabedokumente
- Dokument-Hashes
- Analysezeitpunkt
- Parameter der Ausfuehrung

Ausgaben sollten moeglichst enthalten:

- Ergebnistext
- strukturierte Felder
- Quellenbezug
- Hinweise auf Unsicherheit

## Menschliche Nachpruefung

Analyseergebnisse sollen als bearbeitbare Arbeitsgrundlage dienen und nicht als unpruefbare Endwahrheit.

Deshalb sinnvoll:

- Ergebnisse als Entwurf kennzeichnen
- Belegstellen oder Kurzquellen ausgeben
- offene Fragen sichtbar machen
- unsichere Aussagen markieren
- Export fuer redaktionelle Nachbearbeitung erlauben

## Empfohlene Umsetzungsreihenfolge

### Phase 1

- Einzel-Dokumentanalyse
- neutrale Zusammenfassung
- Beschluss- und Finanzfokus

### Phase 2

- TOP-Analyse
- Zusammenfuehrung mehrerer Dokumente
- bessere Priorisierung

### Phase 3

- Sitzungsanalyse
- journalistischer Modus
- Buerger-Erklaermodus

### Phase 4

- Vergleichsanalyse
- Monitoring geaenderter oder neuer Dokumente
- automatisierte Benachrichtigung oder Warteschlangenlogik

## Offene Architekturfragen

- Welche Analyseergebnisse werden dauerhaft gespeichert?
- Welche nur on-demand erzeugt?
- Welche Modelle duerfen lokal laufen?
- Welche Ergebnisse muessen mit Quellenbeleg ausgegeben werden?
- Welche Modi kommen zuerst in die Developer-GUI?
- Welche Modi spaeter in die finale User-Oberflaeche?

## Definition of Done fuer einen ersten sinnvollen Meilenstein

Task 4 muss nicht komplett abgeschlossen sein, um nutzbar zu werden. Ein realistischer erster Meilenstein waere:

- einheitliche Analyse-Schnittstelle
- mindestens zwei Analysemodi
- Analyse auf Dokument- und TOP-Ebene
- Speicherung von Modell-, Prompt- und Kontext-Metadaten
- nachvollziehbare Ausgaben mit Quellenbezug
- Tests fuer Kernfluesse und Fehlerfaelle
