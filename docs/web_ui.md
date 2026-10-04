# Django-Weboberfläche

## Zweck

Die Weboberfläche unter `web/` ist die lokale Arbeitsoberfläche für Ratsi Melle. Sie bündelt die bestehenden Analyseansichten, Datenpflegepfade und Servicefunktionen in einer klaren Django-Struktur.

Die Anwendung ist für den lokalen Betrieb auf dem Entwicklungsrechner gedacht. Sie ist nicht für öffentlichen Betrieb, Mehrbenutzerbetrieb oder Deployment ausgelegt und enthält keine Benutzerverwaltung.

`scripts/run_web.py` ist der primaere UI-Startpunkt.

## Start

```bash
python scripts/run_web.py
```

Danach ist das Dashboard erreichbar:

```text
http://127.0.0.1:8000/
```

Alternativ kann ein anderer Host oder Port übergeben werden:

```bash
python scripts/run_web.py 127.0.0.1:8001
```

## Warum `web/`

Die Django-Anwendung liegt bewusst unter `web/`, damit sie als lokale Oberfläche neben den bestehenden CLI-, Daten- und Analysemodulen entwickelt werden kann. Fachlogik aus `src/` wird nicht kopiert, sondern von den Web-Services genutzt. So bleibt die Weboberfläche ein separater Einstiegspunkt, ohne die bestehenden Skripte und Module zu ersetzen.

## Grundstruktur

```text
web/
  manage.py
  web/
    settings.py
    urls.py
  core/
    templates/base.html
    templates/core/dashboard.html
    static/core/css/
  analysis/
    urls.py
    views.py
    services.py
    templates/analysis/
  data_tools/
    urls.py
    views.py
    services.py
    templates/data_tools/
  publishing/
    urls.py
    views.py
    templates/publishing/
  search/
    urls.py
    views.py
    templates/search/
  settings_ui/
    urls.py
    views.py
    templates/settings_ui/
```

`core` enthält das gemeinsame Layout, das Dashboard, zentrale CSS-Dateien und gemeinsam genutzte Helfer. `analysis` enthält die Analyse-Navigation, Views und Service-Fassade für Sitzungen, Analysejobs, Prompt-Vorlagen und den Analyse-Start. `data_tools` enthält die Views und Service-Fassade für technische Fetch-, Build- und Servicejob-Funktionen. `search` enthält die semantische Dokumentensuche über den konfigurierten lokalen Qdrant-Vektorindex oder Qdrant-Server. `publishing` ist derzeit ein Platzhalter; `settings_ui` verwaltet bereits den optionalen Hugging-Face-Token.

Analyse-Seitentemplates und fachliche Analyse-Partials liegen ausschließlich unter `web/analysis/templates/analysis/`. Daten-Templates liegen ausschließlich unter `web/data_tools/templates/data_tools/`. `web/core/templates/` bleibt auf `base.html`, das Dashboard und gemeinsam nutzbare Core-Partials beschränkt.

## Navigation

Das gemeinsame Layout in `web/core/templates/base.html` stellt Header, Hauptnavigation, Inhaltsbereich und Footer bereit. Die Hauptpunkte sind als Dropdown-Menüs aufgebaut. Die Navigation zeigt:

- Dashboard
- Analyse mit Unterpunkten für Übersicht, Analyse starten, Antworten lesen, Prompt-Vorlagen, Sitzungen und Analysejobs
- Daten mit Unterpunkten für Fetch, Build und Vektorindex
- Veröffentlichung
- Suche
- Einstellungen

Die Navigation ist per Tastatur bedienbar, besitzt sichtbare Fokusmarkierungen und lässt sich auf kleinen Bildschirmen mit einem semantischen Menübutton öffnen. Ein Sprunglink führt direkt zum Hauptinhalt. Lange Formulare verwenden passende Zahlen-, Datums- und Suchfelder; sicherheitsrelevante Löschaktionen verlangen eine Bestätigung.

Der Header zeigt den Projektnamen "Ratsi Melle" und die Unterzeile "Lokale Arbeitsoberfläche". Der Footer markiert die Anwendung als lokale Entwicklungsoberfläche. Die CSS-Dateien liegen zentral unter `web/core/static/core/css/`:

