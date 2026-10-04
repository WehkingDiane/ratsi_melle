# Konzept zur Embedding-Modellverwaltung

## Status und Zweck

Dieses Dokument beschreibt das Zielbild fuer die schrittweise implementierte
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

## Inventur des bestehenden Modellvertrags (M1.1)

Stand der Inventur: 27. September 2026. Erfasst wurde der produktive Code samt
Build- und Evaluationsskripten, Tests, Laufzeitkonfiguration und vorhandener
lokaler Modellablage. Die Inventur beschreibt bewusst den Ist-Zustand vor der
Zentralisierung in M1.2.

### Modelle, Revisionen und Dimensionen

| Bestandteil | Bestehende Definition und Verbraucher | Revision | Dimension beziehungsweise Ausgabe |
| --- | --- | --- | --- |
| Dense-Modell | `microsoft/harrier-oss-v1-0.6b` in `src/analysis/embeddings.py` sowie nochmals in `src/indexing/passages.py`; verwendet von beiden Vektor-Builds, Evaluation und Websuche | nicht angegeben; der Bibliotheksstandard ist damit eine bewegliche Referenz | 1024, separat als `_EMBEDDING_DIM` in `src/analysis/vector_store.py` hinterlegt |
| Tokenizer | dieselbe Harrier-ID aus `src/indexing/passages.py`, direkt durch `AutoTokenizer.from_pretrained` in `src/indexing/passage_builder.py` geladen | nicht angegeben; der zur Laufzeit aufgeloeste `_commit_hash` fliesst nur in den Passage-Fingerprint ein | keine Vektordimension; Abschnittsstandard 768 Tokens mit 96 Tokens Ueberlappung |
| Sparse-Modell | `Qdrant/bm25` in `src/analysis/bm25_sparse.py`; verwendet von beiden Vektor-Builds, Evaluation und Websuche | nicht angegeben und nicht in Payloads oder Freigabedaten erfasst | sparse Indizes und Werte ohne feste Dimension im Qdrant-Schema |

Harrier-Dokumente werden ohne Instruktion eingebettet. Suchanfragen erhalten den
festen Praefix `Instruct: Retrieve semantically similar municipal council
documents\nQuery: `. Dense-Vektoren werden normalisiert. Diese beiden Parameter
sind ebenfalls fachlich indexrelevant, besitzen derzeit aber kein eigenes
Pipelinekennzeichen.

### Cache- und Offlinepfade

- `src/paths.py` definiert `MODELS_DIR` als `data/models/`. Der Pfad wird von den
  Modell-Ladern noch nicht verwendet; lokal liegt dort nur `.gitkeep`.
- `SentenceTransformer` erhaelt weder einen lokalen Modellpfad noch `cache_folder`
  oder eine Revision. Harrier und seine Tokenizer-Abhaengigkeiten verwenden daher
  den impliziten Hugging-Face-Cache. Dessen Bibliotheksstandard ist
  `$HF_HUB_CACHE`, andernfalls `$HF_HOME/hub` und schliesslich typischerweise
  `~/.cache/huggingface/hub`.
- Der Passage-Tokenizer erhaelt ebenfalls nur die Hub-ID und
  `local_files_only=not INDEXER_ALLOW_MODEL_DOWNLOADS`, aber weder Revision noch
  expliziten Cachepfad.
- `SparseTextEmbedding` erhaelt nur `model_name="Qdrant/bm25"`. `cache_dir`,
  `specific_model_path` und `local_files_only` werden nicht gesetzt; Speicherort
  und ein moeglicher Download folgen damit vollstaendig dem FastEmbed-Standard.
- `INDEXER_ALLOW_MODEL_DOWNLOADS` ist in `src/config/settings.py` fest auf
  `False` gesetzt und wirkt auf Harrier und den Passage-Tokenizer. BM25 beachtet
  diesen Schalter nicht. Globale Offlinevariablen wie `HF_HUB_OFFLINE` werden vom
  Projekt nicht gesetzt.
- Ein optionaler Hugging-Face-Token wird vor dem Laden von Harrier aus Keyring
  beziehungsweise `HF_TOKEN` oder `HUGGING_FACE_HUB_TOKEN` bezogen. Er bestimmt
  keine Modellidentitaet und keinen Cachepfad.

Die lokale Arbeitskopie enthaelt weder vorbereitete Artefakte unter
`data/models/` noch ein Modellmanifest. Vorhandene benutzerspezifische
Bibliothekscaches sind deshalb kein versionierter oder projektweit pruefbarer
Bestand.

### Pipeline- und Indexkennzeichen

| Kennzeichen | Ist-Zustand |
| --- | --- |
| Passage-Pipeline | `PIPELINE_VERSION = "passages-1"` in `src/indexing/passages.py` |
| Legacy-Evaluation | nur der Berichtswert `legacy-10-pages` in `scripts/evaluate_search.py` |
| Collections | `ratsi_passages`, Legacy `ratsi_documents` und `landkreis_publications` |
| Qdrant-Vektornamen | `harrier` fuer Dense- und `bm25` fuer Sparse-Vektoren |
| Passage-Payload | enthaelt Harrier-ID als `model`, `passages-1` als `pipeline_version` und einen Fingerprint mit dem zur Laufzeit aufgeloesten Tokenizer-Commit |
| Freigabemarker | enthaelt fuer `ratsi_passages` aktuell nur `model` und `pipeline_version`; im Serverbetrieb zusaetzlich URL-Hash und Punktanzahl |
| Legacy- und Landkreis-Payloads | enthalten keine Modell-ID, Modellrevision, Tokenizer-Revision oder Pipeline-Version |

Damit fehlen im bestehenden Vertrag insbesondere feste Revisionen fuer alle drei
Komponenten, ein expliziter gemeinsamer Modellstamm, die Sparse-Offlinegarantie
und ein einheitlicher Kompatibilitaetsdatensatz. Die Paketvorgaben sind zudem nur
Bereiche (`sentence-transformers>=5.4,<6.0`, `transformers>=5.5,<6.0`,
`qdrant-client>=1.12`, `fastembed>=0.4.0`) und legen keine konkrete
Bibliothekskombination fest. Diese Luecken sind Eingaben fuer M1.2 bis M1.5 und
werden in M1.1 noch nicht technisch geschlossen.

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

### Festgelegte Modellrevisionen (M1.3)

Die Revisionen wurden am 27. September 2026 ueber die offiziellen
Hugging-Face-Modellmetadaten aufgeloest und als vollstaendige Commit-SHAs in
`src/config/embedding_models.py` festgelegt:

| Bestandteil | Modell-ID | Commit-SHA |
| --- | --- | --- |
| Dense-Modell | `microsoft/harrier-oss-v1-0.6b` | `f9b9dc8d367d443f2479d27aa5d8d2850c0774ee` |
| Tokenizer | `microsoft/harrier-oss-v1-0.6b` | `f9b9dc8d367d443f2479d27aa5d8d2850c0774ee` |
| Sparse-Modell | `Qdrant/bm25` | `22b8d2af71a76161e18dd432d2cee0eefa66e412` |

Harrier und Tokenizer stammen aus demselben Repository und werden deshalb auf
denselben Snapshot festgelegt. Die FastEmbed-Modelldefinition weist
`Qdrant/bm25` als Hugging-Face-Quelle aus, besitzt selbst aber kein Feld fuer eine
Revision. Das Vorbereitungsskript muss den BM25-Snapshot daher mit dem zentral
festgelegten SHA beziehen und FastEmbed spaeter ueber einen lokalen Modellpfad
verwenden. Ein spaeterer Stand von `main` darf keine dieser Revisionen implizit
ersetzen.

Die Pipeline-Version bezeichnet ausschliesslich Aenderungen an Embedding,
Tokenisierung, Chunking oder Sparse-Verarbeitung, die erzeugte Indexdaten fachlich
veraendern koennen. Sie ist unabhaengig von der allgemeinen Anwendungsversion in
`VERSION`. Eine Aenderung der Weboberflaeche erfordert damit keinen Neuaufbau;
eine relevante Aenderung der Abschnittsbildung kann ihn dagegen erfordern.

### Versionsvertrag fuer Pipeline und Manifest (M1.4)

Die zentrale Konfiguration definiert zwei bewusst getrennte Versionen:

- `EMBEDDING_PIPELINE_VERSION = "passages-1"` bezeichnet die fachliche
  Erzeugungssemantik der Vektordaten. Der bestehende Wert wird uebernommen, damit
  die zentrale Definition denselben Stand wie die bisherige Passage-Pipeline
  beschreibt. Der Wert muss geaendert werden, wenn Query-Instruktion,
  Normalisierung, Tokenisierung, Abschnittsbildung, Dense-Verarbeitung oder
  Sparse-Verarbeitung erzeugte beziehungsweise abgefragte Vektoren fachlich
  anders interpretieren. Ein Modellwechsel wird zusaetzlich durch die gesonderten
  Modellrevisionen sichtbar.
- `MODEL_MANIFEST_FORMAT_VERSION = 1` bezeichnet ausschliesslich die Struktur und
  Auswertungsregeln des lokalen Modellmanifests. Die ganzzahlige Version wird
  erhoeht, wenn ein vorhandener Leser die neue Manifeststruktur oder die Bedeutung
  ihrer Pflichtfelder nicht mehr sicher auswerten kann. Geaenderte Artefakte oder
  Modellrevisionen bei unveraendertem Schema erzeugen ein neues Manifest, aber
  keine neue Formatversion.

Nicht indexrelevante Aenderungen an GUI, Logging oder Betriebsdokumentation
veraendern keine der beiden Versionen. Die allgemeine Anwendungsversion in
`VERSION` bleibt unabhaengig. Bis zur Verbraucherumstellung in Phase 4 bleibt die
bisherige gleichlautende Konstante in `src/indexing/passages.py` bestehen.

## Laufzeitkonfiguration

`src/config/settings.py` enthaelt nur installationsbezogene Werte, insbesondere
den lokalen Modellstamm unter standardmaessig `data/models/` (ueberschreibbar mit
`RATSI_MODELS_DIR`) und gegebenenfalls Timeouts des Vorbereitungsvorgangs. Eine
Downloadfreigabe fuer Indexer oder Suche ist nicht vorgesehen.

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
Hashfelder und ohne fluechtige Erstellungsmetadaten gebildet.

### Manifestschema und kanonischer Hash (M1.5)

`src/config/embedding_model_manifest.py` definiert das unveraenderliche Schema
fuer den vorbereiteten Gesamtbestand. Das Manifest enthaelt:

- `manifest_format_version`, `pipeline_version`, `created_at` und
  `manifest_sha256`
- je einen Eintrag fuer Dense-Modell, Tokenizer und Sparse-Modell mit Modell-ID,
  konfigurierter und aufgeloester Revision sowie relativem lokalem Modellpfad
- je Kernartefakt relativen POSIX-Pfad, Dateigroesse und SHA-256
- die beteiligten Versionen von Transformers, Sentence Transformers, FastEmbed
  und Hugging Face Hub

Die Kernartefakte werden als unveraenderliche Allowlists in
`src/config/embedding_models.py` gepflegt. Harrier umfasst die Modell- und
Sentence-Transformers-Konfiguration samt Gewichtsdatei, der Tokenizer seine
Tokenizer-Konfigurationen und Vokabulardateien, BM25 `config.json` und die vom
bisherigen FastEmbed-Standard verwendete englische Stopwortliste. Nur diese
relativen Pfade werden gehasht. Sie werden validiert, auf Eindeutigkeit geprueft und
lexikografisch sortiert; absolute Pfade, Rueckspruenge und Windows-Trennzeichen
sind unzulaessig. Damit bleiben Cache-Metadaten, Locks und temporaere Dateien
ausgeschlossen.

Der gepinnte Harrier-Snapshot enthaelt nachweislich keine
`sentence_bert_config.json`; die offizielle Dateiliste und der direkte Abruf am
festgelegten Commit bestaetigen dies. Sentence Transformers kann eine solche
Transformer-Modulkonfiguration jedoch laden und damit unter anderem
Loader-Argumente oder die maximale Sequenzlaenge veraendern. Die Datei ist daher
nicht faelschlich als erforderliches Downloadartefakt eingetragen, sondern als
zentral erwartbar abwesend definiert. Vorbereitung und Pruefung muessen sowohl
fehlende beziehungsweise veraenderte Pflichtartefakte als auch ein unerwartetes
lokales Hinzufuegen von `sentence_bert_config.json` ablehnen. Die im gepinnten
Snapshot tatsaechlich vorhandenen `config.json`, `config_sentence_transformers.json`
und `modules.json` bleiben Pflichtartefakte und werden gehasht.

Die kanonische Serialisierung verwendet UTF-8-JSON mit sortierten
Objektschluesseln, deterministisch sortierten Artefaktlisten und ohne unbedeutende
Leerzeichen. Der Wert `manifest_sha256` dient als stabiler
Kompatibilitaets-Hash und wird aus genau dieser Darstellung ohne das Feld
`manifest_sha256` selbst sowie ohne `created_at` berechnet. Ein bereits gesetzter
Hash oder ein neuer Erstellungszeitpunkt bei ansonsten identischer Vorbereitung
kann das erneute Berechnungsergebnis deshalb nicht veraendern. Aenderungen an
Modellidentitaet, Revisionen, Artefakten, Bibliotheksversionen, Pipeline oder
Manifestformat bleiben dagegen hashwirksam.

Es gibt zwei Pruefstufen:

1. Die normale lokale Pruefung validiert Manifestformat, Modellidentitaet,
   Revisionen, erwartete Pfade, Existenz, Dateigroessen und Lesezugriff auf alle
   Kernartefakte. Sie darf keine Netzwerkverbindung aufbauen und soll schnell
   genug fuer Statusanzeigen sein; grosse Artefakte werden dabei nicht gelesen.
2. Eine ausdrueckliche Tiefenpruefung berechnet die festgelegten SHA-256-Werte
   erneut. Grosse Gewichtsdateien werden nicht bei jedem Build- oder Suchstart
   vollstaendig gehasht.

Die gemeinsame lokale Statuspruefung meldet `bereit`, `fehlt`, `unvollstaendig`
oder `inkompatibel` und liefert Status, kurze Meldung sowie bei einem gueltigen
Bestand dessen Manifest-Hash als maschinenlesbare Felder.

## Vorbereitungsskript

Das Skript `scripts/prepare_embedding_models.py` bietet seit M3.1/M3.2 lokale
Schnell- und Tiefenpruefungen:

```text
python scripts/prepare_embedding_models.py --check
python scripts/prepare_embedding_models.py --check --deep
python scripts/prepare_embedding_models.py --check --json
python scripts/prepare_embedding_models.py --check --deep --json
```

Beide verwenden die gemeinsame Statuspruefung und `RATSI_MODELS_DIR` beziehungsweise
standardmaessig `data/models/`. Die menschenlesbare Ausgabe nennt Pruefstufe,
Status und kurze Meldung sowie bei einem bereiten Bestand dessen Manifest-Hash.
`--deep` berechnet zusaetzlich alle festgelegten Artefakt-SHA-256-Werte erneut.
`--json` ersetzt die CLI-Meldung durch genau ein JSON-Objekt auf stdout:

```json
{"check_level":"fast","manifest_sha256":null,"message":"Das lokale Modellmanifest fehlt.","status":"fehlt"}
```

