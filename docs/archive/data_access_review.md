# Datenzugriff & Compliance-Check

Dieser Bericht dokumentiert den initialen Abgleich der Nutzungsbedingungen für das Ratsinformationssystem der Stadt Melle und angrenzende Informationsquellen.

## Zielsysteme

| Quelle | Zweck | URL-Hinweise |
| ------ | ----- | ------------ |
| Ratsinformationssystem Melle | Sitzungstermine, Tagesordnungen, Vorlagen | `https://session.melle.info/bi/` (Weiterleitungen auf `sessionnet.krz.de/melle/bi/` möglich) |
| Stadtportal Melle | Impressum, Datenschutz, rechtliche Hinweise | `https://www.melle.de/` |

## Technische Erreichbarkeit

- 30.10.2025: Abrufe per `curl` aus der aktuellen Umgebung liefern HTTP 403 (Forbidden). Ein Abgleich der Inhalte ist dadurch hier nicht möglich. Zugriffstests sollten von einem Netzwerk mit regulärem Browserzugriff wiederholt werden.

## Erwartete Anforderungen (Basierend auf SessionNet-Installationen)

1. **Robots.txt prüfen:** SessionNet-Instanzen definieren meist Crawler-Regeln unter `/robots.txt`. Abrufe müssen sich daran halten.
2. **Nutzungsbedingungen:** Üblicherweise enthalten Seiten wie `/info.asp` oder `/disclaimer.asp` Hinweise zur Nutzung öffentlicher Dokumente. Screenshots/Exporte nur zu dokumentarischen Zwecken verwenden.
3. **Datenschutz:** Personenbezogene Daten (z. B. Ansprechpartner:innen, Kontaktdaten) dürfen nicht massenhaft gespeichert oder veröffentlicht werden. Ergebnisse des Analyse-Tools sollen sensible Daten filtern oder pseudonymisieren.
4. **Lastverteilung:** Abrufintervalle so wählen, dass die Infrastruktur nicht überlastet wird (z. B. respektvolle Pausen zwischen Requests, Caching).

## Empfohlene nächste Schritte

1. **Manuelle Sichtung im Browser:** Zugriff über ein lokales Netzwerk herstellen und Screenshots/Notizen der Seiten „Impressum“, „Datenschutz“ und „Nutzungsbedingungen“ ablegen.
2. **Dokumentation ergänzen:** Die gewonnenen Informationen als Markdown-Datei im Ordner `docs/` speichern (z. B. `legal_summary.md`).
3. **Crawler-Implementierung anpassen:** Robots.txt respektieren, Rate-Limits konfigurieren und ggf. Kontakt zur Stadt Melle aufnehmen, falls hohe Abrufvolumina geplant sind.
4. **Datenschutzfolgeabschätzung:** Prüfen, ob verarbeitete Daten personenbezogene Informationen enthalten. Bei Bedarf Anonymisierung oder Zugriffsbeschränkungen einführen.

Bis zur abgeschlossenen Sichtung gelten diese Punkte als vorläufig. Die endgültige Freigabe erfolgt nach dokumentierter Prüfung der Originaltexte.
