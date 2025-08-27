import json
import os
import struct
import zlib
from typing import Dict, List

def variable_byte_encode(numbers: List[int]) -> bytes:
    result = bytearray()
    for num in numbers:
        if num == 0:
            result.append(128)
            continue
        bytes_for_num = []
        while num >= 128:
            bytes_for_num.append(num % 128)
            num //= 128
        bytes_for_num.append(num)
        for i in range(len(bytes_for_num) - 1):
            result.append(bytes_for_num[i])
        result.append(bytes_for_num[-1] | 128)
    return bytes(result)

def delta_encode(numbers: List[int]) -> List[int]:
    if not numbers:
        return []
    result = [numbers[0]]
    for i in range(1, len(numbers)):
        result.append(numbers[i] - numbers[i-1])
    return result


def compress_index(path_to_index_file: str, path_to_compressed_files_directory: str) -> None:
    os.makedirs(path_to_compressed_files_directory, exist_ok=True)

    with open(path_to_index_file, 'r', encoding='utf-8') as f:
        index = json.load(f)

    all_docids = set()
    for term_data in index.values():
        all_docids.update(term_data.keys())
    sorted_docids = sorted(all_docids)
    docid_to_int = {docid: i for i, docid in enumerate(sorted_docids)}
    int_to_docid = {i: docid for docid, i in docid_to_int.items()}


    with open(os.path.join(path_to_compressed_files_directory, 'docid_mapping.json'), 'w', encoding='utf-8') as f:
        json.dump(int_to_docid, f)

    compressed_index = {}
    for term, postings in index.items():
        int_postings = [(docid_to_int[docid], positions) for docid, positions in postings.items()]
        int_postings.sort(key=lambda x: x[0])

        docids = [p[0] for p in int_postings]
        all_positions = [p[1] for p in int_postings]

        delta_docids = delta_encode(docids)
        encoded_docids = variable_byte_encode(delta_docids)

        encoded_positions_list = []
        for positions in all_positions:
            if positions:
                sorted_positions = sorted(positions)
                delta_positions = delta_encode(sorted_positions)
                encoded_positions = variable_byte_encode(delta_positions)
                encoded_positions_list.append(encoded_positions)
            else:
                encoded_positions_list.append(b'')

        compressed_index[term] = {
            'docids': encoded_docids,
            'positions': encoded_positions_list,
            'doc_count': len(int_postings)
        }

    compressed_data = {}
    for term, data in compressed_index.items():
        positions_data = b''.join([struct.pack('<I', len(pos)) + pos for pos in data['positions']])
        compressed_data[term] = {
            'docids': data['docids'],
            'positions_data': positions_data,
            'doc_count': data['doc_count']
        }

    with open(os.path.join(path_to_compressed_files_directory, 'terms.json'), 'w', encoding='utf-8') as f:
        json.dump(list(index.keys()), f)

    binary_file = os.path.join(path_to_compressed_files_directory, 'compressed_index.bin')
    with open(binary_file, 'wb') as f:
        serialized_data = json.dumps(compressed_data, default=lambda x: x.hex() if isinstance(x, bytes) else x)
        compressed_binary = zlib.compress(serialized_data.encode('utf-8'), level=9)
        f.write(compressed_binary)

    metadata = {
        'total_terms': len(index),
        'total_docids': len(sorted_docids),
        'compression_method': 'variable_byte_delta_zlib'
    }
    with open(os.path.join(path_to_compressed_files_directory, 'metadata.json'), 'w', encoding='utf-8') as f:
        json.dump(metadata, f)

    print(f"Compression complete. Files saved to {path_to_compressed_files_directory}")
