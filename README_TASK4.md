# Task 4: Analysemodul entwickeln - sichere KI

Dieses Dokument beschreibt den Task 4 der Projekt-Roadmap des Ratsinformations-Analysewerkzeugs. Ziel dieses Meilensteins ist der Entwurf und die Implementierung eines modularen Analysemoduls, das Dokumente, Tagesordnungspunkte und ganze Sitzungen auswertet und zuverlässige, reproduzierbare Ergebnisse liefert. Im Vergleich zur ursprünglichen Fassung legt diese Version besonderen Wert auf Datensicherheit, Transparenz und Risiko-Management, damit der Einsatz von KI vertrauenswürdig und nachvollziehbar bleibt.

Der aktuelle GUI-Bezug in diesem Dokument meint die vorhandene Developer-GUI fuer interne Workflows. Eine finale Endnutzer-GUI ist noch nicht begonnen beziehungsweise nicht fertig. Auch die langfristige Code- bzw. Technologiesprache des Gesamtprojekts bleibt derzeit offen.

## Umsetzungsstand (2026-03-13)

- Umgesetzt:
  - Einheitliche Analyse-API mit `AnalysisRequest`, `AnalysisService` und versioniertem `AnalysisOutputRecord`.
  - Analysemodi `summary`, `decision_brief` und `financial_impact` fuer Dokument- und TOP-nahe Ausgaben produktiv nutzbar.
  - Zusaetzliche Modi `journalistic_brief`, `citizen_explainer` und `topic_classifier` in der Developer-GUI freigeschaltet.
  - Audit-Trail erweitert um Modus, Parameter, Prompt-Version, Modellname und Dokument-Hashes.
  - Sicherheitsmechanismen fuer sensible Daten sowie Unsicherheits-, Plausibilitaets- und Bias-/Balance-Signale im Output.
  - Menschliche Review-Funktion in Developer-GUI und CLI (`scripts/review_analysis_job.py`).
  - TOP-Analyse mit Gruppierung pro Tagesordnungspunkt, Themenhinweisen und Inkonsistenz-Markierungen.
  - Lokaler Vorbereitungsbericht fuer `journalistic_brief` mit Konflikthinweisen, Datenluecken und Nachrecherchebedarf.
  - Erster Monitoring-Modus `change_monitor` mit Aenderungssignalen, Vorversionsvergleich und Beobachtungsbedarf im Scope.
- Noch offen:
  - Weitergehende inhaltliche Bias-Metriken und strengere Fachregeln fuer spaetere Modi.
  - Echte KI-gestuetzte redaktionelle Verdichtung mit Dokumentuebergabe, Quellenpflicht und belastbaren Belegausgaben.
  - Breitere Zeitreihen- und Benachrichtigungslogik ueber mehrere Sitzungen hinweg.

## 1 Zielbild

Das Analysemodul soll strukturierte Informationen aus dem Ratsinformationssystem in mehreren Analyseebenen aufbereiten (Dokument, TOP, Sitzung, Vergleich). Unterschiedliche Zielgruppen (Journalist:innen, Bürger:innen, Ratsmitglieder) sollen Ergebnisse in passender Detailtiefe erhalten: von kurzen neutralen Zusammenfassungen über finanzielle Bewertungen bis hin zu thematischen Klassifikationen. Alle Analysen müssen nachvollziehbar, faktentreu und quellenbasiert sein.

## 2 Leitprinzipien

- Faktentreue vor Sprachglanz. Analyseergebnisse müssen sich strikt an den Inhalten der zugrunde liegenden Dokumente orientieren. Halluzinationen sind zu kennzeichnen und zu minimieren.
- Klare Trennung von Quelle, Extraktion, Analyse und Interpretation. Rohdaten und extrahierte Metadaten werden separat gespeichert. Analyse- und Interpretationsschritte operieren ausschließlich auf dieser strukturierten Basis.
- Reproduzierbarkeit und Auditierbarkeit. Jede Analyse speichert den vollständigen Eingabekontext, verwendete Modelle, Prompt-Versionen, Ausführungsparameter und Hashes der Eingangsdokumente. Dadurch können Ergebnisse jederzeit nachgestellt und überprüft werden.
- Hybridansatz aus Regeln und KI. Strukturelle Informationen wie Datum, Gremium, Dokumenttyp oder finanzielle Kennzahlen werden regelbasiert extrahiert. KI-Modelle kommen erst im zweiten Schritt für Verdichtung, thematische Einordnung und Verknüpfung zum Einsatz.
- Sicherheits- und Risiko-Management. Datenschutz, Bias-Kontrolle, Erklärbarkeit und menschliche Überprüfbarkeit sind integrale Bestandteile des Designs. Analysen werden als „Entwürfe“ gekennzeichnet, bis sie durch Review freigegeben sind.
- Erweiterbarkeit. Die Architektur muss neue Analysemodi, zusätzliche Datenquellen und unterschiedliche KI-Modelle (lokal, API-basiert, verschiedene Größen) aufnehmen können.

