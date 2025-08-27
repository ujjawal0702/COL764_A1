# # import os
# # import zlib
# # import pickle
# # import struct
# # import json
# # from typing import List, Dict, Tuple

# # # -------------------
# # # Helper Decoders
# # # -------------------
# # def read_variable_byte_number(data: bytes, offset: int):
# #     """
# #     Reads one variable-byte encoded number starting at offset.
# #     Returns (decoded_number, bytes_consumed).
# #     """
# #     n = 0
# #     shift = 0
# #     consumed = 0
# #     for i in range(offset, len(data)):
# #         byte = data[i]
# #         consumed += 1
# #         if byte & 0x80:  # last byte in this number
# #             n |= (byte & 0x7F) << shift
# #             return n, consumed
# #         else:
# #             n |= (byte & 0x7F) << shift
# #             shift += 7
# #     raise ValueError("Invalid variable-byte encoding")

# # def variable_byte_decode(data: bytes) -> List[int]:
# #     """Decode bytes using variable-byte encoding."""
# #     numbers = []
# #     n = 0
# #     shift = 0
# #     for byte in data:
# #         if byte & 0x80:  # last byte
# #             n |= (byte & 0x7F) << shift
# #             numbers.append(n)
# #             n = 0
# #             shift = 0
# #         else:
# #             n |= (byte & 0x7F) << shift
# #             shift += 7
# #     return numbers

# # def delta_decode(gaps: List[int]) -> List[int]:
# #     """Reconstruct numbers from delta encoding."""
# #     if not gaps:
# #         return []
# #     result = [gaps[0]]
# #     for gap in gaps[1:]:
# #         result.append(result[-1] + gap)
# #     return result

# # def decompress_with_method(data: bytes, method: str = 'zlib') -> bytes:
# #     """Reverse of compress_with_method."""
# #     if method == 'zlib':
# #         return zlib.decompress(data)
# #     elif method == 'lzma':
# #         import lzma
# #         return lzma.decompress(data)
# #     else:
# #         return data

# # # -------------------
# # # Term + Doc Decoding
# # # -------------------

# # def rebuild_terms(compressed_terms: bytes) -> List[str]:
# #     term_dict_data = pickle.loads(decompress_with_method(compressed_terms, 'zlib'))
# #     terms = []
# #     prev_term = ""
# #     for prefix_len, suffix in term_dict_data:
# #         term = prev_term[:prefix_len] + suffix
# #         terms.append(term)
# #         prev_term = term
# #     return terms

# # def rebuild_docs(compressed_docs: bytes) -> List[str]:
# #     try:
# #         # Try small-integer delta-coded version
# #         doc_data = decompress_with_method(compressed_docs, 'zlib')
# #         count = struct.unpack('<H', doc_data[:2])[0]
# #         gaps = list(struct.unpack(f'<{count}H', doc_data[2:]))
# #         int_doc_ids = delta_decode(gaps)
# #         return [str(doc_id) for doc_id in int_doc_ids]
# #     except Exception:
# #         # Fallback to prefix-coded string version
# #         doc_data = pickle.loads(decompress_with_method(compressed_docs, 'zlib'))
# #         docs = []
# #         prev_doc = ""
# #         for prefix_len, suffix in doc_data:
# #             doc = prev_doc[:prefix_len] + suffix
# #             docs.append(doc)
# #             prev_doc = doc
# #         return docs

# # # -------------------
# # # Postings Decoding
# # # -------------------
# # def read_variable_byte_number(data: bytes, offset: int) -> Tuple[int, int]:
# #     """
# #     Reads a single variable-byte encoded number from data starting at offset.
# #     Returns (number, bytes_consumed).
# #     """
# #     n = 0
# #     shift = 0
# #     consumed = 0
# #     for i in range(offset, len(data)):
# #         byte = data[i]
# #         consumed += 1
# #         if byte & 0x80:  # last byte
# #             n |= (byte & 0x7F) << shift
# #             return n, consumed
# #         else:
# #             n |= (byte & 0x7F) << shift
# #             shift += 7
# #     raise ValueError("Invalid variable-byte encoding")

# # def decompress_postings(compressed_postings: bytes, num_terms: int, doc_list: List[str], term_list: List[str]) -> Dict[str, Dict[str, List[int]]]:
# #     all_chunks = decompress_with_method(compressed_postings, 'zlib')
# #     offset = 0
# #     index = {}

# #     for t in range(num_terms):
# #         # Read metadata
# #         num_docs, vb_len = struct.unpack('<II', all_chunks[offset:offset+8])
# #         offset += 8

