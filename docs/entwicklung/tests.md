# Tests gezielt ausführen

[Dokumentation](../README.md)


`integration` prüft das Zusammenspiel mehrerer Komponenten mit lokalen oder simulierten Abhängigkeiten. `live` benötigt echte Dienste, Modelle oder nicht versionierte Quelldaten und ist standardmäßig ausgeschlossen. Die vollständige Testsuite wird vor einem PR vom Nutzer ausgeführt.

```bash
python -m pytest -m "not integration and not live"  # schnelle reguläre Tests
python -m pytest -m "integration and not live"      # Integrationstests
python -m pytest                                     # vollständiger Lauf vor dem PR
```


Agenten führen ausschließlich gezielte, schnelle Tests für konkrete Änderungen aus. Den vollständigen PR-Testlauf übernimmt der Nutzer; verbindlich sind die [Agentenregeln](../../AGENTS.md).
