# Grundkonzept Django-Oberfläche

Hinweis: Dieses Dokument beschreibt das Ziel- und Konzeptbild der Django-Oberfläche. Den aktuellen implementierten Stand der lokalen Weboberfläche beschreibt [docs/web_ui.md](web_ui.md).

Ziel:
- Die produktartige Oberflaeche wird als Django-Anwendung unter `web/` weiterentwickelt.
- Aktive UI-Entwicklung konzentriert sich ausschliesslich auf diesen Django-Pfad.
- Streamlit und die Desktop-GUI sind deprecated Legacy-Pfade und werden nicht mehr als aktive Hauptpfade geplant.
- Die Django-Oberflaeche soll in klar getrennte Seiten aufgeteilt werden, damit jede Seite einzeln gestaltet, gebaut und iteriert werden kann.

## 1. Rollenverteilung der Oberflächen

### Django
- primäre Nutzeroberfläche
- produktartige Recherche- und Analyseoberfläche
- saubere Seitenstruktur mit festen URLs
- langfristig bessere Basis für Layout, Rechte, gespeicherte Ansichten und stabile Navigation

### Deprecated Legacy-Pfade
- `src/interfaces/web/streamlit_app.py` bleibt nur fuer Legacy-Kompatibilitaet erhalten.
- `src/interfaces/gui/` bleibt nur fuer bestehende lokale Alt-Workflows erhalten.
- Neue UI-Funktionen, Navigation und Dokumentation entstehen unter `web/`.

## 2. Leitprinzipien für die Django-Oberfläche

- Jede Hauptfunktion bekommt eine eigene Seite.
- Navigation und Seitenstruktur sind wichtiger als ein frühes Detaildesign.
- Fachlogik bleibt möglichst außerhalb von Views und Templates.
- Bestehende Python-Fachlogik aus `src/analysis/`, `src/fetching/`, `src/interfaces/shared/` und später weiteren Servicemodulen wird wiederverwendet.
- Dokumente, Sitzungen, TOPs und Analysen werden als zusammenhängender Recherchefluss gedacht, nicht als lose Einzelfeatures.

## 3. Empfohlene Hauptnavigation

### 1. Dashboard
- schneller Einstieg
- Status der lokalen Datenbasis
- zuletzt bearbeitete Sitzungen
- letzte Analysen
- Hinweise, wenn lokaler Index oder Vektorindex fehlen

### 2. Recherche
- Sitzungen filtern
- Gremien wählen
- Sitzungslisten durchsuchen
- einzelne Sitzungen und TOPs öffnen
- Dokumente einer Sitzung oder eines TOPs einsehen

### 3. Semantische Suche
- freie Suchanfrage
- Trefferliste aus dem Vektorindex
- später Filter nach Gremium, Zeitraum, Dokumenttyp, Sitzung
- Treffer auf Sitzung, TOP oder Dokument herunterbrechen

### 4. Analyse
- Gremium, Sitzung, TOP oder Dokumente gezielt wählen
- Prompt konfigurieren
- Provider und Modell wählen
- KI-Analyse starten
- Ergebnis lesen, speichern, später erneut öffnen

### 5. Dokumente
- dokumentzentrierte Ansicht
- Dateiliste, Typen, Metadaten, Quellen
- später PDF-Viewer oder Textvorschau

### 6. Einstellungen
- Provider-Konfiguration
- API-Keys
- Prompt-Vorlagen
- später systemweite Defaults

## 4. Minimale erste Seitenaufteilung

Für einen ersten strukturierten Django-Start reichen diese Seiten:

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

## 5. Fachliche Kernobjekte der Django-Oberfläche

Die Oberfläche sollte nicht um technische Skripte, sondern um diese Nutzobjekte herum gebaut werden:

- `Gremium`
- `Sitzung`
- `TOP`
- `Dokument`
- `Analyseauftrag`
- `Analyseergebnis`

Diese Objekte können in Django anfangs auch ohne vollständige neue DB-Modelle über bestehende SQLite-/Service-Zugriffe abgebildet werden. Wichtiger ist zuerst die Seiten- und Interaktionslogik.

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
- seitenspezifische Interaktion

### Bestehende Projektlogik
- Datenzugriff
- Analyse-Service
- Prompt-Verwaltung
- Vektorsuche
- Pfadauflösung

Das heißt:
- Django soll möglichst die vorhandene Fachlogik konsumieren
- nicht alles neu in Django hinein kopieren

## 8. Priorisierte Reihenfolge für die Umsetzung

### Phase 1: Grundgerüst
- Django-Projekt anlegen
- Basislayout mit Header, linker Navigation, Content-Bereich
- Platzhalterseiten für Dashboard, Recherche, Suche, Analyse, Einstellungen

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

### Phase 5: Design und Nutzerführung
- visuelle Gestaltung
- konsistente Komponenten
- bessere Lesbarkeit und Orientierung

## 9. Was nicht prominent in die Django-Hauptoberflaeche gehoert

- rohe Skriptsteuerung für Fetch/Build als prominente Hauptfunktion
- technische Diagnosepfade für Entwickler
- alte Export-Workflows als primäre Nutzerfunktion

Diese Dinge gehoeren, falls weiter benoetigt, in klar abgegrenzte Django-Admin-/Operations-Seiten statt in Streamlit.

## 10. Ergebnis dieses Grundkonzepts

Die Django-Oberfläche wird:
- nutzerzentriert
- seitenbasiert
- layoutstabil
- gestalterisch flexibler als Streamlit

Deprecated Legacy-Pfade bleiben nur als Kompatibilitaet erhalten:
- `src/interfaces/web/streamlit_app.py`
- `src/interfaces/gui/`
