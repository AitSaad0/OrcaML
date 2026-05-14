"""
run_service.py — Logique métier pour la création et la gestion des runs.

Ce module contient :
  - _sample_hyperparameters() : échantillonnage Random Search (Bergstra & Bengio)
  - RunService                : toutes les opérations CRUD + orchestration Celery

Flux général d'un run :
    RunService.create_batch_runs() / create_auto_runs()
        → valider la compatibilité algo / task_type (is_regression_algorithm)
        → valider les HP
        → créer Run + TrainingConfig en base (flush avant commit)
        → soumettre train_iris_run.delay() à Celery
        → stocker celery_task_id sur le Run
        → commit + refresh
"""
import logging
import uuid
import numpy as np
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from src.config.celery import celery
from src.environment.models.Environment import Environment
from src.environment.models.Task_type import TaskType
from src.runs.models.run import Algorithm, HP_BOUNDS, Run, RunStatus, TrainingConfig
from src.runs.schemas.run import AutoRunCreate, BatchRunCreate, MAX_MANUAL_ATTEMPTS_PER_ALGO

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_hyperparameters(algorithm: Algorithm, n_iter: int, random_state: int) -> list[dict]:
    """Génère n_iter combinaisons d'hyperparamètres par échantillonnage aléatoire.

    Implémente le vrai Random Search (Bergstra & Bengio, 2012) : chaque HP
    est tiré indépendamment depuis sa propre distribution, ce qui est plus
    efficace qu'une grille exhaustive pour les espaces de haute dimension.

    Distributions supportées (définies dans HP_BOUNDS) :
        "int"       → randint(min, max)  — borne max incluse
        "float"     → uniform(min, max)
        "log_float" → exp(uniform(log(min), log(max)))
                      Utilisé pour C, learning_rate : donne une couverture
                      uniforme sur l'échelle logarithmique.
        "choice"    → choix aléatoire parmi une liste de valeurs discrètes

    Si l'algorithme n'a pas de bornes définies dans HP_BOUNDS (ex. algo simple),
    retourne une liste avec les hyperparamètres par défaut comme unique combinaison.

    Args:
        algorithm:    L'algorithme pour lequel générer les combinaisons.
        n_iter:       Nombre de combinaisons à générer (min=5, max=50).
        random_state: Graine pour la reproductibilité des tirages.

    Returns:
        Liste de n_iter dicts { nom_param: valeur }.
    """
    rng    = np.random.RandomState(random_state)
    bounds = HP_BOUNDS.get(algorithm, {})

    # Algorithme sans bornes définies → une seule combinaison avec les défauts
    if not bounds:
        return [TrainingConfig.get_default_hyperparameters(algorithm)]

    combinations = []
    for _ in range(n_iter):
        hp = {}
        for param, meta in bounds.items():
            if meta["type"] == "int":
                # +1 pour que max soit inclus (randint est exclusif côté droit)
                hp[param] = int(rng.randint(meta["min"], meta["max"] + 1))

            elif meta["type"] == "float":
                hp[param] = float(round(rng.uniform(meta["min"], meta["max"]), 4))

            elif meta["type"] == "log_float":
                # Échantillonnage uniforme dans l'espace log puis retour en espace linéaire
                log_val = rng.uniform(np.log(meta["min"]), np.log(meta["max"]))
                hp[param] = float(round(np.exp(log_val), 4))

            elif meta["type"] == "choice":
                # rng.choice() peut retourner un np.str_ → .tolist() pour convertir en str Python
                hp[param] = rng.choice(meta["values"]).tolist() if hasattr(
                    rng.choice(meta["values"]), "tolist"
                ) else meta["values"][rng.randint(0, len(meta["values"]))]

        combinations.append(hp)

    return combinations


def _check_task_type_compatibility(algorithm: Algorithm, environment_id: UUID, db: Session):
    """Vérifie que l'algorithme est compatible avec le task_type de l'environment.

    Utilise TrainingConfig.is_regression_algorithm() pour détecter les algorithmes
    de régression pure (ex. LINEAR_REGRESSION) et rejeter leur utilisation dans
    un environment de classification.

    Note : XGBOOST n'est pas bloqué car il supporte les deux modes
    (XGBClassifier / XGBRegressor selon task_type dans run_tasks.py).

    Args:
        algorithm:      L'algorithme à valider.
        environment_id: UUID de l'environment cible.
        db:             Session SQLAlchemy active.

    Raises:
        ValueError: Si l'algorithme est de régression pure et l'environment est CLASSIFICATION.
    """
    if not TrainingConfig.is_regression_algorithm(algorithm):
        return  # Algorithme compatible avec les deux modes → pas de vérification nécessaire

    environment = db.execute(
        select(Environment).where(Environment.id == environment_id)
    ).scalar_one_or_none()

    if environment and environment.task_type == TaskType.CLASSIFICATION:
        raise ValueError(
            f"{algorithm.value} est un algorithme de régression pure "
            f"et ne peut pas être utilisé dans un environment de classification."
        )


