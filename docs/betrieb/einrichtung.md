# Einrichtung und Start

[Dokumentation](../README.md)

Voraussetzungen sind Python (empfohlen 3.14), pip und Git. Unter Windows die virtuelle Umgebung `.venv`, unter WSL `.venv-wsl` verwenden. Falls `python` fehlt, `python3` beziehungsweise `.venv-wsl/bin/python` nutzen. Tkinter ist für die Weboberfläche nicht erforderlich.

Aus dem Repository-Stamm in der aktivierten Umgebung:

```bash
pip install -r requirements.txt
python web/manage.py migrate
python scripts/run_web.py
```

Danach ist die lokale Entwicklungsoberfläche unter `http://127.0.0.1:8000/` erreichbar. Öffentliche Bereiche sind ohne Anmeldung nutzbar. Für die RI-Datenpflege zuerst ein lokales Webkonto gemäß [RI-Webanleitung](../ri/oberflaeche.md) einrichten. Für Daten und Suchmodelle folgen [Datenabruf](../datenabruf/README.md) und [Indexaufbau](../suche/indizes.md). Der [RI-Zugang](../ri/zugang.md) wird separat pro System eingerichtet.
