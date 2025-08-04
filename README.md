# 📊 Flowchart CFG Generator

This is an interactive Streamlit web application that transforms Python code into a **flowchart-style Control Flow Graph (CFG)** and computes **cyclomatic complexity** to help you understand, evaluate, and improve your code quality.

---

## 🚀 Features

- ✅ **Flowchart Generation**
  - Parses Python code and visualizes its control flow using Graphviz.
  - Supports `if`, `else`, `elif`, `while`, `for`, `return`, assignments, function calls, and more.

- 📈 **Cyclomatic Complexity Analysis**
  - Uses McCabe’s formula: `M = E - N + 2P`
  - Also computes decision points + 1
  - Risk level categorized as Low, Moderate, High, or Very High

- 🎨 **Interactive Visuals**
  - Color-coded and shaped nodes: Start/End, Processes, Decisions, Inputs/Outputs, and Function Calls
  - Graph statistics, complexity breakdown, and node details included

- 📥 **Export**
  - Download the Graphviz DOT file of the generated CFG

---

