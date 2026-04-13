# Grundkonzept Django-Oberflaeche

Ziel:
- Die grosse produktartige Oberflaeche wird kuenftig als Django-Anwendung aufgebaut.
- Streamlit bleibt als schnelle interne Developer-Oberflaeche fuer Fetch-, Build- und Diagnosepfade bestehen.
- Die Django-Oberflaeche soll in klar getrennte Seiten aufgeteilt werden, damit jede Seite einzeln gestaltet, gebaut und iteriert werden kann.

## 1. Rollenverteilung der Oberflaechen

### Django
- primaere Nutzeroberflaeche
- produktartige Recherche- und Analyseoberflaeche
- saubere Seitenstruktur mit festen URLs
- langfristig bessere Basis fuer Layout, Rechte, gespeicherte Ansichten und stabile Navigation

### Streamlit
- interne Developer-/Operations-Oberflaeche
- schnelle Skript-Runner fuer Fetch und Build
- Status- und Diagnoseansichten
- fruehe oder experimentelle KI-Analysepfade

## 2. Leitprinzipien fuer die Django-Oberflaeche

- Jede Hauptfunktion bekommt eine eigene Seite.
- Navigation und Seitenstruktur sind wichtiger als ein fruehes Detaildesign.
- Fachlogik bleibt moeglichst ausserhalb von Views und Templates.
- Bestehende Python-Fachlogik aus `src/analysis/`, `src/fetching/`, `src/interfaces/shared/` und spaeter weiteren Servicemodulen wird wiederverwendet.
- Dokumente, Sitzungen, TOPs und Analysen werden als zusammenhaengender Recherchefluss gedacht, nicht als lose Einzelfeatures.

## 3. Empfohlene Hauptnavigation

### 1. Dashboard
- schneller Einstieg
- Status der lokalen Datenbasis
- zuletzt bearbeitete Sitzungen
- letzte Analysen
- Hinweise, wenn lokaler Index oder Vektorindex fehlen

### 2. Recherche
- Sitzungen filtern
- Gremien waehlen
- Sitzungslisten durchsuchen
- einzelne Sitzungen und TOPs oeffnen
- Dokumente einer Sitzung oder eines TOPs einsehen

### 3. Semantische Suche
- freie Suchanfrage
- Trefferliste aus dem Vektorindex
- spaeter Filter nach Gremium, Zeitraum, Dokumenttyp, Sitzung
- Treffer auf Sitzung, TOP oder Dokument herunterbrechen

### 4. Analyse
- Gremium, Sitzung, TOP oder Dokumente gezielt waehlen
- Prompt konfigurieren
- Provider und Modell waehlen
- KI-Analyse starten
- Ergebnis lesen, speichern, spaeter erneut oeffnen

### 5. Dokumente
- dokumentzentrierte Ansicht
- Dateiliste, Typen, Metadaten, Quellen
- spaeter PDF-Viewer oder Textvorschau

### 6. Einstellungen
- Provider-Konfiguration
- API-Keys
- Prompt-Vorlagen
- spaeter systemweite Defaults

## 4. Minimale erste Seitenaufteilung

Fuer einen ersten strukturierten Django-Start reichen diese Seiten:

### `dashboard/`
- System- und Datenstatus
- Schnelllinks

### `research/`
- Sitzungsfilter
- Gremien
- Sitzungsliste

### `research/session/<id>/`
- Sitzung im Detail
- TOP-Liste
- Dokumente

### `search/`
- semantische Suche

### `analysis/new/`
- neue Analyse anlegen

### `analysis/<id>/`
- Ergebnisansicht

### `settings/`
- API-Keys und Prompt-Vorlagen

## 5. Fachliche Kernobjekte der Django-Oberflaeche

Die Oberflaeche sollte nicht um technische Skripte, sondern um diese Nutzobjekte herum gebaut werden:

- `Gremium`
- `Sitzung`
- `TOP`
- `Dokument`
- `Analyseauftrag`
- `Analyseergebnis`

Diese Objekte koennen in Django anfangs auch ohne vollstaendige neue DB-Modelle ueber bestehende SQLite-/Service-Zugriffe abgebildet werden. Wichtiger ist zuerst die Seiten- und Interaktionslogik.

## 6. Empfohlene Django-Projektstruktur

```text
django_ui/
  manage.py
  config/
    settings.py
    urls.py
  apps/
    dashboard/
    research/
    search/
    analysis/
    documents/
    settings_ui/
  templates/
    base.html
    components/
  static/
    css/
    js/
    images/
```

## 7. Trennung von Verantwortung

### Django-Apps
- Routing
- Views
- Templates
- Formularlogik
- Seitenspezifische Interaktion

### Bestehende Projektlogik
- Datenzugriff
- Analyse-Service
- Prompt-Verwaltung
- Vektorsuche
- Pfadauflösung

Das heisst:
- Django soll moeglichst die vorhandene Fachlogik konsumieren
- nicht alles neu in Django hinein kopieren

## 8. Priorisierte Reihenfolge fuer die Umsetzung

### Phase 1: Grundgeruest
- Django-Projekt anlegen
- Basislayout mit Header, linker Navigation, Content-Bereich
- Platzhalterseiten fuer Dashboard, Recherche, Suche, Analyse, Einstellungen

### Phase 2: Recherchefluss
- Gremienfilter
- Sitzungsliste
- Sitzungsdetailseite
- Dokumentlisten

### Phase 3: Analysefluss
- Analyseauftrag aus Sitzung/TOP/Dokumenten erzeugen
- Provider- und Prompt-Konfiguration
- Ergebnisansicht

### Phase 4: Suche
- semantische Suche in eigene Django-Seite integrieren
- Verlinkung zu Sitzung/TOP/Dokument

### Phase 5: Design und Nutzerfuehrung
- visuelle Gestaltung
- konsistente Komponenten
- bessere Lesbarkeit und Orientierung

## 9. Was bewusst nicht in die Django-Hauptoberflaeche gehoert

- rohe Skriptsteuerung fuer Fetch/Build als prominente Hauptfunktion
- technische Diagnosepfade fuer Entwickler
- alte Export-Workflows als primaere Nutzerfunktion

Diese Dinge bleiben besser in Streamlit oder spaeter in einem Admin-/Operations-Bereich.

## 10. Ergebnis dieses Grundkonzepts

Die Django-Oberflaeche wird:
- nutzerzentriert
- seitenbasiert
- layoutstabil
- gestalterisch flexibler als Streamlit

Die Streamlit-Oberflaeche bleibt:
- schnell
- technisch
- developer-orientiert
- ideal fuer Datenpflege, Build-Pfade und interne Erstanalysen
