# Ratsbereich über die Oberfläche bedienen

[RI-Übersicht](README.md) · [CLI-Datenablauf](datenablauf.md)

Seit 0.8.0 lassen sich die RI-Skripte in der lokalen Django-Oberfläche starten.
Der Ratsbereich ist wie die übrige Oberfläche direkt ohne Web-Anmeldung und ohne
Benutzerkonto nutzbar. Die RI-Jobhistorie bleibt von den öffentlichen Datenjobs getrennt.

Der aktuelle RI-Webstand ist ein Prototyp. Formulare, Datenstatus, Jobhistorie und
Auftragsausgabe verwenden seit 0.8.1 die Gestaltungselemente des BI-Bereichs.
Seit 0.9.3 verwenden BI und RI gemeinsame Formular-/Feldrenderer, Statuspanelrahmen
und Auftragsanzeigen einschließlich Live-Aktualisierung. Bereichsspezifische Fakten,
Formularprüfung und Jobablagen bleiben getrennt. Die Bausteine und Unterschiede
stehen in den [UI-Regeln](../entwicklung/ui_guidelines.md#wiederverwendung-zwischen-bi-und-ri);
weitere Backendarbeit folgt gemäß [Aufgabenliste](../plans/project_tasks.md).

## Einrichtung

Beim erstmaligen Einrichten aus dem Repository-Stamm mit der passenden Python-Umgebung:

```powershell
python web/manage.py migrate
python scripts/run_web.py
```

Anschließend über das Hauptmenü **Ratsbereich** die gewünschte Seite öffnen.
Eine zusätzliche Navigationsleiste innerhalb der RI-Seiten entfällt seit 0.9.2. Die bisherigen
Adressen `/ratsbereich/anmelden/` und `/ratsbereich/abmelden/` führen direkt zum
RI-Datenstatus; ein Anmeldeformular wird nicht mehr angezeigt.

Für Online-Aufträge muss der bestehende [RI-Portalzugang](zugang.md) eingerichtet
sein. Die Skripte verwenden den Token aus `.env/ri_token.txt` und übernehmen die
Portal-Anmeldung und Abmeldung. Portalpasswort und Token werden nicht in
Webformulare eingegeben oder als Auftragsparameter angenommen.
Die Oberfläche wird lokal über `127.0.0.1` betrieben.

## Seiten und Aktionen

| Seite | Aktion |
| --- | --- |
| Zugang | `login_ri.py`: Portalzugang prüfen und anschließend wieder abmelden |
| Unterlagen herunterladen | `fetch_ri_sessions.py`: gewählte Sitzungsmonate und Dokumente abrufen |
| Datenbank aktualisieren | `build_ri_online_index_db.py`: Online-Metadaten erfassen |
| Datenbank aktualisieren | `build_ri_local_index.py`: vorhandene Dateien lokal indexieren |
| Datenstatus und Jobs | RI-Datenbankstatus und separate Auftragshistorie ansehen |

Jahr und Monate folgen der [Abrufkonfiguration](datenablauf.md#pfade-und-konfiguration).
Ohne Monatsangabe werden die zugänglichen Monate des Jahres gewählt; frühere
Monate werden ausgeschlossen. Ungültige Angaben werden im Formular angezeigt.
Der Download bietet die Option zum erneuten Herunterladen vorhandener Dokumente;
die Builder bieten Aktualisierung bekannter Sitzungen beziehungsweise ausschließlich
bekannter Sitzungen. Die genaue CLI-Semantik steht in der Datenablaufanleitung.

Erst das Absenden eines Formulars startet einen Auftrag. Die Oberfläche öffnet
danach dessen Detailseite und aktualisiert dort Status und Ausgabe automatisch.
Alternativ kann der Status manuell aktualisiert werden. Das Schließen der Seite
beendet den Hintergrundauftrag nicht. Der Webserver muss dafür weiterlaufen.
Formulare behalten CSRF-Schutz und strikte Parameterprüfung.

## Sitzungen und Dokumente

Seit 0.9.0 öffnet **Ratsbereich → Sitzungen** unter `/ratsbereich/sitzungen/`
den lokalen RI-Bestand im gleichen Listen- und Detailaufbau wie BI. Seit 0.9.1
führt auch „RI öffnen“ auf der Startseite direkt zur Sitzung; die gemeinsamen
Dashboard-Regeln stehen in der [Sitzungsübersicht](../oberflaeche/sitzungen.md). Voraussetzung
ist ein aufgebauter lokaler RI-Index unter `data/ri/db/local_index.sqlite`;
der Onlineindex allein genügt nicht. Nach einem Download unter **Datenbank
aktualisieren** den lokalen Index aktualisieren, damit neue Dateien und TOPs erscheinen.

Die Liste bietet Suche nach Sitzung, ID, Gremium oder Ort, Filter nach Gremium
und Jahr sowie 20 Sitzungen pro Seite. Ein Klick auf die Sitzung öffnet Datum,
Ort, Quellenstatus, Tagesordnung und die vollständige Dokumentliste.

Die TOP-Nummer stammt aus dem Portal: `Ö` bedeutet öffentlich, `N` nicht öffentlich.
Fehlt das Präfix, erscheint „nicht gekennzeichnet“. Diese Angabe betrifft den TOP.
Der separat angezeigte Dokumentstatus stammt weiterhin aus dem gespeicherten
[BI-Abgleich](datenablauf.md#dokument-id-und-öffentlichkeitskennzeichnung): Auch
unter einem öffentlichen TOP können interne Anlagen liegen. Beim Öffnen einer
Sitzung wird kein neuer Online-Abgleich gestartet.

**PDF öffnen** erscheint für vorhandene, nicht leere PDF-Dateien innerhalb des
zugehörigen RI-Sitzungsordners. Fehlende Dateien zählen im Quellenstatus als
fehlend; andere Dateiformate werden aufgelistet, aber nicht im PDF-Endpunkt ausgeliefert.
Dateipfade außerhalb der RI-Rohdatenwurzel oder des Sitzungsordners, auch über
Symlinks, werden abgelehnt. PDF-Links sind an Sitzung und lokalen Dokumenteintrag
gebunden. Listen, Details und PDFs werden mit privaten No-Store-Headern geliefert.
Die Ansichten bleiben wie die übrige lokale Oberfläche ohne Web-Anmeldung nutzbar.

Bei leerer Liste zunächst Filter zurücksetzen und den lokalen RI-Index prüfen.
Ein unlesbarer Index wird als Fehler gemeldet; es gibt keinen Rückgriff auf BI.
Unbekannte Sitzungen und fehlende PDFs liefern HTTP 404. BI-Suche, BI-Analyseauswahl
und öffentliche Sitzungslisten beziehen weiterhin ausschließlich ihren eigenen Bestand.

## Status und Jobablage

Auf den Formularseiten und der Statusseite zeigt „Aktueller Status“ den lokalen
und den Online-Index mit Sitzungs- und Dokumentzahlen. Fehlende Bestände erscheinen
gedämpft, lesbare grün und unlesbare als Fehler. „Status aktualisieren“ lädt die
Seite neu. Die Statusseite ergänzt TOP-Zahlen und die Jobhistorie in einer
auf schmalen Bildschirmen horizontal scrollbaren Tabelle.
Die Auftragsansicht zeigt Status, Exit-Code, Start und Ende sowie eine Laufanzeige.
Erfolgreiche Aufträge erscheinen grün, laufende und mit Hinweisen abgeschlossene
Aufträge als Warnung, fehlgeschlagene als Fehler. Status und Ausgabe aktualisieren
sich dort automatisch. Bei vorübergehenden Verbindungsfehlern bleibt der letzte
Auftragsstatus sichtbar; eine separate Fehlermeldung erscheint und die Aktualisierung
wird automatisch erneut versucht.

RI-Aufträge liegen ausschließlich unter `data/ri/db/ri_jobs.sqlite`. Die Jobliste
und Status-API der Bürgerinformation verwenden weiterhin ihre eigene Ablage und
enthalten keine RI-Aufträge. RI-Jobseiten und die zugehörige Status-API sind lokal
direkt erreichbar und werden mit privaten No-Store-Headern geliefert, damit die
Ausgaben nicht zwischengespeichert werden.

| Status | Bedeutung |
| --- | --- |
| wartet / läuft | Auftrag ist reserviert oder wird ausgeführt |
| erfolgreich | Skript hat Exitcode 0 geliefert |
| mit Hinweisen abgeschlossen | Exitcode 2, etwa bei Dokumentfehlern, ungeprüften Sitzungen oder unbestätigter Abmeldung |
| fehlgeschlagen | Startfehler, anderer Exitcode oder unterbrochener Auftrag |

Die Ausgabe ist begrenzt und wird als Text angezeigt. Es wird kein erfundener
Prozentfortschritt ausgegeben. Eine Warnung bei Exitcode 2 ist in der Ausgabe zu
prüfen; Portal- und entfernte Proton-Abmeldung bleiben unterschiedliche Ergebnisse.
Vorhandene RI-Jobdaten bleiben nach einem Serverneustart lesbar. Nicht mehr laufende
Aufträge werden als unterbrochen erkannt, sobald weder ihr Serverprozess noch ihr
Kindprozess existiert.

Laufende RI-Webaufträge erscheinen oben in derselben Jobanzeige wie die Datenjobs
der anderen Bereiche. Im Ratsbereich fragt diese Anzeige ausschließlich die separate
RI-Status-API ab; die BI-Anzeige bleibt auf BI-/Wartungsjobs begrenzt. Die Formularseite
zeigt zusätzlich einen Link zum aktiven RI-Auftrag.

Gleichzeitig ist höchstens ein RI-Webauftrag erlaubt. Beim Absenden werden die
Start-Schaltflächen gegen Doppelabsenden gesperrt. Solange ein Auftrag läuft, bleiben
sie gesperrt und werden nach dessen Abschluss automatisch wieder freigegeben. Falls
trotzdem ein weiterer Start übermittelt wird, öffnet sich der bereits vorhandene
Jobstatus mit dem Hinweis, dass kein zusätzlicher Auftrag gestartet wurde. Dieser Slot koordiniert die Weboberfläche; während eines
Webauftrags keine zusätzlichen RI-Skripte manuell per CLI starten.

## Grenzen und Prüfung

Die Webanbindung umfasst Skriptsteuerung, Datenbankstatus, Jobausgaben sowie
Sitzungslisten, Sitzungsdetails und lokale PDF-Auslieferung. RI-Dokumente werden
[manuell verwaltet und gelöscht](datenablauf.md#aufbewahrung-und-manuelles-löschen). RI-Suche und Vektorindex sind für diese Ausbaustufe nicht vorgesehen;
die entsprechenden alten Platzhalter starten keine Aufträge.

## Reale UI-Abnahme vom 22.11.2026

Unter Windows mit Python 3.14 wurde die Kette **Webformular → Download → lokaler
Indexaufbau → gefilterte Sitzungsliste → Detailansicht → PDF im neuen Tab** mit
dem regulären RI-Bestand durchgeführt. Datenbanken und vorhandene Dezemberdateien
wurden vorher lokal unter `data/ri/ui_acceptance/` gesichert; Dateikopien wurden
per SHA-256 geprüft. Dieser Ordner gehört zum ignorierten RI-Laufzeitbestand.

| Sitzung | TOPs | Dokumente nach Download und Indexaufbau | PDF-Prüfung |
| --- | --- | --- | --- |
| Verwaltungsausschuss 8178, 01.12.2026 | 23 N-Einträge einschließlich Unterpunkten | 43 vorhanden, 0 fehlend | Über UI geöffnet, HTTP 200 und PDF-Inhalt |
| Betriebsausschuss 8179, 02.12.2026 | 10 Ö- und 2 N-Einträge | 14 vorhanden, 0 fehlend | Über UI geöffnet, HTTP 200 und PDF-Inhalt |

Die erneute lokale HTML-Analyse stimmt für beide Sitzungen mit den gespeicherten
TOP-Nummern überein. Dokument-IDs und TOP-Zuordnungen sind vollständig; alle 57
Dateien stimmen mit den SHA-1-Prüfsummen ihrer Manifeste überein. Der BI-Abgleich
weist für 8179 zehn öffentliche und vier nicht öffentliche Dokumente aus. Für
8178 schlug der BI-Abgleich fehl; alle 43 Dokumente bleiben entsprechend der
bestehenden Regel nicht öffentlich. Das ist kein Nachweis einer öffentlichen
Erreichbarkeit dieser Dokumente.

Der Dezember-Download (`09f8df1a26364587b4e23970bb07d45c`) führte 57 echte
Dokumentdownloads aus und endete mit **Exitcode 2 / mit Hinweisen abgeschlossen**:
Die Detailansichten 9516 und 8181 wurden als ungeprüft übersprungen. Die RI-Abmeldung
ist bestätigt, die entfernte Proton-Abmeldung blieb unbestätigt. Der Hinweisstatus,
die Abschlussmeldung und das Ausblenden der Laufanzeige wurden im Browser geprüft.

Der anschließend über das Webformular gestartete lokale Indexaufbau mit
„Bestehende Sitzungen aktualisieren“ (`7c0a2536712949638e4a66e936844ea9`) endete
mit **Exitcode 0**: 17 Sitzungen, 255 TOP-Einträge und 220 Dokumente. Dabei wurden
drei fehlende oder unzulässige Altdateien der Sitzung 8176 gemeldet und ausgelassen;
die beiden Dezember-Beispielsitzungen sind vollständig. Diese Altbestandshinweise
und die beiden ungeprüften Detailansichten bleiben gesondert zu untersuchen.

Die Details passen bei 1440 und 390 Pixel Breite ohne seitlichen Seitenüberlauf.
Die geöffneten RI-PDFs tragen private No-Store-Header. Die geprüfte RI-PDF-Kennung
und der RI-Downloadauftrag liefern über die entsprechenden BI-Endpunkte HTTP 404.
Die Abnahme gilt für diese begrenzte UI-Stichprobe; Exportfunktionen,
unbeaufsichtigter Betrieb und allgemeine Parser-Vollständigkeit sind damit nicht abgenommen.

## Nachprüfung der Hinweise vom 27.11.2026

Die gespeicherte Dezember-Kalenderseite nennt für 9516 (Feuerwehr und Ordnung)
„verschoben auf den 12.01.2027“, für 8181 (Finanzen und Beteiligungen)
„verschoben auf den 07.12.2026“. Der neue Dezembertermin ist als 9514 eingetragen.
Eine neue Januar-Sitzungs-ID wurde bei dieser Prüfung nicht nachgewiesen.

Ein gezielter authentifizierter Abruf der HTML-Metadaten bestätigt: 9516 und 8181
antworten jeweils mit HTTP 302 auf `/ri/si0050.asp` mit derselben Sitzungs-ID.
`checked_metadata_url()` erlaubt derzeit nur Kalender und `si0057.asp`-Details;
daher wird diese alternative Terminansicht als `RiPageUnavailable` ausgelassen.
9514 antwortet dagegen mit HTTP 200, datierter Überschrift und erkannter Tagesordnung.
Die Warnungen sind bei diesen beiden alten Terminen somit durch Verschiebung und
die nicht unterstützte Terminansicht erklärbar, nicht durch einen lokalen Indexfehler.
Kalenderhinweise werden bisher noch nicht als eigener Verschiebungsstatus erfasst;
der gemeinsame Kalenderparser ordnet den ersten Hinweistext dem Uhrzeitfeld zu.

Bei 8176 enthält das am 27.11.2026 erneuerte Manifest 14 vorhandene, nicht leere
Dateien mit korrekten SHA-1-Prüfsummen. Auch die langen Pfade lassen sich unter
Windows normal öffnen; ein aktuelles Pfadlängenproblem wurde nicht reproduziert.
Der reguläre RI-Index enthält weiterhin 11 Dokumente. Darin fehlen die inzwischen
vorhandenen Dokument-IDs 146339, 146340 und 146087. Alle elf indexierten Pfade sind
vorhanden. Ein Probeimport mit den unveränderten Builderfunktionen in eine reine
Arbeitsspeicher-Datenbank übernimmt alle 14 Einträge ohne Warnung.

Für 8176 ist deshalb aktuell ein erneuter **lokaler Indexaufbau** erforderlich,
kein weiterer Dokumentdownload. Die genaue damalige Ursache der drei Warnungen
vom 22.11. lässt sich aus deren allgemeinen Logmeldungen nicht mehr eindeutig
rekonstruieren; die heutigen Befunde ersetzen keinen historischen Dateischnappschuss.
Bei der Nachprüfung wurden keine regulären Indizes oder Rohdateien verändert und
keine PDFs heruntergeladen. Diagnoseergebnisse liegen lokal unter `data/ri/diagnostics/`.

## Indexnachlauf und Kalenderstatusprüfung vom 27.11.2026

Nach ausdrücklichem Nutzerauftrag wurde der reguläre lokale RI-Index für **8176**
aktualisiert. Vorher wurde die Datenbank lokal gesichert. Die bestehenden
Builderfunktionen wurden auf diese einzelne Sitzung begrenzt ausgeführt; danach
wurden die Tabellenzeilen aller anderen Sitzungen und die Rohmetadaten mit dem
vorherigen Stand verglichen und als unverändert bestätigt. Ergebnis: 12 TOP-Einträge,
**14 Dokumente im Index, 14 Dateien verfügbar, 0 fehlend**. Die drei Dokument-IDs
146339, 146340 und 146087 sind jetzt enthalten. Auch der RI-Sitzungsservice meldet
diesen vollständigen Quellenstatus. Ein zusätzlicher Download war nicht nötig.
Sicherung und Ergebnis liegen lokal unter `data/ri/diagnostics/`.

Anschließend wurde die Kalender-Statusbehandlung anhand der gespeicherten echten
November-/Dezemberkalender geprüft. Zusätzlich zu 9516/8181 enthalten diese die
Absagen 7168 („findet nicht statt“) und 7169 („abgesagt“). Der Parser schreibt die
Hinweise in `start_time` und behält das ursprüngliche Datum. Sitzungsmodell und
RI-Indizes besitzen dafür keine eigenen Status-/Ersatzterminfelder. Ein isolierter
Probelauf mit den tatsächlich geparsten Einträgen bestätigt: Die Dashboard-Gruppierung
sortiert sie allein nach Datum weiter als normale Termine ein; das Template würde
den Hinweis in der Uhrzeitspalte ausgeben. Die betroffenen IDs waren im regulären
Dashboard-Datenbestand dieser Prüfung nicht enthalten; die Gruppierungsprobe
ist daher ausdrücklich keine Behauptung über aktuell sichtbare Zeilen.
Die Erkennung und Anzeige verschobener/abgesagter Termine bleibt umzusetzen.
Bei dieser Prüfung wurde keine Kalender-/Anwendungslogik geändert.

Gezielte Offline-Tests stehen in der [Testdokumentation](../entwicklung/tests.md).
Sie prüfen den lokalen Zugriff ohne Anmeldung, die Formulare und simulierte
Auftragsabläufe. Reale Portalprüfungen oder Downloads werden dabei nicht gestartet.
