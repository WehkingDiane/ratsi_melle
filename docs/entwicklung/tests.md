# Tests gezielt ausführen

[Dokumentation](../README.md)

`integration` prüft das Zusammenspiel mehrerer Komponenten mit lokalen oder simulierten Abhängigkeiten. `live` benötigt echte Dienste, Modelle oder nicht versionierte Quelldaten und ist standardmäßig ausgeschlossen. Die vollständige Testsuite wird vor einem PR vom Nutzer ausgeführt.

```bash
python -m pytest -m "not integration and not live"  # schnelle reguläre Tests
python -m pytest -m "integration and not live"      # Integrationstests
python -m pytest                                     # vollständiger Lauf vor dem PR
```

Agenten führen ausschließlich gezielte, schnelle Tests für konkrete Änderungen aus. Den vollständigen PR-Testlauf übernimmt der Nutzer; verbindlich sind die [Agentenregeln](../../AGENTS.md).

## Live-Tests

Live-Tests sind standardmäßig ausgeschlossen. Ein expliziter Lauf mit `python -m pytest -m live` benötigt die jeweils im Test angegebenen Dienste, Modelle oder lokalen Quelldaten. Den Umfang vorab am konkreten Test prüfen; dieser Befehl ist keine allgemeine Abnahme und wird vom Agenten hier nicht ausgeführt.

## Optionaler PDF-Belastungstest

Der lokale Opt-in-Test erzeugt aus den versionierten Fixtures ein 300-seitiges PDF. Er benötigt keinen Download. Aus dem Repository-Stamm unter WSL/Linux:

```bash
RATSI_PDF_STRESS=1 python -m pytest tests/test_pdf_fixtures.py::test_pdf_stress_with_300_original_pages
```

Unter PowerShell vor dem gezielten pytest-Aufruf `$env:RATSI_PDF_STRESS = "1"` setzen und anschließend mit `Remove-Item Env:RATSI_PDF_STRESS` entfernen. Herkunft und Pflege der Dateien stehen in der [Fixture-Dokumentation](../../tests/fixtures/pdf/README.md).

## Dokument-IDs und Downloadmeldungen

Gezielte Offline-Prüfung der SessionNet-Manifest- und Downloadänderungen:

```bash
python -m pytest -q tests/test_sessionnet_client_documents.py tests/test_sessionnet_completed_downloads.py tests/test_sessionnet_detail_parser.py tests/test_sessionnet_incremental_downloads.py
```

Die Tests prüfen eindeutige und fehlende Dokument-IDs, Metadaten ohne lokale Datei, die Ergänzung alter Manifest-Einträge auch bei Wiederverwendung oder fehlgeschlagenem Download sowie Downloadmeldungen mit ID bei unveränderter Abruf-URL. Netzwerkantworten sind simuliert; vorhandene Laufzeitdaten werden nicht verändert. Die einmalige lokale Nachpflege ist in der [Abrufanleitung](../datenabruf/sessionnet.md#dokument-id-im-manifest) dokumentiert.

## Regulärer RI-CLI-Ablauf

Gezielte Tests ohne Token, Portalzugriff oder Änderungen an lokalen Laufzeitdaten:

```bash
python -m pytest -q tests/test_ri_config.py tests/test_ri_online_index.py tests/test_ri_fetch.py tests/test_ri_local_index.py
```

Die Tests prüfen Anmeldung und Abmeldung mit simulierten Antworten, erlaubte Ziele,
Abrufgrenze und Konfigurationsfehler, BI-/RI-Dokumentkennzeichnung, wiederholte Builds,
getrennte Datenbankpfade und den Ausschluss fehlender lokaler Dateien. Größen- und
Streamfehler werden bis zum RI-Exitcode geprüft, einschließlich alter Manifest-Einträge,
Fortsetzung mit nachfolgenden Sitzungen und erfolgreichem Wiederholungslauf. Integrationstests
verwenden ausschließlich pytest-Temporärverzeichnisse. Der [RI-Datenablauf](../ri/datenablauf.md)
ist der verbindliche Ort für Bedienung und Dateiverträge.
