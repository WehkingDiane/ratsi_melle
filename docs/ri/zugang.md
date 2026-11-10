# RI-Zugang einrichten und prüfen

Unter Windows und Linux/WSL gilt derselbe Ablauf: Token in einer lokalen Textdatei hinterlegen und die Check-Skripte starten. Eine Speicherpasswort-Abfrage oder separate Eintragsbindung gibt es für diesen Ablauf nicht. Die Schritte laden keine RI-Unterlagen herunter. Der weitere Ausbau steht im [RI-Plan](../plans/ri_ratsbereich_plan.md).

## Voraussetzungen

- Projektabhängigkeiten und aktivierte Python-Umgebung; unter WSL alternativ `.venv-wsl/bin/python` statt `python` verwenden.
- Installierte Proton Pass CLI 2.7.0 (`ba80a19`), unter Windows und WSL jeweils für das betreffende System. Der Check installiert keine Software. Unter Windows wird neben `PATH` auch der offizielle Benutzerordner `%LOCALAPPDATA%/Programs/ProtonPass` geprüft.
- Vollständiger Proton-Pass-Zugriffstoken mit Freigabe ausschließlich für den gewünschten RI-Tresor mit genau einem aktiven Login-Eintrag. Die serverseitigen Schreibrechte sind nicht durch die Anwendung eingeschränkt; der Anwendungscode führt keine Schreiboperationen an Einträgen oder Rechten aus.

