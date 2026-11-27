# Glossar

[Dokumentation](README.md)

| Begriff | Bedeutung |
| --- | --- |
| SessionNet | Informationssystem für Sitzungen, Tagesordnungspunkte und Dokumente. |
| BI / Bürgerinformation | Öffentlicher SessionNet-Bereich unter `/bi/`. |
| RI / Ratsbereich | Geschützter SessionNet-Bereich unter `/ri/`; die Anwendung bietet bislang manuelle Zugangstests. |
| TOP | Tagesordnungspunkt einer Sitzung. |
| Rohdaten | Heruntergeladene Originalseiten und Dokumente unter `data/raw/`. |
| Online-Index | Lokal gespeicherte Kalender- und Metadaten zum Auswählen von Sitzungen für den Abruf. |
| Lokaler Index | Aus den Rohdaten aufgebaute SQLite-Datenbank mit Sitzungs- und Dokumentmetadaten. |
| Vektorindex | Suchbestand mit numerischen Textrepräsentationen für semantische Suche. |
| Qdrant | Speicher und Suchdienst für Vektoren; serverbasiert oder lokal nutzbar. |
| Collection | Getrennter Vektorbestand innerhalb von Qdrant. |
| PAT | Persönlicher Zugriffstoken; hier für den Zugriff auf den freigegebenen Proton-Pass-Tresor. |
