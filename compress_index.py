import os
import json
from typing import Dict, List, Tuple, Any, BinaryIO

############################################
# Variable-Byte (VB) encoding/decoding
############################################

def vb_encode_number(n: int) -> bytes:
    if n < 0:
        raise ValueError("VB encode only supports non-negative integers")
    out = bytearray()
    while True:
        chunk = n & 0x7F  # 7 bits
        n >>= 7
        if n == 0:
            out.append(0x80 | chunk)  # last byte: set MSB=1
            break
        else:
            out.append(chunk)         # continuation: MSB=0
    return bytes(out)

def vb_encode_list(nums: List[int]) -> bytes:
    out = bytearray()
    for x in nums:
        out.extend(vb_encode_number(x))
    return bytes(out)

def vb_decode_stream(fp: BinaryIO, count: int = None) -> List[int]:
    """
    Decode a sequence of VB-coded integers from file-like object fp.
    If count is None, decode until EOF.
    If count is provided, decode exactly that many integers (or until EOF).
    """
    res: List[int] = []
    current = 0
    shift = 0
    while True:
        b = fp.read(1)
        if not b:
            # EOF
            if shift != 0:
                raise EOFError("Truncated VB integer at EOF")
            break
        b = b[0]
        current |= (b & 0x7F) << shift
        if (b & 0x80) != 0:
            # last byte of this integer
            res.append(current)
            current = 0
            shift = 0
            if count is not None and len(res) >= count:
                break
        else:
            shift += 7
    return res

def vb_decode_bytes(buf: bytes) -> List[int]:
    from io import BytesIO
    return vb_decode_stream(BytesIO(buf))

############################################
# Gap encoding helpers
############################################

def gaps_from_sorted(nums: List[int]) -> List[int]:
    """Given a sorted list of non-negative ints, return gap-encoded list."""
    gaps: List[int] = []
    prev = 0
    for i, v in enumerate(nums):
        if i == 0:
            gaps.append(v)  # base 0: first gap is absolute value
        else:
            gaps.append(v - prev)
        prev = v
    return gaps

def sorted_from_gaps(gaps: List[int]) -> List[int]:
    """Inverse of gaps_from_sorted."""
    res: List[int] = []
    prev = 0
    for i, g in enumerate(gaps):
        if i == 0:
            res.append(g)
            prev = g
        else:
            val = prev + g
            res.append(val)
            prev = val
    return res

############################################
# On-disk layout
############################################
# postings.dat (binary)
# For each term (written in lexicographic order):
#   VB(doc_freq)
#   For each document (in increasing int docID):
#       VB(doc_gap)          # gap-encoded docIDs
#       VB(tf)               # term frequency (len(positions))
#       VB(pos_gap_1) ... VB(pos_gap_tf)   # positions gap-encoded per document
#
# terms.lex (jsonlines)
# Each line is a JSON object:
# {"term": "<term>", "offset": <byte_offset>, "length": <num_bytes>, "df": <doc_freq>}
#
# docmap.json
# {
#   "doc_to_int": {"docid_str": int_id, ...},
#   "int_to_doc": ["docid_str for int_id 0", "docid_str for int_id 1", ...]
# }
#
# meta.json
# {
#   "format_version": 1,
#   "encoding": "VB",
#   "has_positions": true,
#   "doc_base": 0  # meaning first gap equals first absolute docID
# }

############################################
# Compression
############################################

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

