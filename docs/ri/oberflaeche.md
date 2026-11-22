# RI-Skripte über die Oberfläche bedienen

[RI-Übersicht](README.md) · [CLI-Datenablauf](datenablauf.md)

Seit 0.8.0 lassen sich die RI-Skripte in der lokalen Django-Oberfläche starten.
Der Ratsbereich ist wie die übrige Oberfläche direkt ohne Web-Anmeldung und ohne
Benutzerkonto nutzbar. Die RI-Jobhistorie bleibt von den öffentlichen Datenjobs getrennt.

Der aktuelle RI-Webstand ist ein Prototyp. Formulare, Datenstatus, Jobhistorie und
Auftragsausgabe verwenden seit 0.8.1 die Gestaltungselemente des BI-Bereichs.
Die weitere gemeinsame Nutzung geeigneter Frontend- und Backendkomponenten folgt
gemäß [Aufgabenliste](../plans/project_tasks.md).

## Einrichtung

Beim erstmaligen Einrichten aus dem Repository-Stamm mit der passenden Python-Umgebung:

```powershell
python web/manage.py migrate
python scripts/run_web.py
```

Anschließend über **Ratsbereich** die gewünschte Seite öffnen. Die bisherigen
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

## Status und Jobablage

Auf den Formularseiten und der Statusseite zeigt „Aktueller Status“ den lokalen
und den Online-Index mit Sitzungs- und Dokumentzahlen. Fehlende Bestände erscheinen
gedämpft, lesbare grün und unlesbare als Fehler. „Status aktualisieren“ lädt die
Seite neu. Die Statusseite ergänzt TOP-Zahlen und die Jobhistorie in einer
auf schmalen Bildschirmen horizontal scrollbaren Tabelle.
Die Auftragsansicht zeigt Status, Exit-Code, Start und Ende sowie eine Laufanzeige.
Erfolgreiche Aufträge erscheinen grün, laufende und mit Hinweisen abgeschlossene
Aufträge als Warnung, fehlgeschlagene als Fehler. Status und Ausgabe aktualisieren
sich dort automatisch.

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

Die Webanbindung umfasst die Skriptsteuerung, Datenbankstatus und Jobausgaben.
Sitzungslisten, interne Dateiauslieferung und Bestandsbereinigung sind noch nicht
angebunden. RI-Suche und Vektorindex sind für diese Ausbaustufe nicht vorgesehen;
die entsprechenden alten Platzhalter starten keine Aufträge.

Gezielte Offline-Tests stehen in der [Testdokumentation](../entwicklung/tests.md).
Sie prüfen den lokalen Zugriff ohne Anmeldung, die Formulare und simulierte
Auftragsabläufe. Reale Portalprüfungen oder Downloads werden dabei nicht gestartet.
