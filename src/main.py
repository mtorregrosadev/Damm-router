"""
Damm Smart Truck — Punt d'entrada principal
Importa executar_ruta des del mòdul router i llança l'optimització.
"""

from router import executar_ruta

if __name__ == '__main__':
    resultat = executar_ruta('DR0006', '19/03/2026', 4)

    print("\n── Resum retornat pel mòdul ──")
    print(f"Ruta:              {resultat['ruta']}")
    print(f"Data:              {resultat['data']}")
    print(f"Clients visitats:  {resultat.get('clients_visitats', '—')}")
    print(f"Clients saltats:   {resultat.get('clients_saltats', '—')}")
    print(f"Temps total:       {resultat.get('temps_total_min', '—')} min")
