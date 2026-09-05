import logs
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from api.gerrit import router as gerrit_router
from api.jira import router as jira_router
from api.settings import router as settings_router

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
app.include_router(settings_router)

@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.perf_counter()

    response = await call_next(request)

    elapsed = time.perf_counter() - start

    print(
        f"{request.method} {request.url.path} "
        f"-> {response.status_code} "
        f"({elapsed:.3f}s)"
    )

    return response