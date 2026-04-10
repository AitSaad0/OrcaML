from fastapi import FastAPI
from src.auth.routers.auth import router as auth_router
from src.auth.routers.users import router as users_router
from src.project.routers.project import router as projects_router

app = FastAPI(title="OrcaML")

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(projects_router)



@app.get("/")
def root():
    return {"status": "running"}
