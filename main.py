from fastapi import FastAPI
#from auth.routers.auth import router as auth_router
#from auth.routers.users import router as users_router

app = FastAPI(title="OrcaML")

#app.include_router(auth_router)
#app.include_router(users_router)


@app.get("/")
def root():
    return {"status": "running"}
