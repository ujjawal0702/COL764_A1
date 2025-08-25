from typing import List, Union, Optional
import json

class ASTNode:
    """Node class for Abstract Syntax Tree representation of Boolean queries."""
    
    def __init__(self, value: str, left: Optional['ASTNode'] = None, right: Optional['ASTNode'] = None):
        self.value = value  # The operator or term
        self.left = left    # Left child
        self.right = right  # Right child
    
    def is_operator(self) -> bool:
        """Check if this node represents an operator."""
        return self.value in {'AND', 'OR', 'NOT'}
    
    def is_term(self) -> bool:
        """Check if this node represents a term."""
        return not self.is_operator()
    
    def to_dict(self) -> dict:
        """Convert AST to dictionary for JSON serialization."""
        result = {'value': self.value}
        if self.left:
            result['left'] = self.left.to_dict()
        if self.right:
            result['right'] = self.right.to_dict()
        return result
    
    def __str__(self) -> str:
        """String representation for debugging."""
        if self.is_term():
            return self.value
        elif self.value == 'NOT':
            return f"NOT({self.right})"
        else:
            return f"({self.left} {self.value} {self.right})"

class BooleanQueryParser:
    """Parser for Boolean queries with operator precedence."""
    
    def __init__(self):
        # Operator precedence: higher number = higher precedence
        self.precedence = {
            'OR': 1,
            'AND': 2,
            'NOT': 3
        }
        
        # Associativity: 'L' = left, 'R' = right
        self.associativity = {
            'OR': 'L',
            'AND': 'L',
            'NOT': 'R'  # NOT is right associative
        }
    
    def is_operator(self, token: str) -> bool:
        """Check if token is an operator."""
        return token in {'AND', 'OR', 'NOT'}
    
    def get_precedence(self, operator: str) -> int:
        """Get precedence of an operator."""
        return self.precedence.get(operator, 0)
    
    def infix_to_postfix(self, tokens: List[str]) -> List[str]:
        """
        Convert infix notation to postfix using Shunting Yard algorithm.
        
        Operator precedence (highest to lowest):
        1. () - parentheses
        2. NOT
        3. AND  
        4. OR
        """
        output = []
        operator_stack = []
        
        for token in tokens:
            if token == '(':
                operator_stack.append(token)
            
            elif token == ')':
                # Pop operators until we find the matching '('
                while operator_stack and operator_stack[-1] != '(':
                    output.append(operator_stack.pop())
                
                # Remove the '(' from stack
                if operator_stack and operator_stack[-1] == '(':
                    operator_stack.pop()
            
            elif self.is_operator(token):
                # Pop operators with higher or equal precedence
                while (operator_stack and 
                       operator_stack[-1] != '(' and
                       operator_stack[-1] in self.precedence and
                       (self.get_precedence(operator_stack[-1]) > self.get_precedence(token) or
                        (self.get_precedence(operator_stack[-1]) == self.get_precedence(token) and
                         self.associativity[token] == 'L'))):
                    output.append(operator_stack.pop())
                
                operator_stack.append(token)
            
            else:
                # It's a term/operand
                output.append(token)
        
        # Pop remaining operators
        while operator_stack:
            if operator_stack[-1] in '()':
                raise ValueError("Mismatched parentheses")
            output.append(operator_stack.pop())
        
        return output
    
    def postfix_to_ast(self, postfix_tokens: List[str]) -> ASTNode:
        """Convert postfix expression to Abstract Syntax Tree."""
        stack = []
        
        for token in postfix_tokens:
            if self.is_operator(token):
                if token == 'NOT':
                    # NOT is unary operator
                    if not stack:
                        raise ValueError("Invalid expression: NOT operator without operand")
                    operand = stack.pop()
                    node = ASTNode(token, right=operand)
                    stack.append(node)
                else:
                    # Binary operators (AND, OR)
                    if len(stack) < 2:
                        raise ValueError(f"Invalid expression: {token} operator needs two operands")
                    right = stack.pop()
                    left = stack.pop()
                    node = ASTNode(token, left=left, right=right)
                    stack.append(node)
            else:
                # It's a term
                node = ASTNode(token)
                stack.append(node)
        
        if len(stack) != 1:
            raise ValueError("Invalid expression: multiple root nodes")
        
        return stack[0]
    
    def evaluate_ast(self, node: ASTNode, document_terms: set) -> bool:
        """
        Recursively evaluate the AST against a set of document terms.
        
        Args:
            node: Current AST node
            document_terms: Set of terms present in a document
            
        Returns:
            Boolean result of the query evaluation
        """
        if node.is_term():
            # Check if term exists in document
            return node.value in document_terms
        
        elif node.value == 'NOT':
            # NOT operation on right child
            return not self.evaluate_ast(node.right, document_terms)
        
        elif node.value == 'AND':
            # AND operation on both children
            left_result = self.evaluate_ast(node.left, document_terms)
            right_result = self.evaluate_ast(node.right, document_terms)
            return left_result and right_result
        
        elif node.value == 'OR':
            # OR operation on both children
            left_result = self.evaluate_ast(node.left, document_terms)
            right_result = self.evaluate_ast(node.right, document_terms)
            return left_result or right_result
        
        else:
            raise ValueError(f"Unknown operator: {node.value}")
    
    def parse_query(self, query_tokens: List[str]) -> dict:
        """
        Main parsing function that converts tokens to both postfix and AST.
        
        Args:
            query_tokens: List of preprocessed query tokens
            
        Returns:
            Dictionary containing postfix notation and AST
        """
        try:
            # Convert to postfix
            postfix = self.infix_to_postfix(query_tokens)
            
            # Build AST from postfix
            ast = self.postfix_to_ast(postfix)
            
            return {
                'original_tokens': query_tokens,
                'postfix': postfix,
                'ast': ast,
                'ast_dict': ast.to_dict()  # For JSON serialization
            }
        
        except Exception as e:
            raise ValueError(f"Error parsing query {' '.join(query_tokens)}: {e}")

