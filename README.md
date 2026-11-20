# cpas-agent
## Site de démonstration

Le site permet de poser des questions à l'agent et présente le projet (corpus, résultats du benchmark).

```bash
pip install fastapi uvicorn pyyaml
uvicorn app:app --app-dir src --reload
```

Puis ouvrir http://127.0.0.1:8000. Il faut que l'index soit construit (`python src/index.py`) et que la clé `MISTRAL_API_KEY` soit dans le fichier `.env`.
