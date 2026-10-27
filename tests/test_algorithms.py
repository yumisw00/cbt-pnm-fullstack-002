import random
from app.algorithms import fisher_yates, essay_score

def test_fisher_yates_preserves_elements():
    values=[1,2,3,4,5]
    out=fisher_yates(values, random.Random(7))
    assert sorted(out)==values
    assert values==[1,2,3,4,5]

def test_essay_score_range():
    result=essay_score('Protokol HTTPS memakai enkripsi TLS untuk keamanan data', 'HTTPS memakai TLS untuk enkripsi dan keamanan data', ['HTTPS','TLS'], 20)
    assert 0 <= result['score'] <= 20
    assert 0 <= result['cosine_similarity'] <= 1
