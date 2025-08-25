import json
import os
import re
from typing import Dict, List, Set, Any, Union
from query_parser import BooleanQueryParser, ASTNode

def load_stopwords(stopwords_file: str) -> Set[str]:
    """Load stopwords from file with encoding detection."""
    stopwords = set()
    
    encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'latin-1', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(stopwords_file, "r", encoding=encoding) as f:
                for line in f:
                    w = line.strip().lower()
                    if w:
                        stopwords.add(w)
            return stopwords
        except UnicodeDecodeError:
            continue
        except Exception:
            continue
    
    raise ValueError(f"Could not decode {stopwords_file} with any common encoding")

def remove_non_ascii(s: str) -> str:
    """Keep only ASCII characters."""
    return ''.join(c for c in s if ord(c) < 128)

def tokenize_query_text(text: str, stopwords: Set[str]) -> List[str]:
    """Tokenize query text using Task 1 rules."""
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
    """Insert implicit AND operators between consecutive non-operator tokens."""
    if not tokens:
        return tokens
    
    operators = {'AND', 'OR', 'NOT'}
    result = []
    
    for i, token in enumerate(tokens):
        result.append(token)
        
        if i == len(tokens) - 1:
            continue
            
        current_token = token
        next_token = tokens[i + 1]
        
        should_insert_and = True
        
        if current_token in {'AND', 'OR'}:
            should_insert_and = False
        elif next_token in {'AND', 'OR'}:
            should_insert_and = False
        elif current_token == '(':
            should_insert_and = False
        elif next_token == ')':
            should_insert_and = False
        elif current_token == 'NOT':
            should_insert_and = False
        
        if should_insert_and:
            result.append('AND')
    
    return result

def preprocess_query_title(title: str, stopwords: Set[str]) -> List[str]:
    """Preprocess a query title into tokenized form with implicit ANDs."""
    # Protect operators and parentheses
    title_protected = title
    title_protected = re.sub(r'\bAND\b', ' __AND__ ', title_protected, flags=re.IGNORECASE)
    title_protected = re.sub(r'\bOR\b', ' __OR__ ', title_protected, flags=re.IGNORECASE)
    title_protected = re.sub(r'\bNOT\b', ' __NOT__ ', title_protected, flags=re.IGNORECASE)
    title_protected = title_protected.replace('(', ' __LPAREN__ ')
    title_protected = title_protected.replace(')', ' __RPAREN__ ')
    
    # Tokenize
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