- `base.css` für Grundvariablen und Basiselemente
- `layout.css` für Seitenstruktur
- `navigation.css` für Hauptnavigation und mobiles Menü
- `components.css` für Panels, Buttons, Tabellen und Formulare
- `status.css` für Status- und Hinweisfarben

Buttons folgen einem funktionsbezogenen Farbschema: `primary` ist auslösenden Hauptaktionen wie Starten, Speichern, Suchen oder Bauen vorbehalten; `secondary` kennzeichnet Navigation und reine Ansicht; `utility` steht für Filter, Reset und Abbruch; `danger` kennzeichnet löschende oder deaktivierende Aktionen.

## URLs

- `/` zeigt das Dashboard. Vor „Letzte Sitzungen“ stehen die nächsten fünf bekannten Termine ab dem heutigen Datum, chronologisch aufsteigend. Die Termine stammen aus dem Online-Index und werden durch lokal bekannte Sitzungen ergänzt. Bei fehlendem oder unlesbarem Online-Index wird der lokale Rückfall ausdrücklich angezeigt. Nur lokal indexierte Termine verlinken auf eine lokale Sitzungsdetailseite. „Letzte Sitzungen“ enthält ausschließlich Termine vor dem heutigen Datum.
- `/analyse/` zeigt den Analyse-Einstieg.
- `/analyse/starten/` bietet den Formularfluss zum Starten einer Analyse.
- `/analyse/antworten/` listet Jobs mit einem gefüllten KI-Antwortabschnitt und zeigt die ausgewählte Antwort in einer reduzierten Leseansicht. Prompt, Dokumentpfade, Roh-JSON und weitere technische Angaben bleiben auf der verlinkten Jobdetailseite. Maßgeblich ist der vorhandene Antwortinhalt, damit auch nachträglich aufbereitete Antworten trotz veralteter Statusmetadaten lesbar bleiben.
- `/analyse/prompts/` listet private Prompt-Vorlagen und bietet Scope-Filter.
- `/analyse/prompts/neu/` zeigt das Formular zum Anlegen einer Prompt-Vorlage.
- `/analyse/prompts/<template_id>/` zeigt das Formular zum Bearbeiten einer Prompt-Vorlage.
- `/analyse/prompts/<template_id>/duplizieren/` dupliziert eine Vorlage per POST.
- `/analyse/prompts/<template_id>/deaktivieren/` deaktiviert eine Vorlage per POST.
- `/analyse/sitzungen/` listet Sitzungen aus dem lokalen Index mit Suche, Gremiums-/Jahresfilter und Paginierung.
- `/analyse/sitzungen/<session_id>/` zeigt Sitzungsdetails.
- `/analyse/sitzungen/<session_id>/dokumente/<document_id>/pdf/` liefert eine lokal vorhandene PDF inline fuer die Browseransicht.
- `/analyse/jobs/` listet jeden Workflow-Job genau einmal mit einer einfachen fortlaufenden Nummer und einem Titel wie `Job 1 - Analyse Sitzung 2026-08-13 - Ortsrat Melle-Mitte`. Interne lokale Quell-IDs werden nicht angezeigt.
- `/analyse/jobs/<job_id>/` zeigt Analyseoutputs, einschließlich alter v1-Ausgaben, sowie Provider, Tokenverbrauch und Antwortstatus. Manuell erzeugte Analysegrundlagen tragen den Status `prepared` statt `done` und können auf derselben Seite nach Auswahl von Provider und Modell ausgeführt werden. Fehlgeschlagene Provideraufrufe lassen sich dort im selben Job erneut absenden. Beim Absenden wird der Button sofort gesperrt und ein deutlich sichtbarer Laufhinweis eingeblendet; parallel erhält der Workflow-Job den Status `running`, sodass kein zweiter Aufruf gestartet werden kann.
- Markdown-Ausgaben werden auf der Jobdetailseite serverseitig formatiert dargestellt; der unveränderte Quelltext bleibt aufklappbar. Die Vorschau entfernt nicht freigegebenes HTML, Attribute und unsichere URL-Schemata.
- `/daten/` zeigt links die Weiterleitungen zu Fetch, Build und Vektorindex; rechts stehen der aktuelle Status mit manueller Aktualisierung und die letzten Datenjobs.
- `/daten/fetch/` startet vorhandene Fetch-Skripte für SessionNet-Sitzungen und Landkreis-Veröffentlichungen.
- `/daten/build/` startet vorhandene SQLite-Build-Skripte für Ratsinfo- und Landkreis-Indizes. Der lokale Ratsinfo-Build übernimmt veraltete TOP- und Dokumentmetadaten aus einer neueren `session_detail.html` direkt in SQLite, ohne Dateien unter `data/raw/` zu verändern; Dokumentanzahl und lokale Verfügbarkeit bleiben dabei getrennt. Auch der Online-Build verändert `data/raw/` nicht.
- `/daten/vektor/` zeigt Ratsinfo- und Landkreis-Vektorstatus und startet Ratsinfo- oder Landkreis-Vektorindex-Builds. Beim Landkreis-Build koennen Datenwurzel und maximale Textlaenge pro Dokument fuer externe Rohdaten und knappen XPU/GPU-Speicher gesetzt werden.
- `/daten/jobs/<job_id>/` zeigt Status und Ausgabe eines gestarteten Datenjobs. Die letzten 50 Datenjobs werden in `data/db/service_jobs.sqlite` gespeichert und bleiben nach einem Serverneustart sichtbar; zuvor laufende Jobs werden dabei als unterbrochen markiert.
- `/daten/jobs/<job_id>/status/` liefert den aktuellen Datenjobstatus als JSON für die automatische Logaktualisierung.
- Die Datenjob-ID wird als `run_id` an das gestartete Skript weitergegeben. Damit lassen sich die begrenzte Ausgabe in der Weboberfläche und das vollständige rotierende Log unter `logs/<skriptname>.log` eindeutig zuordnen.
- `/daten/status/details/` zeigt den Datenstatus je vorhandenem Jahr ohne Zeitraumbeschränkung. „Details nach Jahr“ im gemeinsamen Statusbereich und der Dashboard-Datenstatus verlinken darauf. Die Übersicht vergleicht Rohdatenordner, lokale und Online-Sitzungen sowie Dokumentanzahlen und nennt anhand der Sitzungs-IDs die Unterschiede: lokal oder als Rohdaten vorhandene Sitzungen ohne Online-Eintrag, Online-Sitzungen ohne Rohdaten und Rohdaten ohne lokalen Index. Aufklappbare Jahreslisten zeigen Datum, Sitzungs-ID, Gremium und die Verfügbarkeit in jedem Bestand. Fehlende oder unlesbare Quellen werden als „nicht ermittelbar“ statt als Null dargestellt. Die Seite liest vorhandene Daten; sie lädt keine Sitzungen nach und verändert keine Indizes. „Details aktualisieren“ berechnet die Ansicht erneut. Der Vektorstatus gilt für den gesamten Index; eine jährliche Vektorabdeckung wird nicht aus Sitzungszahlen abgeleitet.
- `/daten/status/` liefert den frisch berechneten Rohdaten-, Datenbank-, Vektorindex- und lokalen Modellstatus als JSON für die manuelle Aktualisierung.
- `/veroeffentlichung/` ist ein Platzhalter für Publikations- und Reviewfunktionen.
- `/suche/` durchsucht lokal indexierte Dokumentinhalte semantisch über den Qdrant-Vektorindex. Die Suche nutzt Harrier-Dense-Embeddings, BM25-Sparse-Vektoren und RRF-Rangfusion. Bei aktiven Datums-, Gremiums- oder Dokumenttypfiltern werden bis zu 100 semantische Kandidaten geladen, anschließend gefiltert und erst danach auf 20 sichtbare Treffer begrenzt. Dadurch können relevante gefilterte Dokumente auch dann erscheinen, wenn sie im ungefilterten Ranking hinter Platz 20 liegen. Neu aufgebaute Vektorindizes liefern außerdem kurze Textausschnitte. Die Quellen-Auswahl bietet Ratsinfo als Standard und Landkreis als getrennte Collection `landkreis_publications`; beim Wechsel zu Landkreis werden die dort nicht anwendbaren Ratsinfo-Filter Gremium und Dokumenttyp verworfen.
- Ratsinfo nutzt nach vollstaendigem Erstaufbau `ratsi_passages`. Die Treffer zeigen einzelne Abschnitte, Seitenzahlen und Links zur lokalen PDF-Fundstelle. Bis zur Umschaltung bleibt `ratsi_documents` aktiv. Details zu Migration und Messung stehen in [search_quality.md](search_quality.md).
- `/einstellungen/` verwaltet lokale Einstellungen, darunter die sichere Ablage eines Hugging-Face-Tokens im OS-Schlüsselring.

