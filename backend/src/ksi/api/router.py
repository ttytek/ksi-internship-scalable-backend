from fastapi import APIRouter

from ksi.api.routes import health, ranking, submissions, tasks, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(tasks.router)
api_router.include_router(submissions.router)
api_router.include_router(ranking.router)
