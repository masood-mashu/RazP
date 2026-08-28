import json
import tempfile
import unittest
from pathlib import Path

from api.risk_api import RiskEngine


class RiskEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / "snapshot.json"
        path.write_text(json.dumps({"model":{"version":"test-v1"},"threshold":.5,"measured":{},"source":{},"alerts":[{"address":"actor-1","time_step":4,"score":.8,"band":"high","action":"Human review","model_version":"test-v1"}]}), encoding="utf-8")
        self.engine = RiskEngine(path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_health_and_alerts(self):
        self.assertEqual(self.engine.health()["status"], "ok")
        self.assertEqual(self.engine.list_alerts()["count"], 1)
        self.assertFalse(self.engine.ready()["ready"])

    def test_known_score_is_returned(self):
        self.assertEqual(self.engine.score({"address":"actor-1","time_step":4})["result"]["band"], "high")

    def test_unknown_score_is_safe_monitor(self):
        result = self.engine.score({"address":"unknown"})["result"]
        self.assertEqual(result["band"], "monitor")
        self.assertEqual(result["score"], 0.0)

    def test_missing_address_is_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.score({})

    def test_non_object_features_are_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.score({"address": "actor-1", "features": []})


if __name__ == "__main__":
    unittest.main()