Alte Service-URLs unter `/analyse/service/` werden auf den Datenbereich umgeleitet, damit technische Datenpflege nicht mehr im Analysebereich hängt.

## Sitzung vorbereiten und Analyse starten

Der Startfluss unter `/analyse/starten/` nutzt den bestehenden `AnalysisService` aus `src.analysis.service`. Die Seite ist als Arbeitsassistenz aufgebaut: Nutzer wählen zuerst eine Sitzung und danach entweder `Sitzung vorbereiten` für einen Überblick über alle Tagesordnungspunkte oder `TOP analysieren` für eine kritischere Detailanalyse einzelner Tagesordnungspunkte.

Bei einer Analyse der ganzen Sitzung werden alle lokal verfügbaren Dokumente dieser Sitzung in die Analysegrundlage aufgenommen und an den KI-Provider übergeben. Die Analyse-Startseite weist darauf ausdrücklich hin und zeigt, wie viele lokale Dokumente verfügbar sind.

Bei einer TOP-Analyse sind nur Tagesordnungspunkte auswählbar, für die lokal vorhandene Dokumente aufgelöst werden können. Die Analyse-Startseite zeigt pro TOP, ob analysierbare Dokumente vorhanden sind. TOPs ohne lokale Dokumentquelle bleiben deaktiviert, weil die KI sonst nur Metadaten ohne belastbare Analysegrundlage hätte.

