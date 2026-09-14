from pathlib import Path


class VectorstoreProvisioner:
    """Provisions an isolated vector store for tenant company knowledge."""

    def __init__(self, base_path: str = "vectorstores"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def get_tenant_store_path(self, org_id: str) -> Path:
        store_path = self.base_path / f"org_{org_id}"
        store_path.mkdir(parents=True, exist_ok=True)
        return store_path


vectorstore_provisioner = VectorstoreProvisioner()
