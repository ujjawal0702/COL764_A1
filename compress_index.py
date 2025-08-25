# # =========================
# # Task 3: Index Compression
# # =========================
# # - Maps string docIDs to integers
# # - Gap-encodes integer docIDs per term (base 0; first gap is absolute int docID)
# # - Gap-encodes positions within each document (base 0)
# # - Variable-Byte encodes all integer sequences
# # - Writes compact artifacts into <COMPRESSED_DIR>:
# #     postings.dat  (binary VB-coded postings)
# #     terms.lex     (JSONL: {term, offset, length, df})
# #     docmap.json   (string<->int docID mapping)
# #     meta.json     (format metadata)

# import os
# import json
# from typing import Dict, List, Tuple, Any, BinaryIO

# # -------------------------
# # Variable-Byte (VB) coding
# # -------------------------

# def _vb_encode_number(n: int) -> bytes:
#     if n < 0:
#         raise ValueError("VB encode only supports non-negative integers")
#     out = bytearray()
#     while True:
#         chunk = n & 0x7F
#         n >>= 7
#         if n == 0:
#             out.append(0x80 | chunk)  # last byte (MSB=1)
#             break
#         else:
#             out.append(chunk)         # continuation (MSB=0)
#     return bytes(out)

# def _vb_encode_list(nums: List[int]) -> bytes:
#     out = bytearray()
#     for x in nums:
#         out.extend(_vb_encode_number(x))
#     return bytes(out)

# # -------------------------
# # Gap encoding helpers
# # -------------------------

# def _gaps_from_sorted(nums: List[int]) -> List[int]:
#     # base 0: first gap equals first absolute value
#     if not nums:
#         return []
#     gaps: List[int] = []
#     prev = 0
#     for i, v in enumerate(nums):
#         if i == 0:
#             gaps.append(v)
#         else:
#             gaps.append(v - prev)
#         prev = v
#     return gaps

# # -------------------------
# # Helpers for compression
# # -------------------------

# def _collect_all_docids(index: Dict[str, Dict[str, List[int]]]) -> List[str]:
#     docids = set()
#     for postings in index.values():
#         for doc_id in postings.keys():
#             docids.add(doc_id)
#     return sorted(docids)

# def _build_docid_maps(docids_sorted: List[str]) -> Tuple[Dict[str, int], List[str]]:
#     doc_to_int = {d: i for i, d in enumerate(docids_sorted)}
#     int_to_doc = list(docids_sorted)
#     return doc_to_int, int_to_doc

# def _encode_term_postings(term_postings: Dict[str, List[int]],
#                           doc_to_int: Dict[str, int]) -> Tuple[bytes, int]:
#     """
#     Per-term binary slice layout (must match decompressor):
#       VB(df)
#       For each document (ascending integer docID):
#         VB(doc_gap)
#         VB(tf)
#         VB(pos_gap_1) ... VB(pos_gap_tf)
#     """
#     items = []
#     for doc_str, pos_list in term_postings.items():
#         int_id = doc_to_int[doc_str]
#         pos_sorted = sorted(pos_list)
#         items.append((int_id, pos_sorted))
#     items.sort(key=lambda x: x[0])  # sort by integer docID

#     df = len(items)
#     out = bytearray()
#     out.extend(_vb_encode_number(df))  # DF

#     int_ids = [it[0] for it in items]
#     doc_gaps = _gaps_from_sorted(int_ids)

#     for (doc_gap, (_, pos_sorted)) in zip(doc_gaps, items):
#         out.extend(_vb_encode_number(doc_gap))  # doc gap
#         tf = len(pos_sorted)
#         out.extend(_vb_encode_number(tf))       # term frequency
#         if tf > 0:
#             pos_gaps = _gaps_from_sorted(pos_sorted)  # base 0 within each doc
#             out.extend(_vb_encode_list(pos_gaps))      # positions as gaps

#     return bytes(out), df

# # -------------------------
# # Public API
# # -------------------------

# def compress_index(path_to_index_file: str, path_to_compressed_files_directory: str) -> None:
#     """
#     Reads logical index.json (term -> {doc_id_str: [positions]}) and writes compressed artifacts:
#       <COMPRESSED_DIR>/postings.dat  (binary VB-coded postings)
#       <COMPRESSED_DIR>/terms.lex     (jsonlines: {term, offset, length, df})
#       <COMPRESSED_DIR>/docmap.json   (string<->int docID maps)
#       <COMPRESSED_DIR>/meta.json     (format metadata)
#     """
#     # Load logical inverted index
#     with open(path_to_index_file, "r", encoding="utf-8") as f:
#         index: Dict[str, Dict[str, List[int]]] = json.load(f)

#     outdir = path_to_compressed_files_directory
#     os.makedirs(outdir, exist_ok=True)