class BooleanRetrieval:
    """Boolean retrieval system using inverted index and query evaluation."""
    
    def __init__(self, inverted_index: Dict[str, Dict[str, List[int]]], stopwords_file: str = None):
        """
        Initialize Boolean retrieval system.
        
        Args:
            inverted_index: Dictionary mapping terms to {doc_id: [positions]}
            stopwords_file: Path to stopwords file (optional)
        """
        self.inverted_index = inverted_index
        self.parser = BooleanQueryParser()
        self.stopwords = set()
        
        if stopwords_file and os.path.exists(stopwords_file):
            self.stopwords = load_stopwords(stopwords_file)
    
    def get_documents_for_term(self, term: str) -> Set[str]:
        """Get all document IDs containing a specific term."""
        if term in self.inverted_index:
            return set(self.inverted_index[term].keys())
        return set()
    
    def evaluate_ast_boolean(self, node: ASTNode) -> Set[str]:
        """
        Recursively evaluate AST to get matching document IDs.
        
        Args:
            node: AST node to evaluate
            
        Returns:
            Set of document IDs that match the query
        """
        if node.is_term():
            # Return documents containing this term
            return self.get_documents_for_term(node.value)
        
        elif node.value == 'NOT':
            # Get all documents, then subtract those matching the right operand
            right_docs = self.evaluate_ast_boolean(node.right)
            
            # Get all document IDs from the index
            all_docs = set()
            for term_postings in self.inverted_index.values():
                all_docs.update(term_postings.keys())
            
            return all_docs - right_docs
        
        elif node.value == 'AND':
            # Intersection of left and right results
            left_docs = self.evaluate_ast_boolean(node.left)
            right_docs = self.evaluate_ast_boolean(node.right)
            return left_docs & right_docs
        
        elif node.value == 'OR':
            # Union of left and right results
            left_docs = self.evaluate_ast_boolean(node.left)
            right_docs = self.evaluate_ast_boolean(node.right)
            return left_docs | right_docs
        
        else:
            raise ValueError(f"Unknown operator: {node.value}")
    
    def execute_query(self, query_title: str) -> Set[str]:
        """
        Execute a single Boolean query and return matching document IDs.
        
        Args:
            query_title: Raw query title string
            
        Returns:
            Set of matching document IDs
        """
        try:
            # Step 1: Tokenize using Task 1 rules
            tokens = preprocess_query_title(query_title, self.stopwords)
            
            if not tokens:
                return set()
            
            # Step 2: Parse query (implicit ANDs already inserted)
            parsed_result = self.parser.parse_query(tokens)
            ast = parsed_result['ast']
            
            # Step 3: Evaluate AST using postings lists
            matching_docs = self.evaluate_ast_boolean(ast)
            
            return matching_docs
            
        except Exception as e:
            print(f"Error executing query '{query_title}': {e}")
            return set()
    
    def process_queries(self, query_file_path: str, output_dir: str):
        """
        Process all queries from file and generate TREC format output.
        
        Args:
            query_file_path: Path to query JSON file
            output_dir: Directory to save docids.txt
        """
        # Load queries
        encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'latin-1', 'cp1252']
        content = None
        
        for encoding in encodings:
            try:
                with open(query_file_path, 'r', encoding=encoding) as f:
                    content = f.read().strip()
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            raise ValueError(f"Could not decode {query_file_path}")
        
        # Parse JSON
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
            raise ValueError(f"JSON parsing error: {e}")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'docids.txt')
        
        results = []
        
        # Process each query
        for query in queries:
            query_id = query.get('query_id', '')
            title = query.get('title', '')
            
            if not query_id or not title:
                continue
            
            print(f"Processing query {query_id}: {title}")
            
            # Execute query
            matching_docs = self.execute_query(title)
            
            # Sort document IDs lexicographically for ranking
            sorted_docs = sorted(matching_docs)
            
            # Generate TREC format lines
            for rank, doc_id in enumerate(sorted_docs, 1):
                results.append({
                    'qid': query_id,
                    'docid': doc_id,
                    'rank': rank,
                    'score': 1  # Constant score for Boolean retrieval
                })
            
            print(f"  Found {len(matching_docs)} matching documents")
        
        # Write results to file
        with open(output_file, 'w', encoding='utf-8') as f:
            for result in results:
                f.write(f"{result['qid']} {result['docid']} {result['rank']} {result['score']}\n")
        
        print(f"\nResults written to: {output_file}")
        print(f"Total result lines: {len(results)}")

def boolean_retrieval(inverted_index: object, path_to_query_file: str, output_dir: str) -> None:
    """
    Main Boolean retrieval function as specified in the assignment.
    
    Args:
        inverted_index: Inverted index object (dictionary)
        path_to_query_file: Path to query JSON file
        output_dir: Output directory for docids.txt
    """
    # Create retrieval system
    retrieval_system = BooleanRetrieval(inverted_index)
    
    # Process queries and generate output
    retrieval_system.process_queries(path_to_query_file, output_dir)

def load_inverted_index(index_file_path: str) -> Dict[str, Dict[str, List[int]]]:
    """Load inverted index from JSON file."""
    encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'latin-1', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(index_file_path, 'r', encoding=encoding) as f:
                return json.load(f)
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"Error with {encoding}: {e}")
            continue
    
    raise ValueError(f"Could not load index from {index_file_path}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 4:
        print("Usage: python boolean_retrieval.py <index_file> <query_file> <output_dir>")
        print("\nExample:")
        print('python boolean_retrieval.py "index.json" "queries.json" "output"')
        sys.exit(1)
    
    index_file = sys.argv[1]
    query_file = sys.argv[2]
    output_directory = sys.argv[3]
    
    try:
        # Load inverted index
        print(f"Loading inverted index from: {index_file}")
        index = load_inverted_index(index_file)
        print(f"Loaded index with {len(index)} terms")
        
        # Execute Boolean retrieval
        print(f"\nProcessing queries from: {query_file}")
        boolean_retrieval(index, query_file, output_directory)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)