import sys
from graph.substitution import PatientConsultation

def main():
    print("=" * 60)
    print(" 🌿 RECIPE SUBSTITUTION KNOWLEDGE GRAPH - CLIENT INTERFACE 🌿")
    print("=" * 60)
    
    print("\nInizializzazione del Knowledge Graph in corso...")
    try:
        pc = PatientConsultation()
    except Exception as e:
        print(f"Errore durante l'inizializzazione del grafo: {e}")
        sys.exit(1)
        
    print("Inizializzazione completata!\n")
    
    while True:
        print("\n" + "-" * 60)
        ingredient = input("👉 Quale ingrediente vuoi sostituire? (o 'exit' per uscire): ").strip()
        
        if ingredient.lower() in ['exit', 'quit', 'q', 'esci']:
            print("Chiusura del client. A presto!")
            break
            
        if not ingredient:
            continue
            
        print("\n[Opzionale] Quali ALLERGIE ha il paziente?")
        allergies_input = input("Scrivi le allergie separate da virgola (es. dairy, peanut) o premi Invio per saltare: ").strip()
        allergies = [a.strip().lower() for a in allergies_input.split(",")] if allergies_input else []
        
        print("\n[Opzionale] Quali OBIETTIVI NUTRIZIONALI (da ridurre) ha il paziente?")
        print("Opzioni valide: sodium, saturated_fat, sugar, calories, fat, carbs")
        goals_input = input("Scrivi gli obiettivi separati da virgola o premi Invio per saltare: ").strip()
        reduce_goals = [g.strip().lower() for g in goals_input.split(",")] if goals_input else []
        
        print("\n[Opzionale] In che contesto o CUCINA verrà usato?")
        cuisine_input = input("Scrivi la cucina (es. italian, mexican) o premi Invio per saltare: ").strip()
        cuisine = cuisine_input if cuisine_input else "Any"
        
        # Build patient and context objects
        patient = {
            "allergies": allergies,
            "goals": {"reduce": reduce_goals}
        }
        
        recipe_context = {
            "cuisine": cuisine,
            "role": "Any"
        }
        
        print("\n🔍 Ricerca dei migliori sostituti nel Knowledge Graph in corso...\n")
        
        # Interroga il grafo
        pc.ask(ingredient=ingredient, patient=patient, recipe_context=recipe_context, top_n=5)

if __name__ == "__main__":
    # Esegui il client in modo interattivo
    main()
