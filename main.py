import streamlit as st
import ast
import graphviz
from typing import List, Dict, Set, Optional, Tuple
import re

class CFGNode:
    """Represents a node in the Control Flow Graph"""
    def __init__(self, node_id: int, label: str, node_type: str = "process", condition: str = None):
        self.node_id = node_id
        self.label = label
        self.node_type = node_type  # process, decision, start, end, input, output, call
        self.condition = condition  # For decision nodes
        self.successors: List[Tuple[int, str]] = []  # (node_id, edge_label)
        self.predecessors: Set[int] = set()
    
    def add_successor(self, node_id: int, edge_label: str = ""):
        self.successors.append((node_id, edge_label))
    
    def add_predecessor(self, node_id: int):
        self.predecessors.add(node_id)
    
    def get_shape(self) -> str:
        """Get Graphviz shape for the node type"""
        shapes = {
            "start": "ellipse",
            "end": "ellipse", 
            "process": "box",
            "decision": "diamond",
            "input": "parallelogram",
            "output": "parallelogram",
            "call": "box"
        }
        return shapes.get(self.node_type, "box")
    
    def get_color(self) -> str:
        """Get color for the node type"""
        colors = {
            "start": "lightgreen",
            "end": "lightcoral",
            "process": "lightyellow", 
            "decision": "lightblue",
            "input": "lightcyan",
            "output": "lightgreen",
            "call": "plum"
        }
        return colors.get(self.node_type, "lightgray")

