import json
import re
import os
from typing import List, Dict, Set, Union, Optional
from collections import defaultdict
import sys


class BooleanQueryParser:
   
    
    def __init__(self):
     
        self.precedence = {'OR': 1, 'AND': 2, 'NOT': 3}
        self.right_associative = {'NOT'}
        
    def tokenize_query(self, query: str) -> List[str]:
       
        query = re.sub(r'([()])', r' \1 ', query)
        
      
        tokens = [token.strip() for token in query.split() if token.strip()]
        
        processed_tokens = []
        for token in tokens:
            if token.upper() in ['AND', 'OR', 'NOT']:
                processed_tokens.append(token.upper())
            elif token in ['(', ')']:
                processed_tokens.append(token)
            else:
                processed_tokens.append(token.lower())
                
        return processed_tokens
    
    def preprocess_query(self, title: str, stopwords: Set[str]) -> List[str]:
      
        tokens = self.tokenize_query(title)
        
        processed = []
        for token in tokens:
            if token in ['AND', 'OR', 'NOT', '(', ')']:
                processed.append(token)
            else:
               
                token = token.lower()
               
                token = re.sub(r'\d+', '', token)
              
                if token and token not in stopwords:
                    processed.append(token)
        
        return processed
    
    def insert_implicit_ands(self, tokens: List[str]) -> List[str]:
      
        if not tokens:
            return tokens
            
        result = []
        operators = {'AND', 'OR', 'NOT'}
        
        for i in range(len(tokens)):
            result.append(tokens[i])
            
          
            if i == len(tokens) - 1:
                break
                
            current = tokens[i]
            next_token = tokens[i + 1]
          
            should_insert_and = False
            
            if current not in operators and current != '(' and current != ')':
              
                if (next_token not in operators and next_token != ')') or next_token == '(' or next_token == 'NOT':
                    should_insert_and = True
            elif current == ')':
               
                if (next_token not in operators and next_token != ')') or next_token == '(' or next_token == 'NOT':
                    should_insert_and = True
                    
            if should_insert_and:
                result.append('AND')
                
        return result
    
    def infix_to_postfix(self, tokens: List[str]) -> List[str]:
       
        output = []
        operator_stack = []
        operators = {'AND', 'OR', 'NOT'}
        
        for token in tokens:
            if token not in operators and token not in ['(', ')']:
              
                output.append(token)
            elif token in operators:
                
                while (operator_stack and 
                       operator_stack[-1] != '(' and
                       operator_stack[-1] in operators and
                       (self.precedence[operator_stack[-1]] > self.precedence[token] or
                        (self.precedence[operator_stack[-1]] == self.precedence[token] and 
                         token not in self.right_associative))):
                    output.append(operator_stack.pop())
                operator_stack.append(token)
            elif token == '(':
                operator_stack.append(token)
            elif token == ')':
                while operator_stack and operator_stack[-1] != '(':
                    output.append(operator_stack.pop())
                if operator_stack and operator_stack[-1] == '(':
                    operator_stack.pop()  
                    
   
        while operator_stack:
            output.append(operator_stack.pop())
            
        return output
    
    def evaluate_postfix(self, postfix: List[str], inverted_index: Dict) -> Set[str]:
       
        stack = []
        
        for token in postfix:
            if token == 'AND':
                if len(stack) >= 2:
                    right = stack.pop()
                    left = stack.pop()
                    result = left.intersection(right)
                    stack.append(result)
                else:
                  
                    stack.append(set())
            elif token == 'OR':
                if len(stack) >= 2:
                    right = stack.pop()
                    left = stack.pop()
                    result = left.union(right)
                    stack.append(result)
                else:
                   
                    stack.append(set())
            elif token == 'NOT':
                if len(stack) >= 1:
                    operand = stack.pop()
                   
                    all_docs = set()
                    for term_postings in inverted_index.values():
                        all_docs.update(term_postings.keys())
                    result = all_docs - operand
                    stack.append(result)
                else:
                   
                    stack.append(set())
            else:
               
                if token in inverted_index:
                    
                    doc_ids = set(inverted_index[token].keys())
                    stack.append(doc_ids)
                else:
                   
                    stack.append(set())
        
        return stack[0] if stack else set()
    
    def parse_and_evaluate(self, query: str, inverted_index: Dict, stopwords: Set[str]) -> Set[str]:
       
        tokens = self.preprocess_query(query, stopwords)
        
        if not tokens:
            return set()
        
      
        tokens_with_ands = self.insert_implicit_ands(tokens)
        
       
        postfix = self.infix_to_postfix(tokens_with_ands)
        
      
        result = self.evaluate_postfix(postfix, inverted_index)
        
        return result


def load_inverted_index(index_path: str) -> Dict:
  
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                raise ValueError("Inverted index file is empty")
            return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"Error parsing inverted index JSON: {e}")
        print("Make sure your inverted index file is in valid JSON format")
        raise
    except FileNotFoundError:
        print(f"Inverted index file not found: {index_path}")
        raise
    except Exception as e:
        print(f"Unexpected error loading inverted index: {e}")
        raise


