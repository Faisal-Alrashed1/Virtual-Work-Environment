from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.db import Base


class TenantDBManager:
    """Manages separate isolated databases for each company tenant."""

    def __init__(self, base_dir: str = "tenants"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._engines = {}

    def get_tenant_db_url(self, org_id: str) -> str:
        db_path = self.base_dir / f"tenant_{org_id}.db"
        return f"sqlite:///{db_path}"

    def get_tenant_session(self, org_id: str):
        if org_id not in self._engines:
            db_url = self.get_tenant_db_url(org_id)
            engine = create_engine(db_url, connect_args={"check_same_thread": False})
            Base.metadata.create_all(bind=engine)
            self._engines[org_id] = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return self._engines[org_id]()


tenant_db_manager = TenantDBManager()