class FlowchartCFGBuilder(ast.NodeVisitor):
    """AST visitor to build flowchart-style Control Flow Graph"""
    
    def __init__(self):
        self.nodes: Dict[int, CFGNode] = {}
        self.current_node_id = 0
        self.entry_node = None
        self.current_exits: Set[int] = set()  # Current exit points
        self.function_name = None
        
    def create_node(self, label: str, node_type: str = "process", condition: str = None) -> int:
        """Create a new CFG node"""
        node_id = self.current_node_id
        self.nodes[node_id] = CFGNode(node_id, label, node_type, condition)
        self.current_node_id += 1
        return node_id
    
    def add_edge(self, from_node: int, to_node: int, label: str = ""):
        """Add an edge between two nodes"""
        if from_node in self.nodes and to_node in self.nodes:
            self.nodes[from_node].add_successor(to_node, label)
            self.nodes[to_node].add_predecessor(from_node)
    
    def connect_exits_to_node(self, target_node: int):
        """Connect all current exit nodes to target node"""
        for exit_node in self.current_exits:
            self.add_edge(exit_node, target_node)
        self.current_exits = {target_node}
    
    def visit_Module(self, node):
        """Visit module (top-level)"""
        # Create start node
        self.entry_node = self.create_node("START", "start")
        self.current_exits = {self.entry_node}
        
        if node.body:
            self.visit_statements(node.body)
        
        # Create end node
        end_node = self.create_node("END", "end")
        self.connect_exits_to_node(end_node)
    
    def visit_statements(self, statements):
        """Visit a list of statements"""
        for stmt in statements:
            self.visit(stmt)
    
    def visit_FunctionDef(self, node):
        """Visit function definition"""
        self.function_name = node.name
        
        # Function start
        func_start = self.create_node(f"def {node.name}({', '.join([arg.arg for arg in node.args.args])})", "start")
        self.connect_exits_to_node(func_start)
        
        # Visit function body
        if node.body:
            self.visit_statements(node.body)
        
        # Add implicit return if no explicit return
        if not any(isinstance(stmt, ast.Return) for stmt in node.body):
            return_node = self.create_node("return None", "output")
            self.connect_exits_to_node(return_node)
    
    def visit_If(self, node):
        """Visit if statement"""
        condition_text = ast.unparse(node.test)
        decision_node = self.create_node(condition_text, "decision", condition_text)
        self.connect_exits_to_node(decision_node)
        
        # Save current exits
        saved_exits = set()
        
        # Visit if body (True branch)
        self.current_exits = {decision_node}
        if node.body:
            self.visit_statements(node.body)
        saved_exits.update(self.current_exits)
        
        # Visit else body (False branch)
        self.current_exits = {decision_node}
        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                # elif case
                self.visit(node.orelse[0])
            else:
                self.visit_statements(node.orelse)
        saved_exits.update(self.current_exits)
        
        # Add edge labels
        true_edges = []
        false_edges = []
        for successor_id, label in self.nodes[decision_node].successors:
            if not label:  # Add labels to unlabeled edges
                if len(true_edges) == 0:
                    true_edges.append((successor_id, "True"))
                else:
                    false_edges.append((successor_id, "False"))
        
        # Update edge labels
        self.nodes[decision_node].successors = []
        for node_id, label in true_edges:
            self.nodes[decision_node].add_successor(node_id, "True")
        for node_id, label in false_edges:
            self.nodes[decision_node].add_successor(node_id, "False")
        
        self.current_exits = saved_exits
    
    def visit_While(self, node):
        """Visit while loop"""
        condition_text = ast.unparse(node.test)
        decision_node = self.create_node(condition_text, "decision", condition_text)
        self.connect_exits_to_node(decision_node)
        
        # Visit loop body
        self.current_exits = {decision_node}
        if node.body:
            self.visit_statements(node.body)
        
        # Connect body exits back to condition
        for exit_node in self.current_exits:
            self.add_edge(exit_node, decision_node)
        
        # Loop exit (False condition)
        self.current_exits = {decision_node}
        
        # Add edge labels
        body_successors = []
        for successor_id, label in self.nodes[decision_node].successors:
            if successor_id != decision_node:  # Not the back edge
                body_successors.append(successor_id)
        
        # Update edge labels
        new_successors = []
        for successor_id, label in self.nodes[decision_node].successors:
            if successor_id == decision_node:
                new_successors.append((successor_id, "True"))
            else:
                new_successors.append((successor_id, "False"))
        
        self.nodes[decision_node].successors = new_successors
    
    def visit_For(self, node):
        """Visit for loop"""
        target = ast.unparse(node.target)
        iter_expr = ast.unparse(node.iter)
        condition_text = f"for {target} in {iter_expr}"
        decision_node = self.create_node(condition_text, "decision", condition_text)
        self.connect_exits_to_node(decision_node)
        
        # Visit loop body
        self.current_exits = {decision_node}
        if node.body:
            self.visit_statements(node.body)
        
        # Connect body exits back to condition
        for exit_node in self.current_exits:
            self.add_edge(exit_node, decision_node)
        
        # Loop exit
        self.current_exits = {decision_node}
    
    def visit_Return(self, node):
        """Visit return statement"""
        if node.value:
            return_text = f"return {ast.unparse(node.value)}"
        else:
            return_text = "return"
        
        return_node = self.create_node(return_text, "output")
        self.connect_exits_to_node(return_node)
        self.current_exits = set()  # Return terminates flow
    
    def visit_Assign(self, node):
        """Visit assignment"""
        targets = [ast.unparse(target) for target in node.targets]
        value = ast.unparse(node.value)
        assign_text = f"{' = '.join(targets)} = {value}"
        
        assign_node = self.create_node(assign_text, "process")
        self.connect_exits_to_node(assign_node)
    
    def visit_AugAssign(self, node):
        """Visit augmented assignment (+=, -=, etc.)"""
        target = ast.unparse(node.target)
        op = ast.unparse(node.op)
        value = ast.unparse(node.value)
        assign_text = f"{target} {op}= {value}"
        
        assign_node = self.create_node(assign_text, "process")
        self.connect_exits_to_node(assign_node)
    
    def visit_Expr(self, node):
        """Visit expression statement"""
        if isinstance(node.value, ast.Call):
            # Function call
            call_text = ast.unparse(node.value)
            if any(func in call_text.lower() for func in ['print', 'input']):
                node_type = "output" if 'print' in call_text.lower() else "input"
            else:
                node_type = "call"
            call_node = self.create_node(call_text, node_type)
            self.connect_exits_to_node(call_node)
        else:
            # Other expression
            expr_text = ast.unparse(node.value)
            expr_node = self.create_node(expr_text, "process")
            self.connect_exits_to_node(expr_node)
    
    def visit_Call(self, node):
        """Visit function call (when part of assignment)"""
        call_text = ast.unparse(node)
        if any(func in call_text.lower() for func in ['input']):
            node_type = "input"
        else:
            node_type = "call"
        return self.create_node(call_text, node_type)
    
    def generic_visit(self, node):
        """Handle other node types"""
        try:
            stmt_text = ast.unparse(node)
            if len(stmt_text.strip()) > 0:
                process_node = self.create_node(stmt_text, "process")
                self.connect_exits_to_node(process_node)
        except:
            # Fallback for unparseable nodes
            process_node = self.create_node(f"# {type(node).__name__}", "process")
            self.connect_exits_to_node(process_node)
        
        super().generic_visit(node)