def _encode_term_postings(term_postings: Dict[str, List[int]], doc_to_int: Dict[str, int]) -> Tuple[bytes, int]:
    """
    Build the byte stream for one term.
    Return (bytes, df). term_postings: dict[str_docid] -> positions (sorted ints).
    """
    # Ensure deterministic ordering: docIDs lex order of string docIDs, then map to ints
    # but for compression efficiency and deterministic decoding we will write in increasing integer docIDs.
    items = []
    for doc_str, pos_list in term_postings.items():
        int_id = doc_to_int[doc_str]
        # positions must be sorted ascending
        pos_sorted = sorted(pos_list)
        items.append((int_id, pos_sorted))
    items.sort(key=lambda x: x[0])  # sort by integer docID

    df = len(items)
    out = bytearray()
    # write doc_freq
    out.extend(vb_encode_number(df))

    # docID gaps need the sorted int docIDs
    int_ids = [it[0] for it in items]
    doc_gaps = gaps_from_sorted(int_ids)

    # iterate in parallel to write for each doc:
    for (doc_gap, (_, pos_sorted)) in zip(doc_gaps, items):
        # doc gap
        out.extend(vb_encode_number(doc_gap))
        # tf
        tf = len(pos_sorted)
        out.extend(vb_encode_number(tf))
        if tf > 0:
            # positions are stored as gaps
            pos_gaps = gaps_from_sorted(pos_sorted)
            out.extend(vb_encode_list(pos_gaps))
    return bytes(out), df

