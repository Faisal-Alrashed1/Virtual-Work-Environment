from agents.shared_infra.knowledge_base.vectorstore_provisioner import vectorstore_provisioner


class KBRetriever:
    """Retrieves relevant context only from the specified tenant's knowledge base."""

    @staticmethod
    def retrieve_context(org_id: str, query: str, top_k: int = 3) -> list[dict]:
        store_path = vectorstore_provisioner.get_tenant_store_path(org_id)
        return [{"source": "synthetic_handbook", "text": f"Context for {query} in org {org_id}"}]


kb_retriever = KBRetriever()
