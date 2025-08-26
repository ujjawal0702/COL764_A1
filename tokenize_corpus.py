
import json
import os
import sys
import re
from typing import Iterable, List, Dict, Any

DIGIT_PATTERN = re.compile(r'[0-9]')
NON_ASCII_PATTERN = re.compile(r'[^\x00-\x7F]')


def preprocess_text(text: str) -> str:
    """
    Preprocess text according to Task 1 rules:
    1. Lowercase
    2. Remove digits 0-9
    3. Remove non-ASCII characters
    """
    if not isinstance(text, str):
        text = str(text)
    text = text.lower()
    text = DIGIT_PATTERN.sub('', text)      # remove digits
    text = NON_ASCII_PATTERN.sub('', text)  # remove non-ASCII
    return text


def load_stopwords(stopwords_file: str) -> set:
    """
    Load stopwords from file into a set for fast lookup
    (tokens are compared post-preprocessing, so stopwords
    should be given in their final token form, e.g., lowercase).
    """
    if not os.path.isfile(stopwords_file):
        raise FileNotFoundError(f"Stopwords file not found: {stopwords_file}")

    stopwords = set()
    with open(stopwords_file, 'r', encoding='utf-8') as f:
        for line in f:
            word = line.strip()
            if word:  # Skip empty lines
                stopwords.add(word)
    return stopwords


def _gather_strings(value: Any) -> Iterable[str]:
    """
    Recursively yield string leaves from nested dicts/lists/tuples.
    We ignore non-string scalars (ints/floats/bools/None).
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _gather_strings(v)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _gather_strings(item)
    # else: ignore non-string scalars


def extract_document_content(doc: Dict[str, Any]) -> str:
    """
    Extract all content from document except doc_id.
    Concatenate only textual fields (including strings inside nested structures).
    """
    parts: List[str] = []
    for key, value in doc.items():
        if key == "doc_id":
            continue
        for s in _gather_strings(value):
            parts.append(s)
    return ' '.join(parts)


def load_documents_from_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Load documents from a JSON file. Supports:
    - Single JSON object (dict)
    - JSON array of objects (list[dict])
    - JSONL (one JSON dict per line)
    Returns a list of dict documents.
    """
    documents: List[Dict[str, Any]] = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        if not content:
            return documents

        # Try standard JSON parse first (dict or list)
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                documents = [data]
                return documents
            if isinstance(data, list):
                documents = [d for d in data if isinstance(d, dict)]
                return documents
        except json.JSONDecodeError:
            pass

        # Fallback: JSON Lines (JSONL)
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    documents.append(obj)
            except json.JSONDecodeError:
                continue

        return documents

    except Exception:
        return []


def build_vocab(corpus_dir: str, stopwords_file: str, vocab_dir: str) -> None:
    """
    Build vocabulary from corpus with stopword removal.

    Args:
        corpus_dir (str): Path to corpus directory
        stopwords_file (str): Path to stopwords file
        vocab_dir (str): Directory to save vocab.txt
    """
    if not os.path.isdir(corpus_dir):
        raise FileNotFoundError(f"Corpus directory not found: {corpus_dir}")

    stopwords = load_stopwords(stopwords_file)
    vocab = set()

    # Process all files deterministically
    for root, dirs, files in os.walk(corpus_dir):
        dirs.sort()
        files.sort()
        for filename in files:
            file_path = os.path.join(root, filename)
            if not os.path.isfile(file_path):
                continue

            documents = load_documents_from_file(file_path)
            if not documents:
                continue

            for doc in documents:
                if not isinstance(doc, dict):
                    continue

                # Extract content (everything except doc_id)
                text = extract_document_content(doc)

                # Preprocess
                text = preprocess_text(text)

                # Tokenize (split on whitespace only)
                tokens = text.split()

                for token in tokens:
                    if token and token not in stopwords:
                        vocab.add(token)

    os.makedirs(vocab_dir, exist_ok=True)

    # Write sorted vocabulary (one token per line)
    vocab_file_path = os.path.join(vocab_dir, 'vocab.txt')
    with open(vocab_file_path, 'w', encoding='utf-8') as f:
        for token in sorted(vocab):
            f.write(token + '\n')


def main():
    if len(sys.argv) != 4:
        print("Usage: python tokenize_corpus.py <CORPUS_DIR> <STOPWORDS_FILE> <VOCAB_DIR>", file=sys.stderr)
        sys.exit(1)

    corpus_dir = sys.argv[1]
    stopwords_file = sys.argv[2]
    vocab_dir = sys.argv[3]

    try:
        build_vocab(corpus_dir, stopwords_file, vocab_dir)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