Die offiziellen [Installationshinweise der CLI](https://protonpass.github.io/pass-cli/get-started/installation/) beschreiben die Installation. Die projektseitige CLI-Zielversion bleibt 2.7.0.

## Token hinterlegen oder ersetzen

Im Repository-Stamm einen Ordner `.env` und darin eine UTF-8-Textdatei `ri_token.txt` anlegen. `.env` ist hier ausdrücklich ein **Ordner**, keine dotenv-Konfigurationsdatei. Die Datei enthält ausschließlich den vollständigen Token als eine Zeile, ohne Anführungszeichen, Variablennamen oder JSON:

```text
.env/ri_token.txt
```

Den Token im Editor einfügen und speichern. Bei einem abgelaufenen oder widerrufenen Token den Inhalt durch einen neuen Token ersetzen. Die Gültigkeitsdauer wird bei Proton festgelegt, nicht durch diese Datei. Der Check prüft die tatsächliche Nutzbarkeit durch Anmeldung; er berechnet kein Ablaufdatum.

Der komplette Ordner `.env/` ist von Git ausgeschlossen. Der Token liegt darin **unverschlüsselt**; Dateizugriff auf das eigene Benutzerkonto begrenzen und die Datei nicht veröffentlichen oder in öffentliche Sicherungen übernehmen. Unter Linux können die Rechte mit `chmod 600 .env/ri_token.txt` begrenzt werden; auf einem unter Windows eingebundenen WSL-Dateisystem hängen wirksame Rechte auch von den Windows-Berechtigungen ab.

Die Datei wird immer relativ zum Repository gefunden, unabhängig vom aktuellen Arbeitsverzeichnis. Wenn Windows und WSL dasselbe Checkout verwenden, können sie dieselbe Datei lesen. Bei getrennten Checkouts muss die Datei in jedem Checkout vorhanden sein. Es gibt kein Token-Speicherskript mehr und keinen Zugriff auf früher hinterlegte RI-Tokens in Windows Credential Manager oder GNOME Keyring.

## RI-Proton-Anmeldung testen

Aus dem Repository-Stamm starten:

```bash
python scripts/setup/check_ri_proton_login.py
```

Erwartetes Ergebnis: erfolgreiche Proton-Anmeldung und Ausgabe der sichtbaren Tresore mit Namen/IDs. Der Test liest keine Login-Felder und meldet sich nicht bei RI an. Er übergibt den Token ausschließlich dem Login-Unterprozess per Umgebung, nicht als Prozessargument. Native Fehlerausgaben bleiben intern; der vollständige Token wird aus der ausdrücklich angezeigten Tresorliste ausgeblendet.

## Gezielten Zugriff und RI-Anmeldung prüfen

```bash
python scripts/setup/check_ri_access.py
```

Der Test akzeptiert genau einen sichtbaren Tresor mit genau einem aktiven Login-Eintrag. Erst danach werden dessen Benutzername (ersatzweise E-Mail) und Passwort intern gelesen und für die RI-Anmeldung verwendet. Mehrere Tresore, mehrere aktive Einträge oder ein anderer Eintragstyp führen zum Abbruch vor dem Passwortabruf. Es wird keine dauerhafte Tresor-/Eintrags-ID gespeichert: Der einzige Eintrag wird bei jedem Lauf anhand des aktuellen Tokens geprüft. Deshalb den Token ausschließlich für den beabsichtigten RI-Tresor freigeben. Ein neuer alleiniger Eintrag wird beim nächsten Lauf verwendet; eine frühere Identität wird nicht mehr abgeglichen.

Erwartetes Ergebnis: RI-Anmeldung und anschließende RI-Abmeldung bestätigt, ohne Ausgabe von Zugangsdaten. Alte Referenzdateien unter `%LOCALAPPDATA%/ratsi_melle/ri_proton_access.json` beziehungsweise `~/.local/share/ratsi_melle/ri_proton_access.json` werden nicht mehr gelesen oder verändert. `--configure` entfällt.

## Temporäre Sitzungen und Abmeldung

Beide Checks verwenden pro Aufruf ein eigenes temporäres CLI-Sitzungsverzeichnis und erzwingen `PROTON_PASS_KEY_PROVIDER=fs`. Damit benötigt auch die CLI keinen Betriebssystem-Schlüsselspeicher. Laut [CLI-Konfiguration](https://protonpass.github.io/pass-cli/get-started/configuration/) liegt dabei der Sitzungsschlüssel als `local.key` neben den verschlüsselten Sitzungsdaten. Diese Ablage gilt nur für das temporäre Check-Verzeichnis; persönliche CLI-Sitzungen und deren Einstellungen werden nicht übernommen.

Nach dem Versuch wird Proton abgemeldet und das temporäre Verzeichnis entfernt. Wenn normale Abmeldung fehlschlägt, wird lokale Bereinigung versucht. Sie bestätigt keine entfernte Abmeldung; eine entfernte Sitzung kann bis zum Ablauf bestehen bleiben. Ein harter Prozessabbruch kann temporäre Dateien zurücklassen. Es wird keine dauerhafte Anwendungssitzung eingerichtet.

Exitcodes: `0` = Check erfolgreich und Proton-Abmeldung bestätigt; `2` = Check erfolgreich, entfernte Proton-Abmeldung nicht bestätigt; `1` = Check- oder Bereinigungsfehler. Der bisher bekannte Windows-Abmeldehinweis stammt aus dem alten Keyring-Ablauf; ob er mit Dateisitzungen weiterhin auftritt, muss real geprüft werden.

## Typische Fehler

| Meldung | Nächster Schritt |
| --- | --- |
| Token-Datei fehlt, ist leer oder ungültig | Die in der Meldung genannte Datei erstellen und nur den vollständigen Token eintragen. Windows darf nicht unbemerkt `.txt.txt` anhängen. |
| Token-Datei nicht lesbar | Zugriffsrechte und UTF-8-Kodierung prüfen. |
| Proton CLI fehlt | CLI für das betreffende Betriebssystem installieren und Erreichbarkeit prüfen. |
| Anmeldung fehlgeschlagen | Gültigkeit/Freischaltung des Tokens und Netzwerk prüfen; bei Bedarf Datei durch neuen Token ersetzen. |
| Genau ein Tresor/Login erforderlich | Freigabe des Tokens und Inhalt des RI-Tresors prüfen. |
| Alte Anleitung fragt nach Speicherpasswort oder Bindung | Die beiden oben genannten Check-Skripte verwenden; alte Speicherhilfen und das frühere lokale PowerShell-Setup sind abgelöst. |

## Grenzen des RI-Anmeldetests

Das feste Testziel ist `https://session.melle.info/ri/`. Der Test liest das öffentliche Anmeldeformular und sendet den Zugang genau einmal an den geprüften RI-Anmeldeendpunkt. Passwortänderung und Kennwort-Wiederherstellung werden nicht ausgewählt. HTTPS, Host und Zielpfade werden vor Weiterleitungen geprüft; Wiederholung eines Passwort-POST bei 307/308 wird abgelehnt. Es gibt keine automatischen Anmeldewiederholungen.

Der beobachtete Ablauf nutzt nach dem POST `ylogonstart.asp` und kann HTML-Meta-Weiterleitungen enthalten. Der Formularparameter `logongopn` erhält den Seitennamen `info` ohne `.asp`. Die reine Abschlussseite `smc_end.asp` nach der Abmeldung wird nicht angefordert; stattdessen wird der geschützte Einstieg erneut geprüft.

Eine HTTP-200-Antwort allein gilt nicht als Erfolg: Die geschützte Einstiegsseite muss einen erkannten Abmeldelink enthalten. Danach wird die RI-Abmeldung über erneute Prüfung des geschützten Einstiegs bestätigt. Der Test lädt keine Sitzungen oder Dokumente herunter und schreibt weder HTML noch HTTP-Cookies auf Platte. Eine möglicherweise notwendige zusätzliche Anmeldung, Passwortänderung oder ein verändertes Formular führt zum Abbruch. Bei einem Abbruch nach dem Passwortversand kann eine entfernte RI-Sitzung bis zu ihrem Ablauf bestehen bleiben; lokale Cookies werden verworfen. Der BI-Abruf und die öffentliche Datenhaltung werden nicht verwendet.

Die frühere Variante mit OS-Tokenablage und fester Eintragsbindung wurde bis 0.5.76 unter Windows und WSL real geprüft. Der neue Dateifluss ist synthetisch getestet; die echte Abnahme auf beiden Betriebssystemen steht noch aus. RI-Dokumentabruf, RI-Index und Webzugang sind nicht Bestandteil dieser Umstellung.
