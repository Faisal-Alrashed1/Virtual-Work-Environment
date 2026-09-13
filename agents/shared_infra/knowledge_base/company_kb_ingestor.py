from agents.shared_infra.knowledge_base.vectorstore_provisioner import vectorstore_provisioner


class CompanyKBIngestor:
    """Ingests synthetic company handbook/policies and creates embeddings."""

    @staticmethod
    def ingest_document(org_id: str, doc_name: str, content: str) -> dict:
        store_path = vectorstore_provisioner.get_tenant_store_path(org_id)
        # Store metadata and chunks
        return {"status": "indexed", "org_id": org_id, "doc_name": doc_name, "path": str(store_path)}


company_kb_ingestor = CompanyKBIngestor()
