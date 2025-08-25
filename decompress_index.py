import json
import struct
import os
from typing import Dict, List, Any

def variable_byte_decode_single(data: bytes, offset: int) -> tuple:
    """
    Decode a single integer from variable-byte encoded data.
    Returns (decoded_number, new_offset)
    """
    result = 0
    shift = 0
    
    while offset < len(data):
        byte = data[offset]
        offset += 1
        
        if byte >= 128:
            # This is the last byte (continuation bit is set)
            result += (byte - 128) << shift
            break
        else:
            # More bytes to come
            result += byte << shift
            shift += 7
    
    return result, offset

def variable_byte_decode_list(data: bytes) -> List[int]:
    """
    Decode a list of integers from variable-byte encoded data.
    """
    result = []
    offset = 0
    
    while offset < len(data):
        number, offset = variable_byte_decode_single(data, offset)
        result.append(number)
    
    return result

def delta_decode(deltas: List[int]) -> List[int]:
    """
    Decode delta-encoded integers back to original values.
    """
    if not deltas:
        return []
    
    result = [deltas[0]]
    for i in range(1, len(deltas)):
        result.append(result[-1] + deltas[i])
    return result

def load_doc_mapping(compressed_index_dir: str) -> List[str]:
    """
    Load document ID mapping from binary file.
    """
    doc_mapping_path = os.path.join(compressed_index_dir, 'doc_mapping.bin')
    
    with open(doc_mapping_path, 'rb') as f:
        # Read number of documents
        num_docs = struct.unpack('I', f.read(4))[0]
        
        doc_ids = []
        for _ in range(num_docs):
            # Read length of doc_id
            doc_id_len = struct.unpack('I', f.read(4))[0]
            # Read doc_id
            doc_id_bytes = f.read(doc_id_len)
            doc_id = doc_id_bytes.decode('utf-8')
            doc_ids.append(doc_id)
    
    return doc_ids

def load_terms(compressed_index_dir: str) -> List[str]:
    """
    Load terms list from terms.txt file.
    """
    terms_path = os.path.join(compressed_index_dir, 'terms.txt')
    
    terms = []
    with open(terms_path, 'r', encoding='utf-8') as f:
        for line in f:
            terms.append(line.strip())
    
    return terms

def decompress_index(compressed_index_dir: str) -> Dict[str, Any]:
    """
    Decompress the index back to its original format.
    Returns the inverted index as a dictionary object.
    """
    print("Loading compressed index components...")
    
    # Load document ID mapping
    doc_ids = load_doc_mapping(compressed_index_dir)
    print(f"Loaded {len(doc_ids)} document IDs")
    
    # Load terms
    terms = load_terms(compressed_index_dir)
    print(f"Loaded {len(terms)} terms")
    
    # Load metadata
    metadata_path = os.path.join(compressed_index_dir, 'metadata.json')
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    # Load compressed data
    compressed_data_path = os.path.join(compressed_index_dir, 'compressed_data.bin')
    
    print("Decompressing index data...")
    decompressed_index = {}
    
    with open(compressed_data_path, 'rb') as f:
        for term in terms:
            if term not in metadata:
                continue
                
            term_metadata = metadata[term]
            offset = term_metadata['offset']
            num_docs = term_metadata['num_docs']
            
            # Seek to the term's data
            f.seek(offset)
            
            # Read number of documents (should match metadata)
            stored_num_docs = struct.unpack('I', f.read(4))[0]
            assert stored_num_docs == num_docs, f"Document count mismatch for term '{term}'"
            
            # Read length of encoded doc_ids
            doc_ids_len = struct.unpack('I', f.read(4))[0]
            
            # Read encoded doc_ids
            encoded_doc_ids = f.read(doc_ids_len)
            
            # Read positions offsets length
            offsets_len = struct.unpack('I', f.read(4))[0]
            
            # Read encoded positions offsets
            encoded_offsets = f.read(offsets_len)
            
            # Read positions data length
            positions_data_len = struct.unpack('I', f.read(4))[0]
            
            # Read encoded positions data
            encoded_positions_data = f.read(positions_data_len)
            
            # Decode doc_ids
            delta_doc_ids = variable_byte_decode_list(encoded_doc_ids)
            original_doc_ids = delta_decode(delta_doc_ids)
            
            # Decode positions offsets
            positions_offsets = variable_byte_decode_list(encoded_offsets)
            
            # Decode positions for each document
            term_postings = {}
            
            for i in range(num_docs):
                doc_int = original_doc_ids[i]
                doc_id = doc_ids[doc_int]  # Map back to string
                
                # Extract positions data for this document
                start_offset = positions_offsets[i]
                end_offset = positions_offsets[i + 1]
                
                doc_positions_data = encoded_positions_data[start_offset:end_offset]
                
                # Decode positions
                if doc_positions_data:
                    delta_positions = variable_byte_decode_list(doc_positions_data)
                    original_positions = delta_decode(delta_positions)
                else:
                    original_positions = []
                
                term_postings[doc_id] = original_positions
            
            # Sort by doc_id lexicographically (should already be sorted)
            term_postings = dict(sorted(term_postings.items()))
            decompressed_index[term] = term_postings
    
    # Sort terms lexicographically (should already be sorted)
    decompressed_index = dict(sorted(decompressed_index.items()))
    
    print(f"Decompression completed! Reconstructed {len(decompressed_index)} terms")
    
    # Save the decompressed index as JSON file
    output_path = os.path.join(compressed_index_dir, 'decompressed_index.json')
    print(f"Saving decompressed index to: {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(decompressed_index, f, indent=2)
    
    print("Decompressed index saved successfully!")
    
    return decompressed_index

def verify_decompression(original_index_path: str, decompressed_index: Dict[str, Any]) -> bool:
    """
    Verify that the decompressed index matches the original index.
    """
    print("Verifying decompression accuracy...")
    
    # Load original index
    with open(original_index_path, 'r', encoding='utf-8') as f:
        original_index = json.load(f)
    
    # Compare keys (terms)
    original_terms = set(original_index.keys())
    decompressed_terms = set(decompressed_index.keys())
    
    if original_terms != decompressed_terms:
        print("ERROR: Term sets don't match!")
        print(f"Missing terms: {original_terms - decompressed_terms}")
        print(f"Extra terms: {decompressed_terms - original_terms}")
        return False
    
    # Compare postings for each term
    for term in original_terms:
        original_postings = original_index[term]
        decompressed_postings = decompressed_index[term]
        
        if original_postings != decompressed_postings:
            print(f"ERROR: Postings don't match for term '{term}'!")
            return False
    
    print("SUCCESS: Decompressed index matches original exactly!")
    return True

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python decompress_index.py <compressed_index_dir> [original_index_file]")
        sys.exit(1)
    
    compressed_dir = sys.argv[1]
    
    if not os.path.exists(compressed_dir):
        print(f"Error: Compressed directory '{compressed_dir}' not found!")
        sys.exit(1)
    
    # Decompress the index
    decompressed = decompress_index(compressed_dir)
    
    # If original index file provided, verify the decompression
    if len(sys.argv) >= 3:
        original_index_file = sys.argv[2]
        if os.path.exists(original_index_file):
            verify_decompression(original_index_file, decompressed)
        else:
            print(f"Warning: Original index file '{original_index_file}' not found. Skipping verification.")