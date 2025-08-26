#!/usr/bin/env python3
"""
COL764 Assignment 1 - Task 2
Positional Inverted Index Builder (timed, first-doc_id-wins)
"""
import json
import os
import sys
import re
import time
from collections import defaultdict

# Regex: remove digits + non-ASCII
CLEAN_PATTERN = re.compile(r"[0-9]|[^\x00-\x7F]")

def preprocess_text(text: str) -> str:
    """Lowercase, remove digits, remove non-ASCII characters."""
    if not isinstance(text, str):
        text = str(text)
    return CLEAN_PATTERN.sub("", text.lower())

def load_vocabulary(vocab_path: str) -> set:
    """Load vocabulary into a set."""
    t0 = time.perf_counter()
    vocab = set()
    with open(vocab_path, "r", encoding="utf-8") as f:
        for line in f:
            token = line.strip()
            if token:
                vocab.add(token)
    t1 = time.perf_counter()
    print(f"[TIMING] load_vocabulary: {len(vocab)} tokens in {t1 - t0:.3f}s", file=sys.stderr)
    return vocab  # [1]

def extract_tokens(doc: dict) -> list:
    """Extract and tokenize all fields except 'doc_id'."""
    tokens = []
    for key, value in doc.items():
        if key == "doc_id" or value is None:
            continue
        cleaned = preprocess_text(value if isinstance(value, str) else str(value))
        tokens.extend(cleaned.split())
    return tokens  # [1]

def load_documents(file_path: str) -> list:
    """
    Load documents from file (JSONL/NDJSON: one JSON object per line).
    """
    t0 = time.perf_counter()
    docs = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and "doc_id" in obj:
                    docs.append(obj)
    except Exception as e:
        print(f"[ERROR] Cannot read {file_path}: {e}", file=sys.stderr)
    t1 = time.perf_counter()
    print(f"[TIMING] load_documents: {os.path.basename(file_path)} -> {len(docs)} docs in {t1 - t0:.3f}s", file=sys.stderr)
    return docs  # [1]

def build_index(collection_dir: str, vocab_path: str):
    """Build in-memory positional inverted index with first-doc_id-wins."""
    if not os.path.isdir(collection_dir):
        raise FileNotFoundError(f"Collection directory not found: {collection_dir}")

    overall_start = time.perf_counter()
    vocab = load_vocabulary(vocab_path)
    print(f"[INFO] Loaded vocab size: {len(vocab)}", file=sys.stderr)

    inverted_index = defaultdict(lambda: defaultdict(list))
    seen_docs = set()  # ensures duplicates are skipped early [1]
    total_docs = 0
    total_tokens = 0

    walk_start = time.perf_counter()
    for root, dirs, files in os.walk(collection_dir):
        dirs.sort()
        files.sort()
        for filename in files:
            file_path = os.path.join(root, filename)
            if not os.path.isfile(file_path):
                continue

            file_start = time.perf_counter()
            documents = load_documents(file_path)  # includes its own timing
            parse_done = time.perf_counter()

            idx_ops = 0
            kept_docs = 0
            skipped_dups = 0

            for doc in documents:
                # Resolve doc_id and enforce "first wins"
                doc_id = doc.get("doc_id")
                if not isinstance(doc_id, str):
                    doc_id = str(doc_id) if doc_id is not None else ""
                if not doc_id:
                    continue
                if doc_id in seen_docs:
                    skipped_dups += 1
                    continue
                seen_docs.add(doc_id)

                tokens = extract_tokens(doc)
                kept_docs += 1
                total_docs += 1
                total_tokens += len(tokens)

                # Index tokens that are in the vocab; positions from full stream
                postings_for_term = inverted_index  # local alias
                contains = vocab.__contains__       # micro-optimization
                for pos, token in enumerate(tokens):
                    if contains(token):
                        postings = postings_for_term[token]
                        postings[doc_id].append(pos)
                        idx_ops += 1

            index_done = time.perf_counter()
            print(
                f"[TIMING] file {filename}: parse {parse_done - file_start:.3f}s | "
                f"tokenize+index {index_done - parse_done:.3f}s | "
                f"docs kept {kept_docs} | dups skipped {skipped_dups} | kept-ops {idx_ops}",
                file=sys.stderr,
            )

    walk_done = time.perf_counter()

    # Sort positions
    sort_start = time.perf_counter()
    for postings in inverted_index.values():
        for plist in postings.values():
            plist.sort()
    sort_done = time.perf_counter()

    overall_done = time.perf_counter()
    print(f"[INFO] Processed {total_docs} docs, {total_tokens} tokens total", file=sys.stderr)
    print(f"[INFO] Index terms (with postings): {len(inverted_index)}", file=sys.stderr)
    print(
        f"[TIMING] walk {walk_done - walk_start:.3f}s | sort {sort_done - sort_start:.3f}s | "
        f"build total {overall_done - overall_start:.3f}s",
        file=sys.stderr,
    )

    # Prepare ordered dict for saving (terms/docs sorted)
    order_start = time.perf_counter()
    final_index = {}
    for term in sorted(inverted_index.keys()):
        docs_map = inverted_index[term]
        final_index[term] = {doc_id: docs_map[doc_id] for doc_id in sorted(docs_map.keys())}
    order_done = time.perf_counter()
    print(f"[TIMING] prepare save (sort terms/docs): {order_done - order_start:.3f}s", file=sys.stderr)

    return final_index  # [1]

def save_index(inverted_index, index_dir: str) -> None:
    """Save inverted index to index.json in <index_dir>."""
    os.makedirs(index_dir, exist_ok=True)
    index_file = os.path.join(index_dir, "index.json")
    t0 = time.perf_counter()
    with open(index_file, "w", encoding="utf-8") as f:
        # Pretty printing required by spec examples; if allowed, use compact to speed up.
        json.dump(inverted_index, f, ensure_ascii=False, indent=2)
    t1 = time.perf_counter()
    print(f"[TIMING] save_index: wrote {index_file} in {t1 - t0:.3f}s", file=sys.stderr)

def main():
    if len(sys.argv) != 4:
        print("Usage: python index.py <COLLECTION_DIR> <VOCAB_PATH> <INDEX_DIR>", file=sys.stderr)
        sys.exit(1)

    collection_dir = sys.argv[1]
    vocab_path = sys.argv[2]
    index_dir = sys.argv[3]

    try:
        run_start = time.perf_counter()
        print(f"[INFO] Building index from {collection_dir}", file=sys.stderr)
        print(f"[INFO] Using vocab: {vocab_path}", file=sys.stderr)
        inverted_index = build_index(collection_dir, vocab_path)
        built = time.perf_counter()
        print(f"[INFO] Built index with {len(inverted_index)} terms", file=sys.stderr)
        save_index(inverted_index, index_dir)
        saved = time.perf_counter()
        print(
            f"[TIMING] end-to-end: build {built - run_start:.3f}s | save {saved - built:.3f}s | total {saved - run_start:.3f}s",
            file=sys.stderr,
        )
        print(f"[INFO] Saved index to {index_dir}/index.json", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