def calculate_cyclomatic_complexity(nodes: Dict[int, CFGNode]) -> int:
    """
    Calculate cyclomatic complexity using the formula: M = E - N + 2P
    Where:
    - E = number of edges
    - N = number of nodes  
    - P = number of connected components (usually 1 for a single program)
    """
    if not nodes:
        return 0
    
    N = len(nodes)  # Number of nodes
    E = sum(len(node.successors) for node in nodes.values())  # Number of edges
    P = 1  # Connected components (assuming single program)
    
    # McCabe's cyclomatic complexity formula
    complexity = E - N + 2 * P
    
    return max(complexity, 1)  # Minimum complexity is 1

def calculate_complexity_by_decisions(nodes: Dict[int, CFGNode]) -> int:
    """
    Alternative calculation: Count decision points + 1
    This is often easier to understand and matches manual counting
    """
    decision_count = sum(1 for node in nodes.values() if node.node_type == "decision")
    return decision_count + 1

def get_complexity_rating(complexity: int) -> Tuple[str, str]:
    """Get complexity rating and color based on complexity value"""
    if complexity <= 10:
        return "Low Risk", "green"
    elif complexity <= 20:
        return "Moderate Risk", "orange" 
    elif complexity <= 50:
        return "High Risk", "red"
    else:
        return "Very High Risk", "darkred"

def create_flowchart_cfg(code: str) -> Dict[int, CFGNode]:
    """Create flowchart-style CFG from Python code string"""
    try:
        tree = ast.parse(code)
        builder = FlowchartCFGBuilder()
        builder.visit(tree)
        return builder.nodes
    except SyntaxError as e:
        st.error(f"Syntax error in code: {e}")
        return {}
    except Exception as e:
        st.error(f"Error parsing code: {e}")
        return {}

def visualize_flowchart_cfg(nodes: Dict[int, CFGNode]) -> str:
    """Create Graphviz representation of flowchart CFG"""
    if not nodes:
        return ""
    
    dot = graphviz.Digraph(comment='Control Flow Graph', format='png')
    dot.attr(rankdir='TB', splines='ortho')
    dot.attr('node', fontname='Arial', fontsize='10')
    dot.attr('edge', fontname='Arial', fontsize='9')
    
    # Add nodes with appropriate shapes and colors
    for node_id, node in nodes.items():
        shape = node.get_shape()
        color = node.get_color()
        
        # Format label for better readability
        label = node.label
        if len(label) > 30:
            # Break long labels into multiple lines
            words = label.split()
            lines = []
            current_line = []
            current_length = 0
            
            for word in words:
                if current_length + len(word) + 1 <= 30:
                    current_line.append(word)
                    current_length += len(word) + 1
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = len(word)
            
            if current_line:
                lines.append(' '.join(current_line))
            
            label = '\\n'.join(lines)
        
        dot.node(
            str(node_id), 
            label, 
            shape=shape, 
            fillcolor=color, 
            style='filled',
            width='1.5' if shape == 'diamond' else '1.0',
            height='1.0' if shape == 'diamond' else '0.5'
        )
    
    # Add edges with labels
    for node_id, node in nodes.items():
        for successor_id, edge_label in node.successors:
            if edge_label:
                dot.edge(str(node_id), str(successor_id), label=edge_label)
            else:
                dot.edge(str(node_id), str(successor_id))
    
    return dot.source

