# Gemeinsame Darstellungsregeln

Die Django-Oberfläche verwendet ein gemeinsames Desktop-Layout. Die Regeln
gelten für Dashboard, Analyse, Datenpflege, Suche, Veröffentlichung und
Einstellungen. Die fachliche Reihenfolge bleibt: Überschrift, Hauptaufgabe,
Ergebnisse und ergänzende Informationen. Das Dashboard bleibt eine durchgehende
Spalte mit kommenden Sitzungen, vergangenen Sitzungen und anschließendem Status.

## Arbeitsbereiche

„Daten“ enthält die normalen Fetch- und Build-Abläufe mit ihrem Status.
„Service“ bündelt Wartung und Einstellungen. Modellvorbereitung, Prüfungen und
Modell-/Legacy-Jobhistorie stehen auf `/service/wartung/`, Einstellungen auf
`/service/einstellungen/`. Wartungsjobs verwenden auch beim Öffnen älterer
Datenjob-Links die Service-Navigation. Die Vektorseite zeigt nur normale Builds
und Indexstatus; ein Link führt zur Wartung. Seitenaufrufe starten keine Jobs.

## Zentrale Werte

Gestaltungswerte stehen in `web/core/static/core/css/base.css` unter `:root`.
Bestehende Bausteine verwenden diese Variablen statt eigener Seitenabstände.

| Variable | Wert | Verwendung |
| --- | --- | --- |
| `--space-page` | 20 px | Abstand zwischen Bereichen und Layoutspalten |
| `--space-panel` | 18 px | Innenabstand eines Panels |
| `--space-content` | 14 px | Inhalte innerhalb eines Panels und Formularfelder |
| `--space-inline` | 10 px | Zusammengehörige Aktionen |
| `--space-field` | 6 px | Beschriftung und zugehöriges Eingabefeld |
| `--space-compact` | 8 px | Kompakte Gruppen und Rückmeldungen |
| `--control-height` | 44 px | Normale Buttons und einzeilige Eingaben |
| `--control-height-small` | 30 px | Kompakte Nebenaktionen |
| `--font-page-title` | 32 px | Seitentitel |
| `--font-section-title` | 18 px | Bereichstitel |
| `--font-caption` | 13 px | Ergänzende Beschriftungen |
| `--table-cell-padding` | 10 / 12 px | Vertikaler / horizontaler Zellabstand |
| `--table-compact-padding` | 8 / 10 px | Kompakte Tabellen |

Farben für Erfolg, Warnung, Fehler und Information werden ebenfalls dort mit
Text-, Hintergrund- und Rahmenfarbe definiert. Farbänderungen erfolgen an diesen
Werten, nicht an einzelnen Templates.

## Seiten und Bereiche

`base.html` stellt automatisch einen `page-stack` um den Inhaltsblock bereit.
Templates benötigen keinen eigenen Seitencontainer. `content-stack` verwendet
dieselbe Regel für untergeordnete Gruppen, beispielsweise in einer Statusspalte.
`grid two-columns`, `grid three-columns`, `split-content` und `answer-reader`
verwenden denselben Bereichsabstand; ihre fachlich erforderlichen Spalten bleiben
erhalten.

Ein `panel` besitzt 18 px Innenabstand und 14 px zwischen seinen direkten
Inhalten. Container bestimmen die Abstände; direkte Kinder von Seiten-,
Inhalts-, Panel- und Formularcontainern erhalten keine zusätzlichen Außenränder.
Seitenspezifische Margin-Korrekturen und leere Abstandselemente vermeiden.
Gerenderte Markdown-Inhalte behalten ihre interne Textformatierung.
Aufklappbare `details.panel` behalten das native Öffnen und Schließen.

Für einen Bereichskopf mit Nebenaktion steht
`core/partials/panel_header.html` bereit:

```django
{% include "core/partials/panel_header.html" with heading="Aktueller Status" refresh_label="Status aktualisieren" only %}
```

Optional sind `heading_id`, `meta` oder `link_url` mit `link_label` möglich.
Die Aktualisierung behält `data-service-status-refresh` für das vorhandene
JavaScript. Mit `only` werden ausschließlich die vorgesehenen Parameter
übergeben. Fachliche IDs, Formulardaten und JavaScript-Attribute bleiben in den
jeweiligen Templates.

## Formulare und Aktionen

`form-stack` gruppiert Felder vertikal. Beschriftungen stehen beim zugehörigen
Feld; Checkboxen und Radiobuttons stehen neben ihrem Text. Mehrzeilige Textfelder
können höher sein als normale Eingaben. Pflichtangaben, Eingabetypen und
Bestätigungen bleiben erhalten.

| Klasse | Bedeutung |
| --- | --- |
| `button primary` | Auslösen, speichern, suchen, filtern oder bauen |
| `button secondary` | Eine Seite oder vorhandene Inhalte öffnen |
| `button utility` | Aktualisieren, zurücksetzen oder abbrechen |
| `button danger` | Löschen |
| `small` | Kompakte Nebenaktion, zusätzlich zur Rollenklasse |

Links auf ein Startformular sind Navigation; erst dessen Absenden ist die
auslösende Hauptaktion. Buttons und Links verwenden dieselbe Schrift.
Deaktivierte Aktionen bleiben als solche erkennbar. Datums-, Uhrzeit- und
Datum/Uhrzeit-Zellen verwenden `date-value`, `time-value` oder `datetime-value`.
Der fachliche Inhalt und die Datenformatierung bleiben Aufgabe der Services.

## Rückmeldungen und Laufzustände

Erfolgs- und Fehlermeldungen verwenden denselben Baustein:

```django
{% include "core/partials/messages.html" with messages=messages errors=errors only %}
```

Erfolge werden mit `notice status-ok` und `role="status"`, Fehler mit
`notice status-error` und `role="alert"` ausgegeben. Die Texte bleiben
automatisch maskiert. `notice status-warning` ist für Warnungen vorgesehen.
Informationen verwenden `info-panel` oder `notice`; `running-banner` zeigt eine
laufende Aktion. Ein leerer Bestand (`empty-state`) ist eine neutrale Information.
Status immer auch durch Text ausdrücken, nicht ausschließlich durch Farbe.

`hidden` muss unabhängig vom Layout zuverlässig ausblenden. Die gemeinsame
Grundregel hat deshalb Vorrang vor `display: flex` oder `display: grid`.
Vorhandene Live-Regionen und JavaScript-Selektoren bleiben bestehen.

## Änderungen prüfen

- Gemeinsame Regeln an den zentralen Bausteinen ändern, nicht pro Seite kopieren.
- Repräsentative Seiten mit Formularen, Tabellen, leeren Beständen und geöffneten
  Details am Desktop prüfen; dabei tatsächliche Abstände im Browser messen.
- Versteckte Laufhinweise vor einer Aktion prüfen. Für Layoutprüfungen keine
  realen Builds, Downloads, Tokenänderungen oder KI-Aufträge starten.
- Bei Stylesheet-Änderungen die gemeinsame `ui_version` in `base.html` bewusst
  aktualisieren. Alle Stylesheets erhalten denselben Cache-Parameter.
- Bestehende Seiten- und Workflowtests ausführen und diese Dokumentation bei
  geänderten Regeln aktualisieren.
