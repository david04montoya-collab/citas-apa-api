from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Claves API ya insertadas
PUBMED_API_KEY = "d65daf8493357bd078d3abe98d1860dd9608"
SERPAPI_KEY = "4656512120f4468e4bbc0ea857a2db17af9b68eb301e50f940529c3a3073674a"

# Función para buscar en PubMed
def buscar_pubmed(query):
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "api_key": PUBMED_API_KEY,
        "retmax": 3
    }
    r = requests.get(url, params=params)
    data = r.json()
    ids = data.get("esearchresult", {}).get("idlist", [])
    
    articulos = []
    for pmid in ids:
        summary_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        summary_params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "json",
            "api_key": PUBMED_API_KEY
        }
        s = requests.get(summary_url, params=summary_params).json()
        info = s.get("result", {}).get(pmid, {})
        if info:
            articulos.append({
                "titulo": info.get("title"),
                "autores": ", ".join([a["name"] for a in info.get("authors", [])]),
                "año": info.get("pubdate", "").split(" ")[0],
                "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            })
    return articulos

# Función para buscar en Google Académico vía SerpAPI
def buscar_google_scholar(query):
    url = "https://serpapi.com/search"
    params = {
        "engine": "google_scholar",
        "q": query,
        "api_key": SERPAPI_KEY
    }
    r = requests.get(url, params=params)
    resultados = r.json().get("organic_results", [])
    articulos = []
    for art in resultados[:3]:
        articulos.append({
            "titulo": art.get("title"),
            "autores": art.get("publication_info", {}).get("authors", ""),
            "año": art.get("publication_info", {}).get("year", ""),
            "link": art.get("link")
        })
    return articulos

# Función para formatear en APA
def formatear_apa(articulo):
    autores = articulo.get("autores", "Autor desconocido")
    año = articulo.get("año", "s.f.")
    titulo = articulo.get("titulo", "Sin título")
    link = articulo.get("link", "")
    return f"{autores} ({año}). {titulo}. {link}"

# Ruta principal
@app.route("/buscar", methods=["GET"])
def buscar():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Falta el parámetro 'q'"}), 400
    
    pubmed_results = buscar_pubmed(query)
    google_results = buscar_google_scholar(query)
    todos = pubmed_results + google_results
    citas_apa = [formatear_apa(a) for a in todos]
    
    return jsonify({
        "tema": query,
        "citas": citas_apa
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
