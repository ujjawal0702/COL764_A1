import re
import json
import sys
import os

def load_stopwords(stopword_file):
    sw = set()
    with open(stopword_file, "r", encoding="utf-8") as f:
        for line in f:
            w = line.strip().lower()
            if w:
                sw.add(w)
    return sw

TOKEN_RE = re.compile(r"[a-z]+")


def tokenize(text, stopwords):
    tokens = TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in stopwords]


def build_vocab(corpus_path, stopword_file, vocab_dir):
    stopwords = load_stopwords(stopword_file)
    vocab = set()


    if os.path.isdir(corpus_path):
        files = [os.path.join(corpus_path, f) for f in os.listdir(corpus_path)]
    else:
        files = [corpus_path]

    for path in files:
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
            
                doc = json.loads(line)

                parts = []
                for k, v in doc.items():
                    if k == "doc_id":
                        continue
                    parts.append(str(v))
                text = " ".join(parts)

                for tok in tokenize(text, stopwords):
                    vocab.add(tok)

    os.makedirs(vocab_dir, exist_ok=True)
    out_path = os.path.join(vocab_dir, "vocab.txt")
    with open(out_path, "w", encoding="utf-8") as out:
        for tok in sorted(vocab):
            out.write(tok + "\n")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python tokenize_corpus.py <CORPUS_PATH> <STOPWORDS_FILE> <VOCAB_DIR>")
        sys.exit(1)

    corpus_path = sys.argv[1]
    stopwords_file = sys.argv[2]
    vocab_dir = sys.argv[3]

    build_vocab(corpus_path, stopwords_file, vocab_dir)