# #         vb_doc_ids = all_chunks[offset:offset+vb_len]
# #         offset += vb_len
# #         doc_ids = delta_decode(variable_byte_decode(vb_doc_ids))

# #         postings = {}
# #         for doc_id in doc_ids:
# #             # Decode positions (length prefix or raw)
# #             length_numbers = variable_byte_decode(all_chunks[offset:offset+5])  # safe slice
# #             if length_numbers:
# #                 count = length_numbers[0]
# #                 length_len = len(variable_byte_encode(count))
# #                 offset += length_len
# #                 vb_positions = all_chunks[offset:offset+len(all_chunks)]
# #                 pos_deltas = variable_byte_decode(vb_positions)
# #                 offset += len(vb_positions)
# #                 positions = delta_decode(pos_deltas)
# #             else:
# #                 positions = []
# #             postings[doc_list[doc_id]] = positions

# #         index[term_list[t]] = postings

# #     return index

# # # -------------------
# # # Main Decompressor
# # # -------------------

# # def decompress_index(path_to_compressed_files_directory: str, output_index_file: str) -> None:
# #     # Load compressed files
# #     with open(os.path.join(path_to_compressed_files_directory, 'docs.bin'), 'rb') as f:
# #         num_docs = struct.unpack('<I', f.read(4))[0]
# #         compressed_docs = f.read()
# #     with open(os.path.join(path_to_compressed_files_directory, 'terms.bin'), 'rb') as f:
# #         num_terms = struct.unpack('<I', f.read(4))[0]
# #         compressed_terms = f.read()
# #     with open(os.path.join(path_to_compressed_files_directory, 'postings.bin'), 'rb') as f:
# #         compressed_postings = f.read()
# #     with open(os.path.join(path_to_compressed_files_directory, 'meta.bin'), 'rb') as f:
# #         compressed_metadata = f.read()
# #         metadata = pickle.loads(decompress_with_method(compressed_metadata, 'zlib'))

# #     # Rebuild docs and terms
# #     doc_list = rebuild_docs(compressed_docs)
# #     term_list = rebuild_terms(compressed_terms)

# #     # Rebuild postings
# #     index = decompress_postings(compressed_postings, num_terms, doc_list, term_list)

# #     # Save decompressed index
# #     with open(output_index_file, 'w', encoding='utf-8') as f:
# #         json.dump(index, f, ensure_ascii=False, indent=2)

# #     print(f"Decompression complete. Restored index at {output_index_file}")
# # if __name__ == "__main__":
# #     import sys
# #     if len(sys.argv) < 3:
# #         print("Usage: python decompress.py <compressed_dir> <restored_index.json>")
# #         sys.exit(1)

# #     compressed_dir = sys.argv[1]
# #     output_file = sys.argv[2]

# #     decompress_index(compressed_dir, output_file)

# import json
# import os
# import struct
# import zlib
# from typing import Dict, List, Any

# # ---------------------------
# # Utility Decoding Functions
# # ---------------------------
# def variable_byte_decode(data: bytes) -> List[int]:
#     result = []
#     i = 0
#     while i < len(data):
#         num = 0
#         shift = 0
#         while i < len(data):
#             byte = data[i]
#             i += 1
#             if byte & 128:
#                 num += (byte & 127) << shift
#                 break
#             else:
#                 num += byte << shift
#                 shift += 7
#         result.append(num)
#     return result

# def delta_decode(deltas: List[int]) -> List[int]:
#     if not deltas:
#         return []
#     result = [deltas[0]]
#     for i in range(1, len(deltas)):
#         result.append(result[-1] + deltas[i])
#     return result

# # ---------------------------
# # Decompression
# # ---------------------------
# def decompress_index(compressed_index_dir: str) -> Dict[str, Any]:
#     with open(os.path.join(compressed_index_dir, 'docid_mapping.json'), 'r', encoding='utf-8') as f:
#         int_to_docid = {int(k): v for k, v in json.load(f).items()}

#     with open(os.path.join(compressed_index_dir, 'terms.json'), 'r', encoding='utf-8') as f:
#         terms = json.load(f)

#     binary_file = os.path.join(compressed_index_dir, 'compressed_index.bin')
#     with open(binary_file, 'rb') as f:
#         compressed_binary = f.read()
#         decompressed_data = zlib.decompress(compressed_binary).decode('utf-8')
#         compressed_index = json.loads(decompressed_data)

#     for term_data in compressed_index.values():
#         term_data['docids'] = bytes.fromhex(term_data['docids'])
#         term_data['positions_data'] = bytes.fromhex(term_data['positions_data'])

#     reconstructed_index = {}
#     for term in terms:
#         if term in compressed_index:
#             data = compressed_index[term]
#             delta_docids = variable_byte_decode(data['docids'])
#             docids = delta_decode(delta_docids)

