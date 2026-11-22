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

## Gremienfilter

Die Sitzungsübersicht fasst Gremiennamen zusammen, die sich nur durch Bindestriche,
Leerzeichen oder Groß-/Kleinschreibung unterscheiden. Eine vorhandene Schreibweise
mit Bindestrich wird bevorzugt angezeigt. Auch Filterlinks mit einer abweichenden
Schreibweise finden alle zugehörigen Sitzungen. Gespeicherte Sitzungsdaten bleiben
unverändert; die Vereinheitlichung erfolgt beim Aufbau der Übersicht.
