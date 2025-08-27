import json
import os
import struct
import zlib
from typing import Dict, List, Any

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


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python decompress.py <compressed_dir> <output_index.json>")
        sys.exit(1)

    compressed_dir = sys.argv[1]
    output_file = sys.argv[2]

    decompress_index(compressed_dir, output_file)