`status`, `message` und `manifest_sha256` stammen aus der gemeinsamen Status-API;
`check_level` bezeichnet `fast` oder `deep`. Der Hash ist nur bei einem bereiten
Bestand gesetzt. Eine ungueltige Einstellung fuer `RATSI_MODELS_DIR` liefert
im JSON-Modus ebenfalls dieses Schema mit `status="inkompatibel"` und Exitcode
`2`; im menschenlesbaren Modus erscheint die kurze Fehlermeldung auf stderr.
Ungueltige Argumente werden mit Usage-Meldung auf stderr und Exitcode `2`
abgelehnt, auch bei `--json`.

Exitcode `0` bedeutet `bereit`, `1` einen fehlenden, unvollstaendigen oder
inkompatiblen Bestand und `2` einen Aufruf- oder Konfigurationsfehler. Die Pruefung
veraendert keine Dateien und legt auch kein fehlendes Modellverzeichnis an.
Seit M3.3/M3.4 ist zudem die ausdrueckliche Vorbereitung gepinnter Modelle verfuegbar:

```text
python scripts/prepare_embedding_models.py --download
python scripts/prepare_embedding_models.py --download --json
```

`--check` arbeitet garantiert offline. `--download` verwendet
`huggingface_hub.snapshot_download` mit ausschliesslich den Modell-IDs,
vollstaendigen Commit-SHAs und Kernartefakt-Allowlists aus `embedding_models.py`.
Dense-Modell und Tokenizer werden bei identischer ID und Revision als gemeinsamer
Snapshot mit der vereinigten Artefaktliste geladen; BM25 wird separat geladen.
Freie Modell-IDs oder Revisionen sind keine CLI-Parameter.

Wenn kein gepruefter Bestand wiederverwendet werden kann, wird in einen passenden
vorhandenen oder einen neuen temporaeren Ordner unter
`<Modellstamm>/.preparation/download-*/` heruntergeladen. Darunter liegen die
Snapshots jeweils unter `<Modell-ID>/<Commit-SHA>/`. Hugging-Face-Cachemetadaten koennen innerhalb
dieser lokalen Snapshotordner entstehen. Umgeleitete `.preparation`- oder
`inventories`-Verzeichnisverknuepfungen werden abgelehnt.

M3.4 prueft vor der Freigabe alle Pflichtartefakte: Sie muessen lesbare,
nichtleere regulaere lokale Dateien innerhalb des erwarteten Modellpfads sein.
Unerwartete verhaltensrelevante Dateien wie `sentence_bert_config.json` werden
abgelehnt. Das Kandidatenmanifest erfasst konfigurierte und ueber den gepinnten
Download bezogene Revisionen, relative Modellpfade, Dateigroessen und SHA-256,
die installierten Versionen von Transformers, Sentence Transformers, FastEmbed
und Hugging Face Hub sowie den UTC-Erstellungszeitpunkt. Anschliessend wird die
gemeinsame lokale Tiefenpruefung auf den vollstaendigen Kandidaten angewendet.

Ein neuer gepruefter Kandidatenordner wird auf demselben Dateisystem nach
`<Modellstamm>/inventories/<Kandidatenmanifest-Hash>/` verschoben. Die
inhaltsbezogene Adresse verhindert wechselnde Kompatibilitaets-Hashes allein
aufgrund zufaelliger Downloadordner oder neuer Erstellungszeiten. Existiert der
Zielbestand schon, wird er tiefengeprueft und mit dem Kandidaten verglichen;
abweichende oder beschaedigte Bestandsdateien werden nicht ueberschrieben.

Das aktive Manifest enthaelt die freigegebenen relativen Pfade unter `inventories/`
und einen entsprechend neu berechneten Manifest-Hash. Es wird in einer separaten
Datei im Modellstamm vollstaendig geschrieben, geflusht und mit `fsync` gesichert.
Erst `os.replace` auf `<Modellstamm>/manifest.json` aktiviert den Bestand atomar.
Leser sehen damit entweder das bisherige oder das neue vollstaendige Manifest.
Bestehende Modellordner werden erhalten, damit zuvor gestartete Leser ihre alten
Pfade weiter nutzen koennen.

Ein Fehler oder Abbruch vor dem Manifestwechsel laesst den vorherigen Bestand
aktiv. Bei einer Erstvorbereitung bleibt ohne erfolgreichen Manifestwechsel der
Status `fehlt`. Kandidaten, noch nicht aktivierte Bestaende, temporaere
Manifestdateien bei Abbruch und alte Bestaende werden nicht automatisch
geloescht.

Seit M3.5 erfolgt die Wiederverwendung in dieser festen Reihenfolge:

1. Ein gueltiges aktives Manifest wird mit allen Artefakt-SHA-256-Werten und
   exakt den aktuell installierten Bibliotheksversionen verglichen. Bei Erfolg
   bleibt der Bestand unveraendert; weder Hub-Import, Zugangsdatenabfrage noch
   Download oder Manifestwechsel werden ausgefuehrt.
2. Vollstaendig gepruefte Bestandsordner unter `inventories/`, deren
   Kandidatenmanifest-Hash ihrem Ordnernamen entspricht, koennen ohne erneuten
   Download atomar aktiviert werden. Damit laesst sich ein Abbruch nach dem
   Verschieben, aber vor dem Manifestwechsel abschliessen.
3. Vollstaendige, tiefengepruefte Kandidaten unter `.preparation/download-*/`
   koennen ebenfalls ohne Hub-Aufruf freigegeben werden. Modellvertrag und
   Bibliotheksversionen muessen weiterhin exakt passen.
4. Fuer teilweise heruntergeladene Kandidaten muss `download-plan.json` exakt
   zum aktuellen Vertrag passen: Planformat `1`, Pipeline- und Manifestformat,
   Modell-IDs, Commit-SHAs und vereinigte Artefaktlisten. Unpassende, unlesbare
   oder unbekannte Altplaene sowie verlinkte Kandidatenordner werden nicht
   weiterbeschrieben. Die Auswahl passender Ordner erfolgt lexikografisch.

Nach einem erfolgreichen Snapshot-Download entsteht `snapshot-<Nummer>.json`
als Bestaetigung mit Modell-ID, Revision sowie Artefaktpfaden, Groessen und
SHA-256-Werten. Vor einer Wiederverwendung werden alle diese Werte erneut aus
den lokalen Dateien berechnet und exakt verglichen. Eine vorhandene Datei oder
Hub-Cachemetadaten allein gelten nicht als Bestaetigung. Fehlende, unlesbare oder
nicht mehr passende Bestaetigungen fuehren zu einem erneuten Download des
betroffenen Snapshots mit `force_download=True`.

Die Wiederaufnahme erfolgt damit auf Snapshotebene: Bereits bestaetigte
Snapshots bleiben erhalten, der unterbrochene oder beschaedigte Snapshot wird
vollstaendig erneut bezogen. Eine Wiederaufnahme einzelner Gewichtsdateien auf
Byteebene wird nicht zugesichert. Ein erneuter Download schreibt nur in den
passenden Kandidatenordner; aktive oder alte freigegebene Dateien werden nie
repariert oder ueberschrieben. Nach der Wiederaufnahme gelten unveraendert die
vollstaendige Manifestbildung, Tiefenpruefung und atomare Freigabe aus M3.4.

`--download --json` liefert bei Erfolg ein einzelnes Objekt mit
`operation="download"`, `status="bereit"`, `message`, `inventory_dir` und
`manifest_sha256` sowie `reused`. `reused=true` kennzeichnet einen bereits
vollstaendig geprueften Bestand, der ohne erneuten Download wiederverwendet oder
freigegeben wurde; die Wiederaufnahme nur einzelner bestaetigter Snapshots setzt
diesen Wert nicht. Exitcode `0` bedeutet einen geprueften und freigegebenen
Modellbestand. Bei Download-, Pruef- oder Freigabefehlern folgt Exitcode `1` mit
`operation="download"`, `status="fehlgeschlagen"`, einer kurzen `message` und
seit M3.6 einem stabilen `error_code`.
Ungueltige Laufzeiteinstellungen liefern dasselbe Fehlerschema und Exitcode `2`.
Rohe SDK-Fortschrittsausgaben werden seit M3.7 unterdrueckt; sichere
Start-/Endereignisse stehen im Komponentenlog.

### Erwartbare Vorbereitungsfehler (M3.6)

CLI-Meldungen nennen den betroffenen Schritt und die naechste sinnvolle Aktion;
erwartbare Download-, Dateisystem- und Prueffehler erzeugen keinen Traceback.
Die JSON-Ausgabe unterscheidet:

| `error_code` | Bedeutung und naechster Schritt |
| --- | --- |
| `network_unavailable` | Verbindung, Timeout, Offline-Einstellung, HTTP 429 oder HTTP 5xx; Internet und Proxy pruefen, Download erneut starten |
| `disk_full` | ENOSPC, Speicherquota oder Windows-Fehler 112; lokalen Speicher freigeben, Download erneut starten |
| `permission_denied` | Fehlender Lese-/Schreibzugriff oder schreibgeschuetztes Dateisystem; Verzeichnisrechte pruefen |
| `incomplete_artifacts` | Fehlende, leere, beschaedigte oder ungueltige Artefakte/Manifeste; Vorbereitung erneut starten, bei Wiederholung Kandidaten pruefen |
| `source_unavailable` | Andere HTTP-Fehler wie 401, 403 oder 404; Zugangsdaten und gepinnte Quelle pruefen |
| `dependency_missing` | Hub- oder Modell-Abhaengigkeit fehlt; `requirements.txt` installieren |
| `download_failed` / `preparation_failed` | Nicht genauer klassifizierter Fehler; Verbindung, Modellstamm und Verzeichnisrechte pruefen |
| `configuration_error` | Ungueltige Laufzeiteinstellung; Konfiguration korrigieren, Exitcode `2` |

Die Klassifikation beruecksichtigt auch verschachtelte Ausnahmen, etwa einen
Anbieterfehler mit zugrunde liegendem ENOSPC. Bekannte Fehler vor der Aktivierung
lassen das aktive Manifest unveraendert und behalten Kandidaten fuer die
Wiederaufnahme bei.
Auch `RuntimeError` bei der Pfadaufloesung, etwa durch Symlink-Schleifen unter
Python 3.11/3.12, wird in der Vorbereitung und beim Anlegen des Downloadziels
abgefangen. Der Fehler liefert `preparation_failed`, Exitcode `1` und keine
rohen Ausnahmetexte oder Tracebacks. Die Mindestversion bleibt Python 3.11+.

Nur `--download` konfiguriert das gemeinsame rotierende Projektlog unter
`logs/embedding_model_preparation.log` beziehungsweise `RATSI_LOG_DIR`.
`--log-level` hat Vorrang vor `RATSI_LOG_LEVEL`, danach gilt `INFO`; erlaubte
explizite Level sind DEBUG, INFO, WARNING, ERROR und CRITICAL. `--check` bleibt
rein lesend und konfiguriert keine Logdatei, auch bei gesetztem `--log-level`.

`event=model_preparation_failed` protokolliert Fehlercode, Arbeitsschritt,
Fehlerklasse, numerisches `errno` und gegebenenfalls HTTP-Status. UTC-Zeit,
Komponente und Lauf-ID folgen `src/observability.py`; `RATSI_RUN_ID` kann die
Lauf-ID setzen. Bei Erfolg erscheint `event=model_preparation_completed` mit
Bereitschafts- und Wiederverwendungsstatus. Ausnahmetexte, Anbieterantworten,
Requests, Header und URLs werden nicht in diese Diagnosefelder uebernommen.
Fremde SDK-Logs werden aus dem Komponentenlog herausgefiltert. Die kurze
CLI-Meldung beziehungsweise das einzelne JSON-Objekt bleibt von den
Dateiprotokollen getrennt.

Scheitert bereits das Anlegen des Logs, endet der Aufruf ohne Download mit einer
kurzen klassifizierten Meldung. Scheitert ein spaeterer Log-Schreibzugriff, wird
kein Logging-Traceback ausgegeben; die Vorbereitung und ihre CLI-Ergebnismeldung
laufen weiter. Waehrend des synchronen SDK-Aufrufs werden rohe Python-Ausgaben
auf stdout/stderr und Python-Logs vollstaendig unterdrueckt, statt nur bekannte
Tokenzeichenfolgen zu ersetzen. Dies schuetzt auch vor unbekannten, kodierten
oder ueber mehrere Schreibzugriffe verteilten Zugangsdaten. Der vorherige
Logging- und Streamzustand wird auch bei Abbruch wiederhergestellt. Sichere
Start-/Endereignisse enthalten ausschliesslich die konfigurierte Modell-ID und
Revision; rohe SDK-Fortschrittsausgaben werden nicht angezeigt.

`--check` und `--download` schliessen sich gegenseitig aus; `--deep` ist nur bei
`--check` erlaubt. Die Hub-Bibliothek und die Zugangsdaten werden nur beim
Bearbeiten neuer oder teilweise vorbereiteter Downloads geladen. Vollstaendig
gepruefte Bestaende und Kandidaten werden ohne diesen Schritt wiederverwendet.
Der optionale Token wird ueber die vorhandene
Secret-Verwaltung bezogen (Keyring vor `HF_TOKEN` vor `HUGGING_FACE_HUB_TOKEN`)
und nur als API-Argument uebergeben. Ein Keyringfehler erlaubt den Env-Fallback.
Die Token-Umgebung wird nicht veraendert; ohne konfigurierten Token verhindert
`token=False` eine implizite Anmeldung aus dem Hub-Cache.
`huggingface-hub>=1.0,<2.0` wird als direkte Abhaengigkeit gefuehrt.
Echte Live-Downloads wurden fuer M3.3 bis M3.8 nicht ausgefuehrt.

M3.8 ergaenzt echte CLI-Subprozess-Integrationstests mit einem kleinen Fake-Hub
und gesperrtem Netzwerk. Sie pruefen den Aufruf aus einem fremden Arbeitsordner,
atomare Freigabe, Tiefenpruefung und Offline-Wiederverwendung ohne Hub-Import
oder Secret-Zugriff. Ein simulierter Anbieterfehler laesst den alten Bestand
bytegleich bestehen; anschliessend wird nur der unbestaetigte Snapshot nachgeladen.

Die getrennte Datei `tests/test_embedding_model_preparation_live.py` verwendet
die bestehenden Marker `live` und `integration`. Beide Tests brauchen neben der
Marker-Auswahl eine eigene Opt-in-Variable: `RATSI_EMBEDDING_LIVE_SMOKE=1` fuer
gepinntes Anbieter-Metadaten-/Konfigurationslesen ohne Gewichte beziehungsweise
`RATSI_EMBEDDING_LIVE_DOWNLOAD=1` fuer den kompletten Modelldownload samt
Manifestvalidierung und Offline-Wiederverwendung. Der Smoke-Test ist keine
Bereitschaftsabnahme. Die Tests laufen anonym in isolierten Kindprozessen;
Modellstamm, Logs, Tokenpfad und Hub-/Xet-Caches liegen im temporaeren
Testverzeichnis. Die konkreten Aufrufe und der Speicherhinweis stehen im README.
Ohne Opt-in bleiben auch explizit ausgewaehlte Live-Tests uebersprungen.

