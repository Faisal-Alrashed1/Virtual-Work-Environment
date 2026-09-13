from fastapi import Depends, HTTPException
from app.auth.roles import SystemRole
from app.core.security import current_user
from app.models.domain import User


def require_role(*allowed_roles: str):
    def role_checker(user: User = Depends(current_user)) -> User:
        user_role = user.role.value if hasattr(user.role, "value") else str(user.role)
        if user_role not in allowed_roles:
            raise HTTPException(403, "ليس لديك صلاحية للوصول لهذا المورد")
        return user
    return role_checker


require_trainee = require_role(SystemRole.TRAINEE.value, SystemRole.CANDIDATE.value)
require_company_admin = require_role(SystemRole.COMPANY_ADMIN.value)
