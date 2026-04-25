import logging
import uuid
from datetime import datetime, timezone
from itertools import product
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.config.celery import celery
from src.runs.models.run import Algorithm, HP_BOUNDS, Run, RunStatus, TrainingConfig
from src.runs.schemas.run import AutoRunCreate, BatchRunCreate, MAX_MANUAL_ATTEMPTS_PER_ALGO

logger = logging.getLogger(__name__)


class RunService:
    # ─── Batch (1 ou plusieurs algos) ─────────────────────────
    @staticmethod
    def create_batch_runs(environment_id: UUID, body: BatchRunCreate, db: Session) -> list[Run]:
        runs: list[Run] = []
        errors: list[str] = []

        from src.runs.tasks.run_tasks import train_iris_run

        for algorithm in body.algorithms:
            try:
                # 1. Vérifier la limite
                RunService._check_attempts(environment_id, algorithm, db)

                # 2. HP : custom ou defaults
                hp = {}
                if body.hyperparameters and algorithm.value in body.hyperparameters:
                    hp = body.hyperparameters[algorithm.value]
                    RunService._validate_hyperparameters(algorithm, hp)
                else:
                    hp = TrainingConfig.get_default_hyperparameters(algorithm)

                # 3. Créer le run
                run = Run(
                    id=uuid.uuid4(),
                    environment_id=environment_id,
                    algorithm=algorithm,
                    status=RunStatus.PENDING,
                    is_manual=True,
                    created_at=datetime.now(timezone.utc),
                )

                config = TrainingConfig(
                    id=uuid.uuid4(),
                    run_id=run.id,
                    algorithm=algorithm,
                    hyperparameters=hp,
                    test_size=body.test_size if body.test_size is not None else 0.2,
                    random_state=body.random_state if body.random_state is not None else 42,
                    cross_validation=body.cross_validation if body.cross_validation is not None else False,
                    cv_folds=body.cv_folds if body.cv_folds is not None else 5,
                    created_at=datetime.now(timezone.utc),
                )

                db.add(run)
                db.add(config)
                db.flush()

                # 4. Lancer Celery
                task = train_iris_run.delay(str(run.id))
                run.celery_task_id = task.id

                # 5. Commit individuel
                db.commit()
                db.refresh(run)
                runs.append(run)
                logger.info(f"Run {algorithm.value} créé avec succès.")

            except ValueError as ve:
                db.rollback()
                errors.append(f"{algorithm.value}: {str(ve)}")
                logger.warning(f"Validation échouée pour {algorithm.value}: {ve}")

            except Exception as e:
                db.rollback()
                errors.append(f"{algorithm.value}: service de calcul indisponible")
                logger.error(f"Erreur Celery pour {algorithm.value}: {e}")

        if not runs:
            raise ValueError(f"Aucun run créé. Erreurs : {'; '.join(errors)}")

        if errors:
            logger.warning(f"Runs partiellement créés. Échecs : {errors}")

        return runs

    # ─── Grid Search automatique ───────────────────────────────
    @staticmethod
    def create_auto_runs(environment_id: UUID, body: AutoRunCreate, db: Session) -> list[Run]:
        runs: list[Run] = []
        errors: list[str] = []

        from src.runs.tasks.run_tasks import train_iris_run

        for algorithm in body.algorithms:
            grid = TrainingConfig.get_hyperparameter_grid(algorithm)

            if not grid:
                combinations = [TrainingConfig.get_default_hyperparameters(algorithm)]
            else:
                keys = list(grid.keys())
                values = list(grid.values())
                combinations = [dict(zip(keys, combo)) for combo in product(*values)]

            logger.info(f"Grid Search {algorithm.value} → {len(combinations)} combinaisons")

            for hp in combinations:
                try:
                    run = Run(
                        id=uuid.uuid4(),
                        environment_id=environment_id,
                        algorithm=algorithm,
                        status=RunStatus.PENDING,
                        is_manual=False,
                        created_at=datetime.now(timezone.utc),
                    )

                    config = TrainingConfig(
                        id=uuid.uuid4(),
                        run_id=run.id,
                        algorithm=algorithm,
                        hyperparameters=hp,
                        test_size=body.test_size if body.test_size is not None else 0.2,
                        random_state=body.random_state if body.random_state is not None else 42,
                        cross_validation=body.cross_validation if body.cross_validation is not None else False,
                        cv_folds=body.cv_folds if body.cv_folds is not None else 5,
                        created_at=datetime.now(timezone.utc),
                    )

                    db.add(run)
                    db.add(config)
                    db.flush()

                    task = train_iris_run.delay(str(run.id))
                    run.celery_task_id = task.id

                    db.commit()
                    db.refresh(run)
                    runs.append(run)
                    logger.info(f"Auto run {algorithm.value} {hp} créé.")

                except Exception as e:
                    db.rollback()
                    errors.append(f"{algorithm.value} {hp}: service indisponible")
                    logger.error(f"Erreur Celery Grid Search {algorithm.value} {hp}: {e}")

        if not runs:
            raise ValueError(f"Aucun run créé. Erreurs : {'; '.join(errors)}")

        if errors:
            logger.warning(f"Grid Search partiel. Échecs : {errors}")

        return runs

    # ─── Validation des HP ────────────────────────────────────
    @staticmethod
    def _validate_hyperparameters(algorithm: Algorithm, hp: dict):
        
        #Valider que les HP fournis sont dans les intervalles autorisés.
        
        bounds = HP_BOUNDS.get(algorithm, {})

        for param, value in hp.items():
            if param not in bounds:
                raise ValueError(
                    f"Hyperparamètre '{param}' non reconnu pour {algorithm.value}. "
                    f"Paramètres autorisés : {list(bounds.keys())}"
                )

            bound = bounds[param]

            if "min" in bound and "max" in bound:
                if not (bound["min"] <= value <= bound["max"]):
                    raise ValueError(
                        f"{param} doit être entre {bound['min']} et {bound['max']}. "
                        f"Valeur reçue : {value}"
                    )

            if "values" in bound:
                if value not in bound["values"]:
                    raise ValueError(
                        f"{param} doit être parmi {bound['values']}. "
                        f"Valeur reçue : {value}"
                    )

    # ─── Limite de tentatives ─────────────────────────────────
    @staticmethod
    def _check_attempts(environment_id: UUID, algorithm: Algorithm, db: Session):
        count = db.query(Run).filter(
            Run.environment_id == environment_id,
            Run.algorithm == algorithm,
            Run.is_manual.is_(True),
            Run.status.in_([
                RunStatus.PENDING,
                RunStatus.RUNNING,
                RunStatus.COMPLETED,
            ]),
        ).count()

        if count >= MAX_MANUAL_ATTEMPTS_PER_ALGO:
            raise ValueError(
                f"Limite de {MAX_MANUAL_ATTEMPTS_PER_ALGO} tentatives atteinte "
                f"pour {algorithm.value}. "
                f"Utilisez le Grid Search → POST /runs/auto"
            )

    # ─── Annuler un run ───────────────────────────────────────
    @staticmethod
    def cancel_run(run_id: UUID, db: Session) -> Run:
        run = RunService.get_run(run_id, db)
        if not run:
            raise ValueError(f"Le Run {run_id} n'existe pas.")

        if run.status not in [RunStatus.PENDING, RunStatus.RUNNING]:
            raise ValueError(f"Impossible d'annuler un run déjà {run.status.value}.")

        if run.celery_task_id:
            try:
                celery.control.revoke(run.celery_task_id, terminate=True)
                logger.info(f"Task Celery {run.celery_task_id} révoquée.")
            except Exception as e:
                logger.warning(f"Échec révocation Celery pour {run_id}: {e}")

        run.status = RunStatus.CANCELLED
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        logger.info(f"Run {run_id} annulé.")
        return run

    # ─── Lister les runs ──────────────────────────────────────
    @staticmethod
    def get_runs(environment_id: UUID, db: Session) -> list[Run]:
        result = db.execute(
            select(Run)
            .options(selectinload(Run.training_config))
            .where(Run.environment_id == environment_id)
            .order_by(Run.created_at.desc())
        )
        return result.scalars().all()

    # ─── Récupérer un run ─────────────────────────────────────
    @staticmethod
    def get_run(run_id: UUID, db: Session) -> Run | None:
        result = db.execute(
            select(Run)
            .options(selectinload(Run.training_config))
            .where(Run.id == run_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def get_best_manual_run(environment_id: UUID, db: Session) -> Run | None:
        result = db.execute(
            select(Run)
            .options(selectinload(Run.training_config))
            .where(
                Run.environment_id == environment_id,
                Run.status == RunStatus.COMPLETED,
                Run.is_manual.is_(True),
                Run.f1_score.is_not(None),
            )
            .order_by(Run.f1_score.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def get_best_auto_run(environment_id: UUID, db: Session) -> Run | None:
        result = db.execute(
            select(Run)
            .options(selectinload(Run.training_config))
            .where(
                Run.environment_id == environment_id,
                Run.status == RunStatus.COMPLETED,
                Run.is_manual.is_(False),
                Run.f1_score.is_not(None),
            )
            .order_by(Run.f1_score.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()