class ConversationCache:
    """Short-term memory cache for recent agent messages."""

    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages
        self._cache: dict[str, list[dict]] = {}

    def add_message(self, user_id: str, sender: str, body: str):
        if user_id not in self._cache:
            self._cache[user_id] = []
        self._cache[user_id].append({"sender": sender, "body": body})
        if len(self._cache[user_id]) > self.max_messages:
            self._cache[user_id].pop(0)

    def get_recent(self, user_id: str) -> list[dict]:
        return self._cache.get(user_id, [])


conversation_cache = ConversationCache()
