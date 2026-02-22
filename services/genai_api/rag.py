import os
from dataclasses import dataclass
from typing import List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

@dataclass
class Doc:
    doc_id: str
    text: str

class SimpleRAG:
    def __init__(self, corpus_path: str):
        self.corpus_path = corpus_path
        self.docs: List[Doc] = []
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = None

    def load(self):
        self.docs = []
        for fn in sorted(os.listdir(self.corpus_path)):
            if not fn.endswith(".md"):
                continue
            path = os.path.join(self.corpus_path, fn)
            with open(path, "r", encoding="utf-8") as f:
                self.docs.append(Doc(doc_id=fn, text=f.read()))
        self.matrix = self.vectorizer.fit_transform([d.text for d in self.docs])

    def query(self, q: str, top_k: int = 3) -> List[Tuple[str, str, float]]:
        if not self.docs:
            self.load()
        qv = self.vectorizer.transform([q])
        sims = cosine_similarity(qv, self.matrix)[0]
        ranked = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:top_k]
        return [(self.docs[i].doc_id, self.docs[i].text[:800], float(sims[i])) for i in ranked]
