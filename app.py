from fastapi import FastAPI
from api.developers import router as developers_router
app = FastAPI()



@app.get("/")
def root():
    return {"message": "Server is up and running. See /docs for API documentation."}

app.include_router(developers_router)
#app.include_router(team_router)