# ---------------------------------------------------------------------------
# Service principal
# ---------------------------------------------------------------------------

class RunService:
    """Service métier pour les opérations sur les runs d'entraînement.

    Toutes les méthodes sont statiques : pas d'état interne, la session DB
    est toujours injectée en paramètre.
    """

    # ─── Batch (1 ou plusieurs algos) ─────────────────────────────────────

    @staticmethod
    def create_batch_runs(environment_id: UUID, body: BatchRunCreate, db: Session) -> list[Run]:
        """Crée un run manuel pour chaque algorithme demandé.

        Pattern de commit par run : flush → soumettre à Celery → commit.
        Ce pattern évite de perdre des celery_task_id si le commit global échoue,
        et permet de retourner les runs créés avec succès même si certains échouent.

        En cas d'échec partiel :
        - Les runs valides sont retournés normalement.
        - Les erreurs sont loggées mais ne font pas échouer toute la requête.
        - Si AUCUN run n'est créé, une ValueError est levée (→ HTTP 400).

        Args:
            environment_id: UUID de l'environnement cible.
            body:           Corps de la requête (algorithmes, HP, config training).
            db:             Session SQLAlchemy active.

        Returns:
            Liste des Run créés avec succès (peut être < len(body.algorithms)).

        Raises:
            ValueError: Si aucun run n'a pu être créé.
        """
        runs:   list[Run] = []
        errors: list[str] = []

        # Import local pour éviter les imports circulaires entre service et tasks
        from src.runs.tasks.run_tasks import train_iris_run

        for algorithm in body.algorithms:
            try:
                # 1. Vérifier la limite de tentatives manuelles pour cet algo
                RunService._check_attempts(environment_id, algorithm, db)

                # 2. Vérifier la compatibilité algo / task_type
                # Ex: LINEAR_REGRESSION interdit dans un environment CLASSIFICATION
                _check_task_type_compatibility(algorithm, environment_id, db)

                # 3. Résoudre les HP : custom fournis → validation, sinon défauts
                hp = {}
                if body.hyperparameters and algorithm.value in body.hyperparameters:
                    hp = body.hyperparameters[algorithm.value]
                    RunService._validate_hyperparameters(algorithm, hp)
                else:
                    hp = TrainingConfig.get_default_hyperparameters(algorithm)

                # 4. Créer le Run en base
                run = Run(
                    id=uuid.uuid4(),
                    environment_id=environment_id,
                    algorithm=algorithm,
                    status=RunStatus.PENDING,
                    is_manual=True,
                    created_at=datetime.now(timezone.utc),
                )

                # 5. Créer la TrainingConfig associée (relation 1-to-1)
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
                # flush() : envoie les INSERTs sans committer — nécessaire pour avoir
                # run.id disponible avant de soumettre la tâche Celery
                db.flush()

                # 6. Soumettre la tâche Celery et stocker son ID pour pouvoir l'annuler
                task = train_iris_run.delay(str(run.id))
                run.celery_task_id = task.id

                # 7. Commit définitif : le run est maintenant visible par le worker
                db.commit()
                db.refresh(run)
                runs.append(run)
                logger.info(f"Run {algorithm.value} créé avec succès.")

            except ValueError as ve:
                # Erreur de validation métier (limite atteinte, HP invalides, algo incompatible…)
                db.rollback()
                errors.append(f"{algorithm.value}: {str(ve)}")
                logger.warning(f"Validation échouée pour {algorithm.value}: {ve}")

            except Exception as e:
                # Erreur inattendue (Celery indisponible, DB, etc.)
                db.rollback()
                errors.append(f"{algorithm.value}: service de calcul indisponible")
                logger.error(f"Erreur Celery pour {algorithm.value}: {e}")

        # Échec total : rien n'a été créé
        if not runs:
            raise ValueError(f"Aucun run créé. Erreurs : {'; '.join(errors)}")

        # Échec partiel : on continue avec les runs valides
        if errors:
            logger.warning(f"Runs partiellement créés. Échecs : {errors}")

        return runs

    # ─── Random Search automatique ────────────────────────────────────────

    @staticmethod
    def create_auto_runs(environment_id: UUID, body: AutoRunCreate, db: Session) -> list[Run]:
        """Lance un Random Search pour chaque algorithme demandé.

        Pour chaque algorithme, génère body.n_iter combinaisons d'HP via
        _sample_hyperparameters(), puis crée un Run par combinaison.

        Différences avec create_batch_runs() :
        - is_manual=False → pas soumis à MAX_MANUAL_ATTEMPTS_PER_ALGO.
        - Pas de validation HP (les valeurs sont générées dans les bornes).
        - Un échec sur une combinaison n'interrompt pas les autres.

        Args:
            environment_id: UUID de l'environnement cible.
            body:           Corps de la requête (algorithmes, n_iter, config training).
            db:             Session SQLAlchemy active.

        Returns:
            Liste des Run créés avec succès.

        Raises:
            ValueError: Si aucun run n'a pu être créé.
        """
        runs:   list[Run] = []
        errors: list[str] = []

        from src.runs.tasks.run_tasks import train_iris_run

        for algorithm in body.algorithms:
            try:
                # Vérifier la compatibilité algo / task_type avant de générer les combinaisons
                # Évite de créer n_iter runs pour un algo incompatible
                _check_task_type_compatibility(algorithm, environment_id, db)
            except ValueError as ve:
                errors.append(f"{algorithm.value}: {str(ve)}")
                logger.warning(f"Algo incompatible ignoré pour Random Search : {ve}")
                continue

            # Générer toutes les combinaisons HP pour cet algorithme
            combinations = _sample_hyperparameters(
                algorithm=algorithm,
                n_iter=body.n_iter,
                random_state=body.random_state or 42,
            )

            logger.info(f"Random Search {algorithm.value} → {len(combinations)} combinaisons")

            for hp in combinations:
                try:
                    run = Run(
                        id=uuid.uuid4(),
                        environment_id=environment_id,
                        algorithm=algorithm,
                        status=RunStatus.PENDING,
                        is_manual=False,  # ← Marque le run comme automatique
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
                    logger.info(f"Random Search run {algorithm.value} {hp} créé.")

                except Exception as e:
                    db.rollback()
                    errors.append(f"{algorithm.value} {hp}: service indisponible")
                    logger.error(f"Erreur Random Search {algorithm.value} {hp}: {e}")

        if not runs:
            raise ValueError(f"Aucun run créé. Erreurs : {'; '.join(errors)}")

        if errors:
            logger.warning(f"Random Search partiel. Échecs : {errors}")

        return runs

    # ─── Validation des hyperparamètres ───────────────────────────────────

    @staticmethod
    def _validate_hyperparameters(algorithm: Algorithm, hp: dict):
        """Valide que les hyperparamètres fournis respectent les bornes de HP_BOUNDS.

        Deux types de vérifications :
        - Paramètre inconnu → rejeté (protection contre les typos ou HP non supportés).
        - Valeur hors bornes (min/max ou values) → rejeté avec message explicite.

        Les HP non fournis ne sont pas vérifiés (ils seront complétés par les défauts
        dans create_batch_runs si nécessaire).

        Args:
            algorithm: L'algorithme cible.
            hp:        Dict des HP à valider { nom_param: valeur }.

        Raises:
            ValueError: Si un paramètre est inconnu ou sa valeur hors bornes.
        """
        bounds = HP_BOUNDS.get(algorithm, {})

        for param, value in hp.items():
            if param not in bounds:
                raise ValueError(
                    f"Hyperparamètre '{param}' non reconnu pour {algorithm.value}. "
                    f"Paramètres autorisés : {list(bounds.keys())}"
                )

            bound = bounds[param]

            # Vérification numérique (int, float, log_float)
            if "min" in bound and "max" in bound:
                if not (bound["min"] <= value <= bound["max"]):
                    raise ValueError(
                        f"{param} doit être entre {bound['min']} et {bound['max']}. "
                        f"Valeur reçue : {value}"
                    )

            # Vérification énumérative (choice)
            if "values" in bound:
                if value not in bound["values"]:
                    raise ValueError(
                        f"{param} doit être parmi {bound['values']}. "
                        f"Valeur reçue : {value}"
                    )

    # ─── Vérification de la limite de tentatives ──────────────────────────

    @staticmethod
    def _check_attempts(environment_id: UUID, algorithm: Algorithm, db: Session):
        """Vérifie que la limite de runs manuels n'est pas atteinte pour un algo.

        Compte les runs manuels actifs (PENDING, RUNNING, COMPLETED) pour
        l'algorithme dans l'environnement. Les runs FAILED et CANCELLED ne
        sont pas comptés, laissant la possibilité de réessayer après un échec.

        Args:
            environment_id: UUID de l'environnement.
            algorithm:      Algorithme à vérifier.
            db:             Session SQLAlchemy active.

        Raises:
            ValueError: Si le nombre de runs manuels >= MAX_MANUAL_ATTEMPTS_PER_ALGO.
        """
        count = db.query(Run).filter(
            Run.environment_id == environment_id,
            Run.algorithm == algorithm,
            Run.is_manual.is_(True),
            # FAILED et CANCELLED exclus : on peut réessayer après un échec
            Run.status.in_([
                RunStatus.PENDING,
                RunStatus.RUNNING,
                RunStatus.COMPLETED,
            ]),
        ).count()

        if count >= MAX_MANUAL_ATTEMPTS_PER_ALGO:
            raise ValueError(
                f"Limite de {MAX_MANUAL_ATTEMPTS_PER_ALGO} tentatives atteinte "
                f"pour {algorithm.value}."
            )

    # ─── Annulation d'un run ──────────────────────────────────────────────

    @staticmethod
    def cancel_run(run_id: UUID, db: Session) -> Run:
        """Annule un run en révoquant sa tâche Celery et en mettant à jour le statut.

        L'annulation Celery est faite avec terminate=True pour tuer le worker
        immédiatement si la tâche est déjà en cours (SIGTERM envoyé au processus).
        Si la révocation Celery échoue (broker indisponible), le statut est quand même
        mis à CANCELLED en base : le worker orphelin terminera sans écrire ses métriques.

        Args:
            run_id: UUID du run à annuler.
            db:     Session SQLAlchemy active.

        Returns:
            Le Run mis à jour avec status=CANCELLED.

        Raises:
            ValueError: Si le run n'existe pas ou n'est pas annulable.
        """
        run = RunService.get_run(run_id, db)
        if not run:
            raise ValueError(f"Le Run {run_id} n'existe pas.")

        if run.status not in [RunStatus.PENDING, RunStatus.RUNNING]:
            raise ValueError(f"Impossible d'annuler un run déjà {run.status.value}.")

        if run.celery_task_id:
            try:
                # terminate=True : envoie SIGTERM si la tâche est en cours d'exécution
                celery.control.revoke(run.celery_task_id, terminate=True)
                logger.info(f"Task Celery {run.celery_task_id} révoquée.")
            except Exception as e:
                # Non bloquant : on continue et on met à jour la DB quand même
                logger.warning(f"Échec révocation Celery pour {run_id}: {e}")

        run.status      = RunStatus.CANCELLED
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        logger.info(f"Run {run_id} annulé.")
        return run

    # ─── Lecture ──────────────────────────────────────────────────────────

    @staticmethod
    def get_runs(environment_id: UUID, db: Session) -> list[Run]:
        """Retourne tous les runs d'un environnement, triés par date de création desc.

        Charge training_config en eager loading (selectinload) pour éviter
        les requêtes N+1 lors de la sérialisation Pydantic de la liste.
        """
        result = db.execute(
            select(Run)
            .options(selectinload(Run.training_config))
            .where(Run.environment_id == environment_id)
            .order_by(Run.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    def get_run(run_id: UUID, db: Session) -> Run | None:
        """Retourne un run par son ID, avec sa training_config chargée.

        Returns:
            Le Run si trouvé, None sinon.
        """
        result = db.execute(
            select(Run)
            .options(selectinload(Run.training_config))
            .where(Run.id == run_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def get_best_auto_run(environment_id: UUID, db: Session) -> Run | None:
        """Retourne le meilleur run automatique complété.

        Stratégie : tente d'abord classification (f1_score desc),
        puis fallback régression (r2 desc) si aucun run de classification trouvé.
        Couvre ainsi les deux task_type sans changer la signature ni les schemas.
        """
        # Tentative classification
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
        ).scalar_one_or_none()

        if result:
            return result

        # Fallback régression
        return db.execute(
            select(Run)
            .options(selectinload(Run.training_config))
            .where(
                Run.environment_id == environment_id,
                Run.status == RunStatus.COMPLETED,
                Run.is_manual.is_(False),
                Run.r2.is_not(None),
            )
            .order_by(Run.r2.desc())
            .limit(1)
        ).scalar_one_or_none()

    @staticmethod
    def get_best_manual_run(environment_id: UUID, db: Session) -> Run | None:
        """Retourne le meilleur run manuel complété.

        Même stratégie que get_best_auto_run() :
        classification (f1_score) en priorité, régression (r2) en fallback.
        """
        # Tentative classification
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
        ).scalar_one_or_none()

        if result:
            return result

        # Fallback régression
        return db.execute(
            select(Run)
            .options(selectinload(Run.training_config))
            .where(
                Run.environment_id == environment_id,
                Run.status == RunStatus.COMPLETED,
                Run.is_manual.is_(True),
                Run.r2.is_not(None),
            )
            .order_by(Run.r2.desc())
            .limit(1)
        ).scalar_one_or_none()