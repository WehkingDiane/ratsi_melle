# Datenbanken und Suchindizes

[Dokumentation](../README.md)

- `scripts/build_bi_local_index.py` baut `data/db/local_index.sqlite` aus den öffentlichen SessionNet-Rohdaten. `session_detail.html` ist die maßgebliche Quelle für aktuelle TOP- und Dokumentmetadaten im Index.
- `scripts/build_landkreis_publications_db.py` baut `data/db/landkreis_publications.sqlite` getrennt vom SessionNet-Index.
- `scripts/prepare_embedding_models.py` bereitet lokale Suchmodelle vor. `scripts/build_bi_vector_index.py` baut den Ratsinfo-Index in Qdrant; `scripts/build_landkreis_vector_index.py` baut die getrennte Landkreis-Collection. Der Ratsinfo-Abschnittsindex heißt `ratsi_passages`; `ratsi_documents` ist der ältere Dokumentindex und kann je nach lokalem Migrationsstand noch aktiv sein.
- Standardmäßig wird Qdrant unter `http://127.0.0.1:6333` angesprochen. `RATSI_QDRANT_URL` wählt einen anderen Server; `RATSI_QDRANT_MODE=local` nutzt lokalen Speicher unter `data/db/qdrant/`, sofern keine URL gesetzt ist. Datenbank, Modelle und Suchindex müssen zur gleichen lokalen Umgebung gehören.
- `/suche/` bietet semantische Suche in Ratsinfo- und Landkreis-Unterlagen mit Datumsfiltern und, für Ratsinfo, Gremium und Dokumenttyp. Der Landkreisbestand kann zusätzlich per `scripts/search_landkreis_publications.py` in SQLite durchsucht werden.

- Seit 0.5.67 akzeptieren Aufbau und Suche für `ratsi_passages` die beiden konkret geprüften Manifeststände gemäß [Index-Kompatibilität](kompatibilitaet.md). Alte Vektoren und ihre Herkunft bleiben erhalten; neue Punkte dürfen den akzeptierten Windows-Bibliotheksstand verwenden. Der normale Build ergänzt weiterhin nur fehlende oder unvollständige Dokumente. Die temporären Diagnosewerkzeuge wurden entfernt; eine neue gezielte Aktualisierung alter Dokumente ist nicht Teil dieser Änderung.

Die Vektorstatusanzeige nennt vollständig indexierte und erwartete Dokumente sowie die fehlende Anzahl, zum Beispiel „7824 von 7888 Dokumenten / 64 fehlen“. Der Build speichert diese Zahlen nach jedem Lauf; die Oberfläche liest nur diesen Stand, ohne alle Textabschnitte erneut zu scannen. Nach Änderungen am lokalen Index, am Freigabemarker oder an der Punktzahl wird der alte Stand nicht angezeigt. Eine leere, nur durch Lesezugriffe angelegte SQLite-WAL-Datei gilt dabei wie eine fehlende WAL-Datei; ein WAL mit Inhalt wird weiterhin auf Änderungen geprüft. Statusabfragen schließen ihre Datenbankverbindungen nach dem Lesen. Ohne aktuellen Stand erscheint ein Hinweis; `python scripts/check_bi_vector_index.py --update-status` berechnet ihn einmalig neu und speichert nur die Statuszahlen. Indexpunkte und Suchfreigabe bleiben dabei unverändert.

## Aufbau

Nach dem [Datenabruf](../datenabruf/README.md) aus dem Repository-Stamm ausführen:

```bash
python scripts/build_bi_local_index.py
python scripts/prepare_embedding_models.py --download
python scripts/build_bi_vector_index.py
```

Für den Landkreis gelten die [eigenen Aufbaukommandos](../datenabruf/landkreis.md). Nach erfolgreichem Build steht der gespeicherte Abdeckungsstatus in der Oberfläche bereit. Bei fehlenden Modellen oder veraltetem Status hilft die [Fehlerbehebung](../betrieb/fehlerbehebung.md).
