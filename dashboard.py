import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
from graph.substitution import PatientConsultation

# Initialize the knowledge graph
print("Initializing Knowledge Graph...")
pc = PatientConsultation()
ingredients_list = sorted([str(n) for n in pc.G.nodes])

# Options for Dropdowns
allergy_options = [
    {"label": "Dairy", "value": "dairy"},
    {"label": "Gluten", "value": "gluten"},
    {"label": "Peanut", "value": "peanut"},
    {"label": "Tree Nuts", "value": "tree_nuts"},
    {"label": "Egg", "value": "egg"},
    {"label": "Soy", "value": "soy"},
    {"label": "Fish", "value": "fish"},
    {"label": "Shellfish", "value": "shellfish"},
]

goal_options = [
    {"label": "Sodium", "value": "sodium"},
    {"label": "Saturated Fat", "value": "saturated_fat"},
    {"label": "Sugar", "value": "sugar"},
    {"label": "Calories", "value": "calories"},
    {"label": "Total Fat", "value": "fat"},
    {"label": "Carbohydrates", "value": "carbs"},
]

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])
app.title = "Recipe Substitution KG"

# Layout
app.layout = dbc.Container([
    html.Br(),
    html.H2("Recipe Substitution Knowledge Graph", className="text-center mb-4"),
    html.Hr(),
    
    dbc.Row([
        # Sidebar for Inputs
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Consultation Parameters", className="card-title"),
                    html.Br(),
                    
                    html.Label("Target Ingredient:"),
                    dcc.Dropdown(
                        id="input-ingredient",
                        options=[{"label": i, "value": i} for i in ingredients_list],
                        value="Butter",
                        placeholder="Select an ingredient...",
                        className="mb-3"
                    ),
                    
                    html.Label("Allergies to Avoid:"),
                    dcc.Dropdown(
                        id="input-allergies",
                        options=allergy_options,
                        multi=True,
                        placeholder="Select allergies...",
                        className="mb-3"
                    ),
                    
                    html.Label("Nutritional Goals (Reduce):"),
                    dcc.Dropdown(
                        id="input-goals",
                        options=goal_options,
                        multi=True,
                        placeholder="Select nutrients to reduce...",
                        className="mb-4"
                    ),
                    
                    dbc.Button("Find Substitutes", id="btn-search", color="primary", className="w-100")
                ])
            ], className="shadow-sm")
        ], md=4),
        
        # Main Panel for Outputs
        dbc.Col([
            dcc.Loading(
                id="loading-results",
                type="circle",
                children=html.Div(id="output-results")
            )
        ], md=8)
    ])
], fluid=True, className="p-4")

@app.callback(
    Output("output-results", "children"),
    Input("btn-search", "n_clicks"),
    State("input-ingredient", "value"),
    State("input-allergies", "value"),
    State("input-goals", "value")
)
def update_results(n_clicks, ingredient, allergies, goals):
    if not ingredient:
        return html.Div("Please select an ingredient to search.", className="text-muted")
        
    patient = {
        "allergies": allergies or [],
        "goals": {"reduce": goals or []}
    }
    
    data = pc.get_consultation_data(ingredient, patient, recipe_context={}, top_n=5)
    
    if not data["success"]:
        return dbc.Alert(data["message"], color="danger")
        
    results = data["results"]
    if not results:
        return dbc.Alert(f"No substitutes found for {ingredient}.", color="warning")
        
    cards = []
    for idx, res in enumerate(results):
        
        badges = [dbc.Badge(f"Score: {res['score']}", color="info", className="me-2")]
        
        # Build improvements list
        imp_items = []
        for imp in res["improvements"]:
            imp_items.append(html.Li(imp, className="text-success"))
            
        # Build warnings list
        warn_items = []
        for warn in res["warnings"]:
            warn_items.append(html.Li(warn, className="text-danger fw-bold"))
            
        card_body = [
            html.H5(f"Option {idx + 1}: {res['substitute']}", className="card-title"),
            html.Div(badges, className="mb-2"),
            html.P(res["flavor_text"], className="card-text text-muted mb-2")
        ]
        
        if imp_items:
            card_body.append(html.H6("Nutritional Improvements:", className="mt-3"))
            card_body.append(html.Ul(imp_items))
            
        if warn_items:
            card_body.append(html.H6("⚠️ Warnings:", className="mt-2"))
            card_body.append(html.Ul(warn_items))
            
        if not imp_items and not warn_items:
            card_body.append(html.P("No significant nutritional deltas tracked.", className="text-muted fst-italic"))
            
        card = dbc.Card(dbc.CardBody(card_body), className="mb-3 shadow-sm")
        cards.append(card)
        
    return html.Div([
        html.H4(f"Substitutes for '{data['target']}'", className="mb-4"),
        *cards
    ])

if __name__ == "__main__":
    app.run(debug=True, port=8050)