def load_stopwords(stopwords_path: str) -> Set[str]:
  
    stopwords = set()
    try:
        with open(stopwords_path, 'r') as f:
            for line in f:
                stopwords.add(line.strip().lower())
    except FileNotFoundError:
      
        stopwords = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'been', 'by', 'for', 
            'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 
            'the', 'to', 'was', 'will', 'with', 'the', 'this', 'but', 'they', 
            'have', 'had', 'what', 'said', 'each', 'which', 'she', 'do', 
            'how', 'their', 'if', 'up', 'out', 'many', 'then', 'them', 'these', 
            'so', 'some', 'her', 'would', 'make', 'like', 'into', 'him', 'time', 
            'two', 'more', 'very', 'when', 'come', 'may', 'its', 'only', 'think', 
            'now', 'work', 'life', 'only', 'can', 'still', 'should', 'after', 
            'being', 'just', 'where', 'much', 'go', 'well', 'were', 'been', 
            'through', 'when', 'there', 'could', 'people'
        }
    return stopwords


def load_queries(path_to_query_file: str):
   
    queries = []
    
  
    encodings = ['utf-8', 'utf-16', 'utf-8-sig', 'latin-1', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(path_to_query_file, 'r', encoding=encoding) as f:
                content = f.read().strip()
                if not content:
                    continue
                
               
                try:
                    queries = json.loads(content)
                    if isinstance(queries, list):
                       
                        valid_queries = []
                        for i, query in enumerate(queries):
                            if isinstance(query, dict):
                               
                                qid = query.get('qid') or query.get('query_id') or query.get('id') or str(i+1)
                                title = query.get('title') or query.get('query') or ""
                                if title:
                                    valid_queries.append({'qid': str(qid), 'title': str(title)})
                        
                        if valid_queries:
                            print(f"Loaded {len(valid_queries)} queries from JSON array format (encoding: {encoding})")
                            return valid_queries
                
                except json.JSONDecodeError:
                    pass
                
               
                try:
                    queries = []
                    lines = content.split('\n')
                    for line_num, line in enumerate(lines, 1):
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        try:
                            query_obj = json.loads(line)
                            if isinstance(query_obj, dict):
                               
                                qid = query_obj.get('qid') or query_obj.get('query_id') or query_obj.get('id') or str(line_num)
                                title = query_obj.get('title') or query_obj.get('query') or ""
                                if title:
                                    queries.append({'qid': str(qid), 'title': str(title)})
                        except json.JSONDecodeError:
                            continue
                    
                    if queries:
                        print(f"Loaded {len(queries)} queries from JSONL format (encoding: {encoding})")
                        return queries
                
                except Exception:
                    pass
                
                
                try:
                    queries = []
                    lines = content.split('\n')
                    for line_num, line in enumerate(lines, 1):
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        if '\t' in line:
                            parts = line.split('\t', 1)
                            if len(parts) >= 2:
                                qid, title = parts[0], parts[1]
                                queries.append({'qid': qid.strip(), 'title': title.strip()})
                        else:
                           
                            queries.append({'qid': str(line_num), 'title': line})
                    
                    if queries:
                        print(f"Loaded {len(queries)} queries from text format (encoding: {encoding})")
                        return queries
                
                except Exception:
                    pass
                    
        except Exception as e:
            continue
    
   
    raise ValueError(f"Could not parse query file {path_to_query_file}. Tried encodings: {encodings}. Supported formats: JSON array, JSONL, tab-separated text")


def boolean_retrieval(inverted_index_path: str, path_to_query_file: str, output_dir: str, 
                     stopwords_path: str = None) -> None:
   
    print("Loading inverted index...")
    try:
        inverted_index = load_inverted_index(inverted_index_path)
        print(f"Loaded inverted index with {len(inverted_index)} terms")
    except Exception as e:
        print(f"Error loading inverted index: {e}")
        return
    
   
    stopwords = load_stopwords(stopwords_path) if stopwords_path else set()
    
   
    print("Loading queries...")
    try:
        queries = load_queries(path_to_query_file)
    except Exception as e:
        print(f"Error loading queries: {e}")
        return
    
    
    parser = BooleanQueryParser()
    
   
    os.makedirs(output_dir, exist_ok=True)
   
    output_file = os.path.join(output_dir, 'docids.txt')
    
    print(f"Processing {len(queries)} queries...")
    with open(output_file, 'w') as f:
        for query in queries:
            qid = query['qid']
            title = query['title']
            
            print(f"Processing query {qid}: {title}")
            
           
            matching_docs = parser.parse_and_evaluate(title, inverted_index, stopwords)
           
            sorted_docs = sorted(list(matching_docs))
           
            for rank, doc_id in enumerate(sorted_docs, 1):
               
                f.write(f"{qid} {doc_id} {rank} 1\n")
    
    print(f"Results written to {output_file}")




import sys

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 retrieval.py <INVERTED_INDEX_PATH> <QUERY_FILE_PATH> <OUTPUT_DIR>")
        exit(1)

    inverted_index_path = sys.argv[1]
    query_file_path = sys.argv[2]
    output_directory = sys.argv[3]

   
    stopwords_file = "stopwords.txt" 
    stopwords_file_path = stopwords_file if os.path.exists(stopwords_file) else None

 
    if not os.path.exists(inverted_index_path):
        print(f"Error: Inverted index file not found: {inverted_index_path}")
        exit(1)
    if not os.path.exists(query_file_path):
        print(f"Error: Query file not found: {query_file_path}")
        exit(1)

   
    try:
        boolean_retrieval(
            inverted_index_path=inverted_index_path,
            path_to_query_file=query_file_path, 
            output_dir=output_directory,
            stopwords_path=stopwords_file_path
        )
        print("Boolean retrieval completed successfully!")
    except Exception as e:
        print(f"Error during retrieval: {e}")
        import traceback
        traceback.print_exc()
