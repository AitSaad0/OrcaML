from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session , joinedload
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
)
from src.runs.services.run_service import RunService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/environments/{environment_id}/runs",
    tags=["Runs"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Non autorisé"},
        status.HTTP_403_FORBIDDEN: {"description": "Accès refusé"},
        status.HTTP_404_NOT_FOUND: {"description": "Run non trouvé"},
    },
)

# Vérifie que l'environnement existe et appartient à l'utilisateur connecté.
def check_environment(environment_id: UUID, current_user, db: Session):
    """Vérifie que l'environnement existe et appartient à l'user"""
    env = (
        db.query(Environment)
        .options(joinedload(Environment.project))
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
# Crée un batch de runs manuels pour plusieurs algorithmes , et fait commit en base après chaque création pour éviter les problèmes de verrouillage en cas de nombreuses combinaisons.
@router.post("/batch", response_model=BatchRunResponse, status_code=status.HTTP_201_CREATED)
def create_batch_runs(
    environment_id: UUID,
    body: BatchRunCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_environment(environment_id, current_user, db)
    try:
        runs = RunService.create_batch_runs(environment_id, body, db)
        total = len(runs)
        requested = len(body.algorithms)
        
        if total < requested:
            msg = f"{total}/{requested} run(s) lancé(s) — certains ont échoué ⚠️"
        else:
            msg = f"{total} run(s) lancé(s) en parallèle ✅"

        return {"runs": runs, "total": total, "message": msg}

    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Erreur batch runs : {e}")        
        raise HTTPException(status_code=500, detail="Erreur interne.")
# Lance un Grid Search automatique sur les algorithmes demandés.
@router.post(
    "/auto",
    response_model=BatchRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grid Search — Optimisation automatique des HP",
    description="""
    Teste automatiquement toutes les combinaisons d'hyperparamètres.
    Aucune limite de tentatives car le système contrôle les combinaisons.
    """,
)
def create_auto_runs(
    environment_id: UUID,
    body: AutoRunCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_environment(environment_id, current_user, db)
    try:
        runs = RunService.create_auto_runs(environment_id, body, db)
        return {
            "runs": runs,
            "total": len(runs),
            "message": f"Grid Search : {len(runs)} combinaisons testées automatiquement ✅",
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Erreur Grid Search : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne.",
        )

# Liste tous les runs d'un environnement.
@router.get(
    "",
    response_model=list[RunListResponse],
    summary="Lister tous les runs",
)
def list_runs(
    environment_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_environment(environment_id, current_user, db)
    return RunService.get_runs(environment_id, db)

# Retourne le meilleur run automatique complété.
@router.get(
    "/best-auto",
    response_model=BestAutoRunResponse,
    summary="Retourner le meilleur run automatique (F1 score max)",
)
def get_best_auto_run(
    environment_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_environment(environment_id, current_user, db)

    best = RunService.get_best_auto_run(environment_id, db)
    if not best:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun run automatique complété dans cet environnement.",
        )
    return best

# Retourne le meilleur run manuel complété.
@router.get(
    "/best-manual",
    response_model=BestAutoRunResponse,
    summary="Retourner le meilleur run manuel (F1 score max)",
)
def get_best_manual_run(
    environment_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_environment(environment_id, current_user, db)

    best = RunService.get_best_manual_run(environment_id, db)
    if not best:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun run manuel complété dans cet environnement.",
        )
    return best

# Retourne un run précis à partir de son identifiant.
@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    environment_id: UUID,
    run_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

    return run

# Annule un run en cours d'exécution ou en attente.
@router.post(
    "/{run_id}/cancel",
    response_model=CancelRunResponse,
    summary="Annuler un run en cours",
)
def cancel_run(
    environment_id: UUID,
    run_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

    if run.status not in [RunStatus.PENDING, RunStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible d'annuler un run déjà {run.status.value}.",
        )

    try:
        updated_run = RunService.cancel_run(run_id, db)
        return {
            "id": updated_run.id,
            "status": updated_run.status,
            "message": f"Le run {run_id} a été annulé avec succès.",
        }
    except Exception as e:
        logger.error(f"Échec annulation pour run {run_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Échec de la communication avec le service d'exécution.",
        )