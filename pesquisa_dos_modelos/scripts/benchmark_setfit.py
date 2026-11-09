"""Benchmark de inferencia do SetFit (Nivel 2) em CPU.

O custo de inferencia depende da arquitetura (encoder MiniLM-L12 multilingue +
cabeca logistica), nao dos pesos. Por isso usa-se o encoder pre-treinado, com a
cabeca logistica ajustada aos embeddings, sem o ajuste contrastivo.
Uso: python benchmark_setfit.py <dataset.csv> [saida.json]
"""
import json, os, platform, resource, sys, tempfile, time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression

csv = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else None
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
df = pd.read_csv(csv); texts = df["descricao"].fillna("").tolist(); y = df["area_responsavel"].values
res = {"modelo": "setfit (encoder pre-treinado + cabeca logistica)", "n_tickets": len(df),
       "cpu": platform.processor() or platform.machine(), "nucleos": os.cpu_count()}

t = time.perf_counter(); body = SentenceTransformer(MODEL, device="cpu"); res["carga_s"] = round(time.perf_counter() - t, 3)
res["parametros_M"] = round(sum(p.numel() for p in body.parameters()) / 1e6, 1)
head = LogisticRegression(max_iter=1000).fit(body.encode(texts, batch_size=32), y)

with tempfile.TemporaryDirectory() as d:
    body.save(d); joblib.dump(head, Path(d) / "model_head.pkl")
    res["tamanho_disco_mb"] = round(sum(f.stat().st_size for f in Path(d).rglob("*") if f.is_file()) / 1e6, 1)

def predict(batch): return head.predict_proba(body.encode(batch, batch_size=32))
predict(texts[:2])
ts = []
for x in texts:
    t = time.perf_counter(); predict([x]); ts.append(time.perf_counter() - t)
a = np.array(ts) * 1000
res["inferencia_unitaria"] = {"media_ms": round(a.mean(), 2), "mediana_ms": round(float(np.median(a)), 2), "p95_ms": round(float(np.percentile(a, 95)), 2)}
t = time.perf_counter(); predict(texts); res["lote_total_s"] = round(time.perf_counter() - t, 3)
res["pico_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 0)
print(json.dumps(res, ensure_ascii=False, indent=1))
if out: Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
