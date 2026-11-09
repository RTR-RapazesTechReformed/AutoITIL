"""Benchmark de custo computacional (Nivel 2): SVM vs BERTimbau.

Uso:
  python benchmark_custo.py svm  ../data/dataset_nivel_2.csv ../../backend/models/baseline/svm_nivel2.pkl  svm.json
  python benchmark_custo.py bert ../data/dataset_nivel_2.csv <pasta_do_modelo_bertimbau>                  bert.json
Cada modelo roda em processo separado para isolar o pico de memoria (RSS).
Requer: scikit-learn, pandas, psutil; para o BERT, torch e transformers.
"""
from pathlib import Path

import numpy as np
import pandas as pd

kind, csv, model_path = sys.argv[1], sys.argv[2], sys.argv[3]
out = sys.argv[4] if len(sys.argv) > 4 else None
df = pd.read_csv(csv)
res = {"modelo": kind, "n_tickets": len(df), "cpu": platform.processor() or platform.machine(),
       "nucleos": os.cpu_count()}


def size_mb(p):
    p = Path(p)
    if p.is_file():
        return p.stat().st_size / 1e6
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and ".cache" not in f.parts) / 1e6


def stats(ts):
    a = np.array(ts) * 1000
    return {"media_ms": round(a.mean(), 2), "mediana_ms": round(np.median(a), 2),
            "p95_ms": round(np.percentile(a, 95), 2)}


if kind == "svm":
    import joblib
    t = time.perf_counter(); pipe = joblib.load(model_path); res["carga_s"] = round(time.perf_counter() - t, 3)
    texts = df["descricao_limpa"].fillna("").tolist()
    pipe.predict_proba(texts[:5])  # aquecimento
    ts = []
    for x in texts:
        t = time.perf_counter(); pipe.predict_proba([x]); ts.append(time.perf_counter() - t)
    res["inferencia_unitaria"] = stats(ts)
    t = time.perf_counter(); pipe.predict_proba(texts); res["lote_total_s"] = round(time.perf_counter() - t, 3)
    # treino: mesmo pipeline, 5 folds estratificados
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.pipeline import Pipeline
    from sklearn.svm import LinearSVC
    novo = lambda: Pipeline([('tfidf', TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=0.95, sublinear_tf=True)), ('clf', CalibratedClassifierCV(LinearSVC(max_iter=2000, class_weight='balanced'), cv=3))])
    from sklearn.model_selection import StratifiedKFold
    y = df["area_responsavel"].values
    tt = []
    for tr, _ in StratifiedKFold(5, shuffle=True, random_state=42).split(texts, y):
        m = novo(); t = time.perf_counter(); m.fit([texts[i] for i in tr], y[tr]); tt.append(time.perf_counter() - t)
    res["treino_por_fold_s"] = {"media": round(float(np.mean(tt)), 2), "dp": round(float(np.std(tt)), 2)}
else:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    res["torch_threads"] = torch.get_num_threads()
    t = time.perf_counter()
    tok = AutoTokenizer.from_pretrained(model_path); mdl = AutoModelForSequenceClassification.from_pretrained(model_path).eval()
    res["carga_s"] = round(time.perf_counter() - t, 3)
    res["parametros_M"] = round(sum(p.numel() for p in mdl.parameters()) / 1e6, 1)
    texts = df["descricao"].fillna("").tolist()

    def run(batch):
        enc = tok(batch, return_tensors="pt", truncation=True, padding=True, max_length=192)
        with torch.no_grad():
            return torch.softmax(mdl(**enc).logits, -1)

    run(texts[:2])  # aquecimento
    ts = []
    for x in texts:
        t = time.perf_counter(); run([x]); ts.append(time.perf_counter() - t)
    res["inferencia_unitaria"] = stats(ts)
    t = time.perf_counter()
    for i in range(0, len(texts), 32): run(texts[i:i + 32])
    res["lote_total_s"] = round(time.perf_counter() - t, 3)

res["tamanho_disco_mb"] = round(size_mb(model_path), 1)
res["pico_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 0)
print(json.dumps(res, ensure_ascii=False, indent=1))
if out: Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
