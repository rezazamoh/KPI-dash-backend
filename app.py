from fastapi import FastAPI
from api.gerrit import router as gerrit_router
from api.jira import router as jira_router
app = FastAPI()



@app.get("/")
def root():
    return {"message": "Server is up and running. See /docs for API documentation."}

app.include_router(gerrit_router)
app.include_router(jira_router)