import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
from graph.substitution import PatientConsultation
from config import TRIPLE_SIMILARITY

print("Initializing Knowledge Graph...")
pc = PatientConsultation()

_sim = pd.read_csv(TRIPLE_SIMILARITY)
_nodes_with_subs = set(_sim["ingredient_a"]) | set(_sim["ingredient_b"])
ingredients_list = sorted(n for n in pc.G.nodes if n in _nodes_with_subs)

allergy_options = [
    {"label": "🥛 Dairy",     "value": "dairy"},
    {"label": "🌾 Gluten",    "value": "gluten"},
    {"label": "🥜 Peanut",    "value": "peanut"},
    {"label": "🌰 Tree Nuts", "value": "tree_nuts"},
    {"label": "🥚 Egg",       "value": "egg"},
    {"label": "🫘 Soy",       "value": "soy"},
    {"label": "🐟 Fish",      "value": "fish"},
    {"label": "🦐 Shellfish", "value": "shellfish"},
]

goal_options = [
    {"label": "Sodium",        "value": "sodium"},
    {"label": "Saturated Fat", "value": "saturated_fat"},
    {"label": "Sugar",         "value": "sugar"},
    {"label": "Calories",      "value": "calories"},
    {"label": "Total Fat",     "value": "fat"},
    {"label": "Carbohydrates", "value": "carbs"},
]

FC_LABELS = {
    "fat_source":     ("🧈", "Fat",     "warning"),
    "protein_source": ("🥩", "Protein", "danger"),
    "carb_source":    ("🌾", "Carb",    "success"),
}

RANK_MEDALS  = ["🥇", "🥈", "🥉", "4th", "5th"]
RANK_BORDERS = ["#FFD700", "#A8A9AD", "#CD7F32", "#78c2ad", "#78c2ad"]

TEAL = "#78c2ad"

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.MINTY])
app.title = "Ingredient Substitution Advisor"

app.layout = dbc.Container([

    # ── Info modal ───────────────────────────────────────────────────────────
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("How substitutions are computed")),
        dbc.ModalBody([
            html.H6("📊 Match score", className="fw-bold mt-1"),
            html.P(
                "Each substitute receives a match score (0–100%) combining three signals:",
                className="mb-2 small",
            ),
            dbc.Table([
                html.Thead(html.Tr([
                    html.Th("Signal", className="small"),
                    html.Th("Weight", className="small"),
                    html.Th("What it measures", className="small"),
                ])),
                html.Tbody([
                    html.Tr([html.Td("Macro similarity"),   html.Td("90%"), html.Td("Cosine similarity of fat / protein / carb balance per 100 g")]),
                    html.Tr([html.Td("Full nutrition"),      html.Td("5%"),  html.Td("Cosine similarity across the full micronutrient profile")]),
                    html.Tr([html.Td("Recipe co-occurrence"),html.Td("5%"),  html.Td("How often the two ingredients appear together in Food.com recipes")]),
                ]),
            ], size="sm", bordered=True, className="small mb-3"),

            html.H6("🍽️ Culinary role & category filtering", className="fw-bold"),
            html.P([
                "Every ingredient is automatically classified as a ",
                html.Strong("🧈 Fat source"), ", ",
                html.Strong("🥩 Protein source"), ", or ",
                html.Strong("🌾 Carb source"),
                " based on which macronutrient dominates its calorie profile "
                "(fat ≥ 50 kcal%, carb ≥ 50 kcal%, protein ≥ 30 kcal%).",
            ], className="small mb-2"),
            html.P(
                "The graph only connects ingredients within the same role category: "
                "fats substitute fats, proteins substitute proteins, carbs substitute carbs. "
                "The badge next to the ingredient name shows the detected role.",
                className="small mb-3",
            ),

            html.H6("⚠️ Allergen filtering", className="fw-bold"),
            html.P(
                "When you select one or more allergies, any substitute flagged with "
                "that allergen is removed before ranking. The EU Big-14 allergen "
                "framework is used.",
                className="small mb-3",
            ),

            html.H6("📉 Nutritional goals", className="fw-bold"),
            html.P(
                "Goals do not change the ranking; they annotate results. "
                "A ✅ improvement is shown when the substitute has less of the "
                "selected nutrient than the original; ⚠️ when it has more.",
                className="small mb-0",
            ),
        ]),
        dbc.ModalFooter(
            dbc.Button("Close", id="btn-info-close", color="secondary", size="sm")
        ),
    ], id="modal-info", is_open=False, size="lg"),

    # ── Header ──────────────────────────────────────────────────────────────
    dbc.Row(dbc.Col(html.Div([
        dbc.Row([
            dbc.Col([
                html.H2("🥗 Ingredient Substitution Advisor",
                        className="fw-bold mb-1", style={"color": TEAL}),
                html.P("Personalised substitutions for dietary needs · Western European Dietetics Clinic",
                       className="text-muted small mb-0"),
            ]),
            dbc.Col(
                dbc.Button("ℹ️ How it works", id="btn-info-open",
                           color="outline-secondary", size="sm",
                           className="float-end mt-2"),
                width="auto", className="d-flex align-items-center",
            ),
        ], align="center"),
    ], className="py-4"))),

    html.Hr(className="mt-0 mb-4"),

    dbc.Row([

        # ── Sidebar ─────────────────────────────────────────────────────────
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(
                    html.Span("⚙️  Consultation", className="fw-semibold"),
                    style={"background": TEAL, "color": "white",
                           "borderRadius": "10px 10px 0 0", "border": "none"}
                ),
                dbc.CardBody([
                    html.P("Ingredient to replace", className="fw-semibold small text-muted mb-1"),
                    dcc.Dropdown(
                        id="input-ingredient",
                        options=[{"label": i, "value": i} for i in ingredients_list],
                        value="Butter",
                        placeholder="Select an ingredient...",
                        className="mb-3",
                    ),

                    html.P("Allergies to avoid", className="fw-semibold small text-muted mb-1"),
                    dcc.Dropdown(
                        id="input-allergies",
                        options=allergy_options,
                        multi=True,
                        placeholder="None selected…",
                        className="mb-3",
                    ),

                    html.P("Nutritional goals (reduce):", className="fw-semibold small text-muted mb-1"),
                    dcc.Dropdown(
                        id="input-goals",
                        options=goal_options,
                        multi=True,
                        placeholder="None selected…",
                        className="mb-4",
                    ),

                    dbc.Button("🔍  Find Substitutes", id="btn-search",
                               color="success", className="w-100 fw-semibold",
                               style={"borderRadius": "8px"}),
                ]),
            ], style={"borderRadius": "10px", "border": "none"}, className="shadow-sm"),
        ], md=4),

        # ── Results panel ───────────────────────────────────────────────────
        dbc.Col([
            dcc.Loading(
                id="loading-results", type="dot",
                children=html.Div(
                    id="output-results",
                    children=html.Div(
                        "👆 Select an ingredient and click Find Substitutes",
                        className="text-muted text-center py-5 fs-6",
                    ),
                ),
            )
        ], md=8),

    ]),
], fluid=True, className="px-4 pb-5")


