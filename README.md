# Ratsinformations-Analysetool Melle

## **Projektbeschreibung**

Dieses Projekt dient der automatisierten **Erfassung, Analyse und Zusammenfassung kommunalpolitischer Informationen** aus dem Ratsinformationssystem der Stadt Melle ([session.melle.info](https://session.melle.info/bi/info.asp)).  
Ziel ist es, vergangene Sitzungen journalistisch aufzubereiten und zukünftige Sitzungen für Kommunalpolitiker strukturiert vorzubereiten – mit Fokus auf Transparenz, Nachvollziehbarkeit und moderner KI-Unterstützung.

Das Projekt arbeitet mit **Python** und **Streamlit**, nutzt Web-Scraping zur Datenerfassung und kann über ein einfaches Dashboard Daten anzeigen, filtern und analysieren.

---

## **Ziele des Projekts**

1. **Vergangene Sitzungen journalistisch zusammenfassen**  
   - Automatisierte Erfassung von Beschlüssen und Anträgen.  
   - Erstellung verständlicher Kurzfassungen mit KI-Unterstützung.  
   - Einordnung der Themen nach Bedeutung, Gremium und Beschlusslage.

2. **Zukünftige Sitzungen für Kommunalpolitiker aufbereiten**  
   - Zusammenfassung der Tagesordnungspunkte.  
   - Erkennung relevanter Themen (z. B. Klima, Wohnen, Verkehr, Bildung).  
   - Bereitstellung einer KI-gestützten Voranalyse zu möglichen Auswirkungen.

3. **Technische Transparenz schaffen**  
   - Strukturiertes Speichern der Ratsdokumente in nachvollziehbarer Ordnerstruktur.  
   - Zentrale Datenbasis für spätere Visualisierungen, Zeitverläufe oder Presserecherchen.  

---

## **Funktionsumfang (geplant)**

### **1. Sitzungskalender auslesen**
- Automatisches Abrufen des Sitzungskalenders von  
  `https://session.melle.info/bi/si010.asp`.
- Extraktion folgender Informationen:
  - Gremium (z. B. Rat, Ausschuss, Ortsrat)
  - Sitzungsdatum
  - Sitzungsnummer / URL
- Ablage in JSON oder SQLite-Datenbank.

### **2. Vorlagenübersicht auslesen**
- Zu jeder Sitzung werden die zugehörigen **Vorlagen (Anträge, Beschlüsse, Mitteilungen)** gesammelt.  
- Erfassung von:
  - Titel, Nummer, Status, Datum, Antragsteller, Gremium  
  - Volltext oder Link zur Beschlussvorlage (HTML/PDF)
- Speicherung in einer strukturierten Ordnerhierarchie:

