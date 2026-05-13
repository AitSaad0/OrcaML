"""
run_router.py — Endpoints REST pour la gestion des runs d'entraînement.

Toutes les routes sont préfixées par /environments/{environment_id}/runs.
Chaque requête vérifie d'abord que l'environnement existe et appartient
à l'utilisateur connecté via check_environment().

Routes exposées :
    POST   /batch               → Lancer un batch de runs manuels
    POST   /auto                → Lancer un Random Search automatique
    GET    /                    → Lister tous les runs
    GET    /best-auto           → Meilleur run automatique (F1 max)
    GET    /best-manual         → Meilleur run manuel (F1 max)
    GET    /{run_id}            → Détail d'un run
    POST   /{run_id}/cancel     → Annuler un run PENDING ou RUNNING
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
import logging

from src.auth.dependencies.auth import get_current_user
from src.config.db import get_db
from src.environment.models.Environment import Environment
from src.runs.models.run import RunStatus
from src.runs.schemas.run import (
    AutoRunCreate,
    BatchRunCreate,
    BatchRunResponse,
    BestAutoRunResponse,
    CancelRunResponse,
    RunListResponse,
    RunResponse,
    RunPredictRequest,     
    RunPredictResponse,    
)
from src.runs.services.run_service import RunService
from src.runs.services import predict_service 

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/environments/{environment_id}/runs",
    tags=["Runs"],
    # Réponses d'erreur communes documentées dans le Swagger pour toutes les routes
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Non autorisé"},
        status.HTTP_403_FORBIDDEN:    {"description": "Accès refusé"},
        status.HTTP_404_NOT_FOUND:    {"description": "Run non trouvé"},
    },
)


# ---------------------------------------------------------------------------
# Guard — vérification de l'environnement
# ---------------------------------------------------------------------------

def check_environment(environment_id: UUID, current_user, db: Session) -> Environment:
    """Vérifie que l'environnement existe et appartient à l'utilisateur connecté.

    Appelée en tête de chaque endpoint pour s'assurer que l'utilisateur
    ne peut pas accéder aux runs d'un environnement qui ne lui appartient pas.

    Le projet parent est chargé en eager loading (joinedload) pour éviter
    une requête SQL supplémentaire lors de la vérification du user_id.

    Args:
        environment_id: UUID de l'environnement ciblé.
        current_user:   Utilisateur authentifié (injecté par get_current_user).
        db:             Session SQLAlchemy active.

    Returns:
        L'objet Environment si valide.

    Raises:
        HTTPException 404: Si l'environnement n'existe pas en base.
        HTTPException 403: Si l'environnement appartient à un autre utilisateur.
    """
    env = (
        db.query(Environment)
        .options(joinedload(Environment.project))  # Charge project en une seule requête
        .filter(Environment.id == environment_id)
        .first()
    )

    if not env:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Environnement introuvable.",
        )

    if env.project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas accès à cet environnement.",
        )

    return env


# ---------------------------------------------------------------------------
# POST /batch — Batch de runs manuels
# ---------------------------------------------------------------------------

@router.post("/batch", response_model=BatchRunResponse, status_code=status.HTTP_201_CREATED)
def create_batch_runs(
    environment_id: UUID,
    body: BatchRunCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crée un batch de runs manuels pour les algorithmes demandés.

    Chaque algorithme génère un Run indépendant soumis à Celery en parallèle.
    La limite MAX_ALGORITHMS_PER_BATCH (6) et MAX_MANUAL_ATTEMPTS_PER_ALGO (5)
    sont vérifiées dans RunService.create_batch_runs().

    La réponse indique combien de runs ont effectivement été lancés :
    certains peuvent être rejetés (ex. limite d'essais dépassée) sans
    faire échouer toute la requête.
    """
    check_environment(environment_id, current_user, db)
    try:
        runs = RunService.create_batch_runs(environment_id, body, db)
        total     = len(runs)
        requested = len(body.algorithms)

        # Message d'avertissement si des runs ont été ignorés
        if total < requested:
            msg = f"{total}/{requested} run(s) lancé(s) — certains ont échoué ⚠️"
        else:
            msg = f"{total} run(s) lancé(s) en parallèle ✅"

        return {"runs": runs, "total": total, "message": msg}

    except ValueError as ve:
        # Erreurs métier : trop d'algos, HP invalides, limite atteinte…
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Erreur batch runs : {e}")
        raise HTTPException(status_code=500, detail="Erreur interne.")


# ---------------------------------------------------------------------------
# POST /auto — Random Search automatique
# ---------------------------------------------------------------------------

@router.post(
    "/auto",
    response_model=BatchRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Random Search — Optimisation automatique des HP",
    description="""
    Échantillonne aléatoirement des combinaisons d'hyperparamètres (Bergstra & Bengio, 2012).
    Pas de limite de tentatives : le système contrôle entièrement les combinaisons générées.
    Le nombre d'itérations est contrôlé par `n_iter` (défaut=10, min=5, max=50).
    """,
)
def create_auto_runs(
    environment_id: UUID,
    body: AutoRunCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lance un Random Search sur les algorithmes spécifiés.

    Contrairement au batch manuel, les runs auto ne sont pas soumis à la
    limite MAX_MANUAL_ATTEMPTS_PER_ALGO et ont is_manual=False en base.
    Utiliser GET /best-auto pour récupérer le meilleur résultat.
    """
    check_environment(environment_id, current_user, db)
    try:
        runs = RunService.create_auto_runs(environment_id, body, db)
        return {
            "runs": runs,
            "total": len(runs),
            "message": f"Random Search : {len(runs)} combinaisons testées automatiquement ✅",
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Erreur Random Search : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne.",
        )


# ---------------------------------------------------------------------------
# GET / — Liste des runs
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=list[RunListResponse],
    summary="Lister tous les runs d'un environnement",
)
def list_runs(
    environment_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retourne tous les runs (manuels et auto) liés à l'environnement,
    quel que soit leur statut (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED).
    """
    check_environment(environment_id, current_user, db)
    return RunService.get_runs(environment_id, db)


# ---------------------------------------------------------------------------
# GET /best-auto — Meilleur run automatique
# ---------------------------------------------------------------------------

@router.get(
    "/best-auto",
    response_model=BestAutoRunResponse,
    summary="Meilleur run automatique (F1 score max)",
)
def get_best_auto_run(
    environment_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retourne le run automatique complété avec le F1 score le plus élevé.

    ⚠️  Pour les environnements de régression, f1_score est null :
    cette route retournera 404 tant que le tri par métrique de régression
    n'est pas implémenté (voir Phase 4 — open questions).
    """
    check_environment(environment_id, current_user, db)

    best = RunService.get_best_auto_run(environment_id, db)
    if not best:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun run automatique complété dans cet environnement.",
        )
    return best


# ---------------------------------------------------------------------------
# GET /best-manual — Meilleur run manuel
# ---------------------------------------------------------------------------

@router.get(
    "/best-manual",
    response_model=BestAutoRunResponse,
    summary="Meilleur run manuel (F1 score max)",
)
def get_best_manual_run(
    environment_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retourne le run manuel complété avec le F1 score le plus élevé.

    Même limitation que /best-auto pour les tâches de régression.
    """
    check_environment(environment_id, current_user, db)

    best = RunService.get_best_manual_run(environment_id, db)
    if not best:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun run manuel complété dans cet environnement.",
        )
    return best


# ---------------------------------------------------------------------------
# GET /{run_id} — Détail d'un run
# ---------------------------------------------------------------------------

@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    environment_id: UUID,
    run_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retourne le détail complet d'un run : statut, métriques, config, timestamps.

    La double vérification (existence + appartenance à l'env) empêche un
    utilisateur de sonder des run_id d'un autre environnement via cette route.
    """
    check_environment(environment_id, current_user, db)

    run = RunService.get_run(run_id, db)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run introuvable.",
        )

    # Sécurité : s'assurer que le run appartient bien à cet environnement
    if run.environment_id != environment_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce run n'appartient pas à cet environnement.",
        )

    return run


# ---------------------------------------------------------------------------
# POST /{run_id}/cancel — Annulation d'un run
# ---------------------------------------------------------------------------

@router.post(
    "/{run_id}/cancel",
    response_model=CancelRunResponse,
    summary="Annuler un run en cours ou en attente",
)
def cancel_run(
    environment_id: UUID,
    run_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Annule un run dont le statut est PENDING ou RUNNING.

    Seuls ces deux statuts sont annulables : un run COMPLETED, FAILED
    ou déjà CANCELLED ne peut plus être modifié.

    En interne, RunService.cancel_run() révoque la tâche Celery via
    celery_task_id puis passe le statut à CANCELLED en base.

    Raises:
        HTTPException 404: Run introuvable.
        HTTPException 403: Run appartenant à un autre environnement.
        HTTPException 400: Run déjà dans un statut terminal.
        HTTPException 500: Échec de communication avec le broker Celery.
    """
    check_environment(environment_id, current_user, db)

    run = RunService.get_run(run_id, db)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run introuvable.",
        )

    if run.environment_id != environment_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas l'autorisation d'annuler ce run.",
        )

    # Vérifie que le run est encore annulable
    if run.status not in [RunStatus.PENDING, RunStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible d'annuler un run déjà {run.status.value}.",
        )

    try:
        updated_run = RunService.cancel_run(run_id, db)
        return {
            "id":      updated_run.id,
            "status":  updated_run.status,
            "message": f"Le run {run_id} a été annulé avec succès.",
        }
    except Exception as e:
        logger.error(f"Échec annulation pour run {run_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Échec de la communication avec le service d'exécution.",
        )
    # ---------------------------------------------------------------------------
# POST /{run_id}/predict — Prédiction sans déploiement
# ---------------------------------------------------------------------------

@router.post(
    "/{run_id}/predict",
    response_model=RunPredictResponse,
    summary="Prédire depuis un run sans déploiement Docker",
)
def predict_from_run(
    environment_id: UUID,
    run_id:         UUID,
    body:           RunPredictRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Effectue une prédiction directement depuis le modèle MLflow.
    
    Contrairement à /deployments/.../predict, cette route :
      - Ne nécessite pas de container Docker actif
      - Applique automatiquement le même cleaning qu'à l'entraînement
      - Est plus lente (charge le .pkl à chaque appel)
    
    Raises:
        HTTPException 400: Run pas COMPLETED ou CleaningConfig manquante.
        HTTPException 403: Run appartenant à un autre environnement.
        HTTPException 404: Run introuvable.
        HTTPException 500: Erreur chargement modèle ou prédiction.
    """
    check_environment(environment_id, current_user, db)

    run = RunService.get_run(run_id, db)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run introuvable.",
        )

    if run.environment_id != environment_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce run n'appartient pas à cet environnement.",
        )

    try:
        result = predict_service.predict_from_run(
            run_id=run_id,
            features=body.features,
            db=db,
        )
    except ValueError as e:
        logger.warning(f"Predict rejeté pour run {run_id} : {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Predict échoué pour run {run_id} : {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    logger.info(f"Predict réussi — run_id={run_id}, result={result['prediction']}")
    return result