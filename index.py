import sys
import os
import json
import re
from typing import Dict, Any, List, Set, Iterable, Tuple

_DIGIT_RE = re.compile(r"[0-9]")

def _load_vocab(vocab_path: str) -> Set[str]:
    if not os.path.isfile(vocab_path):
        raise FileNotFoundError(f"Vocab file not found: {vocab_path}")
    vocab: Set[str] = set()
    with open(vocab_path, "r", encoding="utf-8") as f:
        for line in f:
            tok = line.rstrip("\n")
            if tok != "":
                vocab.add(tok)
    return vocab

def _load_stopwords(stopwords_file: str) -> Set[str]:
    if not os.path.isfile(stopwords_file):
        raise FileNotFoundError(f"Stopwords file not found: {stopwords_file}")
    sw: Set[str] = set()
    with open(stopwords_file, "r", encoding="utf-8") as f:
        for line in f:
            w = line.strip()
            if w != "":
                sw.add(w)
    return sw

def _tokenize_text_task1(text: str, stopwords: Set[str]) -> List[str]:
    text = text.lower()
    text = _DIGIT_RE.sub("", text)
    raw = text.split()
    return [t for t in raw if t and (t not in stopwords)]

def _doc_tokens_in_vocab(doc: Dict[str, Any], stopwords: Set[str], vocab: Set[str]) -> List[str]:
    
    tokens: List[str] = []
    for key in sorted(doc.keys()):
        if key == "doc_id":
            continue
        val = doc[key]
        if val is None:
            continue
        if isinstance(val, str):
            tks = _tokenize_text_task1(val, stopwords)
        else:
           try:
                sval = str(val)
            except Exception:
                continue
            tks = _tokenize_text_task1(sval, stopwords)
        for tk in tks:
            if tk in vocab:
                tokens.append(tk)
    return tokens

def _try_process_line_delimited(fpath: str) -> Tuple[bool, List[Dict[str, Any]], str]:
    
    docs: List[Dict[str, Any]] = []
    try:
        with open(fpath, "r", encoding="utf-8") as fp:
            for line in fp:
                s = line.strip()
                if not s:
                    continue
                obj = json.loads(s)
                if isinstance(obj, dict):
                    docs.append(obj)
                else:
                    return (False, [], "Non-dict JSON encountered in line-delimited mode")
        return (True, docs, "")
    except json.JSONDecodeError as e:
        return (False, [], f"JSON decode error: {e}")
    except Exception as e:
        return (False, [], str(e))

def _read_whole_file_docs(fpath: str) -> List[Dict[str, Any]]:
    
    with open(fpath, "r", encoding="utf-8") as fp:
        content = fp.read()
    obj = json.loads(content)
    if isinstance(obj, dict):
        return [obj]
    elif isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    else:
        raise ValueError(f"Unsupported JSON structure in {fpath}; expected object or array of objects.")

def build_index(collection_dir: str, vocab_path: str, stopwords_file: str) -> Dict[str, Dict[str, List[int]]]:
    
    if not os.path.isdir(collection_dir):
        raise FileNotFoundError(f"COLLECTION_DIR not found or not a directory: {collection_dir}")

    vocab = _load_vocab(vocab_path)
    stopwords = _load_stopwords(stopwords_file)

    index: Dict[str, Dict[str, List[int]]] = {}

    for root, dirs, files in os.walk(collection_dir):
        files.sort()
        for fname in files:
            fpath = os.path.join(root, fname)
            if not os.path.isfile(fpath):
                continue

            success, docs, _ = _try_process_line_delimited(fpath)
            if not success:
                docs = _read_whole_file_docs(fpath)

            for doc in docs:
                if not isinstance(doc, dict):
                    continue
                doc_id = doc.get("doc_id")
                if not isinstance(doc_id, str):
                    doc_id = str(doc_id) if doc_id is not None else ""

                tokens = _doc_tokens_in_vocab(doc, stopwords, vocab)
                for pos, term in enumerate(tokens):
                    postings = index.get(term)
                    if postings is None:
                        postings = {}
                        index[term] = postings
                    plist = postings.get(doc_id)
                    if plist is None:
                        plist = []
                        postings[doc_id] = plist
                    plist.append(pos)

    for term_postings in index.values():
        for plist in term_postings.values():
            plist.sort()

    return index

def save_index(inverted_index: Dict[str, Dict[str, List[int]]], index_dir: str) -> None:
   
    if not os.path.isdir(index_dir):
        os.makedirs(index_dir, exist_ok=True)

    out_obj: Dict[str, Dict[str, List[int]]] = {}
    for term in sorted(inverted_index.keys()):
        postings = inverted_index[term]
        sorted_postings: Dict[str, List[int]] = {}
        for doc_id in sorted(postings.keys()):
            sorted_postings[doc_id] = postings[doc_id]
        out_obj[term] = sorted_postings

    out_path = os.path.join(index_dir, "index.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_obj, f, ensure_ascii=False, separators=(",", ":"), indent=2)

def _print_usage() -> None:
    print(
        # "Usage:\n"
        # "  python build_index.py <COLLECTION_DIR> <VOCAB_PATH> <STOPWORDS_FILE> <INDEX_DIR>\n\n"
        # "Notes:\n"
        # "- COLLECTION_DIR: directory containing corpus file(s); each file may be line-delimited JSON,\n"
        # "                  a single JSON object, or a JSON array of objects.\n"
        # "- VOCAB_PATH: path to vocab.txt produced by Task 1\n"
        # "- STOPWORDS_FILE: the same stopwords file used in Task 1 (to ensure identical tokenization)\n"
        # "- INDEX_DIR: output directory where index.json will be saved.",
        file=sys.stderr,
    )

if __name__ == "__main__":
    if len(sys.argv) != 5:
        _print_usage()
        sys.exit(1)

    collection_dir = sys.argv[1]
    vocab_path = sys.argv[2]
    stopwords_file = sys.argv[3]
    index_dir = sys.argv[4]

    try:
        inv = build_index(collection_dir, vocab_path, stopwords_file)
        save_index(inv, index_dir)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

