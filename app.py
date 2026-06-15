from fastapi import FastAPI
from api.developers import router as developers_router
from api.team import router as team_router
app = FastAPI()



@app.get("/")
def root():
    return {"message": "Dashboard Backend Running"}


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(developers_router)
app.include_router(team_router)