def compress_index(path_to_index_file: str, path_to_compressed_files_directory: str) -> None:
    # Load the uncompressed JSON index
    with open(path_to_index_file, "r", encoding="utf-8") as f:
        index: Dict[str, Dict[str, List[int]]] = json.load(f)

    # Prepare output dir
    outdir = path_to_compressed_files_directory
    os.makedirs(outdir, exist_ok=True)
    postings_path = os.path.join(outdir, "postings.dat")
    terms_lex_path = os.path.join(outdir, "terms.lex")
    docmap_path = os.path.join(outdir, "docmap.json")
    meta_path = os.path.join(outdir, "meta.json")

    # Build docID maps
    all_docids = _collect_all_docids(index)
    doc_to_int, int_to_doc = _build_docid_maps(all_docids)

    # Write docmap
    with open(docmap_path, "w", encoding="utf-8") as f:
        json.dump({"doc_to_int": doc_to_int, "int_to_doc": int_to_doc}, f, ensure_ascii=False, separators=(",", ":"), indent=2)

    # Write postings.dat and terms.lex
    # Terms must be processed in lexicographic order for determinism
    terms_sorted = sorted(index.keys())

    offset = 0
    with open(postings_path, "wb") as pfp, open(terms_lex_path, "w", encoding="utf-8") as lfp:
        for term in terms_sorted:
            term_postings = index[term]  # dict[str_docid] -> [positions]
            blob, df = _encode_term_postings(term_postings, doc_to_int)
            length = len(blob)
            # write blob to postings.dat
            pfp.write(blob)
            # write one lex line
            entry = {"term": term, "offset": offset, "length": length, "df": df}
            lfp.write(json.dumps(entry, ensure_ascii=False) + "\n")
            offset += length

    # Meta
    meta = {
        "format_version": 1,
        "encoding": "VB",
        "has_positions": True,
        "doc_base": 0
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"), indent=2)

############################################
# Decompression (for Task 4 to reconstruct logical index)
############################################

def _read_terms_lex(terms_lex_path: str) -> List[Dict[str, Any]]:
    lex: List[Dict[str, Any]] = []
    with open(terms_lex_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            obj = json.loads(s)
            lex.append(obj)
    return lex

def _load_docmap(docmap_path: str) -> Tuple[Dict[str, int], List[str]]:
    with open(docmap_path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    return obj["doc_to_int"], obj["int_to_doc"]

def _decode_term_postings_from_slice(blob: bytes, int_to_doc: List[str]) -> Dict[str, List[int]]:
    """
    Given one term's postings slice bytes, decode to {doc_id_str: [positions]}.
    Layout per term:
      VB(df)
      For each doc (df times):
        VB(doc_gap)
        VB(tf)
        VB(pos_gap_1) ... VB(pos_gap_tf)
    """
    vals = vb_decode_bytes(blob)
    if not vals:
        return {}
    idx = 0
    df = vals[idx]
    idx += 1

    # First read all doc gaps and tf counts to know how many position numbers to read for each
    doc_gaps: List[int] = []
    tfs: List[int] = []
    for _ in range(df):
        if idx >= len(vals):
            raise ValueError("Corrupt postings: unexpected end while reading doc_gap/tf")
        doc_gaps.append(vals[idx]); idx += 1
        if idx >= len(vals):
            raise ValueError("Corrupt postings: unexpected end while reading tf")
        tfs.append(vals[idx]); idx += 1

    # Rebuild absolute integer docIDs
    int_docids = sorted_from_gaps(doc_gaps)

    # Now read positions for each doc
    postings: Dict[str, List[int]] = {}
    for doc_int, tf in zip(int_docids, tfs):
        pos_gaps = vals[idx: idx + tf]
        if len(pos_gaps) != tf:
            raise ValueError("Corrupt postings: not enough position gaps")
        idx += tf
        positions = sorted_from_gaps(pos_gaps) if tf > 0 else []
        doc_str = int_to_doc[doc_int]
        postings[doc_str] = positions

    if idx != len(vals):
        # Extra bytes in slice; possible if you change layout. Here we expect exact use.
        pass
    return postings

def decompress_index(compressed_index_dir: str) -> Dict[str, Dict[str, List[int]]]:
    postings_path = os.path.join(compressed_index_dir, "postings.dat")
    terms_lex_path = os.path.join(compressed_index_dir, "terms.lex")
    docmap_path = os.path.join(compressed_index_dir, "docmap.json")
    meta_path = os.path.join(compressed_index_dir, "meta.json")

    # load maps and lex
    doc_to_int, int_to_doc = _load_docmap(docmap_path)
    terms_lex = _read_terms_lex(terms_lex_path)

    # read postings slices
    with open(postings_path, "rb") as pfp:
        result: Dict[str, Dict[str, List[int]]] = {}
        for entry in terms_lex:
            term = entry["term"]
            offset = entry["offset"]
            length = entry["length"]
            pfp.seek(offset)
            blob = pfp.read(length)
            postings = _decode_term_postings_from_slice(blob, int_to_doc)
            # ensure docIDs are lexicographically sorted in logical JSON reconstruction
            # although dict in Python 3.7+ preserves insertion order, we'll sort when saving
            result[term] = postings
    return result

############################################
# Utility: Save decompressed logical index (exact JSON format)
############################################

def save_index_logical(inverted_index: Dict[str, Dict[str, List[int]]], path: str) -> None:
    # Ensure deterministic JSON: sort terms and doc IDs
    out_obj: Dict[str, Dict[str, List[int]]] = {}
    for term in sorted(inverted_index.keys()):
        postings = inverted_index[term]
        sorted_postings: Dict[str, List[int]] = {}
        for doc_id in sorted(postings.keys()):
            plist = postings[doc_id]
            sorted_postings[doc_id] = sorted(plist)
        out_obj[term] = sorted_postings

    with open(path, "w", encoding="utf-8") as f:
        json.dump(out_obj, f, ensure_ascii=False, separators=(",", ":"), indent=2)

############################################
# Optional CLI glue
############################################

def _print_usage():
    print(
        "Usage:\n"
        "  python compress_index.py <PATH_TO_INDEX_JSON> <COMPRESSED_DIR>\n"
        "  python decompress_index.py <COMPRESSED_DIR> <OUT_JSON>\n",
        flush=True
    )

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        _print_usage()
        sys.exit(1)

    mode_or_index = sys.argv[1]

    # Two modes for convenience:
    # 1) compress: python this.py compress <index.json> <compressed_dir>
    # 2) decompress: python this.py decompress <compressed_dir> <out.json>
    if mode_or_index == "compress":
        if len(sys.argv) != 4:
            _print_usage()
            sys.exit(1)
        index_json = sys.argv[2]
        comp_dir = sys.argv[3]
        compress_index(index_json, comp_dir)
        print("Compressed index written to:", comp_dir)
    elif mode_or_index == "decompress":
        if len(sys.argv) != 4:
            _print_usage()
            sys.exit(1)
        comp_dir = sys.argv[2]
        out_json = sys.argv[3]
        inv = decompress_index(comp_dir)
        save_index_logical(inv, out_json)
        print("Decompressed logical index written to:", out_json)
    else:
        # Backward compatible single-call interpretation (optional)
        _print_usage()
        sys.exit(1)
