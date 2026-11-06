# Aktuelle Projektaufgabe

Stand: 06.11.2026. Das aktuelle Vorhaben ist der geschützte Ratsbereich für SessionNet `/ri/`, einschließlich der vorgezogenen Vorbereitung von Navigation und Seitenaufbau ohne RI-Zugang. Der [detaillierte Umsetzungsplan](ri_ratsbereich_plan.md) enthält Schutzgrenzen, Abnahmen und die vorgesehene Aufteilung in Teilbranches. Der vorhandene Funktionsumfang steht im [Ist-Stand](../ist_stand.md).

## Kontext

Zugangsdaten für `/ri/` liegen noch nicht vor. Gleichheit der RI-Seitenstruktur mit dem öffentlichen `/bi/`-Bereich ist eine Annahme, die erst nach Anmeldung geprüft werden kann. Schritt 1a ist umgesetzt und über PR #90 in den Vorhaben-Branch übernommen: Bereichsnavigation, quellengebundene öffentliche Einstiege, informative RI-Platzhalter und ein vertikales Seitenlayout sind vorhanden. Öffentliche Daten bleiben weiterhin im bisherigen Ablauf verfügbar. RI-Daten werden zunächst vollständig als intern behandelt.

Bereits erledigt (Statuskontext; die Aufgabenliste darunter enthält nur offene Arbeiten):

- **Erledigt:** BI-/RI-Skriptnamen einschließlich Aufrufern, Tests und Dokumentation geordnet; über PR #89 übernommen.
- **Erledigt:** Navigation, öffentliche Einstiege, RI-Platzhalter und vertikalen Seitenaufbau einschließlich dokumentierter Tests und Browserabnahme umgesetzt; über PR #90 übernommen.
- **Erledigt:** Eigenen Branch `codex/feature/ri-proton-pass-zugang` und [abhakbaren Proton-Pass-Teilplan](ri_proton_pass_zugang_plan.md) angelegt (Commit `cab37b4`). Dokumentations- und lokale CLI-Vorprüfung sind begonnen: Version 2.3.3, Optionen für Eintragsfreigabe und Feldabruf sowie allgemeine Tarifvoraussetzungen sind geprüft. Der Nutzer bestätigt einen passenden Tarif sowie CLI 2.7.0 unter Windows und WSL. Eine geführte lokale Speicherhilfe ist in Version 0.5.69 implementiert; ihr WSL-Test ist noch nicht erfolgreich, eine gezielte Diagnose ist seit 0.5.70 vorhanden. Reale Abnahme, Kontofreischaltung, sichere Tokenablage und Proton-Anbindung bleiben offen.

## RI-Vorhaben

#### Konkrete Aufgaben

- [ ] Daten- und Zugriffskontrakt für den lokalen Ratsbereich festlegen; Betriebsmodell, Speicherort und Suchindex-Zugriff nach Erhalt der Zugangsdaten prüfen.
- [ ] Sicheren RI-Zugangsabruf über Proton Pass mit ausschließlich lesendem Zugriff auf einen Eintrag einrichten, implementieren und prüfen; [Schritt-für-Schritt-Teilplan](ri_proton_pass_zugang_plan.md) abarbeiten.
- [ ] Eigenen authentifizierten RI-Fetcher für Sitzungsübersicht, Details und Dokumente umsetzen; öffentliche Parserfunktionen nur nach Strukturprüfung wiederverwenden.
- [ ] Getrennte RI-Rohdatenwurzel und RI-SQLite-Indizes aufbauen; Herkunft und Kennzeichnung pro Dokument speichern.
- [ ] RI-Dokumente in einem eigenen, zugriffsgeschützten Suchindex indexieren und getrennt durchsuchen.
- [ ] Abruf, Datenbankaufbau und Suche in einen geschützten Ratsbereich der Django-Oberfläche integrieren.
- [ ] Trennung zwischen öffentlichem und internem Bestand mit Tests und einer kleinen lokalen RI-Stichprobe abnehmen; Betriebsdokumentation aktualisieren.