## 3 Analyseziele

Folgende Ergebnisarten sollten unterstützt werden:

- Kurze neutrale Zusammenfassung - faktenbasierte Kurzfassung eines Dokuments oder TOPs.
- Ausführliche Zusammenfassung - detaillierte Darstellung für Fachpublikum.
- Strukturierte Extraktion relevanter Inhalte - z. B. Akteur:innen, Beträge, Fristen.
- Beschlussanalyse - Darstellung des Beschlusses, Verantwortlichkeiten und Folgeschritte.
- Finanzanalyse - Herausarbeitung von Kosten, Finanzierung, Fördermitteln und Risiken.
- Themenklassifikation und Priorisierung - Zuordnung zu Themenfeldern (Verkehr, Soziales usw.) und Bewertung der politischen Relevanz.
- Vergleichs- und Monitoringanalysen - Analyse von Entwicklungen über mehrere Sitzungen oder Zeiträume.

## 4 Analyseebenen

### 4.1 Dokumentanalyse

Ein einzelnes Dokument wird isoliert betrachtet. Typische Anwendungsfälle: Zusammenfassung einer Vorlage, Zerlegung einer Beschlussvorlage in Kernaussagen oder Prüfung eines Protokollauszugs auf getroffene Entscheidungen. Zusätzlich müssen sensible Daten erkannt und anonymisiert werden, und das System soll auf Unsicherheiten oder fehlende Informationen hinweisen.

### 4.2 TOP-Analyse

Alle Dokumente zu einem Tagesordnungspunkt werden gemeinsam analysiert. Über die bisherigen Ziele hinaus sollten Inkonsistenzen zwischen Vorlage und Beschluss markiert und Risiken hervorgehoben werden.

### 4.3 Sitzungsanalyse

Die Gesamtheit der relevanten Dokumente einer Sitzung wird zunaechst lokal zu einem Vorbereitungsbericht verdichtet. Dieser Bericht markiert Themen, Konflikthinweise, Datenluecken und Nachrecherchebedarf. Eine spaetere KI-Verdichtung darf erst auf dieser qualitaetsgeprueften Dokumentbasis aufsetzen und muss jede belastbare Aussage mit Quellenbezug ausgeben.

### 4.4 Vergleichs- und Monitoringanalyse

Mehrere Sitzungen oder Dokumentstände werden über Zeiträume hinweg verglichen. Zusätzlich sollen Trends, Versionen und potenzielle Bias-Verschiebungen erkannt werden.

## 5 Analysemodi

Um die Analyseziele abzudecken, werden verschiedene Modi definiert:

- `summary` - neutrale Kurzfassung mit Quellenangaben.
- `decision_brief` - Fokus auf Beschlussinhalt, Zuständigkeit und nächste Schritte.
- `financial_impact` - Analyse von Kosten, Finanzierung, Haushalt, Fördermitteln und Risiken.
- `citizen_explainer` - leicht verständliche Erklärungen ohne Fachsprache.
- `journalistic_brief` - lokaler Vorbereitungsbericht als KI-Platzhalter; keine fertige journalistische Analyse.
- `topic_classifier` - thematische Einordnung.
- `change_monitor` - Vergleich neuer Dokumente mit früheren Ständen.

Jeder Modus definiert klar, welche Eingaben er benötigt und welche strukturierten Felder er ausgibt; weitere Modi lassen sich später ergänzen.

## 6 Fachliche Analysearten

Unabhängig vom Modus werden diese Perspektiven unterstützt: Zusammenfassung, Beschlussanalyse, Finanzanalyse, Akteursanalyse, Themenklassifikation, Priorisierung und Hinweise auf Unsicherheiten/Halluzinationen.

## 7 Sicherer Einsatz von KI

### 7.1 Regelbasiert vs. KI

Ein reines KI-System ist ungeeignet. Daher gelten:

