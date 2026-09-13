from enum import Enum


class SystemRole(str, Enum):
    TRAINEE = "learner"
    CANDIDATE = "candidate"
    COMPANY_ADMIN = "recruiter"