def query_parser(query_tokens: List[str]) -> Union[List[str], ASTNode]:
    """
    Main query parser function as specified in assignment.
    
    Args:
        query_tokens: List of preprocessed query tokens
        
    Returns:
        Can return either postfix notation (List[str]) or AST (ASTNode)
    """
    parser = BooleanQueryParser()
    result = parser.parse_query(query_tokens)
    
    # Return AST by default (can be modified to return postfix if needed)
    return result['ast']

def parse_preprocessed_queries(preprocessed_queries: dict) -> dict:
    """
    Parse all preprocessed queries.
    
    Args:
        preprocessed_queries: Dictionary from query preprocessing step
        
    Returns:
        Dictionary with parsed query information
    """
    parser = BooleanQueryParser()
    parsed_queries = {}
    
    for query_id, query_data in preprocessed_queries.items():
        tokens = query_data['preprocessed_tokens']
        
        try:
            parsed_result = parser.parse_query(tokens)
            
            parsed_queries[query_id] = {
                'original_title': query_data['original_title'],
                'preprocessed_tokens': tokens,
                'preprocessed_string': query_data['preprocessed_string'],
                'postfix': parsed_result['postfix'],
                'postfix_string': ' '.join(parsed_result['postfix']),
                'ast_dict': parsed_result['ast_dict'],
                'ast_object': parsed_result['ast']
            }
            
            print(f"Query {query_id}: {query_data['original_title']}")
            print(f"  Tokens: {tokens}")
            print(f"  Postfix: {parsed_result['postfix']}")
            print(f"  AST: {parsed_result['ast']}")
            print()
            
        except Exception as e:
            print(f"Error parsing query {query_id}: {e}")
            parsed_queries[query_id] = {
                'error': str(e),
                'original_title': query_data['original_title'],
                'preprocessed_tokens': tokens
            }
    
    return parsed_queries

# Test function
def test_boolean_parser():
    """Test the Boolean query parser with examples from the assignment."""
    
    parser = BooleanQueryParser()
    
    test_cases = [
        # Example (a): not (information and retrieval)
        ['NOT', '(', 'information', 'AND', 'retrieval', ')'],
        
        # Example (b): retrieval information not index (with implicit ANDs)
        ['retrieval', 'AND', 'information', 'AND', 'NOT', 'index'],
        
        # Simple cases
        ['coronavirus', 'AND', 'origin'],
        ['jaguar', 'AND', 'NOT', 'car'],
        ['(', 'information', 'AND', 'retrieval', ')', 'OR', 'indexing']
    ]
    
    print("Testing Boolean Query Parser:")
    print("=" * 50)
    
    for i, tokens in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {' '.join(tokens)}")
        
        try:
            result = parser.parse_query(tokens)
            print(f"Postfix: {result['postfix']}")
            print(f"AST: {result['ast']}")
            
            # Test evaluation with sample document
            sample_doc_terms = {'information', 'retrieval', 'coronavirus', 'origin', 'jaguar'}
            evaluation = parser.evaluate_ast(result['ast'], sample_doc_terms)
            print(f"Evaluation (sample doc): {evaluation}")
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) == 1:
        # Run tests if no arguments provided
        test_boolean_parser()
    
    elif len(sys.argv) == 2:
        # Parse queries from preprocessed JSON file
        preprocessed_file = sys.argv[1]
        
        try:
            with open(preprocessed_file, 'r', encoding='utf-8') as f:
                preprocessed_queries = json.load(f)
            
            parsed_queries = parse_preprocessed_queries(preprocessed_queries)
            
            # Save parsed queries
            output_file = preprocessed_file.replace('.json', '_parsed.json')
            
            # Convert AST objects to dictionaries for JSON serialization
            json_compatible = {}
            for qid, data in parsed_queries.items():
                json_data = data.copy()
                if 'ast_object' in json_data:
                    del json_data['ast_object']  # Remove non-serializable object
                json_compatible[qid] = json_data
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(json_compatible, f, indent=2)
            
            print(f"Parsed queries saved to: {output_file}")
            
        except Exception as e:
            print(f"Error: {e}")
    
    else:
        print("Usage:")
        print("  python boolean_query_parser.py                    # Run tests")
        print("  python boolean_query_parser.py <preprocessed_queries.json>  # Parse queries from file")