- Regelbasierte Vorverarbeitung: Extraktion von Datum, Gremium, Dokumenttyp, finanziellen Schlüsselwörtern usw.; Anonymisierung sensibler Daten.
- KI-gestützte Verdichtung: Erst danach werden längere Inhalte durch Modelle verdichtet oder klassifiziert.
- Plausibilitäts- und Qualitätskontrolle: Nach der KI-Analyse Abgleich mit den extrahierten Fakten; Widersprüche werden markiert und dem/der Reviewer:in angezeigt.

### 7.2 Modell- und Schnittstellenstrategie

Eine einheitliche API kapselt den Umgang mit Modellen: Eingabekontext, Prompt, Modellname/-version, definierte Antwortformate, Fehler-/Bias-Handling und Logging sind standardisiert. So lässt sich flexibel zwischen lokalen und externen Modellen wählen.

### 7.3 Reproduzierbarkeit und Auditierbarkeit

Bei jeder Analyse werden Analysemodus, Prompt-Version, Modellname/-version, Parameter, Zeitstempel, Hashes der Dokumente und der vollständige Prompt gespeichert. Ergebnisse enthalten strukturierte Felder, Quellenverweise, Unsicherheitsmarkierungen und Reviewer-Metadaten.

### 7.4 Menschliche Nachprüfung und Feedback

Analyseergebnisse sind stets als Entwurf zu kennzeichnen. Reviewer:innen sehen Belegstellen, Unsicherheitsmarker und offene Fragen, können Kommentare hinterlassen, Korrekturen vornehmen und die Veröffentlichung freigeben.

## 8 Empfohlene Umsetzungsreihenfolge

- Phase 1 - Basismodule: erledigt.
  Analyse-Schnittstelle, Datenmodelle, Audit-Trail, Sicherheitsmechanismen und die Modi `summary`, `decision_brief` und `financial_impact` sind vorhanden.
- Phase 2 - TOP-Analyse und Priorisierung: weitgehend erledigt.
  Mehrere Dokumente pro TOP werden zusammengefuehrt, `citizen_explainer` und `topic_classifier` sind verfuegbar, Inkonsistenzen werden markiert.
- Phase 3 - Sitzungsanalyse und KI-gestuetzte redaktionelle Perspektive: teilweise erledigt.
  Ein lokaler Vorbereitungsbericht fuer `journalistic_brief` ist vorhanden; die eigentliche KI-gestuetzte redaktionelle Verdichtung mit Dokumentuebergabe steht noch aus.
- Phase 4 - Vergleichs- und Monitoringanalysen: offen.
  Ein erster `change_monitor` mit Vorversionsvergleich ist vorhanden; tiefere Zeitreihen-, Versions- und Benachrichtigungslogik stehen noch aus.

## 9 Offene Architekturfragen

- Welche Analyseergebnisse werden dauerhaft gespeichert und welche nur on-demand erzeugt?
- Wie werden Bias-Erkennung und Qualitätsmetriken integriert?
- Welche Modelle dürfen lokal ausgeführt werden; wann darf externe KI genutzt werden? Welche Datenschutz- und Lizenzanforderungen gelten?
- Welche Ergebnisse müssen zwingend mit Quellenbeleg ausgegeben werden und wie werden sie im GUI dargestellt?
- Welche Analysemodi kommen zuerst in die Developer-GUI; welche später in die Endnutzer-Oberfläche?

## 10 Definition of Done (erster Meilenstein)

Ein erster nutzbarer Meilenstein umfasst:

- Einheitliche Analyse-API mit Audit-Trail, Logging und nachvollziehbaren Artefakten: erreicht.
- Mehrere Analysemodi fuer Dokumentanalyse (`summary`, `decision_brief`, `financial_impact`): erreicht.
- Nachvollziehbare Ergebnisse mit Quellenbezug, strukturierten Feldern und Qualitaetssignalen: erreicht.
- Speicherung von Modell-, Prompt- und Review-Metadaten wie in Abschnitt 7.3: erreicht.
- Sicherheitsmechanismen zum Maskieren personenbezogener Daten sowie Halluzinations-/Plausibilitaetsindikatoren: erreicht.
- Unit-Tests fuer Kernfluesse und Fehlerfaelle: erreicht.
- Menschliche Review-Funktion in Developer-GUI oder CLI: erreicht.

Der erste Meilenstein kann damit als funktional erreicht gelten. Die naechsten Arbeiten betreffen vor allem KI-gestuetzte Verdichtung auf Dokumentbasis, sitzungsweite Vorbereitung und Monitoring.