Die verwendete Download-API fuer feste Revisionen und Artefaktauswahl ist in der
[offiziellen Hugging-Face-Anleitung](https://huggingface.co/docs/huggingface_hub/guides/download)
beschrieben.

### Abschlusspruefung Phase 3 (M3.9)

Der Gesamtdiff gegen `codex/feature/embedding-model-management` wurde statisch
mit den Anforderungen aus M3.1 bis M3.8, der gemeinsamen Manifest-/Status-API
und den vorhandenen Tests abgeglichen:

- Offlinepruefung bleibt lesend und ohne Hub-Import oder Secret-Abfrage;
  CLI-Modi, JSON-Felder und Exitcodes stimmen mit der Dokumentation ueberein.
- Downloadziele, volle Commit-SHAs und Artefaktlisten stammen ausschliesslich
  aus dem zentralen Vertrag; gemeinsame Harrier-/Tokenizer-Snapshots werden
  zusammengefasst.
- Kandidaten werden vollstaendig und tief geprueft. Erst der atomare Wechsel
  des aktiven Manifests gibt einen Bestand frei; alte Bestaende bleiben erhalten.
- Wiederverwendung verlangt gepruefte Artefakte und passende Bibliotheksversionen;
  eine Teilwiederaufnahme vertraut nur erneut geprueften Snapshot-Bestaetigungen.
- Fehlerdiagnosen uebernehmen keine rohen Anbietertexte. Tokenprioritaet,
  anonymer Download und Wiederherstellung des Ausgabezustands sind abgesichert.
- Fake-Hub- und Live-Tests bleiben getrennt; echte Downloads benoetigen Opt-in
  und verwenden isolierte temporaere Laufzeitpfade.
- README, Testaufrufe, direkte Hub-Abhaengigkeit und `VERSION` sind konsistent.
  Veraltete Aussagen zu SDK-Fortschrittsausgaben wurden berichtigt.

Die bereits dokumentierten gezielten Testlaeufe werden als Nachweis verwendet.
Diane hat die regulaere pytest-Ausfuehrung als abgeschlossen bestaetigt; fuer
M3.9 wurde sie auf Wunsch nicht wiederholt. Ein neues detailliertes
Windows-Ergebnisprotokoll wurde hier nicht uebermittelt. Live-Downloads wurden
auch fuer die Abschlusspruefung nicht ausgefuehrt.

Diese Abnahme betrifft ausschliesslich Phase 3, nicht die Gesamtabnahme aus
Phase 7. Verbraucherumstellung und globale Offlinegarantie folgen in Phase 4;
die damals fuer M6.9 vorgesehene Sperre gegen kollidierende Vorbereitungsjobs
ist inzwischen umgesetzt. Es sind fuer
M3.9 keine weiteren Laufzeitcode-Aenderungen erforderlich. `VERSION` bleibt
fuer diesen Doku-/Abschlusscommit bewusst bei `0.5.15`.

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

Seit M5.1 erzeugt `src/config/index_compatibility.py` den unveraenderlichen
`IndexCompatibility`-Datensatz aus den zentralen Dense-, Sparse- und
Tokenizer-IDs samt Commit-SHAs, der Vektordimension, der fachlichen
Pipeline-Version und dem SHA-256-Wert des aktiven Modellmanifests. Die Erzeugung
setzt eine erfolgreiche gemeinsame lokale Bestandspruefung einschliesslich der
installierten Bibliotheksversionen voraus. Ungueltige IDs, Revisionen, Hashes,
Dimensionen und leere Pipeline-Versionen werden abgelehnt. `as_dict()` liefert
die JSON-faehigen Pflichtfelder fuer die folgenden Freigabemarker und Payloads.

Diese Angaben werden in den bestehenden Freigabe- beziehungsweise Buildmetadaten
und in den fuer die Nachvollziehbarkeit erforderlichen Punkt-Payloads gefuehrt.
Die konkrete Speicherung muss fuer lokalen und Serverbetrieb denselben
Kompatibilitaetsvertrag liefern. M5.2 ergaenzt dafuer die gemeinsame
`QdrantConnection`-Marker-API: Pro Collection (`ratsi_passages`,
`ratsi_documents`, `landkreis_publications`) gibt es einen eigenen
`<Collection>.ready.json`-Pfad. Lokal liegt er im Qdrant-Verzeichnis, im
Serverbetrieb unter der SHA-256-adressierten URL-Statuswurzel. Neue
Passage-Freigaben speichern den vollstaendigen Datensatz als `compatibility`
zusammen mit dem Collection-Namen. Servermarker behalten ausserdem URL-Hash
und exakte Punktzahl. Der Leser validiert Collection, URL-Bindung und alle
Kompatibilitaetsfelder; alte Marker ohne Datensatz liefern keinen
Kompatibilitaetsnachweis. Die Aufnahme neuer Freigabeschreibvorgaenge fuer
`ratsi_documents` und `landkreis_publications` ist mit M5.7 umgesetzt; alte
Collections werden dadurch nicht nachtraeglich als kompatibel markiert.

M5.3 schreibt bei neu berechneten Punkten aller drei Collections denselben
vollstaendigen Datensatz unter dem Payload-Feld `index_compatibility`. Dieser
enthaelt Dense-, Sparse- und Tokenizer-ID samt Revision, Manifest-Hash,
Vektordimension und Pipeline-Version. Bei Passagen bleiben die bisherigen Felder
`model` und `pipeline_version` fuer vorhandene Verbraucher bestehen. Der neue
Datensatz wird erst nach der Fingerprint-Berechnung an den Punkt angefuegt;
Snippet-Aktualisierungen vorhandener Punkte setzen ihn nicht, da dabei keine
Vektoren neu berechnet werden. Alt-Punkte ohne Datensatz werden erst nach
verifizierter Uebernahme beziehungsweise getrenntem Neuaufbau behandelt.

Vor dem ersten Schreibzugriff vergleicht ein Builder den vorhandenen Indexstand
mit der aktiven Modellkonfiguration. Bei einer Abweichung darf er die Collection
nicht inkrementell erweitern. Er fordert einen vollstaendigen Neuaufbau oder eine
getrennte Aufbau-Collection an.

M5.7 setzt diese Schranke fuer alle drei Collections vor Collection-Erzeugung,
Payload-Aktualisierung und Vektor-Upsert um. Bei einer nichtleeren Collection
muss ein gueltiger, ziel- und collectionsgebundener Freigabemarker exakt den
aktiven Kompatibilitaetsdatensatz enthalten. Ein fehlender, ungueltiger oder
abweichender Marker bricht den Build vor dem ersten Qdrant-Schreibzugriff ab.
Der Marker erfasst die Punktzahl auch bei lokalem Qdrant. Ein freigegebener
Marker enthaelt ausserdem einen Digest der Punkt-IDs und Vektoren. Build und
Suche vergleichen den gesamten Vektorbestand und die Kompatibilitaetsdaten
aller Punkte mit dem aktuellen Vertrag. Erfolgreiche Suchpruefungen werden je
Prozess bis zu fuenf Minuten zwischengespeichert; Marker- oder
Punktzahlaenderungen erzwingen sofort eine neue Pruefung. Ein Austausch bei
gleicher Punktzahl und unveraendertem Marker kann waehrend dieser Frist
unentdeckt bleiben. Der Cache gilt nur fuer einen Marker, dessen gelesener
Stand ausdruecklich `ready=true` enthaelt; ein inzwischen ausstehender Build
wird vor der Abfrage abgewiesen. Auch bei einem Cache-Treffer wird der Marker
nach der Qdrant-Abfrage erneut gelesen; ein zwischenzeitlich widerrufener
Stand wird abgewiesen. Ein alter Marker fuer eine
ersetzte Collection mit gleicher Punktzahl und abweichenden Vektoren oder
Payloads wird abgelehnt. Bei einem Marker mit `ready=false` darf die Punktzahl
durch den angefangenen Build wachsen oder schrumpfen; alle vorhandenen Punkte
muessen weiterhin den aktiven Vertrag tragen. Nach erfolgreichem Abschluss
wird der Digest fuer den neuen Bestand geschrieben.
Landkreis-Builds speichern `max_text_chars` als Build-Option im Marker und
verweigern eine inkrementelle Fortsetzung mit einem anderen Wert. Aeltere
Landkreis-Marker ohne diese Option benoetigen einen getrennten Neuaufbau,
weil sich ihr tatsaechliches Textlimit nicht belegen laesst.
Bestehende Marker ohne Punktzahl muessen durch einen getrennten Neuaufbau oder
eine erneute verifizierte Uebernahme ersetzt werden.
Neue Collections duerfen mit dem aktiven Vertrag beginnen. Bereits vorhandene
leere Collections muessen dafuer ebenfalls das erwartete
Vektorschema besitzen. Ein alter Marker allein legitimiert kein zwischenzeitlich
neu angelegtes, inkompatibles Qdrant-Schema. Jeder
Schemaabgleich umfasst neben dem Dense-Distanzmass den Dense-Datentyp,
vektorspezifische HNSW- und Quantisierungsoptionen sowie BM25-Modifikator und
Sparse-Datentyp. Die Suche prueft das aktuelle Collection-Schema vor einem
moeglichen Cache-Treffer erneut. Jeder
Build haelt einen Marker mit `ready=false` und Vertrag fest, bis der Lauf
erfolgreich freigegeben ist; dadurch bleibt eine unterbrochene inkrementelle
Fortsetzung pruefbar. Die Passage-Suche behandelt `ready=false` als nicht
freigegeben. Der Collection-Marker behaelt nach einer verifizierten Uebernahme
die Herkunft `legacy_verified`; bereits uebernommene Punkt-Payloads bleiben
bei spaeteren Ergaenzungen unveraendert.
Alle drei Builder halten vor dem Oeffnen des Qdrant-Clients eine Sperre fuer
die jeweilige Collection bis zur Freigabe oder zum Abbruch. Ein zweiter Build
wartet und prueft nach Freigabe den dann aktuellen Marker und Index erneut.
Dieselbe Sperrdatei serialisiert auch die Legacy-Uebernahme. Im Serverbetrieb
muessen alle Builder und Uebernahmeprozesse dieselbe Statuswurzel verwenden;
unabhaengige Rechner ohne gemeinsame Statuswurzel werden nicht koordiniert.
Die Websuche vergleicht vor der Query-Kodierung den Marker der tatsaechlich
ausgewaehlten Collection mit dem aktiven Modellvertrag und weist fehlende oder
abweichende Vertraege sowie `ready=false` zurueck. Die Evaluations-CLI prueft
ihre ausdruecklich gewaehlte Collection auf dieselbe Weise, bevor sie Encoder
startet oder Ergebnisse schreibt.

M5.8 gibt bei einer inkompatiblen Fortsetzung in allen drei Build-CLIs nur
eine `ERROR: Index <Collection> inkompatibel: ...`-Zeile mit dem Grund und dem
Hinweis auf vollstaendigen Neuaufbau oder eine getrennte Aufbau-Collection
aus. Der Exitcode ist `1`; ein Python-Traceback oder ein Qdrant-Schreibzugriff
folgt auf diesen Abbruch nicht. Bei einer alten Collection ohne gueltigen
Marker ist alternativ der einmalige Legacy-Pruefpfad unten verfuegbar.

### Einmalige Uebernahme bestehender Collections

M5.4 stellt die rein lesende Funktion `inspect_legacy_collection` unter
`src/indexing/legacy_index_inspection.py` bereit. Sie verlangt zuerst die
Tiefenpruefung des aktiven lokalen Modellbestands. Danach prueft sie den
Collection-Marker und alle vorhandenen Punkt-Hinweise auf Widersprueche,
das Qdrant-Schema (`harrier`/`bm25`, Cosine, konfigurierte Dimension), die
exakte Punktzahl und die vollstaendige Liste ganzzahliger Punkt-IDs.

Die Stichprobe umfasst alle Punkte bis zu 32; bei groesseren Collections werden
32 IDs nach SHA-256-Rang aus Collection, kanonischem Kompatibilitaetsdatensatz
und Punkt-ID ausgewaehlt. Die Reihenfolge der Qdrant-Scrollseiten beeinflusst
die Auswahl nicht. Die Funktion liest die ausgewaehlten Payloads und Vektoren
neu und rekonstruiert den urspruenglichen Embedding-Text: Passagen verwenden
ihr bestaetigtes `text`-Feld, Ratsinfo-Dokumente die urspruengliche
Zehn-Seiten-Extraktion aus SQLite und lokaler Datei beziehungsweise den
bisherigen Metadaten-Fallback, Landkreis-Punkte den urspruenglichen SQLite-Extrakt mit der Standardgrenze von 6000 Zeichen.
Diese lesende Landkreis-Rekonstruktion ist nur diagnostisch; ohne belegtes
urspruengliches Textlimit gibt sie keinen Legacy-Index zur Uebernahme frei.
Die Quell-SQLite-Dateien werden dazu im Read-only-Modus geoeffnet; ein
fehlender Pfad wird nicht als neue Datenbank angelegt. Bei Dokument- und
Landkreis-Punkten muss das gespeicherte Snippet zum rekonstruierten
Text passen. Fehlende Quellen oder abweichende Buildparameter koennen daher
keinen positiven Nachweis liefern.

Die vorbereiteten lokalen Harrier- und BM25-Adapter berechnen die Stichprobe
neu. Dense-Werte und Sparse-Werte werden mit den im Code festgelegten engen
Toleranzen verglichen; Sparse-Indizes muessen exakt uebereinstimmen. Eine
unvollstaendige Stichprobe oder eine waehrend der Pruefung geaenderte
Punkt-ID-Liste verhindert ein positives Ergebnis. Die Funktion ruft ausschliesslich
Qdrant-Leseoperationen auf und schreibt weder Marker noch Payloads. Ihr
Ergebnis bindet Ziel, Collection, exakte Punktzahl, SHA-256 der sortierten
Punkt-IDs, Stichproben-IDs und aktiven Kompatibilitaetsdatensatz. Das
persistierte Uebernahmeprotokoll und die abschliessenden Abbruchgruende sind
in M5.5 definiert. Die Pruefung bietet noch keinen Freigabeschritt.

Die vor dieser Umstellung aufgebauten Collections enthalten noch keinen
vollstaendigen Kompatibilitaetsdatensatz. Sie muessen deshalb nicht automatisch
neu aufgebaut werden. Fuer `ratsi_passages`, `ratsi_documents` und
`landkreis_publications` wird ein ausdruecklicher, einmaliger Uebernahmepfad
bereitgestellt. Er ist kein allgemeiner Schalter zum Umgehen der
Kompatibilitaetspruefung.

Die Uebernahme laeuft zunaechst strikt lesend und erfordert:

- einen vollstaendig vorbereiteten und tiefengeprueften lokalen Modellbestand
  fuer exakt die aktive Konfiguration
- das erwartete Qdrant-Schema mit den Vektornamen `harrier` und `bm25` sowie
  Dense-Dimension 1024
- vorhandene Modell- und Pipelinehinweise ohne bekannten Widerspruch zur aktiven
  Konfiguration
- fuer jede Passage in der vollstaendigen Punktliste `committed=true`, auch
  ausserhalb der deterministischen Vektorstichprobe
- fuer jeden geprueften Punkt einen unveraenderten, exakt rekonstruierbaren
  urspruenglichen Embedding-Text
- eine deterministisch aus Collection, Punkt-IDs und aktivem
  Kompatibilitaetsdatensatz ausgewaehlte Stichprobe; Auswahlregel und Umfang sind
  fest im Code definiert und nicht als freie Serviceparameter eingebbar
- erneute Dense- und Sparse-Berechnung mit den vorbereiteten Modellen sowie den
  Vergleich mit den gespeicherten Vektoren; Sparse-Indizes muessen exakt passen,
  Werte und Dense-Vektoren innerhalb zentral festgelegter enger Toleranzen

Die Stichprobe ist ein bewusst dokumentierter Migrationskompromiss und kein
mathematischer Nachweis fuer jeden Punkt. Das Uebernahmeprotokoll enthaelt daher
Collection, Punktanzahl, Stichprobenumfang und -IDs, Vergleichstoleranzen,
Kompatibilitaetsdatensatz, Ergebnis und Zeitpunkt. Secrets, Dokumenttexte und
vollstaendige Vektoren werden darin nicht gespeichert.

`inspect_and_write_report(connection, client, collection, report_path)` schreibt
das JSON-Protokoll atomar an einen explizit angegebenen Pfad. Es enthaelt
`report_version=2`, einen UTC-Zeitpunkt, die oeffentliche Zielanzeige und
`target_sha256` des vollstaendigen Server-URL beziehungsweise des aufgeloesten
lokalen Store-Pfads. Fuer `ratsi_documents` enthaelt es zusaetzlich den
aufgeloesten Pfad der Quell-SQLite-Datei. Vorhandene Berichte der Version 1
muessen neu erstellt werden. Bei `result=verified` sind exakte Punktanzahl, SHA-256
der sortierten Punkt-IDs, Stichprobenumfang und -IDs sowie der aktive
Kompatibilitaetsdatensatz enthalten. `result=aborted` traegt genau einen
`abort_code`; unvollstaendige Punkt- und Vertragsnachweise bleiben `null`.
Das Protokoll allein gibt noch keine Collection frei.

Die Stichprobe umfasst maximal 32 Punkte. Dense- und Sparse-Werte verwenden
jeweils absolute und relative Toleranz `1e-4` nach `math.isclose`; Sparse-Indizes
muessen exakt gleich sein. Diese Werte stehen auch im Protokoll und sind keine
Eingabeparameter. Abbruchcodes sind nach Ursache getrennt:

| Ursache | `abort_code` |
| --- | --- |
| Modellbestand oder Schema | `model_unavailable`, `schema_mismatch`, `collection_missing`, `collection_empty` |
| Marker, Modell- oder Pipelinehinweise | `marker_invalid`, `marker_target_mismatch`, `marker_collection_mismatch`, `marker_count_mismatch`, `model_mismatch`, `pipeline_mismatch`, `contract_invalid`, `contract_mismatch` |
| Punktliste und Payload | `point_ids_invalid`, `payload_missing`, `scroll_incomplete`, `point_count_mismatch`, `collection_changed` |
| Quelltext | `source_missing`, `source_ambiguous`, `text_unavailable`, `text_mismatch` |
| Nicht unterstuetzte Landkreis-Uebernahme | `rebuild_required` |
| Stichprobe und Vektoren | `sample_incomplete`, `vector_invalid`, `dense_mismatch`, `sparse_indices_mismatch`, `sparse_values_mismatch` |

Nur wenn alle Voraussetzungen und Vergleiche erfolgreich sind, darf ein zweiter,
ausdruecklich bestaetigter Schritt Metadaten schreiben. Er hinterlegt den aktiven
Kompatibilitaetsdatensatz atomar in den Freigabemetadaten, ergaenzt erforderliche
Punkt-Payloads ohne Neuberechnung der Vektoren und kennzeichnet die Herkunft als
`legacy_verified`. Die Collection bleibt waehrend der Pruefung suchbar. Vorhandene
Vektoren werden weder geloescht noch ueberschrieben; bei einem Abbruch bleibt der
alte Freigabemarker erhalten und die Uebernahme gilt als nicht erfolgt.
Das Pruefergebnis ist an Ziel, Collection, Punktanzahl, einen Digest der Punkt-IDs
und den aktiven Kompatibilitaetsdatensatz gebunden. Der Schreibschritt prueft diese
Bindung erneut und lehnt ein veraltetes Ergebnis ab.

Ein einzelner Vektorfehler, widerspruechliche Metadaten, nicht rekonstruierbarer
Embedding-Text oder eine unvollstaendige Stichprobe verhindert jede Freigabe und
fordert einen getrennten Neuaufbau an. Eine Uebernahme ist pro Collection und
Kompatibilitaetsdatensatz nur einmal moeglich. Nach einer spaeteren Aenderung von
Modellrevision, Vektordimension oder Pipeline-Version ist keine erneute
Legacy-Uebernahme zulaessig; dann bleibt der vollstaendige Neuaufbau verbindlich.

M5.6 stellt `scripts/migrate_legacy_index.py` bereit. Beispiel fuer eine lokale
oder per `RATSI_QDRANT_URL` konfigurierte Passage-Collection:

```bash
python scripts/migrate_legacy_index.py --inspect --collection ratsi_passages --report data/db/legacy_passages_inspection.json
python scripts/migrate_legacy_index.py --apply --collection ratsi_passages --report data/db/legacy_passages_inspection.json --confirm-collection ratsi_passages
```

Der zweite Befehl verlangt die ausgeschriebene Collection als Bestaetigung.
Bei einem mit einer eigenen SQLite-Datei aufgebauten `ratsi_documents`-Index
muss auf beiden Befehlen derselbe Parameter `--source-db PFAD` angegeben werden.
Der Bericht bindet diesen aufgeloesten Pfad; `--apply` lehnt eine andere Quelle
vor der erneuten Pruefung und vor Schreibzugriffen ab. Auch ein bei der
Vorabpruefung abgebrochener Bericht nennt die tatsaechlich gewaehlte Quelle.
Die Legacy-Uebernahme von `landkreis_publications` wird mit
`rebuild_required` abgewiesen, auch wenn ein frueherer Bericht vorliegt: Das
urspruengliche Textlimit ist nicht zuverlaessig nachweisbar. Stattdessen wird
die Landkreis-Collection aus den Quelldaten getrennt neu aufgebaut. Dabei
`--max-text-chars` festlegen und fuer spaetere inkrementelle Laeufe beibehalten;
die Melle-Collections bleiben bestehen. Die konkrete Aufgabe steht in
`docs/project_tasks.md`.
Im lokalen Modus koennen beide Befehle mit `--qdrant-dir PFAD` denselben
abweichenden Qdrant-Speicher wie die Build-CLIs auswaehlen; im Servermodus gilt
weiterhin `RATSI_QDRANT_URL`. Eine fehlende Collection erzeugt ein Protokoll mit
`abort_code=collection_missing`.
Vor dem Oeffnen eines lokalen Speichers muss eine gueltige Qdrant-`meta.json`
vorliegen; ein beliebiges oder leeres Verzeichnis wird mit `store_missing`
abgewiesen, ohne Qdrant-Dateien anzulegen. Ist der Server nicht erreichbar,
meldet der Befehl `qdrant_unavailable`. Bei `--inspect` werden beide
Vorabfehler auch als abgebrochene Inspektionsberichte gespeichert. Ein
Verbindungsabbruch waehrend der lesenden Inspektion erhaelt denselben Abort-Code
und schreibt ebenfalls einen Bericht.
Ein Verbindungsabbruch oder Serverfehler waehrend der erneuten Pruefung bei
`--apply` endet mit `qdrant_unavailable` und Exitcode 1 ohne Traceback; ein
bestehender Inspektionsbericht wird dabei nicht ueberschrieben.
Vor dem ersten Payload-Schreibzugriff prueft er den erfolgreichen Bericht,
das genaue Qdrant-Ziel, den aktiven Modellvertrag und die deterministische
Vektorstichprobe erneut. Punktzahl und Punkt-ID-Digest muessen vor und nach
dem Backfill passen. Fehlende `index_compatibility`-Payloads erhalten den
Vertrag und `index_provenance=legacy_verified`; bereits kompatibel
vektorisierte Punkte behalten ihre bisherige Punkt-Herkunft. Erst nach dem
Ruecklesecheck wird der Freigabemarker mit `provenance=legacy_verified`
atomar veroeffentlicht. Eine Collection mit schon vorhandenem Vertrag im
Marker kann nicht erneut als Legacy uebernommen werden. Bei Fehlern vor der
Markerfreigabe versucht der Befehl, seine Payload-Ergaenzungen zu entfernen;
ein fehlgeschlagener Ruecknahmeversuch meldet `rollback_incomplete`. Qdrant
bietet keine gemeinsame Transaktion fuer mehrere Payload-Chargen und die
Markerdatei; der Marker ist daher die verbindliche Freigabegrenze. Waehrend
der Uebernahme duerfen andere Qdrant-Schreiber ausserhalb dieser
Build- und Uebernahmepfade dieselbe Collection nicht veraendern.
Parallele `--apply`-Aufrufe und Builds fuer dasselbe Ziel und dieselbe Collection werden
ueber eine dauerhaft liegende Sperrdatei neben dem Freigabemarker serialisiert.
Alle Prozesse muessen dafuer dieselbe lokale Statuswurzel nutzen.

Die Freigabemarker unterscheiden einen nativ mit dem aktuellen Vertrag gebauten
Index von `legacy_verified`. Die eingeschraenkte Provenienz bleibt auch nach
erfolgreichen inkrementellen Ergaenzungen erhalten. Die Darstellung in der
Service-Oberflaeche ist in Phase 6 umgesetzt.

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
4. **Bestandsindex pruefen** startet die rein lesende Legacy-Pruefung und zeigt
   Stichprobe, Vergleichsergebnis und Abbruchgruende.
5. **Geprueften Bestand uebernehmen** wird nur nach einer erfolgreichen, noch
   aktuellen Bestandspruefung angeboten und schreibt erst nach ausdruecklicher
   Bestaetigung die `legacy_verified`-Metadaten. Collection, Stichprobenauswahl
   und Vergleichstoleranzen sind nicht frei eingebbar.

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

### Vorabvertrag fuer Phase 6

Vor M6.1 die vorhandenen Service-Fassaden, Command Builder, Jobpersistenz,
Status-API und die CLI-Ausgaben gemeinsam gegen folgende Regeln pruefen. Die
Oberflaeche zeigt Zustaende aus den bestehenden Status- und Berichtsfunktionen;
sie erfindet keine zweite Modell- oder Indexpruefung. Ein schneller Seitenaufruf
startet weder eine Tiefenpruefung noch einen Download oder einen Qdrant-Build.
Die letzte **ausgefuehrte** Pruefung stammt aus einem zugeordneten Servicejob;
der Erstellungszeitpunkt des Manifests ist kein Pruefzeitpunkt. Fehlt ein solcher
Job, zeigt die Seite keinen angeblichen Prueferfolg.

| Aktion oder Zustand | Verbindliche Grenze und erwartetes Ergebnis |
| --- | --- |
| Statusseite, lokal oder Server | Bereitschaft je Harrier, Tokenizer und BM25 samt konfigurierten und vorbereiteten Revisionen aus dem gemeinsamen Manifest; fehlende oder ungueltige Konfiguration wird als Zustand angezeigt. Keine Modell-Netzabfrage, kein Anlegen eines Qdrant-Stores. Speicherbedarf nur aus lokal lesbaren Daten. |
| Lokale Pruefung | Fester Aufruf `prepare_embedding_models.py --check --json`; kein Modell-Download und keine freie Pfad- oder Modellwahl. `fehlt`, `unvollstaendig` und `inkompatibel` bleiben im Ergebnis unterscheidbar, auch wenn der Job mit Exitcode 1 endet. |
| Vorbereitung | Fester Aufruf `--download --json` erst nach serverseitig gepruefter Bestaetigung. Token nur ueber die vorhandene Secret-Verwaltung; weder Kommando, persistierte Jobdaten noch Ausgabe, Fehler oder Logs enthalten ihn. Kein freier Hub-Parameter. |
| Legacy-Pruefung | Nur `ratsi_passages` und `ratsi_documents`; Landkreis liefert `rebuild_required` und verweist auf den getrennten Neuaufbau. Ziel, Quell-SQLite fuer `ratsi_documents` und Berichtspfad kommen aus serverseitiger Konfiguration, nicht aus POST-Feldern. Der Bericht ist je Ziel und Collection eindeutig abgelegt und wird vor Anzeige geprueft. |
| Legacy-Uebernahme | Eigene POST-Aktion mit CSRF und konkreter Bestaetigung der Collection. Nur ein verifizierter Bericht der aktuellen Version fuer genau Ziel, Collection und Quelle wird angeboten. Die CLI prueft unter der Collection-Sperre erneut; ein geaenderter oder inzwischen freigegebener Bestand endet ohne weitere Freigabe. |
| Parallele oder unterbrochene Jobs | Eine atomare Entscheidung vor Jobstart verhindert doppelte Schreibjobs auch ueber mehrere Webprozesse. Modellvorbereitung, Build und Uebernahme respektieren die benoetigten gemeinsamen Sperren auch bei direktem CLI-Start. Der Sperrbereich reicht bis Abschluss oder Abbruch; Wiederanlauf prueft den tatsaechlichen Bestand statt einen alten Jobstatus als Freigabe zu nutzen. Lock-Reihenfolge und gemeinsame Statuswurzel fuer Serverprozesse festlegen. |

Abgleich mit dem Bestand vor M6.1 (M6.0):

| Bestehender Pfad | Entscheidung fuer die Umsetzung |
| --- | --- |
| `web/data_tools/services.py`, `web/core/services/status.py`, `src/config/embedding_model_status.py` | Die Fassade erweitert den gemeinsamen Statuspfad um Anzeigedaten aus derselben validierten Manifestaufnahme einschliesslich Bibliotheksvergleich; kein getrenntes Nachladen des inzwischen austauschbaren Root-Manifests. Konfigurierte Revisionen stammen aus `src/config/embedding_models.py`. Der Bestand wird gemeinsam freigegeben: Ein Gesamtfehler ist keine Diagnose, dass jede einzelne Komponente defekt ist. Nicht verifizierbare Einzelwerte bleiben unbekannt. Artefaktgroessen als erfasste Pflichtdateien kennzeichnen, gemeinsame Dateien im Gesamtwert nicht doppelt zaehlen; kein rekursiver Scan aller Caches. Der bestehende Vektorstatus darf Qdrant abfragen, die Modellanzeige fuegt keinen Qdrant-Zugriff hinzu. |
| `scripts/prepare_embedding_models.py`, `src/embedding_model_preparation.py` | `--check --json` liefert `status`, `message`, `manifest_sha256`, `check_level`; bei Fehlerstatus Exitcode 1, bei ungueltiger Konfiguration 2. `--download --json` gibt ein anderes Ergebnisformat aus. Jobresultate je Aktion auswerten, Exitcode und fachlichen Status getrennt anzeigen. Kein `--check-updates` in Phase 6: die CLI bietet es derzeit nicht an. Der vorbereitete Bestand wechselt atomar per Manifest; seit M6.4/M6.9 serialisiert die gemeinsame Modellsperre Downloads und Verbraucher. |
| `web/core/services/commands.py`, `web/data_tools/views.py` | Neue Aktionen ausschliesslich ueber feste Befehle und eine je Aktion gepruefte Menge an POST-Feldern aufbauen. Die bestehenden Build-Formulare besitzen eigene optionale Parameter; diese duerfen nicht in Modell- oder Legacy-Aktionen uebernommen werden. Bestaetigung und erlaubte Collection serverseitig pruefen, bevor ein Job angelegt wird. |
| `web/core/service_jobs.py`, `src/paths.py` | Jobdaten liegen in `data/db/service_jobs.sqlite`. In-Memory-Sperre, einmaliges Laden und Loeschen/Neuschreiben aller Zeilen sind nicht prozesssicher. Zeilenweise Persistenz und aktuelle Datenbankabfragen muessen fuer alle Nutzer dieser Jobtabelle gelten, auch alte Fetch-/Build-Aktionen. Neue kollidierende Starts werden vor Threadstart transaktional reserviert; bei fehlender Persistenz kein ungesicherter In-Memory-Start. Das Laden durch einen zweiten Webprozess darf laufende fremde Jobs nicht als abgebrochen markieren. Wiederanlauf muss Besitzer und tatsaechlich noch laufenden Kindprozess beruecksichtigen; ein alter Jobstatus hebt niemals eine laufende CLI-Sperre auf. |
| `scripts/migrate_legacy_index.py`, `src/indexing/legacy_inspection_report.py`, `src/indexing/legacy_index_migration.py` | Die CLI kennt `--inspect`/`--apply`, `--collection`, `--report`, fuer `ratsi_documents` `--source-db` und fuer Apply `--confirm-collection`. Nur zwei Melle-Collections in der Web-Allowlist. Ziel aus `QdrantConnection.from_env`, Quell-DB aus der serverseitigen `LOCAL_INDEX_DB`-Zuordnung und Berichte unter `PRIVATE_DATA_DIR / legacy_inspections` ableiten. Pro Pruefjob einen eigenen Bericht behalten; Ziel-Hash, Collection, aufgeloeste Quelle und Job-ID binden. Vor Anzeige das Format pruefen: auch valide Abbruchberichte anzeigen, aber nur `verified` zur Uebernahme anbieten. Die bestehenden fachlichen Validierungen gemeinsam nutzbar machen, nicht im View nachbauen. Landkreis bleibt `rebuild_required` ohne Uebernahme. |
| `src/analysis/vector_store.py`, `src/indexing/passage_builder.py`, `src/indexing/legacy_index_migration.py`, Build- und Migrations-CLIs | Build und Uebernahme teilen bereits `_migration_lock()` je Collection. Der Standard-Ratsinfo-Build delegiert an `passage_builder.main`; auch den Legacy-Build und Landkreis abdecken. Legacy-Inspect und Apply rufen `inspect_legacy_collection()` auf, pruefen Modelle tief und berechnen Vektoren neu: beide benoetigen Schutz vor Modellwechseln. Fuer Vorbereitung, alle Builds, Inspect und Apply eine exklusive Modellsperre je aufgeloestem Modellverzeichnis vor der ersten Modellpruefung halten, bis Ergebnis/Freigabe/Rollback abgeschlossen und Clients geschlossen sind. Einheitliche Reihenfolge: Modellsperre, Collection-Sperre, lokaler Qdrant-Client. Bestehende innere Sperren nicht doppelt erwerben. Reine Status-/Check-Aufrufe bleiben schreibfrei und verwenden eine Manifestaufnahme. |
| `src/config/secrets.py`, `src/embedding_model_preparation.py`, `web/core/service_jobs.py` | Hub-Token im Vorbereitungsprozess per vorhandener Secret-Funktion beziehen. `_private_provider_output()` unterdrueckt bereits rohe SDK-Ausgaben und Logs; diese Grenze beibehalten. Im Webprozess unbekannte Kindprozess-Tokens lassen sich nicht verlaesslich durch Textersetzung entfernen. Deshalb sichere strukturierte Ergebnisfelder und feste Fehlercodes erzeugen; keine rohen Provider-Ausgaben oder Tracebacks als Jobresultat persistieren. Ergaenzende Redaktion bekannter Secrets schuetzt weitere Kanaele, ersetzt die Unterdrueckung aber nicht. Serverseitig abgeleitete Dateipfade sind legitime Befehlsargumente; Token, unbereinigte Ziel-URLs und frei eingegebene Pfade sind es nicht. |

Verbindliche Ergaenzungen aus der erneuten M6.0-Pruefung:

M6.4 und M6.7 duerfen schreibende Webaktionen erst freischalten, wenn die
zugehoerigen Sperr- und Persistenzvoraussetzungen aus M6.8/M6.9 vorliegen.
Die Aufgabenreihenfolge ist keine Erlaubnis fuer voruebergehend ungeschuetzte
Schreibpfade; notwendige Teile dieser Voraussetzungen vorziehen.

- **Pruefhistorie (M6.1/M6.8):** Ein Ergebnis gehoert zu Aktion, aufgeloestem
  Modellverzeichnis, Modellvertrag und Bibliotheksstand; bei Erfolg zusaetzlich
  zum Manifest-Hash. Den letzten abgeschlossenen Versuch samt Fehler anzeigen,
  nicht einen aelteren Erfolg bevorzugen. Laufende Jobs separat zeigen.
  Nach Bestands-/Konfigurationswechsel einen alten Erfolg als historisch
  kennzeichnen; nach Entfernung aus der Historie „kein gespeichertes
  Pruefergebnis“. Aktuelle Bereitschaft weiterhin lokal ermitteln.
- **Bestaetigungsbindung (M6.4/M6.7):** Download-Bestaetigung an den angezeigten
  Modellvertrag und das konfigurierte Modellverzeichnis binden. Legacy-Apply
  zusaetzlich an einen serverseitig aufgeloesten Pruefjob und den Hash seines
  Berichts binden; kein beliebiger Berichtspfad aus POST. Aenderung zwischen
  Anzeige, POST und Kindprozessstart verlangt erneute Bestaetigung. Die CLI
  muss genau den bestaetigten Bericht verwenden und seine Bindung unter den
  Sperren erneut pruefen. Ein Zeitstempel allein belegt keine Aktualitaet;
  entscheidend bleibt die erneute fachliche Pruefung des Bestands.
- **Betriebsgrenze und Parallelitaet (M6.9):** Phase 6 unterstuetzt einen
  koordinierten Betrieb mit gemeinsamem Modellverzeichnis und zuverlaessigen
  Prozesssperren; dadurch laeuft auch ueber verschiedene Collections nur ein
  Build gleichzeitig. Web und CLI verwenden dieselbe Pfadaufloesung und
  Sperrimplementierung. Fuer ein Server-Ziel muessen zudem dieselbe
  `RATSI_QDRANT_STATE_DIR`-Wurzel verwendet werden. Alle Webprozesse teilen
  zudem Jobdatenbank und Berichtswurzel. Mehrere Rechner mit getrennten Zustandsverzeichnissen sind damit
  nicht koordiniert; verteilte Sperren sind ausserhalb Phase 6. Web meldet
  beschaeftigt ohne zweiten Jobstart; direkte CLI-Aufrufe duerfen kontrolliert
  warten. Nach Sperrerwerb Konfiguration und Bestand erneut validieren.
  Sperrdateien bleiben bestehen; nicht ihr Vorhandensein, sondern die aktive
  Betriebssystemsperre entscheidet. Beim lokalen Store Client erst nach
  Sperrerwerb oeffnen, damit ein wartender Job ihn nicht vorzeitig blockiert.

Die folgenden Faelle bilden die Testmatrix fuer M6.1 bis M6.10; vor dem
Phase-6-PR werden sie als Workflow-Tests mit Fake-CLI und isolierten Qdrant-
Bestanden nachgeprueft:

| Fall | Eingaben und erwartete Grenze |
| --- | --- |
| T6-A Status | Bereit/fehlt/unvollstaendig/inkompatibel, ungueltiges `RATSI_MODELS_DIR`, abweichende Bibliotheksversion, lokal/Server und Qdrant erreichbar/nicht erreichbar. GET und Status-API loesen weder Download, Tiefenpruefung noch Qdrant-Build aus; pro Komponente keine erfundene Revision oder Pruefzeit. |
| T6-B Modellaktionen | `--check --json` ohne Netz und Dateiaenderung, Exitcode 0/1/2; `--download --json` nur nach richtiger Bestaetigung. Unbekannte Aktion, zusaetzliche Modell-ID, Revision, Zielpfad, CLI-Argumente und manipulierte POST-Felder werden abgewiesen. Fehlendes/ungueltiges CSRF-Token startet keinen Job. |
| T6-C Legacy-Pruefung | Lokales und Server-Ziel; leere, alte, bereits freigegebene und im Aufbau befindliche Collection. `ratsi_documents` mit Standard- und serverseitig konfigurierter Quell-SQLite, Bericht je Ziel/Collection eindeutig. Landkreis liefert `rebuild_required` und erzeugt keinen Uebernahmejob. |
| T6-D Legacy-Freigabe | Gueltiger, veralteter, abgebrochener, fremder oder unlesbarer Bericht; falsches Ziel, Collection, Quelle oder Format. Fehlende/falsche Bestaetigung und freie Stichproben-/Toleranzwerte werden abgewiesen; erneute CLI-Pruefung unter Collection-Sperre, keine Freigabe bei geaendertem Bestand, sicherer Abbruch auch nach teilweisem Payload-Backfill. |
| T6-E Parallelitaet | Zwei gleichzeitige POSTs aus getrennten Webprozessen sowie direkter CLI-Start gegen Webjob: genau ein kollidierender Schreibjob laeuft. Auch Builds verschiedener Collections und Legacy-Inspect/Apply gegen Vorbereitung testen; Standard-Passage-Build und Legacy-Build einbeziehen. Unterbrechung vor/nach Teil-Download und bei Backfill, Neustart mit verbliebenem Jobdatensatz und erneute Bestandspruefung vor Freigabe. |
| T6-F Jobs und Secrets | Letzte Pruefung fehlt/aktiv/erfolgreich/fehlgeschlagen/aus Historie entfernt; Jobdetail und Status-API stimmen ueberein. Token und URL-Geheimnisse erscheinen weder in Befehlsliste, SQLite, Ausgabe, letzter Zeile, JSON-Antwort noch Log, auch bei Fehlermeldung und abgebrochenem Prozess. |
| T6-G Bindung und Manifestwechsel | Zwischen Anzeige, POST und Ausfuehrung Modellverzeichnis, Konfiguration, Bibliotheksstand, Manifest oder Bericht austauschen: keine falsche Bereitschaft und keine Uebernahme unter alter Bestaetigung. Ein neuer fehlgeschlagener Pruefjob wird statt eines aelteren Erfolgs als letzter Versuch angezeigt. Abbruchberichte bleiben sichtbar. |
| T6-H Mehrprozess-Persistenz | Neuer Modelljob parallel zu bestehendem Fetch-/Build-Job; Laden/Statusabfrage durch zweiten Webprozess, Datenbankfehler, Thread-/Prozessstartfehler und Webneustart bei noch lebendem Kindprozess. Keine verlorenen Jobzeilen, keine falsche Freigabe; Reservierung nach nachgewiesenem Ende wieder nutzbar. Secret-Faelle auch mit nur im Kindprozess bekanntem Token, kodierten und auf mehrere Ausgaben verteilten Werten. |

Die Web-/Service-Matrix fuer M6.10 liegt in
`tests/test_model_management_security.py`; die bestehenden Modellvorbereitungs-,
Legacy- und Historientests ergaenzen sie. Der gezielte Lauf ist
`python -m pytest tests/test_model_management_security.py -q`.
Die Matrix verwendet temporaere Jobdatenbanken, signierte Formulare und eine
Fake-CLI. Sie prueft CSRF-Ablehnung vor Jobreservierung, feste Aktionen und
POST-Felder, ausdrueckliche Bestaetigung, Bibliothekswechsel vor POST und
Reservierung sowie Status-/Exitcode-Abgleich. Private Kindprozessausgaben
werden bei Erfolg, Startfehler, Lesefehler und Prozessabbruch gegen SQLite,
HTML, Job-/Historien-/Status-JSON und Logs geprueft; auch URL-kodierte und
auf mehrere Ausgaben verteilte Secrets sind enthalten.

Keine Tests mit echten Downloads oder produktiven Qdrant-Bestaenden in der
regulaeren Suite.
Phase 6 loest keinen Neuaufbau der Melle-Collections aus; der Landkreis-Neuaufbau
bleibt die separate Aufgabe in `docs/project_tasks.md`.

Vor einem Phase-6-PR den Gesamtdiff einmal gegen diese Matrix und die
Freigabe-/Sperrpfade lesen. Gezielt betroffene Unit- und Integrationstests
ausfuehren und den regulaeren Testlauf nur mit nachvollziehbarer, erlaubter
Umgebung durchfuehren. Neue Reviews sind anschliessend eine weitere Kontrolle.

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
7. Ein bestehender Melle-Legacy-Index kann nur nach erfolgreicher deterministischer
   Vektorstichprobe und ausdruecklicher Bestaetigung als `legacy_verified`
   uebernommen werden; ein Fehler laesst den Freigabemarker unveraendert. Falls
   eine Payload-Ruecknahme fehlschlaegt, koennen einzelne Metadaten ergaenzt
   bleiben, aber die Collection wird nicht freigegeben. Bei `ratsi_documents`
   muessen Pruefung und Freigabe dieselbe Quell-SQLite-Datei nutzen. Eine
   Landkreis-Legacy-Freigabe wird stattdessen vor Qdrant-Zugriffen abgewiesen;
   der gesonderte Neuaufbau speichert das gewaehlte Textlimit im Marker.
8. Ein inkompatibler Modell- oder Pipelinestand verhindert Schreibzugriffe auf
   eine bestehende Collection; die Legacy-Uebernahme kann diese Sperre nach einer
   echten Vertragsaenderung nicht umgehen.
9. Servicebefehle sind fest vorgegeben; Tests decken unzulaessige Parameter,
   CSRF-Schutz, Secret-Redaktion, Statusdarstellung und Servicejobs ab.
10. Parallele kollidierende Vorbereitungs-, Uebernahme- und Buildlaeufe koennen
    keinen freigegebenen Modellbestand beschaedigen.
11. README, `docs/search_quality.md`, `docs/web_ui.md`, Datenverarbeitungskonzept
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

- [x] **M1.1** Bestehende Modellnamen, Revisionen, Dimensionen, Cachepfade und
  Pipelinekennzeichen vollstaendig inventarisieren.
- [x] **M1.2** `src/config/embedding_models.py` mit unveraenderlichen, typisierten
  Definitionen fuer Harrier, Tokenizer und BM25 einfuehren.
- [x] **M1.3** Feste bekannte Revisionen ermitteln und dokumentieren; bewegliche
  Referenzen wie `main` aus der produktiven Konfiguration ausschliessen.
- [x] **M1.4** Pipeline-Version und Manifestformat-Version fachlich definieren.
- [x] **M1.5** Manifest-Schema, kanonische Serialisierung und deterministische
  Auswahl relevanter Pruefsummen implementieren.
- [x] **M1.6** Unit-Tests fuer Konfiguration, Schema, Manifest-Hash und unzulaessige
  Modellangaben ergaenzen.
- [x] **M1.7** Phase 1 pruefen und als eigenen Zwischenstand committen.

### Phase 2: Lokaler Modellstatus

- [x] **M2.1** Zentralen Pfad fuer `data/models/` in der Laufzeitkonfiguration
  bereitstellen, ohne eine Downloadfreigabe fuer Verbraucher einzufuehren.
- [x] **M2.2** Schnelle lokale Pruefung fuer Manifest, Revisionen, Pfade,
  Dateiexistenz und Groessen implementieren.
- [x] **M2.3** Optionale Tiefenpruefung der festgelegten SHA-256-Werte
  implementieren.
- [x] **M2.4** Gemeinsames Statusmodell `bereit`, `fehlt`, `unvollstaendig` und
  `inkompatibel` fuer CLI und Web definieren.
- [x] **M2.5** Tests mit temporaeren vollstaendigen, fehlenden, beschaedigten und
  revisionsfremden Modellbestaenden ergaenzen.
- [x] **M2.6** Nachweisen, dass beide Pruefstufen ohne Netzwerkzugriff arbeiten.
- [x] **M2.7** Phase 2 pruefen und als eigenen Zwischenstand committen.

### Phase 3: Vorbereitungsskript

- [x] **M3.1** `scripts/prepare_embedding_models.py --check` auf die gemeinsame
  lokale Prueflogik aufsetzen.
- [x] **M3.2** `--check --deep` mit eindeutiger, maschinenlesbarer und
  menschenlesbarer Ausgabe ergaenzen.
- [x] **M3.3** `--download` fuer ausschliesslich fest konfigurierte Revisionen
  implementieren.
- [x] **M3.4** Download in ein temporaeres Ziel, Vollstaendigkeitspruefung und
  atomare Freigabe unter `data/models/` implementieren.
- [x] **M3.5** Wiederaufnahme beziehungsweise sichere Wiederverwendung bereits
  vollstaendiger Artefakte festlegen.
- [x] **M3.6** Erwartbare Fehler fuer Netz, Speicherplatz und unvollstaendige
  Artefakte ohne langen CLI-Traceback behandeln.
- [x] **M3.7** Tokenweitergabe und Log-Redaktion mit Tests absichern.
- [x] **M3.8** Downloadtests ohne echten Hub sowie getrennte, markierte Live-Tests
  fuer den realen Anbieter ergaenzen.
- [x] **M3.9** Phase 3 pruefen und als eigenen Zwischenstand committen.

### Phase 4: Verbraucher strikt lokal umstellen

- [x] **M4.1** Harrier-Embedder und Tokenizer auf vorbereitete lokale Pfade und
  feste Revisionen umstellen.
- [x] **M4.2** BM25/FastEmbed auf den vorbereiteten lokalen Bestand umstellen.
- [x] **M4.3** Doppelte Modelldefinitionen aus Passage-, Embedding-, Evaluations-
  und Suchcode entfernen.
- [x] **M4.4** `INDEXER_ALLOW_MODEL_DOWNLOADS` und andere Modell-Downloadpfade aus
  Indexierung und Suche entfernen.
- [x] **M4.5** Vor Modellinitialisierung die schnelle lokale Manifestpruefung und
  handlungsorientierte Fehlermeldungen integrieren.
- [x] **M4.6** Offline-Tests fuer Ratsinfo-Build, Landkreis-Build, Evaluation und
  Websuche ergaenzen; unerwartete Hub-Aufrufe muessen die Tests fehlschlagen
  lassen.
- [x] **M4.7** Phase 4 pruefen und als eigenen Zwischenstand committen.

### Phase 5: Indexkompatibilitaet

- [x] **M5.1** Kompatibilitaetsdatensatz aus Modell-IDs, Revisionen,
  Manifest-Hash, Dimension und Pipeline-Version zentral erzeugen.
- [x] **M5.2** Lokale und serverbezogene Qdrant-Freigabemetadaten um diesen
  Datensatz erweitern.
- [x] **M5.3** Erforderliche Modell- und Pipelineangaben in Punkt-Payloads fuer
  Ratsinfo- und Landkreis-Collections konsistent hinterlegen.
- [x] **M5.4** Rein lesende Bestandspruefung und deterministische
  Vektorstichprobe fuer die einmalige Legacy-Uebernahme implementieren.
- [x] **M5.5** Uebernahmeprotokoll, feste Vergleichstoleranzen und eindeutige
  Abbruchgruende fuer unzureichende oder widerspruechliche Nachweise definieren.
- [x] **M5.6** Ausdruecklich bestaetigte, atomare Freigabe als `legacy_verified`
  und Payload-Backfill ohne Veraenderung vorhandener Vektoren implementieren.
- [x] **M5.7** Kompatibilitaetspruefung vor dem ersten Schreibzugriff eines Builds
  durchsetzen.
- [x] **M5.8** Inkompatible inkrementelle Fortsetzung mit kurzer Meldung und
  Hinweis auf Neuaufbau beziehungsweise Aufbau-Collection verhindern.
- [x] **M5.9** Migrations-, Stichproben-, Abbruch-, Atomizitaets- und
  Wiederanlauftests fuer native, uebernommene und inkompatible Indexstaende
  ergaenzen.
- [x] **M5.10** Phase 5 pruefen und als eigenen Zwischenstand committen.

Nachtrag zur Abnahme nach PR #80: Die historische Landkreis-Uebernahme aus
M5.6/M5.9 wird nicht mehr freigegeben. Tests pruefen den lesenden Nachweis,
den Abbruch `rebuild_required` ohne Qdrant-Schreibzugriff und den nativen
Neuaufbaupfad; `ratsi_documents` verlangt einen quellgebundenen Bericht.

### Phase 6: Service-Oberflaeche

Die Modell- und Reasoning-Empfehlungen folgen der aktuellen Uebersicht in
[`project_tasks.md`](project_tasks.md#aktuelle-gpt-modellreihe). Sie dienen als
Orientierung und sind keine Vorgabe fuer die Bearbeitung.

- [x] **M6.0** Vorabvertrag und Testmatrix oben gegen die bestehenden
  Service-, Job-, Modell- und Qdrant-Pfade abgleichen; offene Entscheidungen
  vor der View-Implementierung festhalten. `[Schwer · GPT-6 Astra / High]`
- [x] **M6.1** Modellstatus in die Service-Fassade und Statusantworten des
  Datenbereichs aufnehmen. `[Mittel · GPT-6 Sol / Medium]`
- [x] **M6.2** Statusdarstellung fuer Harrier, Tokenizer und BM25 unter
  `/daten/vektor/` ergaenzen. `[Mittel · GPT-6 Sol / Medium]`
- [x] **M6.3** Feste Serviceaktion fuer die rein lokale Pruefung implementieren.
  `[Leicht · GPT-6 Luna / Medium]`
- [x] **M6.4** Feste, bestaetigungspflichtige Serviceaktion fuer die Vorbereitung
  der konfigurierten Revisionen implementieren. `[Mittel · GPT-6 Sol / Medium]`
- [x] **M6.5** Freie Modell-IDs, Revisionen, Zielpfade und zusaetzliche
  Kommandoargumente in Formular und Command Builder ausschliessen.
  `[Mittel · GPT-6 Sol / Medium]`
- [x] **M6.6** Feste rein lesende Serviceaktion fuer die Legacy-Bestandspruefung
  und Darstellung des Uebernahmeprotokolls implementieren; nur Melle-Collections,
  mit serverseitig gebundenem Ziel, Quellpfad und Berichtspfad.
  `[Schwer · GPT-6 Astra / Medium]`
- [x] **M6.7** Bestaetigungspflichtige Uebernahmeaktion nur fuer ein erfolgreiches,
  noch aktuelles Pruefergebnis erlauben; freie Collection-, Stichproben- oder
  Toleranzparameter ausschliessen. Programmatische erneute Pruefung unter
  Collection-Sperre bleibt verbindlich. `[Schwer · GPT-6 Astra / High]`
- [x] **M6.8** Fortschritt und Ergebnis ueber die bestehende Servicejob- und
  Jobdetail-Infrastruktur anzeigen. `[Mittel · GPT-6 Sol / Medium]`
- [x] **M6.9** Kollidierende parallele Modellvorbereitungen, Legacy-Uebernahmen
  und Vektor-Builds auch ueber Webprozesse und direkte CLI-Aufrufe verhindern
  oder sicher serialisieren; Abbruch und Wiederanlauf einbeziehen.
  `[Schwer · GPT-6 Astra / High]`
- [x] **M6.10** CSRF-Schutz, Befehls-Allowlist, Bestaetigungsbindung,
  Secret-Redaktion, Statuswerte und Jobstart mit Web- und Service-Tests
  absichern. `[Schwer · GPT-6 Astra / High]`
- [x] **M6.11** Phase 6 pruefen und als eigenen Zwischenstand committen.
  `[Mittel · GPT-6 Sol / Medium]`

#### Abschlusspruefung M6.11 (2026-10-02)

Gepruefter Ausgangsstand: `f26ceb05721148458373e473f2f4a8a370d1805f`.
Der Phase-6-Gesamtdiff ab `6d628bc` (Abschluss von Phase 5 und PR #81)
wurde einschliesslich der Sicherheitsmatrix aus M6.10 und der echten
PDF-Testdateien geprueft. Statusquelle, feste Webbefehle, Bestaetigungs- und
Berichtsbindung, Freigabegrenzen, Jobpersistenz, Sperrreihenfolge und
Wiederanlauf sind mit den Faellen T6-A bis T6-H abgeglichen.

| Bereich | Automatisierter Nachweis |
| --- | --- |
| T6-A/B: lokale Bereitschaft, Status-API und feste Modellaktionen | `test_embedding_model_status.py`, `test_web_pages.py`, `test_web_services.py`, `test_model_preparation_web.py`, `test_service_status_javascript.py` |
| T6-C/D: quellgebundene Melle-Berichte, erneute Pruefung und bestaetigte Freigabe; Landkreis nur Neuaufbau | `test_web_legacy_inspection.py`, `test_web_legacy_apply.py`, `test_migrate_legacy_index.py`, vorhandene Legacy-/Build-Tests |
| T6-E/H: Web-/CLI-Parallelitaet, Reservierung, Client-Lebensdauer, Abbruch und Wiederanlauf | `test_model_operation_coordination.py`, `test_model_preparation_web.py`, `test_build_compatibility.py` |
| T6-F/G: Historie, Manifest-/Vertragswechsel, CSRF und private Kindprozessausgaben | `test_model_job_history.py`, `test_model_job_history_javascript.py`, `test_model_management_security.py` |
| PDF-Zwischenschritt: Original-Pruefsummen, Text/Unicode/Zahlen, Passage-Abdeckung, Scan-Zuordnung, abgeschnittene Dateien und Groessenlimits | `test_pdf_fixtures.py` sowie vorhandene Extraktions-/Passage-Tests |

Testumgebung: isoliertes Linux-Python `3.12.14`, pytest `9.1.1`, Django
`5.2.17`, pypdf `6.9.2`, Qdrant-Client `1.19.1`. Modell-/Providerpfade
verwenden Mocks beziehungsweise einen kleinen Fake-Hub; echte Downloads,
Harrier-Ladevorgaenge und produktive Qdrant-Bestaende wurden nicht verwendet.
Der FastEmbed-BM25-Test verwendet ausschliesslich seinen temporaeren lokalen
Mini-Snapshot und blockiert Hub-Aufrufe. Native OCR wird in den neuen
PDF-Workflows simuliert; der 300-Seiten-Test liest echte Originalseiten.

Der erste regulaere Gesamtlauf `python -m pytest -q` bestand mit
1097 Tests, zwei uebersprungenen Tests und sieben ausgeschlossenen Live-Tests.
Nach Ergaenzen der FastEmbed-Laufzeitabhaengigkeiten besteht der lokale
BM25-Test separat; der aktivierte 300-Seiten-PDF-Test besteht ebenfalls.
Der abschliessende Gesamtlauf umfasst beide zusaetzlich:

```bash
RATSI_PDF_STRESS=1 python -m pytest -q
```

Ergebnis: **1099 bestanden, keine uebersprungenen Tests, sieben Live-Tests
abgewaehlt** (38,12 Sekunden). Alle regulaeren Unit- und Integrationstests
sind damit fuer denselben Quellstand geprueft. Der Phase-6-Gesamtdiff und die
abschliessenden Dokumentationsaenderungen bestehen `git diff --check`.
Es wurden keine neuen Implementierungsfehler gefunden; veraltete
Zukunftsaussagen zu Prozesssperren und Service-Oberflaeche sind korrigiert.

Phase 6 ist als technischer Zwischenstand abgeschlossen. Die praktische
Abnahme mit den vorbereiteten Modellen auf Dianes System, nativen Windows-
Sperren und echter Suche bleibt Phase 7. Produktive Melle-Collections wurden
weder uebernommen noch neu aufgebaut; der Landkreis-Neuaufbau bleibt die
separate Aufgabe in `project_tasks.md`. Fuer diesen Doku-/Abschlusscommit
bleiben `VERSION` bei `0.5.47` und die Extraktionspipeline bei `1.3`.

### Phase 7: Gesamtabnahme und Dokumentation

Zwischenstand vom 4. Oktober 2026: Der erneut ausgefuehrte lokale WSL-Gesamtlauf
besteht mit **1102 Tests, einem uebersprungenen PDF-Belastungstest und sieben
abgewaehlten Live-Tests** (411,30 Sekunden). Die native Windows-Abnahme der drei
Sperr-/Vorbereitungs-/Buildmodule deckte Testhilfenfehler auf: Die globale
Thread-Start-Sperre traf auch die Reader-Threads von `subprocess`; der Windows-
venv-Launcher hinterliess beim alleinigen Beenden des Launchers den eigentlichen
Python-Prozess. Die Testhilfe beendet jetzt unter Windows den eigenen Prozessbaum
mit `taskkill /T /F` und wartet vor dem Schliessen der Eingabepipe. Der Thread-Patch
ist auf den Webstart begrenzt. Nur fehlende native Windows-Symlink-Rechte
(`WinError 1314`) ueberspringen den entsprechenden Test.
Der native Nachlauf besteht mit **136 Tests und einem voraussetzungsbedingt
uebersprungenen Symlink-Test** (39,04 Sekunden); die Sperrfreigabe nach Prozessende
und die Wiederaufnahme des abgebrochenen Downloads sind dabei erfolgreich.
Laufzeitcode und `VERSION` (`0.5.48`) bleiben unveraendert.
Ein echter, separat heruntergeladener und tief gepruefter Abnahmebestand liegt
lokal unter `data/processed/embedding_acceptance_20261004/models/`;
Manifest-Hash: `478077ff73fbf75e6e4e1660de2c9c6d8cbbbab6d9864c7ffe06ee87d34314c9`.
Offline-Build und Suche werden als naechster Schritt am isolierten Testindex
geprueft; produktive Collections bleiben unberuehrt.

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

- Phase 4 umgesetzt auf `codex/feature/embedding-model-management-phase-4`:
  Harrier, Passage-Tokenizer und BM25 nutzen ausschliesslich die per Manifest
  geprueften lokalen Snapshots. FastEmbed bekommt `specific_model_path` und
  `local_files_only=True`; Harrier und der Tokenizer erhalten lokale Pfade und
  `local_files_only=True`. Die Modell-IDs, Dimension und Pipeline-Version kommen
  aus `src/config/embedding_models.py`; der alte Indexer-Downloadschalter ist
  entfernt. Fehlende oder inkompatible Modelle liefern einen kurzen Hinweis auf
  den Vorbereitungsbefehl; die Websuche verlinkt den technischen Servicebereich.
  Betroffene Build-, Evaluations- und Websuchtests sperren unerwartete Hub-Downloads.
  Ein FastEmbed-Test laedt BM25 direkt aus einem kleinen lokalen Testbestand.
  Die gemeinsame Bereitschaftspruefung und jeder Verbraucher vergleichen zudem
  den vollstaendigen Bibliotheksversionssatz aus dem Manifest mit den installierten
  Versionen. Abweichungen und fehlende Bibliotheken liefern `inkompatibel` und
  sperren die Modellinitialisierung. Der vollstaendige
  Lauf `python -m pytest` mit den Projektabhaengigkeiten
  bestand nach dem Review-Fix mit **617 Tests**, 7 Live-Tests blieben abgewählt. Es wurden keine
  echten Modellgewichte heruntergeladen.
  Die praktischen Builds und die Suche mit echten vorbereiteten Modellen bleiben
  Teil der Gesamtabnahme in Phase 7. Allgemeine Version: `0.5.17`.
- Phase 5 begonnen auf `codex/feature/embedding-model-management-phase-5`:
  M5.1 fuehrt den zentralen `IndexCompatibility`-Datensatz ein. Er wird nur aus
  einem lokal geprueften Modellbestand erzeugt und enthaelt alle neun Pflichtfelder
  fuer spaetere Qdrant-Freigaben. Zehn gezielte Tests bestehen. Noch keine
  Freigabemarker, Payloads oder bestehenden Collections wurden veraendert;
  `VERSION` bleibt fuer diesen internen Baustein bei `0.5.17`.
- M5.2 erweitert die lokale und URL-bezogene Marker-API fuer alle drei
  Collections. Neue Passage-Freigaben enthalten den geprueften
  Kompatibilitaetsdatensatz; Marker werden atomar geschrieben und beim Lesen
  an Collection und Serverziel gebunden. Die gezielten Qdrant- und
  Kompatibilitaetstests bestehen mit 49 Tests; ein breiterer Lauf wurde
  nach 73 bestandenen Tests wegen eines langsam laufenden Folgetests
  abgebrochen. Die Legacy- und Landkreis-Builder erhalten
  ihren Freigabeschreibvorgang erst mit M5.7, damit vorhandene Daten nicht
  ungeprueft gestempelt werden. Allgemeine Version: `0.5.18`.
- M5.3 schreibt `index_compatibility` in neu vektorisierte Passage-, Legacy-
  und Landkreis-Punkte. Bestehende Punkte erhalten bei reinen Snippet-Updates
  keine neue Herkunftsangabe. Drei Build-Integrationstests und zwei Tests
  fuer bestehende Snippet-Payloads bestehen; die umfassende Phasenabnahme
  folgt mit M5.9/M5.10.
  Allgemeine Version: `0.5.19`.
- M5.4 implementiert die rein lesende Legacy-Bestandspruefung mit
  Tiefenpruefung des Modellbestands, Schema-/Hinweispruefung, fest auf 32
  Punkte begrenzter deterministischer Stichprobe und lokaler Neuberechnung
  beider Vektortypen. Dreizehn gezielte Tests mit kleinem Qdrant-Lokalbestand
  bestehen, darunter Rekonstruktion fuer alle drei Collections und Abbrueche
  bei widerspruechlichen Vektoren, Texten, Markern und unvollstaendiger
  Stichprobe. Es wurden keine echten Modellgewichte geladen. Allgemeine
  Version: `0.5.20`.
- M5.5 schreibt ein atomisches JSON-Pruefprotokoll fuer erfolgreiche und
  abgebrochene Legacy-Pruefungen. Zielbindung per SHA-256 der vollstaendigen
  Zieladresse, UTC-Zeitpunkt, feste absolute und relative Toleranzen sowie
  stabile Abbruchcodes sind dokumentiert; keine Freigabe oder Qdrant-Aenderung.
  Allgemeine Version: `0.5.21`.
- M5.6 fuehrt die bestaetigte Uebernahme nach erneuter Bestandspruefung aus.
  Fehlende Punkt-Payloads werden ohne Vektorschreibzugriff ergaenzt und vor
  der atomaren Markerfreigabe zurueckgelesen; bei Fehlern erfolgt ein
  Rollback-Versuch. Ein CLI bietet getrennte Pruef- und Freigabebefehle.
  25 gezielte Legacy- und CLI-Tests bestehen. Allgemeine Version: `0.5.22`.
- M5.7 prueft alle drei Builder vor ihrem ersten Qdrant-Schreibzugriff gegen
  einen passenden Freigabemarker. Neue Builds und Fortsetzungen halten den
  Vertrag mit `ready=false` fest und stellen nach Abschluss `ready=true` her;
  `legacy_verified` bleibt erhalten. Gezielte Build- und Qdrant-Tests bestehen.
  Allgemeine Version: `0.5.23`.
- M5.8 liefert fuer alle drei Builds eine einzeilige CLI-Meldung mit Grund,
  Exitcode `1` und Hinweis auf Neuaufbau oder Aufbau-Collection. Tests pruefen
  fehlende und abweichende Marker ohne Qdrant-Schreibzugriff oder Traceback.
  Allgemeine Version: `0.5.24`.
- M5.9 ergaenzt End-to-End-Uebernahmen fuer Ratsinfo-Dokumente und Landkreis,
  Matrix-Tests fuer native und `legacy_verified`-Fortsetzungen aller drei
  Collections, einen nach dem Bericht geaenderten Stichprobenvektor sowie
  atomare Protokollablage. Fehler in einer teilweise geschriebenen Payload-
  Charge und bei der Ruecknahme lassen den alten Marker bestehen; Wiederanlauf
  mit demselben Bericht ist geprueft. Die 108 betroffenen Tests bestehen ohne
  echte Modellgewichte oder produktive Qdrant-Aenderungen. `VERSION` bleibt
  fuer diesen reinen Testschritt bei `0.5.24`.
- M5.10 prueft den Gesamtdiff von Phase 5 gegen M5.1 bis M5.9, die drei
  Build-Einstiege, den Migrationspfad, Freigabemarker, Punkt-Payloads,
  Versionsstand und die betroffenen Anleitungen. Die regulaeren Tests bestehen
  mit 438 Tests, die Integrationstests mit 245 Tests; der gesamte Standardlauf
  besteht mit 683 Tests (7 `live`-Tests ausgeschlossen). Zwei Aussagen zur
  Service-Darstellung und zu einer unvollstaendigen Payload-Ruecknahme wurden
  an den implementierten Stand angepasst. `VERSION` bleibt fuer diesen
  Pruef- und Dokumentationsschritt bei `0.5.24`.
- PR-Review-Nachbesserung: Die Websuche sperrt fehlende oder abweichende
  Modellvertraege vor der Query-Kodierung; die Legacy-Pruefung verlangt
  `committed=true` fuer alle Passagen; Builds pruefen das Qdrant-Vektorschema
  auch bei leeren vorhandenen Collections. Allgemeine Version: `0.5.25`.
- Weitere PR-Review-Nachbesserung: parallele Migrationen teilen sich eine
  pro Collection gesperrte Freigabe; fehlende Collections liefern einen
  strukturierten Abbruch; die Evaluations-CLI und Websuche sperren
  `ready=false` und inkompatible Marker; die Migration akzeptiert einen
  eigenen lokalen Qdrant-Pfad. Der Standardtestlauf besteht mit 708 Tests
  (7 `live`-Tests ausgeschlossen). Allgemeine Version: `0.5.26`.
- **M6.1** umgesetzt: `status.embedding_models` und die Daten-Service-Fassade
  liefern denselben schnellen Offline-Status aus einer validierten
  Manifestaufnahme, einschliesslich Bibliotheksvergleich. Vorbereitete
  Revisionen und Pflichtdateigroessen bleiben bei Gesamtfehlern unbekannt;
  gemeinsame Dateien werden im Gesamtwert einmal gezaehlt. Keine erfundene
  Pruefhistorie; deren Zuordnung folgt in M6.8. 162 gezielte Modell-, CLI-,
  Kompatibilitaets-, Webseiten- und Servicestatus-Tests bestehen, ohne echte
  Modelle oder produktive Qdrant-Bestaende. Allgemeine Version: `0.5.38`.
- **M6.2** umgesetzt: `/daten/vektor/` zeigt den gemeinsamen Modellstatus sowie
  Harrier, Tokenizer und BM25 mit konfigurierten/vorbereiteten Revisionen und
  Pflichtdateigroessen. Die manuelle Aktualisierung entfernt alte Einzelwerte
  bei einem Gesamtfehler; sie startet keinen Modelljob. Gespeicherte
  Pruefhistorie folgt in M6.8. 87 Web- und JavaScript-Tests bestehen.
  Allgemeine Version: `0.5.39`.
- **M6.3** umgesetzt: „Lokal pruefen“ startet `check_embedding_models` als
  bestehenden Servicejob mit festem `--check --json`. CSRF bleibt verbindlich;
  Zusatzfelder und doppelte Parameter werden vor Jobstart abgewiesen. Auch bei
  Exitcode 1 bleibt der fachliche Status in der Jobausgabe erhalten. Tests
  pruefen den Befehlsvertrag, POST/CSRF und einen echten CLI-Unterprozess mit
  fehlendem Bestand. Allgemeine Version: `0.5.40`.
- **M6.4** umgesetzt: „Modelle vorbereiten“ startet ausschliesslich den festen
  Befehl `--download --json`, nach expliziter POST-/CSRF-Bestaetigung. Die
  signierte Bestaetigung gilt 15 Minuten und bindet aufgeloesten Modellpfad,
  gepinnte Revisionen, Pipeline-/Manifestformat und Bibliotheksstand. Der
  Kindprozess prueft diese Bindung nach Sperrerwerb erneut. Konfigurationswechsel
  verlangt erneute Bestaetigung; es gibt keine freien Downloadparameter.
  Die notwendigen Teile von M6.8/M6.9 sind vorgezogen: transaktionale
  SQLite-Reservierung vor Workerstart, aktualisierte prozessuebergreifende
  Jobansicht und eine gemeinsame OS-Modellsperre fuer Vorbereitung, Downloads,
  Builds sowie Legacy-Inspect/-Apply. Reihenfolge bleibt Modellsperre,
  Collection-Sperre, Client. Sperrdateien bleiben nach Prozessende erhalten;
  das Betriebssystem gibt die Sperre frei. Ein lebender Eltern- oder
  Kindprozess behaelt seine Reservierung; erst nach Ende beider wird ein
  unterbrochener Job als fehlgeschlagen markiert. Alle Webprozesse muessen
  dieselbe Jobdatenbank und dieselben Zustandsverzeichnisse nutzen; verteilt
  betriebene Rechner bleiben ausserhalb des Vertrags.
  Vorbereitungsjobs speichern ausschliesslich erlaubte Ergebnisfelder,
  feste Fehlercodes und validierte Manifest-Hashes, keine rohen SDK-Ausgaben
  oder Tracebacks. Fehlende/veraltete/manipulierte Bestaetigung, CSRF,
  konkurrierende Webprozesse, Prozessabbruch, Persistenz-/Startfehler und
  private Provider-Ausgaben sind durch Regressionstests abgesichert.
  Zugeordnete Pruefhistorie und Legacy-Webaktionen bleiben fuer die folgenden
  Aufgaben offen. Allgemeine Version: `0.5.41`.
- **M6.5** umgesetzt: Modellpruefung und -vorbereitung verwenden dieselbe
  strikte Feldpruefung. Unbekannte Felder, doppelte Parameter, Nicht-Textwerte
  und widerspruechliche Aktionsnamen werden vor der Befehlsbildung abgewiesen.
  Modell-IDs, Revisionen, Modell-/Zielpfade und weitere CLI-Argumente bleiben
  ausschliesslich serverseitig vorgegeben. Formulartests pruefen die genaue
  Feldmenge; manipulierte POSTs mit gueltigem CSRF starten keinen Job.
  533 Unit-Tests und 176 betroffene Integrationstests bestehen; ein
  voraussetzungsabhaengiger Test ist uebersprungen. Keine echten Downloads
  oder produktiven Indexaenderungen. Allgemeine Version: `0.5.42`.
- **M6.6** umgesetzt: zwei feste Legacy-Pruefformulare fuer `ratsi_passages`
  und `ratsi_documents`. Signierte, 15 Minuten gueltige Zielbindung an
  Qdrant-Zielhash, Collection, konfigurierte Quell-SQLite, Berichtswurzel und
  Modellvertrag. Die CLI prueft diese Bindung unter der Modellsperre erneut,
  bevor sie einen Client oeffnet. Freie Pfade, Stichproben-/Toleranzparameter
  und Apply-Argumente werden abgewiesen. Jeder Job erhaelt seinen eigenen
  Bericht unter `PRIVATE_DATA_DIR / legacy_inspections / <job_id>.json`.
  Gemeinsame Format-, Zeitstempel- und Vergleichsvalidierung fuer Web und
  bestehende Uebernahme; der Webleser prueft zusaetzlich Ergebnisfelder,
  Ziel/Quelle, Dateigroesse, Symlinks und den gespeicherten Berichtshash.
  Verifizierte und gueltige Abbruchberichte erscheinen im Jobdetail und dessen
  Status-API. Konfigurationswechsel kennzeichnet einen Bericht als historisch;
  nachtraeglich veraenderte/unlesbare Berichte werden nicht als Ergebnis gezeigt.
  Rohes stdout/stderr des Pruefprozesses wird nicht als Jobausgabe gespeichert.
  Die bestehende transaktionale Jobreservierung und OS-Modellsperre decken
  auch Legacy-Pruefungen ab. Windows-Prozessstatus wird ohne `os.kill(pid, 0)`
  abgefragt; native API-Aufrufe sind mit Ersatzfunktionen getestet.
  Landkreis bleibt `rebuild_required` ohne Web-Uebernahme. Keine Payload-,
  Freigabemarker- oder produktiven Indexaenderungen. Gesamtsuite: 902 Tests
  bestanden, ein Test uebersprungen, sieben Live-Tests ausgeschlossen.
  Allgemeine Version: `0.5.43`.
- **M6.7** umgesetzt: Jobdetail bietet eine ausdruecklich bestaetigte
  Uebernahme nur fuer einen gespeicherten Pruefjob mit Status `ok`, Exitcode 0,
  verifiziertem und unveraendertem Bericht sowie passendem aktuellem Modell-
  und Zielvertrag an. Ein vorhandener Freigabemarker schliesst die Aktion aus.
  Signierte, 15 Minuten gueltige Bestaetigung bindet Pruefjob-ID, Ziel/Quelle,
  Modellvertrag und Berichtshash. Kein Collection-, Berichtspfad-, Stichproben-
  oder Toleranzparameter kommt aus POST. Jobstart liest den Pruefjob innerhalb
  der SQLite-Reservierung erneut; fehlende oder aus der Historie entfernte
  Belege starten keinen Uebernahmejob.
  Die CLI prueft die Bindung nach Erwerb der Modellsperre, erwirbt die
  Collection-Sperre vor dem lokalen Client und prueft den bestaetigten Hash
  vor Clientstart sowie nochmals beim Einlesen des tatsaechlich verwendeten
  Berichts unter beiden Sperren. Die bestehende tiefe Bestandspruefung vor
  Payload-Ergaenzung und Freigabemarker bleibt verbindlich. Collection-Sperren
  sind innerhalb desselben Threads wiedereintrittsfaehig, ohne erneute OS-Sperre.
  Webjobs speichern ausschliesslich feste Ergebnis-/Abbruchcodes und validierte
  Punktzahlen; keine Provider-Ausgaben oder Tracebacks. Tests decken die
  erfolgreiche Web-/CLI-Uebernahme am isolierten Qdrant-Testbestand,
  unveraenderte Vektoren, spaetere Bericht-/Punktlistenwechsel und Ruecknahme
  nach teilweise erfolgter Payload-Ergaenzung ab. Produktive Melle-Bestaende
  wurden nicht uebernommen; Landkreis bleibt die separate Neuaufbauaufgabe.
  Gesamtsuite: 944 Tests bestanden, ein Test uebersprungen, sieben Live-Tests
  ausgeschlossen. Allgemeine Version: `0.5.44`.
- **M6.8** umgesetzt; Modell-/Legacy-Historie zeigt je
  Aktion den letzten abgeschlossenen Versuch einschliesslich Fehlern und
  laufende Jobs separat. Persistierte Zuordnung bindet aufgeloesten Modellpfad,
  Modellvertrag und Bibliotheksstand; erfolgreiche Ergebnisse speichern den
  Manifest-Hash. Geaenderte Konfiguration oder Inventare erscheinen historisch,
  alte Jobs ohne Nachweis bleiben unverifiziert. Abschlusszeit wird dauerhaft
  gespeichert; Reihenfolge folgt Abschluss statt Start. Aufbewahrungsgrenze
  bleibt 50 Jobs; geloeschte Ergebnisse verschwinden bei Aktualisierung.
  Lokale Historienabfrage startet weder Downloads noch Qdrant-Probes.
  Jobdetails zeigen echten Lebenszyklus ohne erfundene Prozentwerte und
  aktualisieren Legacy-Protokolle nach Abschluss. SQLite-Schema wird additiv
  erweitert; produktive Modelle, Melle- und Landkreis-Indizes bleiben unberuehrt.
  Tests pruefen Zuordnung, Neustart, Fehler, Abbruch, veraltete Ergebnisse,
  Browser-Aktualisierung und Wiederherstellung nach Speicher-/Abruffehlern.
  Allgemeine Version: `0.5.45`.
- **M6.9** umgesetzt; gemeinsame Prozesssperren fuer
  Vorbereitung, Passage-/Legacy-/Landkreis-Build und Legacy-Inspect/-Apply
  vervollstaendigt. Builds behalten Modell- und Collection-Sperre bis zum
  Schliessen des Clients, auch nach Erfolg, abgelehntem Preflight oder
  fehlgeschlagener Markerpublikation. Legacy-Inspect erwirbt nun ebenfalls
  die Collection-Sperre vor Clientstart. Sperrdateien bleiben als Infrastruktur
  bestehen; Pruefungen veraendern weder Indexdaten noch Freigabemarker.
  Beide Sperrarten verwenden dieselbe OS-Implementierung. Unter Windows wird
  die nichtblockierende Byte-Sperre bei Belegung kontrolliert wiederholt;
  lange CLI-Wartezeiten enden nicht mehr nach zehn nativen Wiederholungen.
  Echte IO-Fehler werden nicht als Belegung verschluckt. Web meldet bei einer
  aktiven CLI-Sperre eindeutig „bereits aktiv“, ohne einen Job anzulegen.
  Tests mit getrennten Prozessen decken alle sechs CLI-Einstiegspfade,
  Collection-Wartezeiten, fortlaufenden Kindprozess nach Elternausfall,
  fehlerhaften gespeicherten Jobstatus und Neustart nach Prozessende ab.
  Eine waehrend des Wartens geaenderte Bestaetigung bricht vor Download ab.
  Ein hart beendeter Teil-Download behaelt den aktiven Bestand unveraendert;
  der Wiederanlauf verwendet den bestaetigten Dense-Snapshot weiter.
  Windows-API-Warte- und Fehlerpfade sind simuliert getestet; die native
  Windows-Abnahme mit echten Modellen bleibt fuer Phase 7 offen.
  Die vorhandenen Backfill-/Rollback- und Mehrprozess-Reservierungstests
  wurden mitgeprueft. Gesamtsuite: 997 Tests bestanden, ein Test uebersprungen,
  sieben Live-Tests ausgeschlossen. Keine produktiven Melle- oder
  Landkreis-Indexaenderungen. Allgemeine Version: `0.5.46`.
- Letzter abgeschlossener Punkt: **M6.10**; 63 neue Web-/Service-Tests
  sichern die vier Modell-/Legacy-Aktionen gegen fehlende, manipulierte und
  fremde CSRF-Tokens, freie und doppelte POST-Felder sowie ungueltige oder
  nach Bibliothekswechsel veraltete Bestaetigungen ab. Gueltige POSTs reservieren
  genau einen Job. Status und Exitcode werden mit Jobdetail und Historie
  abgeglichen; rohe, URL-kodierte und aufgeteilte Kindprozess-Secrets bleiben
  bei Erfolg, Startfehler, Lesefehler und Abbruch aus SQLite, HTML, JSON und Logs.
  Der gezielte neue Testlauf besteht mit 63 Tests. Der regulaere Gesamtlauf
  in einer isolierten Repositorykopie unter `/tmp` ergab 1051 bestandene Tests
  und zehn Starttimeouts; sieben Live-Tests waren ausgeschlossen. Kalte CLI-
  Importe benoetigten hier bereits rund 16 Sekunden. Die Startwartefristen
  der beiden betroffenen Testmodule wurden von zehn auf 60 Sekunden erhoeht;
  ihre Sperr- und Reihenfolgepruefungen bleiben vollstaendig erhalten.
  Der gezielte Nachlauf beider Module besteht mit 68 Tests einschliesslich
  aller zehn zuvor fehlgeschlagenen Faelle. Damit sind alle 1061 regulaeren
  Tests ueber Gesamtlauf und Nachlauf bestaetigt. Die getesteten Quelldateien
  wurden per SHA-256 mit dem Arbeitsbaum abgeglichen. Nur Tests und
  Dokumentation geaendert; allgemeine Version bleibt `0.5.46`.
- Zwischenschritt vor M6.11: Sechs unveraenderte Original-PDFs aus lokalen
  Rohdaten liegen unter `tests/fixtures/pdf/`, dazu eine abgeleitete Mischdatei
  und ein abgeschnittenes Original. Manifest und SHA-256 sichern Herkunft und
  Bytegleichheit. Offline-Tests lesen diese Dateien direkt und pruefen Seiten,
  Umlaute, Zahlen, Textbelege, Passage-Abdeckung und OCR-Zuordnung. Temporaere
  Dateien pruefen die echten 25-/100-MiB-Grenzen; ein optionaler Belastungstest
  erzeugt 300 Seiten aus Originalseiten. Die Original-Fixtures haben Fehler
  der lokalen Analyse bei Schriftdekodierung und Scan-Bilddaten aufgedeckt:
  Pipeline `1.3` nutzt fuer regulaere PDFs jetzt `pypdf` und behandelt unlesbare
  Strukturen kontrolliert als Fehler. Allgemeine Version: `0.5.47`.
  Betroffene PDF-/Extraktions-/Passage-Module: 63 Tests bestanden, ein
  optionaler Test uebersprungen. Der separat aktivierte 300-Seiten-Test besteht.
  Schneller Testkern: 586 Tests bestanden, 520 abgewaehlt; betroffene
  Landkreis-Integration: sechs bestanden, vier abgewaehlt. Keine erneute
  vollstaendige Suite und keine Live- oder nativen OCR-Laeufe.
- **M6.11** abgeschlossen: Gesamtdiff gegen Vorabvertrag und Testmatrix
  T6-A bis T6-H geprueft, einschliesslich M6.10 und des PDF-Zwischenschritts.
  Die Testnachweise und Betriebsgrenzen stehen im Abschlussprotokoll oben.
  Veraltete Zukunftsaussagen zur Service-Oberflaeche und zu Prozesssperren
  korrigiert. Nur Dokumentation geaendert; `VERSION` bleibt bewusst `0.5.47`,
  Extraktionspipeline `1.3`. Phase 6 wird als eigener Zwischenstand committed.
- Naechster regulaerer Punkt: **M7.1**; Gesamtabnahme beginnen. Der bereits
  gruene regulaere Testlauf kann fuer den unveraenderten Stand uebernommen
  werden; die praktische Offline-/Windows-Abnahme aus M7.2/M7.3 bleibt offen.

- Letzter abgeschlossener Punkt: **M3.9**; Phase-3-Gesamtdiff, Anforderungs-
  und Testabdeckung, CLI-/Manifestvertrag, Dokumentation und Versionsstand
  geprueft. Zwei veraltete Fortschrittsaussagen berichtigt; keine erneuten Tests
  oder Live-Downloads ausgefuehrt. Die Phase wird als eigener Zwischenstand
  committed; Phase 4 und die spaetere Gesamtabnahme bleiben offen.
  M3.8: Fake-Hub-Subprozess-Integrationstests
  sowie getrennte, doppelt freizugebende Live-Tests sind ergaenzt. Es wurden
  nur betroffene Tests ausgefuehrt, keine vollstaendige Testsuite und keine
  echten Anbieter-Downloads: Die vier Vorbereitungstestmodule liefern
  **107 bestanden, 2 Live-Tests abgewaehlt**. Bei expliziter Live-Auswahl ohne
  Opt-in werden beide Tests korrekt uebersprungen; beide sind separat sammelbar.
  `VERSION` bleibt fuer diesen Test-/Dokuschritt
  bewusst bei `0.5.15`.
  M3.7: Tokenprioritaet, anonymer Download,
  unveraenderte Token-Umgebung und unterdrueckte SDK-Ausgaben sind abgesichert.
  Tests decken Erfolg, Fehler, JSON-/Textausgabe, DEBUG-Logs, kodierte und
  verteilte Zugangsdaten sowie Offline-Wiederverwendung und Abbruch ab.
  Beide betroffenen Vorbereitungstestmodule bestehen mit 105 Tests.
  M3.6: Erwartbare Netzwerk-, Speicher-,
  Zugriffs- und Artefaktfehler liefern kurze Meldungen und stabile JSON-Fehlercodes.
  Das gemeinsame Komponentenlog erfasst sichere technische Diagnosefelder ohne
  rohe Ausnahmetexte oder Anbieter-Logs. Fehler beim Logzugriff werden ebenfalls
  ohne Traceback behandelt. Die gezielten Tests verwenden einen Fake-Hub und
  gesperrtes Netzwerk. Der Lauf
  `python -m pytest tests/test_embedding_model_preparation.py tests/test_prepare_embedding_models.py -q`
  ist mit 84 Faellen bestanden; der Log-Schreibfehler wurde zusaetzlich gezielt
  mit simuliertem ENOSPC geprueft. Keine vollstaendige Testsuite und kein echter
  Modell-Download wurden ausgefuehrt.
- PR-Review-Nachtrag nach M3.9: Zwei bestehende Fehlerhandler erfassen jetzt
  auch `RuntimeError` von der Pfadaufloesung. Regressionstests pruefen die
  sichere JSON-/Textausgabe, unveraenderte aktive Artefakte und ausbleibende
  Hub-Aufrufe. Die Python-Mindestversion bleibt unveraendert; `VERSION` ist
  fuer diesen sichtbaren Fehlerfix bewusst auf `0.5.16` angehoben.
  Die gezielten Regressionstests samt bestehender Symlink-/Fehlerdiagnosetests
  bestehen mit 14 Faellen; keine vollstaendige Suite und keine Live-Downloads.
- Nachtrag zur von Diane ausgefuehrten regulaeren Windows-Suite: 580 Tests
  bestanden, 3 uebersprungen und 7 abgewaehlt; zwei Archiv-Hook-Tests scheiterten
  wegen CRLF/LF-Konvertierung in temporaeren Test-Repositories. Die Testhilfe
  setzt dort jetzt lokal `core.autocrlf=false`, ohne globale oder Projekt-Git-
  Einstellungen zu aendern. Beide Faelle werden mit LF/CRLF und den globalen
  Einstellungen `false`, `true` und `input` abgesichert. Die strikte Bytepruefung
  des produktiven Archiv-Hooks bleibt unveraendert. Das betroffene Hook-Testmodul
  besteht mit 27 Tests unter WSL und erneut mit 27 Tests bei simulierter
  Windows-CRLF-Schreibweise. Reiner Testfix, daher bleibt
  `VERSION` bei `0.5.15`. Diane hat die pytest-Ausfuehrung inzwischen als
  abgeschlossen bestaetigt; ein neues Ergebnisprotokoll mit aktualisierten
  Zahlen wurde hier nicht uebermittelt. Fuer M3.9 erfolgt keine Wiederholung.
- Phase-3-Branch: `codex/feature/embedding-model-management-phase-3`, abgezweigt
  vom Feature-Branch nach dem Phase-2-Merge. Jeder Umsetzungsschritt erhaelt
  einen eigenen Commit. `VERSION` wurde fuer die SDK-Ausgabesicherung auf `0.5.15`
  angehoben.
- Aktiver Implementierungsstand: Zentraler Modell- und Versionsvertrag,
  Kernartefakt-Allowlists, Manifestschema, kanonische Serialisierung, Hashbildung
  und Eingabevalidierung sind implementiert. Der lokale Modellstamm ist in den
  Laufzeiteinstellungen standardmaessig `data/models/` und kann mit
  `RATSI_MODELS_DIR` ueberschrieben werden. Fuer bestehende Collections ist eine
  einmalige gepruefte Uebernahme als `legacy_verified` vorgesehen. Die lokale
  Schnellpruefung validiert Manifestvertrag, Dateipfade und -groessen und oeffnet
  alle Kernartefakte lesend, ohne deren Inhalte zu hashen. Sie arbeitet ohne
  Netzwerkzugriff. Mit `deep=True` prueft sie
  zusaetzlich alle festgelegten Artefakt-SHA-256-Werte lokal. Die gemeinsame
  Status-API liefert die vier vereinbarten Zustandswerte fuer CLI und Web. Tests
  pruefen vollstaendige, fehlende, beschaedigte und revisions- oder
  modellfremde Bestandsdaten; Netzwerkverbindungen sind waehrend schneller und
  tiefer Pruefung explizit blockiert. Phase 2 liegt auf
  `codex/feature/embedding-model-management-phase-2`, einem Unterbranch von
  `codex/feature/embedding-model-management`; beide zweigen nach dem Phase-1-Merge
  von `main` ab.
- Letzte zugehoerige Commits: `9747dda` fuer M3.1, `08abf5b` fuer M3.2,
  `723dcbe` fuer M3.3, `037ca53` fuer M3.4, `5bb21af` fuer M3.5 und `fd25bce`
  fuer M3.6, `f76892a` fuer M3.7 und `c76a23a` fuer M3.8; `a7ec74c` korrigiert
  die Windows-Hook-Testfixtures; `d4dc1f0` schliesst M3.9 ab.
  Phase 2 ist in den
  uebergeordneten Feature-Branch gemergt.
- Offene Blocker oder Entscheidungen: keine.
