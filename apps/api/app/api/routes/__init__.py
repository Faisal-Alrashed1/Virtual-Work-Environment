from fastapi import APIRouter
from app.api.routes.agents import router as agents_router
from app.api.routes.auth import router as auth_router
from app.api.routes.intake import router as intake_router
from app.api.routes.recruiter import router as recruiter_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.workspace import router as workspace_router

router = APIRouter(prefix="/api")

router.include_router(auth_router)
router.include_router(intake_router)
router.include_router(workspace_router)
router.include_router(agents_router)
router.include_router(tasks_router)
router.include_router(recruiter_router)
