from celery import Celery
# Import de l'objet settings pour une configuration centralisée et fiable
from src.config.config import settings 

celery = Celery(
    "orcaml",
    # Utilisation des variables chargées depuis le .env via Pydantic/Settings
    broker=settings.CELERY_BROKER_URL, 
    backend=settings.CELERY_RESULT_BACKEND,
    # Indique à Celery où trouver les définitions des tâches
    include=["src.runs.tasks.run_tasks"], 
)

celery.conf.update(
    task_track_started=True,  # Permet de suivre l'état "STARTED"
    result_expires=3600,      # Supprime les résultats de Redis après 1h
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Recommandé pour éviter les décalages horaires dans les logs
    timezone="UTC",
    enable_utc=True,
)