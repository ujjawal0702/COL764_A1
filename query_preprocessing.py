import json
import re
from typing import List, Set

def load_stopwords(stopwords_file: str) -> Set[str]:
    """Load stopwords from file with encoding detection."""
    stopwords = set()
    
    # Try different encodings
    encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'latin-1', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(stopwords_file, "r", encoding=encoding) as f:
                for line in f:
                    w = line.strip().lower()
                    if w:
                        stopwords.add(w)
            print(f"Successfully loaded stopwords using {encoding} encoding")
            return stopwords
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"Error with {encoding}: {e}")
            continue
    
    raise ValueError(f"Could not decode {stopwords_file} with any common encoding")

def remove_non_ascii(s: str) -> str:
    """Keep only ASCII characters."""
    return ''.join(c for c in s if ord(c) < 128)

def tokenize_query_text(text: str, stopwords: Set[str]) -> List[str]:
    """
    Tokenize query text using the same process as document tokenization.
    1. Remove digits
    2. Lowercase
    3. Split on whitespace
    4. Remove non-ASCII characters
    5. Remove stopwords
    """
    # Remove digits (0-9)
    text = ''.join(c for c in text if not c.isdigit())
    
    # Handle escape characters
    text = text.replace('"', r'\"')
    text = text.replace('\\', r'\\')
    
    # Split on whitespace
    tokens = text.split()
    
    clean_tokens = []
    for token in tokens:
        # Lowercase
        token = token.lower()
        # Remove non-ASCII characters
        token = remove_non_ascii(token)
        # Keep token if it's not empty and not a stopword
        if token and token not in stopwords:
            clean_tokens.append(token)
    
    return clean_tokens

def insert_implicit_ands(tokens: List[str]) -> List[str]:
    """
    Insert implicit AND operators between consecutive non-operator tokens.
    
    Rules:
    - Insert AND between two consecutive tokens that are not operators
    - Insert AND between ) and a token
    - Insert AND between a token and (
    - Don't insert AND around operators (AND, OR, NOT)
    """
    if not tokens:
        return tokens
    
    operators = {'AND', 'OR', 'NOT'}
    result = []
    
    for i, token in enumerate(tokens):
        result.append(token)
        
        # Don't add AND after the last token
        if i == len(tokens) - 1:
            continue
            
        current_token = token
        next_token = tokens[i + 1]
        
        # Cases where we DON'T insert AND:
        # 1. Current token is an operator (except NOT when followed by non-operator)
        # 2. Next token is an operator (except NOT)
        # 3. Current token is '('
        # 4. Next token is ')'
        
        should_insert_and = True
        
        # Don't insert AND if current token is AND or OR
        if current_token in {'AND', 'OR'}:
            should_insert_and = False
        
        # Don't insert AND if next token is AND or OR
        elif next_token in {'AND', 'OR'}:
            should_insert_and = False
        
        # Don't insert AND if current token is '('
        elif current_token == '(':
            should_insert_and = False
        
        # Don't insert AND if next token is ')'
        elif next_token == ')':
            should_insert_and = False
        
        # Special case: NOT followed by non-operator should have AND inserted before NOT
        # But NOT followed by anything else should not have AND after it
        elif current_token == 'NOT':
            should_insert_and = False
        
        if should_insert_and:
            result.append('AND')
    
    return result

def normalize_operators(tokens: List[str]) -> List[str]:
    """
    Normalize operators to uppercase and handle parentheses.
    """
    operators = {'and', 'or', 'not'}
    result = []
    
    for token in tokens:
        # Check if token is an operator (case-insensitive)
        if token.lower() in operators:
            result.append(token.upper())
        # Keep parentheses as-is
        elif token in {'(', ')'}:
            result.append(token)
        else:
            result.append(token)
    
    return result

