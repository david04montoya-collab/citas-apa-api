from flask import Flask, request, jsonify
import requests
import re

app = Flask(__name__)

# Claves API
PUBMED_API_KEY = "d65daf8493357bd078d3abe98d1860dd9608"
SERPAPI_KEY = "4656512120f4468e4bbc0ea857a2db17af9b68eb301e50f940529c3a3073674a"

# =========================
# Funciones auxiliares
# =========================
def detectar_tema(texto):
    """
    Detecta el tema principal del texto (versión simple: usa las palabras más largas/relevantes).
    """
    palabras = re.findall(r'\w+', texto.lower())
    palabras_filtradas = [p for p in palabras if len(p) > 4]  # ignora palabras cortas
    if not palabras_filtradas:
        return "ciencia"
    # Tomamos la palabra más repetida
    return max(set(palabras_filtradas), key=palabras_filtradas.count)


def buscar_pubmed(query):
    """
    Busca artículos en PubMed relacionados al query.
    """
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
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
        summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        summary_params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "json",
            "api_key": PUBMED_API_KEY
        }
        s = requests.get(summary_url, params=summary_params).json()
        info = s.get("result", {}).get(pmid, {})
        if info:
            autores = [a["name"] for a in info.get("authors", [])]
            if autores:
                primer_autor = autores[0].split(",")[0]
            else:
                primer_autor = "Autor desconocido"
            año = info.get("pubdate", "").split(" ")[0]
            articulos.append({
                "cita_texto": f"{primer_autor}, {año}",
                "referencia": f"{', '.join(autores)} ({año}). {info.get('title')}. https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            })
    return articulos


def buscar_google_scholar(query):
    """
    Busca artículos en Google Scholar usando SerpAPI.
    """
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
        autores_info = art.get("publication_info", {}).get("authors", [])
        autores = [a.get("name") for a in autores_info if isinstance(a, dict)]
        año = art.get("publication_info", {}).get("year", "s.f.")
        if autores:
            primer_autor = autores[0].split(",")[0]
        else:
            primer_autor = "Autor desconocido"
        articulos.append({
            "cita_texto": f"{primer_autor}, {año}",
            "referencia": f"{', '.join(autores)} ({año}). {art.get('title')}. {art.get('link')}"
        })
    return articulos


def insertar_citas(texto, citas):
    """
    Inserta las citas en el texto original en puntos estratégicos.
    """
    oraciones = re.split(r'(?<=[.!?]) +', texto)
    for i in range(min(len(citas), len(oraciones))):
        oraciones[i] += f" ({citas[i]['cita_texto']})"
    return " ".join(oraciones)


# =========================
# Endpoint principal
# =========================
@app.route("/citar", methods=["POST"])
def citar_texto():
    data = request.get_json()
    texto = data.get("texto")
    if not texto:
        return jsonify({"error": "Falta el campo 'texto' en el cuerpo de la solicitud"}), 400

    # Detectar tema
    tema = detectar_tema(texto)

    # Buscar artículos relevantes
    resultados_pubmed = buscar_pubmed(tema)
    resultados_google = buscar_google_scholar(tema)
    todos_resultados = resultados_pubmed + resultados_google

    if not todos_resultados:
        return jsonify({"texto_citado": texto, "referencias": []})

    # Insertar citas en el texto
    texto_citado = insertar_citas(texto, todos_resultados)

    # Preparar referencias
    referencias = [r["referencia"] for r in todos_resultados]

    # Respuesta final
    respuesta_final = f"{texto_citado}\n\nReferencias (APA):\n" + "\n".join(referencias)

    return jsonify({
        "tema_detectado": tema,
        "texto_citado": respuesta_final
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

