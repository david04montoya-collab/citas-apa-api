import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

NCBI_API_KEY = os.getenv("NCBI_API_KEY", "d65daf8493357bd078d3abe98d1860dd9608")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "4656512120f4468e4bbc0ea857a2db17af9b68eb301e50f940529c3a3073674a")

def buscar_pubmed(termino):
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": termino,
        "retmode": "json",
        "api_key": NCBI_API_KEY
    }
    r = requests.get(url, params=params)
    ids = r.json().get("esearchresult", {}).get("idlist", [])
    
    resultados = []
    for pmid in ids:
        fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        fetch_params = {"db": "pubmed", "id": pmid, "retmode": "json"}
        fr = requests.get(fetch_url, params=fetch_params)
        doc = fr.json()
        info = doc["result"][pmid]
        resultados.append({
            "titulo": info.get("title"),
            "autores": [a["name"] for a in info.get("authors", [])],
            "año": info.get("pubdate", "")[:4],
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        })
    return resultados

def buscar_google_scholar(termino):
    url = "https://serpapi.com/search"
    params = {
        "engine": "google_scholar",
        "q": termino,
        "api_key": SERPAPI_KEY
    }
    r = requests.get(url, params=params)
    datos = r.json()
    resultados = []
    for item in datos.get("organic_results", []):
        resultados.append({
            "titulo": item.get("title"),
            "autores": item.get("publication_info", {}).get("authors", []),
            "año": item.get("publication_info", {}).get("year"),
            "url": item.get("link")
        })
    return resultados

def formatear_cita_apa(item):
    autores = ", ".join(item.get("autores", []))
    año = item.get("año", "s.f.")
    titulo = item.get("titulo", "")
    url = item.get("url", "")
    return f"{autores} ({año}). {titulo}. Recuperado de {url}"

@app.route("/buscar", methods=["GET"])
def buscar():
    termino = request.args.get("q")
    if not termino:
        return jsonify({"error": "Falta el parámetro q"}), 400

    pubmed_res = buscar_pubmed(termino)
    scholar_res = buscar_google_scholar(termino)

    citas = [formatear_cita_apa(item) for item in pubmed_res + scholar_res]

    return jsonify({
        "termino": termino,
        "resultados": citas,
        "referencias": "\n".join(citas)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