#     postings_path = os.path.join(outdir, "postings.dat")
#     terms_lex_path = os.path.join(outdir, "terms.lex")
#     docmap_path = os.path.join(outdir, "docmap.json")
#     meta_path = os.path.join(outdir, "meta.json")

#     # Build and save docID mappings
#     all_docids = _collect_all_docids(index)
#     doc_to_int, int_to_doc = _build_docid_maps(all_docids)
#     with open(docmap_path, "w", encoding="utf-8") as f:
#         json.dump(
#             {"doc_to_int": doc_to_int, "int_to_doc": int_to_doc},
#             f, ensure_ascii=False, separators=(",", ":"), indent=2
#         )

#     # Compress postings per term in lexicographic order of terms
#     terms_sorted = sorted(index.keys())
#     offset = 0

#     with open(postings_path, "wb") as pfp, open(terms_lex_path, "w", encoding="utf-8") as lfp:
#         for term in terms_sorted:
#             term_postings = index[term]  # dict: str_docid -> [positions]
#             blob, df = _encode_term_postings(term_postings, doc_to_int)
#             length = len(blob)
#             # write slice
#             pfp.write(blob)
#             # record lex entry with precise byte offset and length
#             lex_entry = {"term": term, "offset": offset, "length": length, "df": df}
#             lfp.write(json.dumps(lex_entry, ensure_ascii=False) + "\n")
#             offset += length

#     # Metadata for sanity
#     meta = {
#         "format_version": 1,
#         "encoding": "VB",
#         "has_positions": True,
#         "doc_base": 0  # first gap equals first absolute int docID
#     }
#     with open(meta_path, "w", encoding="utf-8") as f:
#         json.dump(meta, f, ensure_ascii=False, separators=(",", ":"), indent=2)

# # Optional CLI
# if __name__ == "__main__":
#     import sys
#     if len(sys.argv) != 3 and not (len(sys.argv) == 4 and sys.argv[1] == "compress"):
#         print(
#             "Usage:\n"
#             "  python compress_index.py <PATH_TO_INDEX_JSON> <COMPRESSED_DIR>\n"
#             "  or\n"
#             "  python compress_index.py compress <PATH_TO_INDEX_JSON> <COMPRESSED_DIR>\n",
#             flush=True
#         )
#         raise SystemExit(1)

#     if len(sys.argv) == 3:
#         index_json = sys.argv[1]
#         comp_dir = sys.argv[2]
#     else:
#         index_json = sys.argv[2]
#         comp_dir = sys.argv[3]

#     compress_index(index_json, comp_dir)
#     print(f"Compressed index written to: {comp_dir}")



import json
import struct
import os
from typing import Dict, List, Any

def variable_byte_encode(number: int) -> bytes:
    """
    Encode a single integer using variable-byte encoding.
    Each byte uses 7 bits for data and 1 bit as continuation flag.
    """
    if number == 0:
        return bytes([128])  # 10000000 - continuation bit set for single byte
    
    result = []
    while number >= 128:
        result.append((number % 128))  # Store lower 7 bits
        number //= 128
    result.append(number + 128)  # Set continuation bit for the last byte
    
    return bytes(result)

def variable_byte_encode_list(numbers: List[int]) -> bytes:
    """
    Encode a list of integers using variable-byte encoding.
    """
    result = b''
    for num in numbers:
        result += variable_byte_encode(num)
    return result

def delta_encode(numbers: List[int]) -> List[int]:
    """
    Apply delta encoding to a sorted list of integers.
    First number stays the same, subsequent numbers become differences.
    """
    if not numbers:
        return []
    
    result = [numbers[0]]
    for i in range(1, len(numbers)):
        result.append(numbers[i] - numbers[i-1])
    return result

