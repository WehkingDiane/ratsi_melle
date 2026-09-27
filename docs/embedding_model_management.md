# Konzept zur Embedding-Modellverwaltung

## Status und Zweck

Dieses Dokument beschreibt das Zielbild fuer die noch nicht implementierte
Verwaltung der lokalen Embedding-Modelle. Die zugehoerige konkrete Aufgabe steht
in [project_tasks.md](project_tasks.md#33-extraktion-ocr-und-suche).

Modellbeschaffung, Indexaufbau und Suche werden als getrennte Verantwortlichkeiten
behandelt. Ein bewusst ausgefuehrter Vorbereitungsschritt darf Modelle aus dem
Netz laden. Indexierung, Evaluation und Suche verwenden dagegen ausschliesslich
einen zuvor geprueften lokalen Modellbestand. Offlinebetrieb ist damit keine
optionale Schalterstellung des Indexers, sondern eine feste Architektureigenschaft.

## Ausgangslage

Der Vektorindex kombiniert derzeit:

- `microsoft/harrier-oss-v1-0.6b` fuer Dense-Embeddings und Tokenisierung
- `Qdrant/bm25` aus FastEmbed fuer Sparse-Vektoren
- Qdrant-Collections mit den benannten Vektoren `harrier` und `bm25`

Die Harrier-Modellbezeichnung ist an mehreren Stellen im Code hinterlegt. Der
Indexer fordert zwar lokale Dateien an, einzelne Bibliothekspfade koennen aber
trotzdem Hub-Metadaten abfragen. FastEmbed verwaltet zudem einen eigenen Cache.
Damit sind Modellidentitaet, Vollstaendigkeit und tatsaechlicher Offlinebetrieb
noch nicht als gemeinsamer Vertrag abgesichert.

Ein unbemerkter Wechsel der Modellrevision ist fachlich besonders riskant:
Neue Dokumente koennten mit einer anderen semantischen Repraesentation in eine
bestehende Collection geschrieben werden, ohne dass dies sofort sichtbar wird.

## Ziele

Die Umsetzung soll folgende Eigenschaften herstellen:

1. Eine einzige versionierte Konfiguration legt die erlaubten Modelle und exakten
   Revisionen fest.
2. Modellartefakte werden in einem ausdruecklichen Vorbereitungsschritt lokal
   bereitgestellt und geprueft.
3. Indexierung, Evaluation und Suche fuehren keine Modell-Netzwerkzugriffe aus.
4. Modellbestand, Pipeline und Qdrant-Index sind nachvollziehbar miteinander
   verknuepft.
5. Fehlende oder inkompatible Modelle werden in CLI und Weboberflaeche kurz und
   handlungsorientiert gemeldet.
6. Modellupdates erfolgen nur nach bewusster Auswahl, getrenntem Indexaufbau und
   Qualitaetsvergleich.

## Nicht-Ziele

Nicht Bestandteil dieses Umbaus sind:

- die Auswahl eines anderen oder groesseren Embedding-Modells
- eine freie Modellauswahl in der Weboberflaeche
- ein externer Embedding-API-Dienst
- automatische Modellupdates
- die automatische Aktivierung einer neu aufgebauten Qdrant-Collection
- ein Modellvergleich ohne den vorhandenen Recherchebenchmark

Das aktuell auf der vorhandenen Hardware nutzbare Harrier-Modell bleibt der
verbindliche Ausgangspunkt.

## Verantwortlichkeiten und Abhaengigkeitsrichtung

```text
src/config/embedding_models.py
        │ verbindliche IDs, Revisionen und Kompatibilitaet
        ▼
scripts/prepare_embedding_models.py ── optionaler Netz-Zugriff
        │ atomare Vorbereitung und Manifest
        ▼
data/models/
        │ ausschliesslich lokaler Lesezugriff
        ├──────────────► Indexer und Evaluation
        └──────────────► Websuche
                              │
                              ▼
                           Qdrant
                              │
                              ▼
                    Index-Kompatibilitaetsdaten
```

`prepare_embedding_models.py` ist kein Teilschritt eines normalen Vektor-Builds.
Ein Build oder eine Suchanfrage darf das Vorbereitungsskript weder direkt noch
indirekt starten.

## Verbindliche Modellkonfiguration

Die neue Datei `src/config/embedding_models.py` wird zur kanonischen Quelle fuer:

- Dense-Modell-ID und feste Hugging-Face-Revision
- Tokenizer-ID und feste Revision, falls vom Dense-Modell abweichend
- erwartete Dense-Vektordimension
- Sparse-Modell-ID und feste Revision
- erwartete relative Kernartefakte
- fachliche Pipeline-Version
- Manifestformat-Version

Revisionen werden als unveraenderliche Commit-Hashes gespeichert, nicht als
bewegliche Bezeichner wie `main`. Embedding-, Passage-, Evaluations- und Suchcode
importieren diese Definition, statt eigene Modellnamen zu fuehren.

Die Pipeline-Version bezeichnet ausschliesslich Aenderungen an Embedding,
Tokenisierung, Chunking oder Sparse-Verarbeitung, die erzeugte Indexdaten fachlich
veraendern koennen. Sie ist unabhaengig von der allgemeinen Anwendungsversion in
`VERSION`. Eine Aenderung der Weboberflaeche erfordert damit keinen Neuaufbau;
eine relevante Aenderung der Abschnittsbildung kann ihn dagegen erfordern.

## Laufzeitkonfiguration

`src/config/settings.py` enthaelt nur installationsbezogene Werte, insbesondere
den lokalen Modellstamm unter standardmaessig `data/models/` und gegebenenfalls
Timeouts des Vorbereitungsvorgangs. Eine Downloadfreigabe fuer Indexer oder Suche
ist nicht vorgesehen.

Der ausdrueckliche Aufruf von `prepare_embedding_models.py --download` ist selbst
die Downloadfreigabe. Eine allgemeine Einstellung wie
`INDEXER_ALLOW_MODEL_DOWNLOADS` soll nach der Umstellung entfallen.

Hugging-Face-Zugangsdaten bleiben in der vorhandenen Secret-Verwaltung. Weder
Modellkonfiguration noch Manifest speichern Tokens.

## Lokale Ablage und Manifest

Alle fuer den Betrieb benoetigten Dateien werden unter `data/models/` in stabilen,
revisionsbezogenen Verzeichnissen vorbereitet. Temporaere Downloads liegen nicht
am Zielpfad. Erst nach vollstaendiger Pruefung wird ein vorbereiteter Stand atomar
freigegeben, damit ein Abbruch keinen scheinbar gueltigen Modellbestand erzeugt.

Ein generiertes Manifest beschreibt mindestens:

- Manifestformat-Version
- Dense-, Sparse- und Tokenizer-ID
- jeweils konfigurierte und aufgeloeste Revision
- relative lokale Modellpfade
- erwartete Kernartefakte und Dateigroessen
- deterministisch ausgewaehlte SHA-256-Pruefsummen
- relevante Versionen von Transformers, Sentence Transformers, FastEmbed und
  Hugging Face Hub
- Erstellungszeitpunkt

Die Auswahl der gehashten Artefakte wird zentral definiert. Cache-Metadaten,
Lockdateien und andere fluechtige Bibliotheksdateien gehoeren nicht dazu. Der
Manifest-Hash wird aus einer kanonisch serialisierten Form ohne selbstbezogene
Hashfelder gebildet.

Es gibt zwei Pruefstufen:

1. Die normale lokale Pruefung validiert Manifestformat, Modellidentitaet,
   Revisionen, erwartete Pfade, Existenz und Dateigroessen. Sie darf keine
   Netzwerkverbindung aufbauen und soll schnell genug fuer Statusanzeigen sein.
2. Eine ausdrueckliche Tiefenpruefung berechnet die festgelegten SHA-256-Werte
   erneut. Grosse Gewichtsdateien werden nicht bei jedem Build- oder Suchstart
   vollstaendig gehasht.

## Vorbereitungsskript

Das neue Skript `scripts/prepare_embedding_models.py` bietet zunaechst:

```text
python scripts/prepare_embedding_models.py --check
python scripts/prepare_embedding_models.py --check --deep
python scripts/prepare_embedding_models.py --download
```

`--check` arbeitet garantiert offline. `--download` laedt ausschliesslich die in
`embedding_models.py` festgelegten Revisionen, prueft sie und schreibt danach das
Manifest. Bereits vollstaendig vorbereitete Artefakte werden wiederverwendet.

Eine spaetere Option `--check-updates` darf online ueber neuere Revisionen
informieren. Sie veraendert weder Modellkonfiguration noch lokalen Bestand und
laedt nichts herunter. Eine automatische Option `--update` ist nicht vorgesehen.

Das Skript liefert maschinenlesbare Statusdaten fuer die Weboberflaeche und kurze
menschenlesbare CLI-Meldungen. Erwartbare Fehler wie fehlendes Netz, unzureichender
Speicherplatz oder ein unvollstaendiger Download enden ohne langen Traceback;
technische Details werden strukturiert protokolliert.

## Vertrag fuer Indexierung, Evaluation und Suche

Folgende Pfade laden Modelle nur ueber die vorbereiteten lokalen Verzeichnisse:

- `scripts/build_vector_index.py`
- `scripts/build_landkreis_vector_index.py`
- `scripts/evaluate_search.py`
- semantische Suche in der Weboberflaeche
- gemeinsam verwendete Harrier- und BM25-Adapter unter `src/analysis/`

Bibliotheksaufrufe erhalten lokale Pfade und Offlineparameter. Die reine Angabe
einer Hub-Modell-ID reicht nicht aus, weil Bibliotheken dabei trotz vorhandenem
Cache Metadatenabfragen ausloesen koennen.

Vor dem Laden grosser Gewichte wird die normale Manifestpruefung ausgefuehrt.
Fehlt der lokale Bestand, lautet der Hinweis sinngemaess:

```text
ERROR: Lokales Embedding-Modell fehlt oder ist unvollstaendig.
Vorbereitung: python scripts/prepare_embedding_models.py --download
```

Eine Suchanfrage darf bei diesem Zustand keinen Download versuchen. Die
Weboberflaeche zeigt stattdessen den Modellstatus und einen Link zum technischen
Servicebereich.

## Qdrant- und Indexkompatibilitaet

Der fuer eine Collection freigegebene Indexstand enthaelt mindestens:

- Dense-Modell-ID und Revision
- Sparse-Modell-ID und Revision
- Tokenizer-Revision
- Manifest-Hash
- Vektordimension
- Pipeline-Version

Diese Angaben werden in den bestehenden Freigabe- beziehungsweise Buildmetadaten
und in den fuer die Nachvollziehbarkeit erforderlichen Punkt-Payloads gefuehrt.
Die konkrete Speicherung muss fuer lokalen und Serverbetrieb denselben
Kompatibilitaetsvertrag liefern.

Vor dem ersten Schreibzugriff vergleicht ein Builder den vorhandenen Indexstand
mit der aktiven Modellkonfiguration. Bei einer Abweichung darf er die Collection
nicht inkrementell erweitern. Er fordert einen vollstaendigen Neuaufbau oder eine
getrennte Aufbau-Collection an.

Ein Modellwechsel folgt spaeter diesem Ablauf:

1. neue Revision ausdruecklich in einer Testkonfiguration festlegen
2. Artefakte separat vorbereiten
3. getrennte Collection vollstaendig aufbauen
4. Suchbenchmark mit identischem Dokumentbestand ausfuehren
5. Laufzeit, Speicherbedarf und Ergebnisqualitaet vergleichen
6. neue Konfiguration und Collection bewusst freigeben

## Einbindung in die Service-Oberflaeche

Die Modellverwaltung wird im technischen Servicebereich bei den
Vektorindex-Funktionen unter `/daten/vektor/` ergaenzt. Sie verwendet die
bestehende Servicejob-Infrastruktur und fuehrt keine Modelllogik im Django-View
selbst aus.

Die Seite zeigt fuer Harrier, Tokenizer und BM25 mindestens:

- Status `bereit`, `fehlt`, `unvollstaendig` oder `inkompatibel`
- konfigurierte Revision
- lokal vorbereitete Revision
- lokalen Speicherbedarf, soweit ohne Netz bestimmbar
- Zeitpunkt und Ergebnis der letzten Pruefung

Vorgesehene Aktionen:

1. **Lokal pruefen** startet `--check` als Servicejob ohne Netzwerkzugriff.
2. **Modelle vorbereiten** startet nach ausdruecklicher Bestaetigung `--download`
   fuer die fest konfigurierten Revisionen.
3. Eine spaetere reine Updateauskunft kann `--check-updates` starten, bleibt aber
   klar von Download und Konfigurationsaenderung getrennt.

Die Oberflaeche bietet zunaechst keine Eingabefelder fuer Modell-ID, Revision,
Zielpfad oder zusaetzliche Kommandoargumente. Servicebefehle entstehen
serverseitig aus einer festen Aktionsliste. Schreibende Aktionen verwenden POST
und den vorhandenen CSRF-Schutz.

Pruefung und Download erscheinen mit Fortschritt, Ausgabe und Abschlussstatus auf
der vorhandenen Jobdetailseite. Modellvorbereitung und Vektor-Builds, die dieselben
Artefakte verwenden, werden gegen kollidierende parallele Ausfuehrung geschuetzt
oder sicher serialisiert.

Der optionale Hugging-Face-Token aus der Secret-Verwaltung darf an den
Vorbereitungsprozess weitergegeben werden. Er darf weder in Kommandodarstellung,
Jobausgabe, Statusantworten noch Logs erscheinen.

## Fehler- und Statusmodell

CLI und Web unterscheiden mindestens:

- Modellbestand vollstaendig und kompatibel
- Modell oder Tokenizer fehlt
- Manifest fehlt oder ist unlesbar
- Artefakt ist unvollstaendig oder bei Tiefenpruefung beschaedigt
- vorbereitete Revision weicht von der Konfiguration ab
- Bibliotheksversion ist nach dem definierten Vertrag inkompatibel
- Downloadquelle ist nicht erreichbar
- lokaler Speicher reicht fuer die Vorbereitung nicht aus
- Vorbereitung oder Build ist bereits aktiv

Nur das Vorbereitungsskript meldet Netzwerkfehler von Modellquellen. Indexer und
Suche kennen keinen Modell-Onlinepfad und melden daher ausschliesslich den lokalen
Vorbereitungszustand.

## Tests und Abnahme

Die Umsetzung ist abgeschlossen, wenn folgende Eigenschaften automatisiert
abgesichert sind:

1. Die zentrale Konfiguration ist die einzige Quelle fuer Modell-IDs und
   Revisionen.
2. `--check` funktioniert mit gesperrtem Netzwerk und veraendert keine Dateien.
3. `--download` fordert nur konfigurierte, fest gepinnte Revisionen an und gibt
   erst einen vollstaendigen Bestand frei.
4. Indexierung, Evaluation und Websuche funktionieren mit vorbereiteten Modellen
   ohne Internetzugang. Tests lassen unerwartete Hub-Aufrufe gezielt fehlschlagen.
5. Fehlende oder beschaedigte Artefakte erzeugen in CLI und Web eine kurze,
   handlungsorientierte Meldung.
6. Harrier, Tokenizer und BM25 werden gemeinsam validiert.
7. Ein inkompatibler Modell- oder Pipelinestand verhindert Schreibzugriffe auf
   eine bestehende Collection.
8. Servicebefehle sind fest vorgegeben; Tests decken unzulaessige Parameter,
   CSRF-Schutz, Secret-Redaktion, Statusdarstellung und Servicejobs ab.
9. Parallele kollidierende Vorbereitungs- und Buildlaeufe koennen keinen
   freigegebenen Modellbestand beschaedigen.
10. README, `docs/search_quality.md`, `docs/web_ui.md`, Datenverarbeitungskonzept
    und Betriebsanleitungen beschreiben nach der Umsetzung den tatsaechlichen
    Ablauf.

Live-Downloads werden nur in ausdruecklich markierten Live-Tests ausgefuehrt. Die
regulaere Test- und Integrationssuite verwendet temporaere Modellverzeichnisse,
kleine kontrollierte Artefakte und blockierte Netzwerkzugriffe.

## Fortschreibbarer Umsetzungsplan

Diese Checkliste ist zugleich die Uebergabe zwischen Arbeitslaeufen. Der erste
nicht abgehakte Punkt ist der regulaere Wiedereinstieg. Ein Punkt wird erst als
erledigt markiert, wenn Implementierung, zugehoerige Tests und notwendige
Dokumentation gemeinsam vorliegen. Nach jeder Phase soll ein kleiner,
zusammenhaengender Commit erstellt werden.

Wenn ein Lauf wegen eines Kontext-, Zeit- oder Nutzungslimits unterbrochen wird,
soll vor dem Ende soweit noch moeglich der Abschnitt **Aktuelle Uebergabe**
aktualisiert werden. Angefangene, aber nicht vollstaendig verifizierte Punkte
bleiben unabgehakt und werden dort beschrieben.

### Phase 1: Vertrag und zentrale Konfiguration

- [ ] **M1.1** Bestehende Modellnamen, Revisionen, Dimensionen, Cachepfade und
  Pipelinekennzeichen vollstaendig inventarisieren.
- [ ] **M1.2** `src/config/embedding_models.py` mit unveraenderlichen, typisierten
  Definitionen fuer Harrier, Tokenizer und BM25 einfuehren.
- [ ] **M1.3** Feste bekannte Revisionen ermitteln und dokumentieren; bewegliche
  Referenzen wie `main` aus der produktiven Konfiguration ausschliessen.
- [ ] **M1.4** Pipeline-Version und Manifestformat-Version fachlich definieren.
- [ ] **M1.5** Manifest-Schema, kanonische Serialisierung und deterministische
  Auswahl relevanter Pruefsummen implementieren.
- [ ] **M1.6** Unit-Tests fuer Konfiguration, Schema, Manifest-Hash und unzulaessige
  Modellangaben ergaenzen.
- [ ] **M1.7** Phase 1 pruefen und als eigenen Zwischenstand committen.

### Phase 2: Lokaler Modellstatus

- [ ] **M2.1** Zentralen Pfad fuer `data/models/` in der Laufzeitkonfiguration
  bereitstellen, ohne eine Downloadfreigabe fuer Verbraucher einzufuehren.
- [ ] **M2.2** Schnelle lokale Pruefung fuer Manifest, Revisionen, Pfade,
  Dateiexistenz und Groessen implementieren.
- [ ] **M2.3** Optionale Tiefenpruefung der festgelegten SHA-256-Werte
  implementieren.
- [ ] **M2.4** Gemeinsames Statusmodell `bereit`, `fehlt`, `unvollstaendig` und
  `inkompatibel` fuer CLI und Web definieren.
- [ ] **M2.5** Tests mit temporaeren vollstaendigen, fehlenden, beschaedigten und
  revisionsfremden Modellbestaenden ergaenzen.
- [ ] **M2.6** Nachweisen, dass beide Pruefstufen ohne Netzwerkzugriff arbeiten.
- [ ] **M2.7** Phase 2 pruefen und als eigenen Zwischenstand committen.

### Phase 3: Vorbereitungsskript

- [ ] **M3.1** `scripts/prepare_embedding_models.py --check` auf die gemeinsame
  lokale Prueflogik aufsetzen.
- [ ] **M3.2** `--check --deep` mit eindeutiger, maschinenlesbarer und
  menschenlesbarer Ausgabe ergaenzen.
- [ ] **M3.3** `--download` fuer ausschliesslich fest konfigurierte Revisionen
  implementieren.
- [ ] **M3.4** Download in ein temporaeres Ziel, Vollstaendigkeitspruefung und
  atomare Freigabe unter `data/models/` implementieren.
- [ ] **M3.5** Wiederaufnahme beziehungsweise sichere Wiederverwendung bereits
  vollstaendiger Artefakte festlegen.
- [ ] **M3.6** Erwartbare Fehler fuer Netz, Speicherplatz und unvollstaendige
  Artefakte ohne langen CLI-Traceback behandeln.
- [ ] **M3.7** Tokenweitergabe und Log-Redaktion mit Tests absichern.
- [ ] **M3.8** Downloadtests ohne echten Hub sowie getrennte, markierte Live-Tests
  fuer den realen Anbieter ergaenzen.
- [ ] **M3.9** Phase 3 pruefen und als eigenen Zwischenstand committen.

### Phase 4: Verbraucher strikt lokal umstellen

- [ ] **M4.1** Harrier-Embedder und Tokenizer auf vorbereitete lokale Pfade und
  feste Revisionen umstellen.
- [ ] **M4.2** BM25/FastEmbed auf den vorbereiteten lokalen Bestand umstellen.
- [ ] **M4.3** Doppelte Modelldefinitionen aus Passage-, Embedding-, Evaluations-
  und Suchcode entfernen.
- [ ] **M4.4** `INDEXER_ALLOW_MODEL_DOWNLOADS` und andere Modell-Downloadpfade aus
  Indexierung und Suche entfernen.
- [ ] **M4.5** Vor Modellinitialisierung die schnelle lokale Manifestpruefung und
  handlungsorientierte Fehlermeldungen integrieren.
- [ ] **M4.6** Offline-Tests fuer Ratsinfo-Build, Landkreis-Build, Evaluation und
  Websuche ergaenzen; unerwartete Hub-Aufrufe muessen die Tests fehlschlagen
  lassen.
- [ ] **M4.7** Phase 4 pruefen und als eigenen Zwischenstand committen.

### Phase 5: Indexkompatibilitaet

- [ ] **M5.1** Kompatibilitaetsdatensatz aus Modell-IDs, Revisionen,
  Manifest-Hash, Dimension und Pipeline-Version zentral erzeugen.
- [ ] **M5.2** Lokale und serverbezogene Qdrant-Freigabemetadaten um diesen
  Datensatz erweitern.
- [ ] **M5.3** Erforderliche Modell- und Pipelineangaben in Punkt-Payloads fuer
  Ratsinfo- und Landkreis-Collections konsistent hinterlegen.
- [ ] **M5.4** Kompatibilitaetspruefung vor dem ersten Schreibzugriff eines Builds
  durchsetzen.
- [ ] **M5.5** Inkompatible inkrementelle Fortsetzung mit kurzer Meldung und
  Hinweis auf Neuaufbau beziehungsweise Aufbau-Collection verhindern.
- [ ] **M5.6** Migrations-, Abbruch- und Wiederanlauftests fuer kompatible und
  inkompatible Indexstaende ergaenzen.
- [ ] **M5.7** Phase 5 pruefen und als eigenen Zwischenstand committen.

### Phase 6: Service-Oberflaeche

- [ ] **M6.1** Modellstatus in die Service-Fassade und Statusantworten des
  Datenbereichs aufnehmen.
- [ ] **M6.2** Statusdarstellung fuer Harrier, Tokenizer und BM25 unter
  `/daten/vektor/` ergaenzen.
- [ ] **M6.3** Feste Serviceaktion fuer die rein lokale Pruefung implementieren.
- [ ] **M6.4** Feste, bestaetigungspflichtige Serviceaktion fuer die Vorbereitung
  der konfigurierten Revisionen implementieren.
- [ ] **M6.5** Freie Modell-IDs, Revisionen, Zielpfade und zusaetzliche
  Kommandoargumente in Formular und Command Builder ausschliessen.
- [ ] **M6.6** Fortschritt und Ergebnis ueber die bestehende Servicejob- und
  Jobdetail-Infrastruktur anzeigen.
- [ ] **M6.7** Kollidierende parallele Modellvorbereitungen und Vektor-Builds
  verhindern oder sicher serialisieren.
- [ ] **M6.8** CSRF-Schutz, Befehls-Allowlist, Secret-Redaktion, Statuswerte und
  Jobstart mit Web- und Service-Tests absichern.
- [ ] **M6.9** Phase 6 pruefen und als eigenen Zwischenstand committen.

### Phase 7: Gesamtabnahme und Dokumentation

- [ ] **M7.1** Regulaere Unit-Tests und betroffene Integrationstests ausfuehren.
- [ ] **M7.2** Einen vollstaendigen vorbereiteten Offline-Build ohne Internet
  sowie die anschliessende Suche praktisch pruefen.
- [ ] **M7.3** Verhalten bei fehlendem Modell, unerreichbarer Downloadquelle,
  inkompatiblem Index und parallelem Job praktisch pruefen.
- [ ] **M7.4** README, `docs/search_quality.md`, `docs/web_ui.md`,
  `docs/data_processing_concept.md` und betroffene Betriebsanleitungen an den
  tatsaechlichen Stand anpassen.
- [ ] **M7.5** Versionsanpassung bewusst entscheiden und Releaseauswirkungen
  dokumentieren.
- [ ] **M7.6** Gesamtdiff, Sicherheitsgrenzen, Offlinegarantie und
  Abnahmekriterien abschliessend pruefen.
- [ ] **M7.7** Abschluss committen und diese Aufgabe in `project_tasks.md` als
  erledigt kennzeichnen oder entfernen.

## Aktuelle Uebergabe

- Letzter abgeschlossener Punkt: keiner; bisher liegt nur das Konzept vor.
- Naechster regulaerer Punkt: **M1.1**.
- Aktiver Implementierungsstand: keiner.
- Letzter zugehoeriger Commit: noch keiner.
- Offene Blocker oder Entscheidungen: keine; konkrete bekannte Modellrevisionen
  muessen in **M1.3** aus den vorhandenen lokalen Artefakten beziehungsweise der
  Modellquelle verifiziert werden.
