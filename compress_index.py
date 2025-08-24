# =========================
# Task 3: Index Compression
# =========================
# - Maps string docIDs to integers
# - Gap-encodes integer docIDs per term (base 0; first gap is absolute int docID)
# - Gap-encodes positions within each document (base 0)
# - Variable-Byte encodes all integer sequences
# - Writes compact artifacts into <COMPRESSED_DIR>:
#     postings.dat  (binary VB-coded postings)
#     terms.lex     (JSONL: {term, offset, length, df})
#     docmap.json   (string<->int docID mapping)
#     meta.json     (format metadata)

import os
import json
from typing import Dict, List, Tuple, Any, BinaryIO

# -------------------------
# Variable-Byte (VB) coding
# -------------------------

def _vb_encode_number(n: int) -> bytes:
    if n < 0:
        raise ValueError("VB encode only supports non-negative integers")
    out = bytearray()
    while True:
        chunk = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | chunk)  # last byte (MSB=1)
            break
        else:
            out.append(chunk)         # continuation (MSB=0)
    return bytes(out)

def _vb_encode_list(nums: List[int]) -> bytes:
    out = bytearray()
    for x in nums:
        out.extend(_vb_encode_number(x))
    return bytes(out)

# -------------------------
# Gap encoding helpers
# -------------------------

def _gaps_from_sorted(nums: List[int]) -> List[int]:
    # base 0: first gap equals first absolute value
    if not nums:
        return []
    gaps: List[int] = []
    prev = 0
    for i, v in enumerate(nums):
        if i == 0:
            gaps.append(v)
        else:
            gaps.append(v - prev)
        prev = v
    return gaps

# -------------------------
# Helpers for compression
# -------------------------

def _collect_all_docids(index: Dict[str, Dict[str, List[int]]]) -> List[str]:
    docids = set()
    for postings in index.values():
        for doc_id in postings.keys():
            docids.add(doc_id)
    return sorted(docids)

def _build_docid_maps(docids_sorted: List[str]) -> Tuple[Dict[str, int], List[str]]:
    doc_to_int = {d: i for i, d in enumerate(docids_sorted)}
    int_to_doc = list(docids_sorted)
    return doc_to_int, int_to_doc

def _encode_term_postings(term_postings: Dict[str, List[int]],
                          doc_to_int: Dict[str, int]) -> Tuple[bytes, int]:
    """
    Per-term binary slice layout (must match decompressor):
      VB(df)
      For each document (ascending integer docID):
        VB(doc_gap)
        VB(tf)
        VB(pos_gap_1) ... VB(pos_gap_tf)
    """
    items = []
    for doc_str, pos_list in term_postings.items():
        int_id = doc_to_int[doc_str]
        pos_sorted = sorted(pos_list)
        items.append((int_id, pos_sorted))
    items.sort(key=lambda x: x[0])  # sort by integer docID

    df = len(items)
    out = bytearray()
    out.extend(_vb_encode_number(df))  # DF

    int_ids = [it[0] for it in items]
    doc_gaps = _gaps_from_sorted(int_ids)

    for (doc_gap, (_, pos_sorted)) in zip(doc_gaps, items):
        out.extend(_vb_encode_number(doc_gap))  # doc gap
        tf = len(pos_sorted)
        out.extend(_vb_encode_number(tf))       # term frequency
        if tf > 0:
            pos_gaps = _gaps_from_sorted(pos_sorted)  # base 0 within each doc
            out.extend(_vb_encode_list(pos_gaps))      # positions as gaps

    return bytes(out), df

# -------------------------
# Public API
# -------------------------

def compress_index(path_to_index_file: str, path_to_compressed_files_directory: str) -> None:
    """
    Reads logical index.json (term -> {doc_id_str: [positions]}) and writes compressed artifacts:
      <COMPRESSED_DIR>/postings.dat  (binary VB-coded postings)
      <COMPRESSED_DIR>/terms.lex     (jsonlines: {term, offset, length, df})
      <COMPRESSED_DIR>/docmap.json   (string<->int docID maps)
      <COMPRESSED_DIR>/meta.json     (format metadata)
    """
    # Load logical inverted index
    with open(path_to_index_file, "r", encoding="utf-8") as f:
        index: Dict[str, Dict[str, List[int]]] = json.load(f)

    outdir = path_to_compressed_files_directory
    os.makedirs(outdir, exist_ok=True)

    postings_path = os.path.join(outdir, "postings.dat")
    terms_lex_path = os.path.join(outdir, "terms.lex")
    docmap_path = os.path.join(outdir, "docmap.json")
    meta_path = os.path.join(outdir, "meta.json")

    # Build and save docID mappings
    all_docids = _collect_all_docids(index)
    doc_to_int, int_to_doc = _build_docid_maps(all_docids)
    with open(docmap_path, "w", encoding="utf-8") as f:
        json.dump(
            {"doc_to_int": doc_to_int, "int_to_doc": int_to_doc},
            f, ensure_ascii=False, separators=(",", ":"), indent=2
        )

    # Compress postings per term in lexicographic order of terms
    terms_sorted = sorted(index.keys())
    offset = 0

    with open(postings_path, "wb") as pfp, open(terms_lex_path, "w", encoding="utf-8") as lfp:
        for term in terms_sorted:
            term_postings = index[term]  # dict: str_docid -> [positions]
            blob, df = _encode_term_postings(term_postings, doc_to_int)
            length = len(blob)
            # write slice
            pfp.write(blob)
            # record lex entry with precise byte offset and length
            lex_entry = {"term": term, "offset": offset, "length": length, "df": df}
            lfp.write(json.dumps(lex_entry, ensure_ascii=False) + "\n")
            offset += length

    # Metadata for sanity
    meta = {
        "format_version": 1,
        "encoding": "VB",
        "has_positions": True,
        "doc_base": 0  # first gap equals first absolute int docID
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"), indent=2)

# Optional CLI
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3 and not (len(sys.argv) == 4 and sys.argv[1] == "compress"):
        print(
            "Usage:\n"
            "  python compress_index.py <PATH_TO_INDEX_JSON> <COMPRESSED_DIR>\n"
            "  or\n"
            "  python compress_index.py compress <PATH_TO_INDEX_JSON> <COMPRESSED_DIR>\n",
            flush=True
        )
        raise SystemExit(1)

    if len(sys.argv) == 3:
        index_json = sys.argv[1]
        comp_dir = sys.argv[2]
    else:
        index_json = sys.argv[2]
        comp_dir = sys.argv[3]

    compress_index(index_json, comp_dir)
    print(f"Compressed index written to: {comp_dir}")