def _score_color(score: float) -> str:
    if score >= 0.85: return "success"
    if score >= 0.70: return "info"
    if score >= 0.50: return "warning"
    return "danger"


@app.callback(
    Output("output-results", "children"),
    Input("btn-search", "n_clicks"),
    State("input-ingredient", "value"),
    State("input-allergies", "value"),
    State("input-goals", "value"),
)
def update_results(n_clicks, ingredient, allergies, goals):
    if not ingredient:
        return html.Div("👆 Select an ingredient and click Find Substitutes",
                        className="text-muted text-center py-5 fs-6")

    data = pc.get_consultation_data(
        ingredient,
        {"allergies": allergies or [], "goals": {"reduce": goals or []}},
        {"role": ""},
        top_n=5,
    )

    if not data["success"]:
        return dbc.Alert(data["message"], color="danger", className="mt-3")

    results = data["results"]
    if not results:
        return dbc.Alert(f"No substitutes found for {ingredient}.", color="warning", className="mt-3")

    # Ingredient label / food-group badge
    fc = pc.G.nodes.get(ingredient, {}).get("functional_class")
    fc_badge = html.Span()
    if isinstance(fc, str) and fc in FC_LABELS:
        icon, label, color = FC_LABELS[fc]
        fc_badge = dbc.Badge(f"{icon} {label}", color=color,
                             className="ms-2 align-middle fw-normal")

    header = html.Div([
        html.H4(["Substitutes for ",
                 html.Span(data["target"], style={"color": TEAL}),
                 fc_badge],
                className="mb-1 fw-bold"),
        html.P(f"{len(results)} suggestion{'s' if len(results) != 1 else ''} found",
               className="text-muted small mb-3"),
    ])

    hint = None
    if not allergies:
        hint = dbc.Alert([
            "💡 No allergies selected. Showing all nutritionally similar ingredients. ",
            html.Strong("Add an allergy to filter to safe alternatives."),
        ], color="info", className="mb-3 py-2 small", dismissable=True)

    cards = []
    for idx, res in enumerate(results):

        imp_parts  = [html.Span(f"✅ {imp}  ", className="text-success small me-2")
                      for imp in res["improvements"]]
        warn_parts = [html.Span(f"⚠️ {warn}  ", className="text-danger small fw-bold me-2")
                      for warn in res["warnings"]]
        nutrition_row = html.Div(imp_parts + warn_parts) if (imp_parts or warn_parts) else \
                        html.P("No significant nutritional differences.",
                               className="text-muted small fst-italic mb-0")

        card = dbc.Card(dbc.CardBody([
            dbc.Row([
                # Rank medal
                dbc.Col(
                    html.Div(RANK_MEDALS[idx], style={
                        "fontSize": "1.6rem", "width": "44px", "height": "44px",
                        "display": "flex", "alignItems": "center",
                        "justifyContent": "center",
                        "background": "#f8f9fa", "borderRadius": "50%",
                    }),
                    width="auto", className="pe-2",
                ),
                # Name + flavour text
                dbc.Col([
                    html.H6(res["substitute"], className="mb-0 fw-bold"),
                    html.P(res["flavor_text"], className="text-muted small mb-0"),
                ]),
                # Score bar
                dbc.Col([
                    dbc.Progress(value=int(res["score"] * 100),
                                 color=_score_color(res["score"]),
                                 style={"height": "8px", "borderRadius": "4px"},
                                 className="mb-1"),
                    html.Div(f"{int(res['score'] * 100)}% match",
                             className="text-muted small text-end"),
                ], width=3),
            ], align="center", className="mb-2"),
            nutrition_row,
        ]), className="mb-3 shadow-sm", style={
            "borderRadius": "10px",
            "border": "1px solid #e9ecef",
            "borderLeft": f"5px solid {RANK_BORDERS[idx]}",
        })
        cards.append(card)

    return html.Div([header, hint or html.Span(), *cards])


@app.callback(
    Output("modal-info", "is_open"),
    Input("btn-info-open", "n_clicks"),
    Input("btn-info-close", "n_clicks"),
    State("modal-info", "is_open"),
    prevent_initial_call=True,
)
def toggle_info_modal(open_clicks, close_clicks, is_open):
    return not is_open


if __name__ == "__main__":
    app.run(debug=True, port=8050)
