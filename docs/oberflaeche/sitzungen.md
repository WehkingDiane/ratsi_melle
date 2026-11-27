# Sitzungsübersicht

[Dokumentation](../README.md)

Das Dashboard zeigt kommende und vergangene Termine aus dem BI-Onlineindex sowie
den lokalen BI- und RI-Indizes. Gleiche Sitzungs-IDs erscheinen gemeinsam in einer
Zeile; BI-Onlinetermine haben bei Terminangaben Vorrang. RI-only-Sitzungen sind ebenfalls enthalten.
Unter „Sitzung öffnen“ führen „BI öffnen“ und „RI öffnen“ direkt zum jeweiligen
lokal indexierten Bestand. Sind beide vorhanden, erscheinen beide Links.
Ohne lokalen Eintrag bleibt bei einem BI-Kalendertermin „Im Ratsinfo ansehen“ verfügbar.
Ein nicht lesbarer RI-Index wird gemeldet; BI-Termine bleiben nutzbar.
Die Bestandszahlen im Datenstatus unterscheiden lokale BI- und RI-Sitzungen.
Da das Dashboard RI-Termine enthält, wird es mit privaten No-Store-Headern ausgeliefert.

Die RI-Sitzungsübersicht verwendet dieselben Filter und Darstellungsbausteine mit
eigenem lokalem Bestand. TOP-Kennzeichnung und PDF-Bedienung beschreibt die
[RI-Oberflächenanleitung](../ri/oberflaeche.md#sitzungen-und-dokumente).

## Geänderte Termine

Seit 0.10.0 zeigt das Dashboard verschobene, abgesagte und unklare Termine im
eigenen Abschnitt **Geänderte Termine** (bis zu 20 Einträge). Sie zählen nicht zu
den nächsten fünf regulären Sitzungen. Originaldatum und Originalhinweis bleiben
sichtbar, ein bekanntes Ersatzdatum wird ergänzt. Eine explizit belegte Ersatz-ID
wird angezeigt; Direktlinks erscheinen, wenn deren lokaler BI-/RI-Eintrag vorhanden ist.
Auch Listen und Sitzungsdetails kennzeichnen den Status. Terminänderungen stehen
nicht mehr im Uhrzeitfeld.

Das Dashboard berücksichtigt zusätzlich den separaten RI-Onlinekalender. Bei
unterschiedlichen Statusständen wird die jüngste bekannte Beobachtung verwendet.
Alte Indizes, die einen Änderungsvermerk noch im Uhrzeitfeld enthalten, können ihn
bereits anzeigen; für vollständig gespeicherte neue Statusfelder die betroffenen
Kalender-/lokalen Indizes aktualisieren. Die Datenverträge stehen unter
[Kalenderstatus](../ri/datenablauf.md#kalenderstatus).

## Gremienfilter

Die Sitzungsübersicht fasst Gremiennamen zusammen, die sich nur durch Bindestriche,
Leerzeichen oder Groß-/Kleinschreibung unterscheiden. Eine vorhandene Schreibweise
mit Bindestrich wird bevorzugt angezeigt. Auch Filterlinks mit einer abweichenden
Schreibweise finden alle zugehörigen Sitzungen. Gespeicherte Sitzungsdaten bleiben
unverändert; die Vereinheitlichung erfolgt beim Aufbau der Übersicht.
