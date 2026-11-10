# Fehlerbehebung

[Dokumentation](../README.md)

| Beobachtung | Prüfung / nächster Schritt |
| --- | --- |
| `python` unter WSL fehlt | `python3` oder `.venv-wsl/bin/python` verwenden; siehe [Einrichtung](einrichtung.md). |
| Suchmodelle fehlen | `python scripts/prepare_embedding_models.py --download` ausführen. |
| Qdrant nicht erreichbar | Server unter `RATSI_QDRANT_URL` beziehungsweise dem Standardziel prüfen; siehe [Indexkonfiguration](../suche/indizes.md). |
| Vektorstatus fehlt oder ist veraltet | `python scripts/check_bi_vector_index.py --update-status` berechnet die Statuszahlen erneut. |
| Modellvertrag wird abgewiesen | Die [Kompatibilitätsregeln](../suche/kompatibilitaet.md) prüfen. |
| RI-Token fehlt oder ist ungültig | Token-Datei gemäß [RI-Zugangsanleitung](../ri/zugang.md) prüfen und bei Bedarf ersetzen. |

Befehle aus dem Repository-Stamm mit der passenden Python-Umgebung ausführen. Laufzeitlogs liegen unter `logs/`.
