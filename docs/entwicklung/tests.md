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
