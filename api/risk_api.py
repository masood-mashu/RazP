"""Small local risk API backed by the reproducible prediction artifact."""
from __future__ import annotations

import argparse
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from xgboost import XGBClassifier


class RiskEngine:
    def __init__(self, artifact: Path, model_file: Path | None = None, metadata_file: Path | None = None):
        self.artifact = artifact
        self.snapshot = json.loads(artifact.read_text(encoding="utf-8"))
        self.alerts = self.snapshot.get("alerts", [])
        self.model = None
        self.metadata = {}
        if model_file and metadata_file and model_file.exists() and metadata_file.exists():
            self.model = XGBClassifier()
            self.model.load_model(model_file)
            self.metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

    def health(self):
        return {"status": "ok", "mode": "real-time-inference" if self.model else "artifact-backed", "model_version": self.metadata.get("model_version", self.snapshot["model"]["version"])}

    def ready(self):
        return {"ready": bool(self.model), "model_loaded": bool(self.model), "artifact_loaded": bool(self.snapshot), "model_version": self.metadata.get("model_version", self.snapshot["model"]["version"])}

    def metrics(self):
        return {"model": self.snapshot["model"], "measured": self.snapshot["measured"], "threshold": self.snapshot["threshold"], "source": self.snapshot["source"]}

    def list_alerts(self, limit=50):
        return {"mode": "api", "count": min(limit, len(self.alerts)), "alerts": self.alerts[:limit]}

    def score(self, payload):
        address = payload.get("address")
        timestep = payload.get("time_step")
        if not address:
            raise ValueError("address is required")
        if payload.get("features") is not None and not isinstance(payload["features"], dict):
            raise ValueError("features must be an object")
        if self.model and payload.get("features") is not None:
            features = payload["features"]
            names = self.metadata["features"]
            missing = [name for name in names if name not in features]
            if missing:
                return {"mode":"api", "result":{"address":address,"time_step":timestep,"score":None,"band":"insufficient_evidence","action":"Human review","title":"Evidence unavailable","evidence":[f"missing feature: {name}" for name in missing[:4]],"model_version":self.metadata["model_version"]}}
            try:
                values = [[float(features[name]) for name in names]]
            except (TypeError, ValueError) as exc:
                raise ValueError(f"features must be numeric: {exc}")
            if not all(math.isfinite(value) for value in values[0]):
                raise ValueError("features must be finite numbers")
            score = float(self.model.predict_proba(values)[0, 1])
            threshold = float(self.metadata["threshold"])
            band = "critical" if score >= max(.85, threshold) else "high" if score >= threshold else "monitor"
            evidence = [f"tx activity {int(float(features['tx_count_t']))}", f"counterparties {int(float(features['unique_counterparties_t']))}"]
            return {"mode":"real-time-inference", "result":{"address":address,"time_step":timestep,"score":round(score,6),"band":band,"action":"Monitor" if band == "monitor" else "Human review","title":"Real-time model signal","evidence":evidence,"model_version":self.metadata["model_version"]}}
        matches = [a for a in self.alerts if a.get("address") == address and (timestep is None or a.get("time_step") == timestep)]
        if matches:
            return {"mode": "api", "result": matches[0]}
        return {"mode": "api", "result": {"address": address, "time_step": timestep, "score": 0.0, "band": "monitor", "action": "Monitor", "title": "No recorded alert", "evidence": ["no matching recorded prediction"], "model_version": self.snapshot["model"]["version"]}}


def handler_for(engine):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, data):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self._send(204, {})

        def do_GET(self):
            path = urlparse(self.path).path
            try:
                if path == "/health": return self._send(200, engine.health())
                if path == "/ready": return self._send(200 if engine.ready()["ready"] else 503, engine.ready())
                if path == "/metrics": return self._send(200, engine.metrics())
                if path == "/alerts": return self._send(200, engine.list_alerts())
                return self._send(404, {"error": "not_found"})
            except Exception as exc:
                return self._send(500, {"error": str(exc)})

        def do_POST(self):
            if urlparse(self.path).path != "/score": return self._send(404, {"error": "not_found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 1_000_000:
                    return self._send(413, {"error": "request_too_large"})
                payload = json.loads(self.rfile.read(length) or b"{}")
                return self._send(200, engine.score(payload))
            except (ValueError, json.JSONDecodeError) as exc:
                return self._send(400, {"error": str(exc)})

        def log_message(self, *_):
            return
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, default=Path("demo/data/risk_ops_snapshot.json"))
    parser.add_argument("--model-file", type=Path, default=None)
    parser.add_argument("--metadata-file", type=Path, default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), handler_for(RiskEngine(args.artifact, args.model_file, args.metadata_file)))
    print(f"Risk API listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