def compress_index(path_to_index_file: str, path_to_compressed_files_directory: str) -> None:
    """
    Compress the inverted index using variable-byte encoding with delta compression.
    
    File Layout:
    - doc_mapping.bin: Binary file with document ID mappings
    - terms.txt: List of terms in order
    - compressed_data.bin: Binary compressed postings data
    - metadata.json: Metadata about compression
    """
    # Create output directory if it doesn't exist
    os.makedirs(path_to_compressed_files_directory, exist_ok=True)
    
    print("Loading index file...")
    # Load the original index
    with open(path_to_index_file, 'r', encoding='utf-8') as f:
        index = json.load(f)
    
    print("Creating document ID mappings...")
    # Create mappings for document IDs
    all_doc_ids = set()
    for term_data in index.values():
        all_doc_ids.update(term_data.keys())
    
    # Sort doc_ids lexicographically and create mapping
    sorted_doc_ids = sorted(all_doc_ids)
    doc_id_to_int = {doc_id: i for i, doc_id in enumerate(sorted_doc_ids)}
    
    print(f"Found {len(sorted_doc_ids)} unique document IDs")
    
    # Save the doc_id mapping as binary file for better compression
    doc_mapping_path = os.path.join(path_to_compressed_files_directory, 'doc_mapping.bin')
    with open(doc_mapping_path, 'wb') as f:
        # Write number of documents
        f.write(struct.pack('I', len(sorted_doc_ids)))
        # Write each doc_id with its length
        for doc_id in sorted_doc_ids:
            doc_id_bytes = doc_id.encode('utf-8')
            f.write(struct.pack('I', len(doc_id_bytes)))
            f.write(doc_id_bytes)
    
    print("Compressing index data...")
    # Sort terms lexicographically
    sorted_terms = sorted(index.keys())
    
    # Save terms list
    terms_path = os.path.join(path_to_compressed_files_directory, 'terms.txt')
    with open(terms_path, 'w', encoding='utf-8') as f:
        for term in sorted_terms:
            f.write(term + '\n')
    
    # Compress the postings data
    compressed_data_path = os.path.join(path_to_compressed_files_directory, 'compressed_data.bin')
    metadata = {}
    
    with open(compressed_data_path, 'wb') as f:
        current_offset = 0
        
        for term in sorted_terms:
            postings = index[term]
            
            # Convert doc_ids to integers and sort them
            doc_int_postings = []
            for doc_id, positions in postings.items():
                doc_int = doc_id_to_int[doc_id]
                doc_int_postings.append((doc_int, positions))
            
            # Sort by document integer ID
            doc_int_postings.sort(key=lambda x: x[0])
            
            # Separate doc_ids and positions
            doc_ids = [item[0] for item in doc_int_postings]
            positions_lists = [item[1] for item in doc_int_postings]
            
            # Apply delta encoding to doc_ids (they're sorted)
            delta_doc_ids = delta_encode(doc_ids)
            
            # Encode doc_ids using variable-byte encoding
            encoded_doc_ids = variable_byte_encode_list(delta_doc_ids)
            
            # Encode positions lists
            encoded_positions_data = b''
            positions_offsets = []
            
            for pos_list in positions_lists:
                # Apply delta encoding to positions (they're already sorted)
                delta_positions = delta_encode(pos_list)
                # Encode using variable-byte
                encoded_pos = variable_byte_encode_list(delta_positions)
                
                positions_offsets.append(len(encoded_positions_data))
                encoded_positions_data += encoded_pos
            
            # Write the compressed data for this term
            term_start_offset = current_offset
            
            # Write number of documents for this term
            f.write(struct.pack('I', len(doc_ids)))
            current_offset += 4
            
            # Write length of encoded doc_ids
            f.write(struct.pack('I', len(encoded_doc_ids)))
            current_offset += 4
            
            # Write encoded doc_ids
            f.write(encoded_doc_ids)
            current_offset += len(encoded_doc_ids)
            
            # Write positions offsets
            encoded_offsets = variable_byte_encode_list(positions_offsets + [len(encoded_positions_data)])
            f.write(struct.pack('I', len(encoded_offsets)))
            f.write(encoded_offsets)
            current_offset += 4 + len(encoded_offsets)
            
            # Write encoded positions data
            f.write(struct.pack('I', len(encoded_positions_data)))
            f.write(encoded_positions_data)
            current_offset += 4 + len(encoded_positions_data)
            
            # Store metadata for this term
            metadata[term] = {
                'offset': term_start_offset,
                'num_docs': len(doc_ids)
            }
    
    # Save metadata
    metadata_path = os.path.join(path_to_compressed_files_directory, 'metadata.json')
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    # Calculate and report compression statistics
    original_size = os.path.getsize(path_to_index_file)
    compressed_size = 0
    for file in os.listdir(path_to_compressed_files_directory):
        file_path = os.path.join(path_to_compressed_files_directory, file)
        if os.path.isfile(file_path):
            compressed_size += os.path.getsize(file_path)
    
    compression_ratio = compressed_size / original_size
    
    print(f"\nCompression completed successfully!")
    print(f"Original index size: {original_size:,} bytes")
    print(f"Compressed size: {compressed_size:,} bytes")
    print(f"Compression ratio: {compression_ratio:.3f}")
    print(f"Space saved: {((1 - compression_ratio) * 100):.1f}%")
    print(f"Files created:")
    print(f"  - doc_mapping.bin: Document ID mappings")
    print(f"  - terms.txt: Term vocabulary")
    print(f"  - compressed_data.bin: Compressed postings")
    print(f"  - metadata.json: Index metadata")

if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) != 3:
        print("Usage: python compress_index.py <path_to_index_file> <compressed_files_directory>")
        sys.exit(1)
    
    index_file = sys.argv[1]
    compressed_dir = sys.argv[2]
    
    if not os.path.exists(index_file):
        print(f"Error: Index file '{index_file}' not found!")
        sys.exit(1)
    
    compress_index(index_file, compressed_dir)