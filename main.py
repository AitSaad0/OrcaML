from fastapi import FastAPI
from src.auth.routers.auth import router as auth_router
from src.auth.routers.users import router as users_router
from src.project.routers.project import router as projects_router
from src.environment.routes.environment_routes import router as environments_router
from src.runs.routers.run import router as runs_router
from src.dataset.routers.dataset import router as dataset_router

import src.project.models.project  # noqa: F401
import src.environment.models.Environment  # noqa: F401
import src.auth.models.user  # noqa: F401
import src.runs.models.run  # noqa: F401

app = FastAPI(title="OrcaML")

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(runs_router)
app.include_router(environments_router)
app.include_router(dataset_router)

@app.get("/health")
def health():
    return {"status": "running"}

@app.get("/")
def root():
    return {"status": "running"}