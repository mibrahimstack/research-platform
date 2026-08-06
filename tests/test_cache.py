from api.cache import cache_key, get_json, set_json


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex):
        self.values[key] = value


def test_cache_keys_are_stable_for_equivalent_payloads():
    assert cache_key("search", {"query": "diabetes", "top_k": 5}) == cache_key(
        "search", {"top_k": 5, "query": "diabetes"}
    )


def test_json_cache_round_trip():
    client = FakeRedis()
    set_json(client, "key", {"answer": "cached"}, ttl_seconds=30)

    assert get_json(client, "key") == {"answer": "cached"}