Die Analysegrundlage enthält zusätzlich:

- ob die Sitzung vergangen, heute oder zukünftig ist
- Datum, Gremium und Sitzungsname
- Status und Beschluss-/Abstimmungsinformationen der ausgewählten TOPs, soweit im lokalen Index vorhanden
- die Dokumentliste im Scope
- die Art der KI-Übergabe je Dokument: Textauszug, PDF-Anhang oder nur Metadaten

Textdateien wie `.txt`, `.md` und `.html` werden als Auszug in die Analysegrundlage aufgenommen. PDF-Dateien werden als PDF-Pfade an Provider weitergegeben, die PDF-Anhänge oder PDF-Textextraktion unterstützen. Die Installation über `requirements.txt` enthält `pypdf[crypto]`, damit auch AES-verschlüsselte, ohne Passwort lesbare Ratsdokumente extrahiert werden können.

Mit Provider `none` wird nur die Analysegrundlage samt gerendertem Prompt erzeugt. Das ist der sichere Standard und eignet sich für manuelle ChatGPT-Nutzung. Ein echter automatisierter KI-Aufruf erfolgt erst bei Auswahl eines API-Providers. Ein ChatGPT-Plus-Konto ist kein API-Zugang; für die Automatisierung über OpenAI wird ein API-Key benötigt. Der OpenAI-Provider nutzt standardmäßig `gpt-5.6-luna`, das laut offizieller OpenAI-Modelldokumentation den Endpunkt `v1/chat/completions` unterstützt. Er übergibt das Ausgabelimit als `max_completion_tokens` und ist auf längere strukturierte Antworten ausgelegt. Prompt-Vorlagen werden unter `/analyse/prompts/` verwaltet und privat gespeichert. Das Analyseformular bietet nur aktive Vorlagen an, die zum gewählten Scope passen, und wählt für Sitzungsbriefings beziehungsweise TOP-Analysen passende Vorlagen voraus, wenn sie vorhanden sind.

Jede vorbereitete Markdown-Datei enthält bereits die leere Überschrift `## KI-Analyse`. Wird der Job später auf seiner Detailseite abgesendet, bleibt seine Jobnummer unverändert; Providerstatus, Tokenverbrauch und dieselbe Markdown-Datei werden aktualisiert. Valide strukturierte JSON-Antworten werden deterministisch in deutsche Markdown-Abschnitte, Listen, Dokumentübersichten und Quellenlinks umgewandelt. Die unveränderte Providerantwort bleibt daneben als `*.ki_response.json` erhalten; die lesbare Aufbereitung verursacht keinen weiteren KI-Aufruf.

