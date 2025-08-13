import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Tus claves API (ya incluidas)
NCBI_API_KEY = "d65daf8493357bd078d3abe98d1860dd9608"
SERPAPI_KEY = "4656512120f4468e4bbc0ea857a2db17af9b68eb301e50f940529c3a3073674a"

# Función para buscar en PubMed
def buscar_pubmed(termino):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": termino,
        "retmode": "json",
        "api_key": NCBI_API_KEY,
        "retmax": 3
    }
    r = requests.get(url, params=params)
    ids = r.json().get("esearchresult", {}).get("idlist", [])
    
    resultados = []
    for pmid in ids:
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "json",
            "api_key": NCBI_API_KEY
        }
        fr = requests.get(fetch_url, params=fetch_params).json()
        info = fr["result"][pmid]
        resultados.append({
            "titulo": info.get("title"),
            "autores": [a["name"] for a in info.get("authors", [])],
            "año": info.get("pubdate", "")[:4],
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        })
    return resultados

# Función para buscar en Google Scholar (SerpAPI)
def buscar_google_scholar(termino):
    url = "https://serpapi.com/search"
    params = {
        "engine": "google_scholar",
        "q": termino,
        "api_key": SERPAPI_KEY
    }
    r = requests.get(url, params=params).json()
    resultados = []
    for item in r.get("organic_results", [])[:3]:
        resultados.append({
            "titulo": item.get("title"),
            "autores": [],
            "año": None,
            "url": item.get("link")
        })
    return resultados

# Formatear en estilo APA
def formatear_cita_apa(item):
    autores = ", ".join(item.get("autores", [])) or "Autor desconocido"
    año = item.get("año", "s.f.")
    titulo = item.get("titulo", "")
    url = item.get("url", "")
    return f"{autores} ({año}). {titulo}. Recuperado de {url}"

# Ruta principal de búsqueda
@app.route("/search", methods=["GET"])
def search():
    termino = request.args.get("q")
    if not termino:
        return jsonify({"error": "Falta el parámetro q"}), 400

    pubmed_res = buscar_pubmed(termino)
    scholar_res = buscar_google_scholar(termino)

    citas = [formatear_cita_apa(item) for item in pubmed_res + scholar_res]

    return jsonify({
        "termino": termino,
        "citasAPA": citas,
        "referencias": "\n".join(citas)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
