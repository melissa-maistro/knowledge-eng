import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from graph.query import SubstitutionGraph

try:
    from pyvis.network import Network
except ImportError:
    print("Error: 'pyvis' is not installed. Please run 'pip install pyvis'.")
    sys.exit(1)

def build_interactive_graph():
    print("Initializing SubstitutionGraph...")
    sg = SubstitutionGraph()
    G = sg.G

    print("Generating PyVis visualization...")
    # Initialize the PyVis network graph
    net = Network(height="100vh", width="100%", bgcolor="#ffffff", font_color="black", select_menu=True, filter_menu=True)
    
    # Use BarnesHut with tweaked parameters to spread out the "hairballs"
    net.barnes_hut(gravity=-80, central_gravity=0.3, spring_length=200, spring_strength=0.04, damping=0.09)
    
    # Define colors for different functional classes
    class_colors = {
        "fat_source": "#FFD700",       # Gold
        "protein_source": "#CD5C5C",   # IndianRed
        "carb_source": "#90EE90",      # LightGreen
    }
    
    # Add nodes
    for node, data in G.nodes(data=True):
        # Skip isolated nodes (ingredients with no substitution edges)
        if G.degree(node) == 0:
            continue
            
        fc = data.get("functional_class", None)
        color = class_colors.get(fc, "#A9A9A9") # DarkGray for unknown
        
        allergens = data.get("allergens", set())
        title_lines = [f"<b>{node}</b>"]
        if fc:
            title_lines.append(f"Class: {fc}")
        if allergens:
            title_lines.append(f"Allergens: {', '.join(allergens)}")
        
        # Highlight node if it has allergens by giving it a distinct border
        border_color = "#FF0000" if allergens else "transparent"
        border_width = 3 if allergens else 1
        
        net.add_node(
            node,
            label=node,
            title="<br>".join(title_lines),
            color={"background": color, "border": border_color},
            borderWidth=border_width,
            size=12,
            font={"size": 6} # Much smaller font size
        )
        
    # Add edges
    for u, v, data in G.edges(data=True):
        score = data.get("score", 0.1)
        reason = data.get("reason", "")
        # Use a very thin, darker line so individual edges are visible
        width = 0.5
        color = "rgba(100, 100, 100, 0.6)"
        
        title_lines = [f"Similarity Score: {score:.2f}"]
        if reason:
            title_lines.append(f"Reason: {reason}")
            
        net.add_edge(
            u, v,
            title="<br>".join(title_lines),
            width=0.2, # Very thin thread-like lines
            color=color
        )
        
    # Add interactive UI for the user to tweak physics and layout
    net.show_buttons(filter_=['physics'])
    
    # Save and open the file
    out_file = "knowledge_graph.html"
    net.save_graph(out_file)
    print(f"Graph successfully saved to {out_file}")
    
    # Open in the default web browser
    try:
        webbrowser.open(f"file://{Path(out_file).absolute()}")
        print("Opened in web browser.")
    except Exception as e:
        print(f"Could not open browser automatically: {e}")

if __name__ == "__main__":
    build_interactive_graph()