## Bereits funktionsfähig

- Dashboard mit Datenstatus und Schnelleinstiegen
- Analyse-Startseite mit Schnellauswahl für Sitzungsbriefing und TOP-Detailanalyse
- Analyse starten mit bestehendem `AnalysisService`
- vorbereitete Analysejobs ohne neuen Job direkt aus der Markdown-Vorschau absenden
- eigene Leseansicht für fertig ausgeführte Antworten unter `/analyse/antworten/`
- private Prompt-Vorlagenverwaltung unter `/analyse/prompts/`
- Sitzungsliste und Sitzungsdetails aus `data/db/local_index.sqlite`
- PDF-Ansicht aus den Sitzungsdetails in einem separaten Browser-Tab oder -Fenster, sofern die PDF lokal vorhanden ist
- semantische Dokumentensuche unter `/suche/`
- Hugging-Face-Token-Verwaltung unter `/einstellungen/`
- Analysejobliste und Analysejobdetails aus `data/analysis_outputs/`
- Anzeige alter v1-Analyseoutputs
- Fetch-, Build- und Vektorindex-Servicefunktionen für Ratsinfo und Landkreis unter `/daten/`
- Statusanzeige für laufende Datenjobs im Header; ohne laufenden Job bleibt sie ausgeblendet
- manuelle Aktualisierung des aktuellen Datenstatus auf den Service-Seiten ohne vollständigen Seitenwechsel
- automatische Aktualisierung der Logausgabe auf Datenjob-Detailseiten; nach Abschluss werden der verständliche Endstatus und der aktuelle Datenstatus automatisch nachgeladen

## Platzhalter

- Veröffentlichung und Review
- Suche über Analyseoutputs
- weitere UI-Einstellungen
- Produktives Deployment
- Authentifizierung, Rollen und Benutzerverwaltung

## Private Prompt-Vorlagen

Produktive Prompt-Vorlagen werden nicht im Repository gespeichert. Der Standardpfad liegt im privaten Datenbereich:

```text
data/private/prompt_templates.json
```

Der Pfad kann über Environment-Variablen angepasst werden:

- `RATSI_PRIVATE_DATA_DIR` für den privaten Datenbereich
- `RATSI_PROMPT_TEMPLATES_PATH` für die konkrete JSON-Datei

Beim ersten Zugriff kann die private Datei aus `docs/examples/prompt_templates.example.json` initialisiert werden. Diese Beispiel-Datei enthält nur harmlose Demo-Prompts. Echte Vorlagen werden über die Django-Seite `/analyse/prompts/` erstellt und bleiben durch `.gitignore` außerhalb des Repository-Inhalts geschützt.

Bei Projektaktualisierungen ergänzt die Anwendung neu ausgelieferte Standardvorlagen aus der Beispieldatei automatisch im bestehenden privaten Speicher. Bereits vorhandene IDs werden nicht überschrieben; individuelle Texte, Aktivierungsstatus und Revisionen bleiben erhalten.

Prompt-Vorlagen haben einen primären Scope (`session`, `tops` oder `document`). Intern können geladene Legacy-Vorlagen mehrere Scopes behalten, damit bestehende private JSON-Dateien weiter in allen vorgesehenen Analysekontexten auswählbar bleiben.

## Prompt-Snapshots

Neue Analysejobs speichern Template-ID, Revision und Label. Der gerenderte Prompt-Snapshot wird im privaten Datenbereich abgelegt, damit alte Jobs nachvollziehbar bleiben, auch wenn eine Vorlage später geändert wird.

Automatische Analysen speichern zusätzlich Provider-ID, Eingabe-/Ausgabetokens und den Antwortstatus. `done` setzt eine nicht leere, als JSON-Objekt validierte Providerantwort voraus. Ohne Provider entsteht eine nachvollziehbare Analysegrundlage mit Status `prepared`; Providerfehler, leere Antworten und ungültiges JSON führen zu `error`. Der Workflow-Index liefert die kanonischen Jobs; über `source_job_id` verknüpfte lokale Quelljobs werden darin zusammengeführt. Nicht verknüpfte historische lokale Jobs bleiben für bestehende Installationen weiterhin sichtbar.