def main():
    st.set_page_config(
        page_title="Flowchart CFG Generator",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Flowchart Control Flow Graph Generator")
    st.markdown("Generate professional flowchart-style CFGs from Python code")
    
    # Sidebar with legend and instructions
    with st.sidebar:
        st.header("📖 Instructions")
        st.markdown("""
        1. Enter your Python code in the text area
        2. Click 'Generate Flowchart CFG' 
        3. View the flowchart representation
        
        **Supported Features:**
        - Function definitions
        - If/else statements  
        - While and for loops
        - Assignments and expressions
        - Function calls
        - Return statements
        """)
        
        st.header("🎨 Flowchart Symbols")
        
        # Create a mini legend
        legend_dot = graphviz.Digraph()
        legend_dot.attr(rankdir='TB')
        legend_dot.attr('node', fontsize='8')
        
        legend_dot.node('start', 'START/END', shape='ellipse', fillcolor='lightgreen', style='filled')
        legend_dot.node('process', 'Process', shape='box', fillcolor='lightyellow', style='filled')  
        legend_dot.node('decision', 'Decision', shape='diamond', fillcolor='lightblue', style='filled')
        legend_dot.node('input', 'Input/Output', shape='parallelogram', fillcolor='lightcyan', style='filled')
        legend_dot.node('call', 'Function Call', shape='box', fillcolor='plum', style='filled')
        
        st.graphviz_chart(legend_dot.source)
        
        st.markdown("""
        - **Green Oval**: Start/End points
        - **Yellow Rectangle**: Process steps
        - **Blue Diamond**: Decision points
        - **Cyan Parallelogram**: Input/Output
        - **Purple Rectangle**: Function calls
        """)
        
        st.header("🧮 Cyclomatic Complexity")
        st.markdown("""
        **What is Cyclomatic Complexity?**
        
        Cyclomatic complexity measures the number of linearly independent paths through a program's source code.
        
        **Formula:** M = E - N + 2P
        - E = Number of edges
        - N = Number of nodes  
        - P = Connected components
        
        **Risk Levels:**
        - 1-10: Low risk (Simple)
        - 11-20: Moderate risk
        - 21-50: High risk (Complex)
        - 50+: Very high risk (Untestable)
        """)
    
    # Main interface
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📝 Python Code Input")
        
        # Sample code that creates a nice flowchart with higher complexity
        sample_code = '''def analyze_number(n):
    """Analyze a number and demonstrate various conditions"""
    if n < 0:
        if n % 2 == 0:
            result = "negative even"
        else:
            result = "negative odd"
    elif n == 0:
        result = "zero"  
    else:
        if n > 100:
            result = "large positive"
        else:
            result = "small positive"
        
        # Count and classify numbers
        count = 0
        while count < n and count < 10:
            if count % 2 == 0:
                if count % 5 == 0:
                    print(f"{count} is multiple of 5")
                else:
                    print(f"{count} is even")
            else:
                print(f"{count} is odd")
            count = count + 1
    
    return result

x = int(input("Enter a number: "))
answer = analyze_number(x)
print(f"The number is {answer}")'''
        
        code_input = st.text_area(
            "Enter your Python code:",
            value=sample_code,
            height=500,
            placeholder="Enter your Python code here..."
        )
        
        generate_button = st.button("🚀 Generate Flowchart CFG", type="primary")
    
    with col2:
        st.header("📊 Flowchart Control Flow Graph")
        
        if generate_button and code_input.strip():
            with st.spinner("Generating flowchart CFG..."):
                # Generate CFG
                nodes = create_flowchart_cfg(code_input)
                
                if nodes:
                    # Create visualization
                    dot_source = visualize_flowchart_cfg(nodes)
                    
                    if dot_source:
                        try:
                            st.graphviz_chart(dot_source)
                            
                            # Show statistics and complexity
                            st.subheader("📈 Graph Statistics & Complexity")
                            
                            # Calculate cyclomatic complexity
                            complexity_formula = calculate_cyclomatic_complexity(nodes)
                            complexity_decisions = calculate_complexity_by_decisions(nodes)
                            rating, color = get_complexity_rating(complexity_formula)
                            
                            # Display complexity metrics prominently
                            col_complexity = st.columns(3)
                            with col_complexity[0]:
                                st.metric(
                                    "Cyclomatic Complexity (M = E - N + 2P)", 
                                    complexity_formula,
                                    help=f"E={sum(len(node.successors) for node in nodes.values())}, N={len(nodes)}, P=1"
                                )
                            with col_complexity[1]:
                                st.metric(
                                    "Complexity (Decisions + 1)", 
                                    complexity_decisions,
                                    help="Alternative calculation: Decision points + 1"
                                )
                            with col_complexity[2]:
                                st.markdown(f"**Risk Level**")
                                st.markdown(f"<span style='color: {color}; font-size: 20px; font-weight: bold;'>{rating}</span>", 
                                          unsafe_allow_html=True)
                            
                            # Detailed breakdown
                            total_nodes = len(nodes)
                            total_edges = sum(len(node.successors) for node in nodes.values())
                            node_types = {}
                            for node in nodes.values():
                                node_types[node.node_type] = node_types.get(node.node_type, 0) + 1
                            
                            col_a, col_b, col_c = st.columns(3)
                            with col_a:
                                st.metric("Total Nodes (N)", total_nodes)
                                st.metric("Total Edges (E)", total_edges)
                            with col_b:
                                st.metric("Decision Points", node_types.get('decision', 0))
                                st.metric("Process Steps", node_types.get('process', 0))
                            with col_c:
                                st.metric("I/O Operations", node_types.get('input', 0) + node_types.get('output', 0))
                                st.metric("Function Calls", node_types.get('call', 0))
                            
                            # Complexity explanation
                            with st.expander("🧮 Complexity Calculation Details"):
                                st.markdown(f"""
                                **McCabe's Cyclomatic Complexity Formula: M = E - N + 2P**
                                
                                - **E (Edges)**: {total_edges}
                                - **N (Nodes)**: {total_nodes}  
                                - **P (Connected Components)**: 1
                                
                                **Calculation**: {total_edges} - {total_nodes} + 2(1) = **{complexity_formula}**
                                
                                **Alternative Method (Decision Points + 1)**: {node_types.get('decision', 0)} + 1 = **{complexity_decisions}**
                                
                                **What this means:**
                                - Your code has **{complexity_formula}** independent execution paths
                                - You need **{complexity_formula}** test cases for complete path coverage
                                - Risk level: **{rating}**
                                
                                **Recommendations:**
                                - **Low (1-10)**: Good, maintainable code
                                - **Moderate (11-20)**: Consider refactoring complex functions
                                - **High (21-50)**: Definitely refactor, hard to test
                                - **Very High (50+)**: Immediate refactoring needed
                                """)
                            
                            
                            # Node details
                            with st.expander("🔍 View Node Details"):
                                for node_id, node in nodes.items():
                                    st.write(f"**Node {node_id}** ({node.node_type}): {node.label}")
                                    if node.successors:
                                        successors_info = [f"→ {succ_id}" + (f" ({label})" if label else "") 
                                                         for succ_id, label in node.successors]
                                        st.write(f"  Successors: {', '.join(successors_info)}")
                            
                            # Download options
                            st.download_button(
                                label="📥 Download DOT file",
                                data=dot_source,
                                file_name="flowchart_cfg.dot",
                                mime="text/plain"
                            )
                            
                        except Exception as e:
                            st.error(f"Error generating visualization: {e}")
                            with st.expander("Raw DOT source"):
                                st.code(dot_source, language="dot")
                else:
                    st.warning("Could not generate CFG from the provided code.")
        
        elif generate_button:
            st.warning("Please enter some Python code to generate the flowchart CFG.")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    **Flowchart CFG Generator with Cyclomatic Complexity** 
    
    Creates professional flowchart-style control flow graphs with McCabe's cyclomatic complexity analysis.
    Perfect for code quality assessment, testing planning, and refactoring decisions.
    """)

if __name__ == "__main__":
    main()
