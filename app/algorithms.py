"""Algoritma inti sesuai ruang lingkup TA: Fisher-Yates, TF-IDF/cosine, penalti."""
import random
import re
from typing import Any

try:
    from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
    from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
    _stemmer = StemmerFactory().create_stemmer()
    _stopword_remover = StopWordRemoverFactory().create_stop_word_remover()
except Exception:  # fallback agar aplikasi tetap bisa dijalankan saat dependency NLP belum terpasang
    _stemmer = None
    _stopword_remover = None

PENALTY_WEIGHTS = {
    "VIOL-01": 25,  # tab tersembunyi / berpindah tab
    "VIOL-02": 20,  # kehilangan fokus jendela
    "VIOL-03": 15,  # keluar fullscreen
    "VIOL-04": 10,  # klik kanan
    "VIOL-05": 20,  # salin/tempel
}

def fisher_yates(items: list[Any], rng: random.Random | None = None) -> list[Any]:
    """Menghasilkan permutasi in-place pada salinan, O(n), tanpa mengubah input."""
    result = list(items)
    rand = rng or random.SystemRandom()
    for i in range(len(result) - 1, 0, -1):
        j = rand.randrange(i + 1)
        result[i], result[j] = result[j], result[i]
    return result

def preprocess_id(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", (text or "").lower())
    text = re.sub(r"\s+", " ", text).strip()
    if _stopword_remover:
        text = _stopword_remover.remove(text)
    if _stemmer:
        text = _stemmer.stem(text)
    return text

def essay_score(student_answer: str, reference_answer: str, keywords: list[str] | None = None, max_score: float = 100.0) -> dict:
    """Skor hibrida: 70% cosine similarity + 30% cakupan kata kunci wajib."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    student = preprocess_id(student_answer)
    reference = preprocess_id(reference_answer)
    if not student or not reference:
        cosine = 0.0
    else:
        try:
            matrix = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b").fit_transform([reference, student])
            cosine = float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
        except ValueError:
            cosine = 0.0
    keys = [k.strip().lower() for k in (keywords or []) if k.strip()]
    normalized_student = preprocess_id(student_answer)
    if keys:
        found = [k for k in keys if preprocess_id(k) and preprocess_id(k) in normalized_student]
        coverage = len(found) / len(keys)
    else:
        found, coverage = [], 1.0
    ratio = min(1.0, max(0.0, 0.7 * cosine + 0.3 * coverage))
    return {"cosine_similarity": round(cosine, 4), "keyword_coverage": round(coverage, 4),
            "matched_keywords": found, "score": round(max_score * ratio, 2), "max_score": float(max_score)}

def penalty_for(code: str) -> int:
    return PENALTY_WEIGHTS.get(code, 10)