Bei großen PDF-Mengen priorisiert der Analyseworkflow Beschlussvorlagen und andere entscheidungstragende Quellen. Überschreitet der extrahierte Gesamttext 140.000 Zeichen, wird jedes lesbare Dokument vollständig in Abschnitten von höchstens 40.000 Zeichen voranalysiert. Die Abschnittsergebnisse werden zunächst je Dokument verdichtet; erst danach entsteht aus den Dokumentzusammenfassungen die Gesamtausgabe. Der gespeicherte Tokenverbrauch umfasst alle Stufen.

Gerenderte Prompt-Snapshots und private Prompt-Artefakte werden nicht als normale Quellen oder Dateien in der Job-Detailansicht angezeigt. Die UI kann Metadaten wie Vorlage, Revision und Zeitpunkt anzeigen, ohne private Prompt-Pfade als öffentliche Artefaktquellen auszugeben.

## Datenquellen

- `data/db/local_index.sqlite` für Sitzungen, TOPs, Dokumente und einfache Analyse-Tabellen
- `data/db/analysis_workflow.sqlite` für neuere Analyse-Workflow-Metadaten, falls vorhanden
- `data/analysis_outputs/` nur für JSON- und Markdown-Analyseartefakte
- `data/private/prompt_templates.json` für private Prompt-Vorlagen
- `data/private/analysis_prompts/` für private Prompt-Artefakte
- `data/private/prompt_snapshots/` für gerenderte Prompt-Snapshots

Fehlende Datenquellen führen nicht zu Fehlern. Die Oberfläche zeigt stattdessen leere Listen oder Hinweise. Eine fehlerhafte private Prompt-Vorlagen-Datei blockiert die Analyse- und Vorlagenseiten nicht; die UI zeigt dann keine Vorlagen an, bis die private Datei repariert ist.

### Qdrant-Verbindung und Status

Der Datenstatus enthält unter `status.embedding_models` die lokale Bereitschaft
(`bereit`, `fehlt`, `unvollstaendig` oder `inkompatibel`) und die Komponenten
`dense_model`, `tokenizer` und `sparse_model`. Konfigurierte Revisionen sind
immer enthalten; vorbereitete Revisionen und Größen stammen nur aus einem
gemeinsam validierten Manifest einschließlich des Bibliotheksvergleichs.
Bei einem Gesamtfehler sind diese Einzelwerte und die Einzelbereitschaft `null`.
`size_scope=required_artifacts` bezeichnet die erfassten Pflichtdateien; der
Gesamtwert zählt gemeinsam referenzierte Dateien einmal und umfasst keine
Caches oder alten Modellstände. Diese Schnellprüfung lädt keine Modelle,
verwendet kein Modellnetzwerk und verändert keine Dateien.

