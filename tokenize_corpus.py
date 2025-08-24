import os
import sys
import json

# Stopwords loader
def load_stopwords(stopwords_file):
    stopwords = set()
    with open(stopwords_file, "r", encoding="utf-8") as f:
        for line in f:
            w = line.strip().lower()
            if w:
                stopwords.add(w)
    return stopwords

def remove_non_ascii(s: str) -> str:
    """Keep only ASCII characters."""
    return ''.join(c for c in s if ord(c) < 128)

def tokenize(text, stopwords):
    text = ''.join(c for c in text if not c.isdigit())
    text = text.replace('"', r'\"')
    text = text.replace('\\', r'\\')
    tokens = text.split()

    clean_tokens = []
    for t in tokens:
        t = t.lower()
        t = remove_non_ascii(t)   # remove non-ascii chars
        if t and t not in stopwords:
            clean_tokens.append(t)
    return clean_tokens

def iter_documents(path):
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            data = f.read().strip()
        if not data:
            return
        if data.startswith("["):
            arr = json.loads(data)
            for obj in arr:
                yield obj
        else:
            for line in data.splitlines():
                line = line.strip()
                if line:
                    yield json.loads(line)
    elif os.path.isdir(path):
        for fname in os.listdir(path):
            fpath = os.path.join(path, fname)
            yield from iter_documents(fpath)
    else:
        raise FileNotFoundError(f"No such file or directory: {path}")

def build_vocab(corpus_path, stopwords_file, output_dir):
    stopwords = load_stopwords(stopwords_file)
    vocab = set()
    for doc in iter_documents(corpus_path):
        # check fields exist
        title = doc.get("title", "")
        abstract = doc.get("abstract", "")
        doi = doc.get("doi", "")
        date = doc.get("date", "")
        
        text = f"{title} {abstract} {doi} {date}"
        tokens = tokenize(text, stopwords)
        vocab.update(tokens)
    
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "vocab.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        for tok in sorted(vocab):
            f.write(tok + "\n")
    print(f"[INFO] Wrote {len(vocab)} unique tokens to {out_path}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python tokenize_corpus.py <CORPUS_PATH> <STOPWORDS_FILE> <VOCAB_DIR>")
        sys.exit(1)
    corpus_path = sys.argv[1]
    stopwords_file = sys.argv[2]
    output_dir = sys.argv[3]
    build_vocab(corpus_path, stopwords_file, output_dir)