def preprocess_query_title(title: str, stopwords: Set[str]) -> List[str]:
    """
    Preprocess a query title string into tokenized form with implicit ANDs.
    
    Steps:
    1. Tokenize using the same process as documents
    2. Normalize operators (case-insensitive -> uppercase)
    3. Insert implicit AND operators
    """
    # First, we need to handle operators and parentheses before tokenization
    # to preserve them during the tokenization process
    
    # Replace operators with placeholders to protect them during tokenization
    title_protected = title
    
    # Protect parentheses and operators (case-insensitive)
    title_protected = re.sub(r'\bAND\b', ' __AND__ ', title_protected, flags=re.IGNORECASE)
    title_protected = re.sub(r'\bOR\b', ' __OR__ ', title_protected, flags=re.IGNORECASE)
    title_protected = re.sub(r'\bNOT\b', ' __NOT__ ', title_protected, flags=re.IGNORECASE)
    title_protected = title_protected.replace('(', ' __LPAREN__ ')
    title_protected = title_protected.replace(')', ' __RPAREN__ ')
    
    # Tokenize the protected text
    tokens = tokenize_query_text(title_protected, stopwords)
    
    # Restore operators and parentheses
    restored_tokens = []
    for token in tokens:
        if token == '__and__':
            restored_tokens.append('AND')
        elif token == '__or__':
            restored_tokens.append('OR')
        elif token == '__not__':
            restored_tokens.append('NOT')
        elif token == '__lparen__':
            restored_tokens.append('(')
        elif token == '__rparen__':
            restored_tokens.append(')')
        else:
            restored_tokens.append(token)
    
    # Insert implicit ANDs
    tokens_with_ands = insert_implicit_ands(restored_tokens)
    
    return tokens_with_ands

def preprocess_queries(query_file_path: str, stopwords_file: str) -> dict:
    """
    Preprocess all queries from the query file.
    
    Args:
        query_file_path: Path to the test_queries.json file
        stopwords_file: Path to the stopwords.txt file
    
    Returns:
        Dictionary mapping query_id to preprocessed tokens
    """
    # Load stopwords
    stopwords = load_stopwords(stopwords_file)
    
    # Load queries with encoding detection
    encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'latin-1', 'cp1252']
    content = None
    
    for encoding in encodings:
        try:
            with open(query_file_path, 'r', encoding=encoding) as f:
                content = f.read().strip()
            print(f"Successfully loaded queries using {encoding} encoding")
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"Error with {encoding}: {e}")
            continue
    
    if content is None:
        raise ValueError(f"Could not decode {query_file_path} with any common encoding")
    
    # Handle both array format and line-by-line JSON format
    try:
        if content.startswith('['):
            queries = json.loads(content)
        else:
            queries = []
            for line in content.splitlines():
                line = line.strip()
                if line:
                    queries.append(json.loads(line))
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"First 200 characters of content: {content[:200]}")
        raise
    
    # Preprocess each query
    preprocessed_queries = {}
    
    for query in queries:
        query_id = query.get('query_id')
        title = query.get('title', '')
        
        if query_id and title:
            # Preprocess the title
            preprocessed_tokens = preprocess_query_title(title, stopwords)
            preprocessed_queries[query_id] = {
                'original_title': title,
                'preprocessed_tokens': preprocessed_tokens,
                'preprocessed_string': ' '.join(preprocessed_tokens)
            }
    
    return preprocessed_queries

# Test function to demonstrate the preprocessing
def test_query_preprocessing():
    """Test the query preprocessing with examples from the assignment."""
    
    # Mock stopwords for testing
    test_stopwords = {'the', 'at', 'is', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'to'}
    
    # Test cases from the assignment
    test_cases = [
        "coronavirus origin",  # Should become: coronavirus AND origin
        "jaguar NOT car",      # Should become: jaguar AND NOT car
        "(information retrieval) OR indexing",  # Should become: (information AND retrieval) OR indexing
    ]
    
    print("Testing Query Preprocessing:")
    print("=" * 50)
    
    for i, title in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        print(f"Original: {title}")
        
        tokens = preprocess_query_title(title, test_stopwords)
        result = ' '.join(tokens)
        
        print(f"Preprocessed: {result}")
        print(f"Tokens: {tokens}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) == 1:
        # Run tests if no arguments provided
        test_query_preprocessing()
    elif len(sys.argv) >= 3:
        # Process actual query file
        query_file = sys.argv[1]
        stopwords_file = sys.argv[2]
        output_file = sys.argv[3] if len(sys.argv) >= 4 else None
        
        try:
            results = preprocess_queries(query_file, stopwords_file)
            
            print(f"Processed {len(results)} queries:")
            for query_id, data in results.items():
                print(f"\nQuery ID: {query_id}")
                print(f"Original: {data['original_title']}")
                print(f"Preprocessed: {data['preprocessed_string']}")
            
            # Save to file if output file is specified
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2)
                print(f"\nPreprocessed queries saved to: {output_file}")
        
        except Exception as e:
            print(f"Error processing queries: {e}")
    else:
        print("Usage:")
        print("  python query_preprocessing.py                    # Run tests")
        print("  python query_preprocessing.py <query_file> <stopwords_file> [output_file]  # Process queries")