Die Service-Fassade stellt dieselben Werte über `embedding_model_status()` ohne
Qdrant-Abfrage bereit. Auf `/daten/vektor/` zeigt „Lokale Embedding-Modelle“
den gemeinsamen Status und die Angaben zu Harrier, Tokenizer und BM25.
„Modellstatus aktualisieren“ erneuert diese Werte ohne Seitenwechsel. Bei einem
Gesamtfehler zeigen die Karten „Nicht einzeln verifiziert“ und ersetzen alte
Revisionen und Größen durch „Nicht verifiziert“. „Lokal prüfen“ startet den
festen Befehl `prepare_embedding_models.py --check --json` als Datenjob und
öffnet dessen Jobdetailseite. Die Aktion verwendet POST mit CSRF-Schutz und
akzeptiert keine zusätzlichen Modell-, Pfad- oder Kommandoargumente. Beide
Modellaktionen weisen außerdem doppelte Formularfelder und widersprüchliche
Aktionsnamen ab. Modell-ID, Revision und Zielpfad sind nicht frei eingebbar.
„Lokal prüfen“ arbeitet offline und schreibt keine Modelldateien. Bei einem
unbrauchbaren Bestand endet der Job mit Fehlerstatus; die JSON-Ausgabe unterscheidet weiterhin
`fehlt`, `unvollstaendig` und `inkompatibel`. Die Vektorseite zeigt je Modell- und Legacy-Aktion den letzten abgeschlossenen
Versuch einschließlich Fehlern; laufende Jobs stehen separat. Die Zuordnung
bindet Aktion, aufgelösten Modellpfad, Modellvertrag und Bibliotheksstand.
Erfolgreiche Ergebnisse speichern zusätzlich den Manifest-Hash. Änderungen
am Vertrag, Pfad oder Bestand kennzeichnen ein Ergebnis als historisch.
Ältere Jobs ohne nachgewiesene Zuordnung bleiben ausdrücklich unverifiziert.
Nach Entfernen eines Jobs aus der begrenzten Historie erscheint „Kein
gespeichertes Prüfergebnis“. Bei Speicherfehlern zeigt die Seite stattdessen
eine Warnung und kann sich beim nächsten Abruf erholen. Die Aktualisierung
liest nur lokale Diagnosedaten; sie startet weder Downloads noch Qdrant-Probes.
Jobdetails zeigen Wartestatus, Ausführung und Abschluss, während der
Ausführung einen Fortschrittsbalken ohne Prozentwert. Die Skripte liefern
keinen verlässlichen prozentualen Fortschritt. Nach Abschluss einer
Legacy-Prüfung wird die Detailseite mit dem validierten Protokoll neu geladen.
Die gespeicherten Ergebnisse ersetzen niemals die aktuelle Modellbereitschaft. Manifestdatum und
Zeitpunkt des Seitenaufrufs werden nicht als letzte ausgeführte Prüfung
ausgegeben.

„Modelle vorbereiten“ lädt nach ausdrücklicher Bestätigung die angezeigten,
fest konfigurierten Revisionen in das konfigurierte Modellverzeichnis. Dafür
müssen die Modellbibliotheken im Python-Umfeld des Servers installiert sein.
Die Aktion läuft als Datenjob mit `--download --json`; die Jobdetailseite zeigt
das geprüfte Ergebnis oder einen festen Fehlercode. Rohe Downloadausgaben und
Provider-Tracebacks werden nicht gespeichert. Die signierte Bestätigung ist
15 Minuten gültig und bindet Modellpfad, Revisionen und Bibliotheksstand. Nach
Änderungen die Seite neu laden und erneut bestätigen. Parallele Modell- und
Vektorjobs werden im Web abgewiesen; direkte CLI-Aufrufe warten auf dieselbe
Betriebssystemsperre. Alle Webprozesse verwenden dieselbe Jobdatenbank und
dieselben Modell-/Qdrant-Zustandsverzeichnisse. Ein lebender Unterprozess bleibt
auch nach Ausfall seines Webprozesses geschützt. Nachdem beide beendet sind,
wird der unterbrochene Job als Fehler angezeigt; ein neuer Versuch ist möglich.
Alle Vektor-Builds einschließlich Legacy- und Landkreis-Build verwenden dieselbe
Modellsperre. Die CLI wartet auch unter Windows bei langen Builds weiter auf die
Freigabe. Modell- und Collection-Sperren bleiben bei Erfolg oder Fehler bis zum
Schließen des Qdrant-Clients bestehen. Auch Legacy-Prüfungen erwerben die
Collection-Sperre vor Clientstart. Dabei kann eine dauerhaft verbleibende
Sperrdatei angelegt werden; Indexdaten, Payloads und Freigabemarker ändern sich
durch die Prüfung nicht. Sperrdateien nicht löschen: Entscheidend ist die aktive
Betriebssystemsperre, nicht die Existenz der Datei. Ein neuer Versuch prüft
Konfiguration und Bestand nach Sperrerwerb erneut.

