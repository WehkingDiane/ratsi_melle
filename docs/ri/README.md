# Ratsbereich: aktueller Stand

[Dokumentation](../README.md)

Der RI-Zugang verwendet ab 0.6.0 eine lokale Token-Datei `.env/ri_token.txt`. Unter Windows und Linux/WSL gibt es dieselben zwei Checks für Proton-Anmeldung und RI-Zugriff. Speicherpasswörter, Token-Speicherhilfen und separate Eintragsbindung entfallen. Die [RI-Zugangsanleitung](zugang.md) ist der verbindliche Ort für Einrichtung, Befehle und Fehlerbehebung.

- [Einrichtung und Checks](zugang.md)
- [Weiterer Ausbau](../plans/ri_ratsbereich_plan.md)

## Implementierung

`src/config/ri_proton.py` liest den Token aus der von Git ausgeschlossenen Datei, unabhängig vom Arbeitsverzeichnis. Fehlende, leere oder ungültige Dateien erzeugen feste Hinweise ohne Tokeninhalt. Proton-CLI-Sitzungen verwenden ein neues temporäres Verzeichnis mit Dateischlüssel statt Betriebssystem-Keyring; nach dem Check wird dieses entfernt. Der Token gelangt ausschließlich in die Umgebung des Login-Unterprozesses. Zugangsdaten werden in Darstellungen maskiert.

`scripts/setup/check_ri_proton_login.py` prüft Proton-Anmeldung und zeigt die sichtbaren Tresore. `scripts/setup/check_ri_access.py` akzeptiert genau einen sichtbaren Tresor mit genau einem aktiven Login, liest dessen Zugangsfelder intern und prüft die RI-Anmeldung samt Abmeldung. Eine dauerhafte Bindung an frühere IDs wird nicht mehr geprüft. Die Freigabe des Tokens bestimmt, welcher einzelne RI-Eintrag zugänglich ist. Tresor-, Eintrags- und Rechteänderungen sind im Anwendungscode nicht vorgesehen.

`src/fetching/ri_login.py` verwendet feste HTTPS-Ziele, begrenzte HTML-Antworten und flüchtige HTTP-Cookies. Das Passwort wird höchstens einmal an den geprüften Anmeldeendpunkt gesendet; Hostwechsel und Wiederholung des Passwort-POST bei Weiterleitungen werden abgewiesen. Geschützte Seiten und RI-Unterlagen werden nicht gespeichert.

## Abnahme und Grenzen

Die frühere Umsetzung bis 0.5.76 mit OS-Tokenablage und fester Eintragsbindung wurde auf beiden Betriebssystemen real bestätigt. Der Dateifluss ab 0.6.0 ist mit synthetischen Dateien, CLI-Antworten und RI-Antworten geprüft; echte Windows-/WSL-Läufe stehen noch aus. Eine nicht bestätigte entfernte Proton-Abmeldung bleibt als Warnstatus sichtbar. Neustart-/Ablaufverhalten und unbeaufsichtigter Betrieb sind nicht abgenommen.

RI-Dokumentabruf, Datenhaltung, Index und geschützter Webzugang sind noch nicht aktiviert. Historische Änderungen stehen im [Changelog](../../CHANGELOG.md).
