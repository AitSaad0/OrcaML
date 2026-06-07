from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import logging

from src.auth.routers.auth import router as auth_router
from src.auth.routers.users import router as users_router
from src.project.routers.project import router as projects_router
from src.environment.routes.environment_routes import router as environments_router
from src.runs.routers.run import router as runs_router
from src.dataset.routers.dataset import router as dataset_router
from src.deployments.routers.deployment_routes import router as deployments_router
from src.dataset.routers.cleaning import router as cleaning_router

from src.models import *  # noqa: F401, F403

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(title="OrcaML")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://16.170.57.181:3000",
        "http://16.170.57.181",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(runs_router)
app.include_router(environments_router)
app.include_router(dataset_router)
app.include_router(deployments_router)
app.include_router(cleaning_router)

@app.get("/health")
def health():
    return {"status": "running"}

@app.get("/")
def root():
    return {"status": "running"}