„Legacy-Bestand prüfen“ bietet zwei feste Aktionen für `ratsi_passages` und
`ratsi_documents`. Ziel, Quell-Datenbank und Berichtspfad legt der Server fest;
zusätzliche Pfad-, Stichproben-, Toleranz- oder Apply-Parameter werden abgewiesen.
Die signierte Zielbindung ist 15 Minuten gültig und wird vor Clientstart unter
der Modellsperre erneut geprüft. Die Aktion verändert weder Qdrant-Payloads
noch Freigabemarker. Jeder Job behält einen eigenen privaten Bericht. Auf der
Jobdetailseite zeigt „Legacy-Prüfprotokoll“ Ziel, Quelle, Prüfzeit, Ergebnis,
Stichprobenumfang und Berichtshash; gültige Abbruchberichte bleiben sichtbar.
Bei einem laufenden Job nach Abschluss „Prüfprotokoll anzeigen“ wählen. Die
Jobstatus-API liefert dieselben geprüften Ergebnisfelder. Bei geänderter
Konfiguration erscheint das Ergebnis als historisch; veränderte, fremde oder
unlesbare Protokolle werden abgewiesen. Rohes stdout/stderr wird nicht gespeichert.
Auf der Detailseite eines erfolgreichen Prüfjobs erscheint „Geprüften
Legacy-Bestand übernehmen“, wenn der Bericht unverändert ist, der aktuelle
Modell-/Zielvertrag passt und kein Freigabemarker vorhanden ist. Die Aktion
verlangt ein angekreuztes Bestätigungsfeld und CSRF-Schutz. Eine signierte,
15 Minuten gültige Bindung umfasst Prüfjob-ID und Berichtshash; Collection,
Quelle und Berichtspfad leitet der Server aus diesem Job ab. Der Jobstart
prüft den gespeicherten Beleg erneut. Die CLI erwirbt Modell- und
Collection-Sperre vor Clientstart, prüft den bestätigten Berichtshash und
berechnet die Stichprobe vor einer Freigabe nochmals. Spätere Änderungen
führen zum Abbruch. Die Übernahme ergänzt Kompatibilitätsangaben und den
Freigabemarker, ohne gespeicherte Vektoren zu verändern oder den Index neu
aufzubauen. Sichere
Ergebniszahlen oder feste Abbruchcodes erscheinen in der Jobausgabe. Nach
teilweisem Backfill wird die bestehende Rücknahme verwendet. Abgebrochene,
veränderte, historische oder nicht mehr gespeicherte Prüfjobs können nicht
übernommen werden. Landkreis bleibt „Neuaufbau erforderlich“ (`rebuild_required`)
als separate Aufgabe.

Django und seine Build-Unterprozesse nutzen standardmäßig denselben Qdrant-Server
`http://127.0.0.1:6333` wie die CLI. `RATSI_QDRANT_URL` wählt einen anderen Server.
Mit `RATSI_QDRANT_MODE=local` und ohne URL wird der lokale Index verwendet. Nach einer Änderung der
Umgebung Django neu starten. Auf `/daten/vektor/` wird das konfigurierte Ziel
angezeigt. Dashboard und Vektorstatus prüfen die Verbindung und die Collection;
sie unterscheiden fehlende Collection, unvollständigen Index, unerreichbaren
Server und ungültige Konfiguration. Die Suche lädt bei diesen Fehlern keine
Embedding-Modelle nach. Fehlt der vorbereitete lokale Modellbestand, zeigt die
Suche den Vorbereitungsbefehl und einen Link zum technischen Servicebereich.
URL-Zugangsdaten und URL-Pfade erscheinen nicht in
Statusanzeigen oder Suchfehlern.
Die [Phase-7-Abnahme](embedding_model_management.md#abschlusspruefung-phase-7-2026-10-04)
prueft den Suchservice mit echten lokalen Modellen und einem getrennten
Testindex bei gesperrtem Netzwerk. Auch nach dem Laden der Suchmodelle werden
fehlende Modellbestaende und inkompatible Freigabemarker vor weiteren
Suchanfragen abgewiesen. Native Windows-Prozesssperren, Webstart-Konflikte und
Wiederanlauf nach hartem Testprozessabbruch sind separat geprueft.

Ein vorhandener, noch nicht freigegebener Passage-Index wird als unvollständig
angezeigt. Bis zur Freigabe kann die Suche den bisherigen `ratsi_documents`-Index
verwenden. Servermarker sind an die URL gebunden und müssen für Web und Build
zugänglich sein; Einzelheiten stehen in
[Suchqualität](search_quality.md#qdrant-serverbetrieb).
