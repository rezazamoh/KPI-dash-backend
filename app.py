from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.gerrit import router as gerrit_router
from api.jira import router as jira_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/",)
def root():
    return {"message": "Server is up and running. See /docs for API documentation."}

app.include_router(gerrit_router)
app.include_router(jira_router)