#             positions_data = data['positions_data']
#             positions_list = []
#             offset = 0
#             for _ in range(data['doc_count']):
#                 if offset < len(positions_data):
#                     pos_length = struct.unpack('<I', positions_data[offset:offset+4])[0]
#                     offset += 4
#                     if pos_length > 0:
#                         pos_bytes = positions_data[offset:offset+pos_length]
#                         delta_positions = variable_byte_decode(pos_bytes)
#                         positions = delta_decode(delta_positions)
#                         positions_list.append(positions)
#                         offset += pos_length
#                     else:
#                         positions_list.append([])
#                 else:
#                     positions_list.append([])

#             term_postings = {}
#             for int_docid, positions in zip(docids, positions_list):
#                 string_docid = int_to_docid[int_docid]
#                 term_postings[string_docid] = positions
#             reconstructed_index[term] = term_postings

#     output_file = os.path.join(compressed_index_dir, 'decompressed_index.json')
#     with open(output_file, 'w', encoding='utf-8') as f:
#         json.dump(reconstructed_index, f, indent=2)

#     print(f"Decompression complete. Index saved to {output_file}")
#     return reconstructed_index

# if __name__ == "__main__":
#     import sys
#     if len(sys.argv) != 3:
#         print("Usage: python decompress.py <compressed_dir> <output_index.json>")
#         sys.exit(1)

#     compressed_dir = sys.argv[1]
#     output_file = sys.argv[2]

#     decompress_index(compressed_dir, output_file)

import json
import os
import struct
import zlib
from typing import Dict, List, Any

# ---------------------------
# Utility Decoding Functions
# ---------------------------
def variable_byte_decode(data: bytes) -> List[int]:
    result = []
    i = 0
    while i < len(data):
        num = 0
        shift = 0
        while i < len(data):
            byte = data[i]
            i += 1
            if byte & 128:
                num += (byte & 127) << shift
                break
            else:
                num += byte << shift
                shift += 7
        result.append(num)
    return result

def delta_decode(deltas: List[int]) -> List[int]:
    if not deltas:
        return []
    result = [deltas[0]]
    for i in range(1, len(deltas)):
        result.append(result[-1] + deltas[i])
    return result

# ---------------------------
# Decompression
# ---------------------------
def decompress_index(compressed_index_dir: str, output_file: str) -> Dict[str, Any]:
    with open(os.path.join(compressed_index_dir, 'docid_mapping.json'), 'r', encoding='utf-8') as f:
        int_to_docid = {int(k): v for k, v in json.load(f).items()}

    with open(os.path.join(compressed_index_dir, 'terms.json'), 'r', encoding='utf-8') as f:
        terms = json.load(f)

    binary_file = os.path.join(compressed_index_dir, 'compressed_index.bin')
    with open(binary_file, 'rb') as f:
        compressed_binary = f.read()
        decompressed_data = zlib.decompress(compressed_binary).decode('utf-8')
        compressed_index = json.loads(decompressed_data)

    for term_data in compressed_index.values():
        term_data['docids'] = bytes.fromhex(term_data['docids'])
        term_data['positions_data'] = bytes.fromhex(term_data['positions_data'])

    reconstructed_index = {}
    for term in terms:
        if term in compressed_index:
            data = compressed_index[term]
            delta_docids = variable_byte_decode(data['docids'])
            docids = delta_decode(delta_docids)

            positions_data = data['positions_data']
            positions_list = []
            offset = 0
            for _ in range(data['doc_count']):
                if offset < len(positions_data):
                    pos_length = struct.unpack('<I', positions_data[offset:offset+4])[0]
                    offset += 4
                    if pos_length > 0:
                        pos_bytes = positions_data[offset:offset+pos_length]
                        delta_positions = variable_byte_decode(pos_bytes)
                        positions = delta_decode(delta_positions)
                        positions_list.append(positions)
                        offset += pos_length
                    else:
                        positions_list.append([])
                else:
                    positions_list.append([])

            term_postings = {}
            for int_docid, positions in zip(docids, positions_list):
                string_docid = int_to_docid[int_docid]
                term_postings[string_docid] = positions
            reconstructed_index[term] = term_postings

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(reconstructed_index, f, indent=2)

    print(f"Decompression complete. Index saved to {output_file}")
    return reconstructed_index

# ---------------------------
# Run from Command Line
# ---------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python decompress.py <compressed_dir> <output_index.json>")
        sys.exit(1)

    compressed_dir = sys.argv[1]
    output_file = sys.argv[2]

    decompress_index(compressed_dir, output_file)
