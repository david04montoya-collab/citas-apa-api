from flask import Flask, request, jsonify
import requests
import re
import time
from collections import Counter
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Descargar recursos de NLTK si no están disponibles
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')

app = Flask(__name__)

# Claves API
PUBMED_API_KEY = "d65daf8493357bd078d3abe98d1860dd9608"
SERPAPI_KEY = "4656512120f4468e4bbc0ea857a2db17af9b68eb301e50f940529c3a3073674a"

# Palabras clave científicas por área (para mejorar búsquedas)
AREAS_CIENTIFICAS = {
    'medicina': ['salud', 'enfermedad', 'tratamiento', 'diagnóstico', 'síntoma', 'terapia', 'clínico', 'médico', 'paciente', 'hospital'],
    'biología': ['célula', 'organismo', 'genética', 'evolución', 'ecosistema', 'especie', 'proteína', 'ADN', 'biológico'],
    'química': ['molecular', 'compuesto', 'reacción', 'elemento', 'átomo', 'química', 'síntesis', 'catalizador'],
    'física': ['energía', 'fuerza', 'materia', 'movimiento', 'temperatura', 'presión', 'mecánica', 'cuántico'],
    'neurociencia': ['cerebro', 'neurona', 'cognitivo', 'memoria', 'aprendizaje', 'neural', 'sinapsis', 'cortex'],
    'farmacología': ['fármaco', 'medicamento', 'dosis', 'farmacocinética', 'toxicidad', 'eficacia', 'farmacología']
}

# =========================
# Funciones auxiliares mejoradas
# =========================

def detectar_area_y_tema(texto):
    """
    Detecta el área científica y extrae términos clave específicos.
    """
    try:
        # Normalizar texto
        texto_limpio = re.sub(r'[^\w\s]', ' ', texto.lower())
        palabras = word_tokenize(texto_limpio, language='spanish')
        
        # Filtrar stopwords en español
        try:
            stop_words = set(stopwords.words('spanish'))
        except:
            stop_words = {'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se', 'no', 'te', 'lo', 'le', 'da', 'su', 'por', 'son', 'con', 'para', 'al', 'del', 'los', 'las', 'una', 'como', 'pero', 'sus', 'han', 'ser', 'está', 'este', 'más', 'todo', 'tiene', 'muy', 'bien', 'puede', 'sin', 'hasta', 'entre', 'hacer', 'sobre', 'también', 'donde', 'cuando', 'después', 'todos', 'aunque', 'antes', 'cual', 'cada', 'mismo', 'otros', 'así', 'desde', 'durante', 'mientras', 'tanto', 'según', 'sino', 'vez', 'tal', 'caso', 'forma', 'parte', 'tipo', 'manera', 'través', 'contra'}
        
        palabras_relevantes = [p for p in palabras if len(p) > 3 and p not in stop_words]
        
        # Detectar área científica
        area_scores = {}
        for area, keywords in AREAS_CIENTIFICAS.items():
            score = sum(1 for palabra in palabras_relevantes if any(keyword in palabra or palabra in keyword for keyword in keywords))
            area_scores[area] = score
        
        area_detectada = max(area_scores.items(), key=lambda x: x[1])[0] if max(area_scores.values()) > 0 else 'general'
        
        # Extraer términos clave más frecuentes y relevantes
        contador = Counter(palabras_relevantes)
        terminos_clave = [palabra for palabra, freq in contador.most_common(5) if freq >= 2 or len(palabra) > 6]
        
        # Si no hay términos suficientes, usar los más largos
        if len(terminos_clave) < 2:
            terminos_clave = [palabra for palabra in palabras_relevantes if len(palabra) > 5][:3]
        
        return area_detectada, terminos_clave[:3]  # Máximo 3 términos
        
    except Exception as e:
        print(f"Error en detectar_area_y_tema: {e}")
        return 'general', ['ciencia']


def construir_query_pubmed(area, terminos):
    """
    Construye una query específica para PubMed según el área y términos.
    """
    query_base = " AND ".join(terminos)
    
    # Agregar filtros específicos según el área
    filtros = {
        'medicina': '[Title/Abstract] AND ("clinical trial" OR "systematic review" OR "meta-analysis" OR "randomized controlled trial")',
        'biología': '[Title/Abstract] AND ("molecular biology" OR "cell biology" OR "genetics")',
        'farmacología': '[Title/Abstract] AND ("pharmacology" OR "drug therapy" OR "clinical pharmacology")',
        'neurociencia': '[Title/Abstract] AND ("neuroscience" OR "brain" OR "neural")',
        'química': '[Title/Abstract] AND ("chemistry" OR "chemical" OR "molecular")',
        'física': '[Title/Abstract] AND ("physics" OR "physical sciences")'
    }
    
    filtro = filtros.get(area, '[Title/Abstract]')
    return f"({query_base}) {filtro}"


def evaluar_calidad_articulo_pubmed(info):
    """
    Evalúa la calidad de un artículo de PubMed basado en varios criterios.
    """
    score = 0
    
    # Factor de impacto por tipo de publicación
    pub_types = info.get("pubtype", [])
    for pub_type in pub_types:
        if "Randomized Controlled Trial" in pub_type:
            score += 10
        elif "Systematic Review" in pub_type or "Meta-Analysis" in pub_type:
            score += 15
        elif "Clinical Trial" in pub_type:
            score += 8
        elif "Review" in pub_type:
            score += 5
        elif "Case Reports" in pub_type:
            score += 2
    
    # Año de publicación (más reciente = mejor)
    try:
        year = int(info.get("pubdate", "2000").split(" ")[0])
        if year >= 2020:
            score += 8
        elif year >= 2015:
            score += 5
        elif year >= 2010:
            score += 3
    except:
        pass
    
    # Número de autores (colaboración)
    num_authors = len(info.get("authors", []))
    if num_authors >= 5:
        score += 3
    elif num_authors >= 3:
        score += 2
    
    # Journal con mayor impact factor (heurística simple)
    journal = info.get("fulljournalname", "").lower()
    journals_alto_impacto = ["nature", "science", "cell", "lancet", "nejm", "jama", "pnas"]
    if any(j in journal for j in journals_alto_impacto):
        score += 20
    
    return score


def buscar_pubmed_mejorado(area, terminos):
    """
    Búsqueda mejorada en PubMed con filtros de calidad.
    """
    articulos = []
    try:
        query = construir_query_pubmed(area, terminos)
        print(f"Query PubMed: {query}")
        
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "api_key": PUBMED_API_KEY,
            "retmax": 10,  # Buscamos más para luego filtrar los mejores
            "sort": "relevance"
        }
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        ids = data.get("esearchresult", {}).get("idlist", [])
        print(f"IDs encontrados en PubMed: {len(ids)}")
        
        articulos_candidatos = []
        
        for pmid in ids:
            try:
                time.sleep(0.3)  # Rate limiting
                
                summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                summary_params = {
                    "db": "pubmed",
                    "id": pmid,
                    "retmode": "json",
                    "api_key": PUBMED_API_KEY
                }
                
                s_response = requests.get(summary_url, params=summary_params, timeout=10)
                s_response.raise_for_status()
                s = s_response.json()
                
                info = s.get("result", {}).get(pmid, {})
                if not info or not info.get("title"):
                    continue
                
                # Evaluar calidad
                calidad_score = evaluar_calidad_articulo_pubmed(info)
                
                autores = info.get("authors", [])
                if autores:
                    primer_autor = autores[0].get("name", "").split(",")[0]
                    if len(autores) > 1:
                        autores_texto = f"{primer_autor} et al."
                    else:
                        autores_texto = primer_autor
                else:
                    primer_autor = "Autor desconocido"
                    autores_texto = "Autor desconocido"
                
                año = info.get("pubdate", "").split(" ")[0] if info.get("pubdate") else "s.f."
                journal = info.get("fulljournalname", "Journal desconocido")
                title = info.get("title", "Sin título")
                
                articulo = {
                    "cita_texto": f"{primer_autor}, {año}",
                    "referencia": f"{autores_texto} ({año}). {title}. {journal}. PMID: {pmid}",
                    "calidad_score": calidad_score,
                    "tipo": "PubMed",
                    "año": año,
                    "journal": journal
                }
                
                articulos_candidatos.append(articulo)
                
            except Exception as e:
                print(f"Error procesando PMID {pmid}: {e}")
                continue
        
        # Ordenar por calidad y tomar los mejores
        articulos_candidatos.sort(key=lambda x: x["calidad_score"], reverse=True)
        articulos = articulos_candidatos[:3]  # Top 3 por calidad
        
        print(f"Artículos de PubMed seleccionados: {len(articulos)}")
        for art in articulos:
            print(f"  - Score: {art['calidad_score']}, {art['cita_texto']}")
        
    except Exception as e:
        print(f"Error en buscar_pubmed_mejorado: {e}")
    
    return articulos


def buscar_google_scholar_mejorado(area, terminos):
    """
    Búsqueda mejorada en Google Scholar con filtros académicos.
    """
    articulos = []
    try:
        # Construir query más específica
        query_terminos = " ".join(terminos)
        query_completa = f'"{query_terminos}" filetype:pdf OR site:researchgate.net OR site:springer.com OR site:sciencedirect.com'
        
        print(f"Query Google Scholar: {query_completa}")
        
        url = "https://serpapi.com/search"
        params = {
            "engine": "google_scholar",
            "q": query_completa,
            "api_key": SERPAPI_KEY,
            "num": 10,
            "as_ylo": 2015  # Solo artículos desde 2015
        }
        
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        
        resultados = data.get("organic_results", [])
        print(f"Resultados Google Scholar: {len(resultados)}")
        
        for art in resultados:
            try:
                title = art.get("title", "").strip()
                if not title or len(title) < 10:
                    continue
                
                # Filtrar solo resultados académicos de calidad
                link = art.get("link", "")
                dominios_academicos = ["researchgate", "springer", "sciencedirect", "pubmed", "arxiv", "jstor", "wiley", "tandfonline", "sage", "nature", "science"]
                
                if not any(dominio in link for dominio in dominios_academicos) and not link.endswith('.pdf'):
                    continue
                
                # Extraer información de publicación
                pub_info = art.get("publication_info", {})
                snippet = art.get("snippet", "")
                
                # Evaluar relevancia por snippet
                relevancia_score = 0
                for termino in terminos:
                    if termino.lower() in snippet.lower():
                        relevancia_score += 2
                    if termino.lower() in title.lower():
                        relevancia_score += 3
                
                if relevancia_score < 2:  # Filtrar artículos poco relevantes
                    continue
                
                if isinstance(pub_info, dict):
                    autores_info = pub_info.get("authors", [])
                    año = pub_info.get("year", "s.f.")
                else:
                    autores_info = []
                    año = "s.f."
                
                if autores_info:
                    if isinstance(autores_info[0], dict):
                        primer_autor = autores_info[0].get("name", "").split(",")[0].split(" ")[-1]
                    else:
                        primer_autor = str(autores_info[0]).split(",")[0].split(" ")[-1]
                else:
                    primer_autor = "Autor desconocido"
                
                # Truncar título si es muy largo
                if len(title) > 120:
                    title = title[:120] + "..."
                
                articulo = {
                    "cita_texto": f"{primer_autor}, {año}",
                    "referencia": f"{primer_autor} et al. ({año}). {title}. Disponible en: {link}",
                    "relevancia_score": relevancia_score,
                    "tipo": "Google Scholar"
                }
                
                articulos.append(articulo)
                
            except Exception as e:
                print(f"Error procesando resultado Scholar: {e}")
                continue
        
        # Ordenar por relevancia
        articulos.sort(key=lambda x: x["relevancia_score"], reverse=True)
        articulos = articulos[:2]  # Top 2 más relevantes
        
        print(f"Artículos Google Scholar seleccionados: {len(articulos)}")
        
    except Exception as e:
        print(f"Error en buscar_google_scholar_mejorado: {e}")
    
    return articulos


def insertar_citas_inteligente(texto, citas):
    """
    Inserta citas de manera más inteligente basada en el contenido.
    """
    try:
        if not citas:
            return texto
        
        oraciones = re.split(r'(?<=[.!?]) +', texto.strip())
        oraciones = [o.strip() for o in oraciones if o.strip()]
        
        if len(oraciones) == 0:
            return texto
        
        # Insertar citas en oraciones con afirmaciones científicas
        oraciones_con_citas = []
        cita_index = 0
        
        for i, oracion in enumerate(oraciones):
            oracion_procesada = oracion
            
            # Identificar oraciones que necesitan citas (afirmaciones, datos, resultados)
            patrones_citas = [
                r'\b(estudios? muestran?|investigación|evidencia|datos|resultados?|análisis)\b',
                r'\b(según|de acuerdo|investigadores?|científicos?)\b',
                r'\b(se ha demostrado|se observa|se encuentra)\b',
                r'\b(porcentaje|estadística|prevalencia|incidencia)\b'
            ]
            
            necesita_cita = any(re.search(patron, oracion.lower()) for patron in patrones_citas)
            
            # También citar cada 2-3 oraciones si no hay patrones específicos
            if not necesita_cita and i > 0 and i % 3 == 0:
                necesita_cita = True
            
            if necesita_cita and cita_index < len(citas):
                oracion_procesada = oracion.rstrip() + f" ({citas[cita_index]['cita_texto']})"
                cita_index += 1
            
            oraciones_con_citas.append(oracion_procesada)
        
        # Si quedan citas sin usar, distribuirlas en oraciones restantes
        while cita_index < len(citas) and len(oraciones_con_citas) > 0:
            pos = len(oraciones_con_citas) - (len(citas) - cita_index)
            if pos >= 0 and pos < len(oraciones_con_citas):
                if not re.search(r'\([^)]+,\s*\d{4}\)$', oraciones_con_citas[pos]):
                    oraciones_con_citas[pos] = oraciones_con_citas[pos].rstrip() + f" ({citas[cita_index]['cita_texto']})"
                    cita_index += 1
            else:
                break
        
        return " ".join(oraciones_con_citas)
        
    except Exception as e:
        print(f"Error en insertar_citas_inteligente: {e}")
        return texto


# =========================
# Endpoint principal mejorado
# =========================
@app.route("/citar", methods=["POST"])
def citar_texto():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No se recibieron datos JSON válidos"}), 400
        
        texto = data.get("texto", "").strip()
        if not texto:
            return jsonify({"error": "El campo 'texto' es requerido"}), 400
        
        if len(texto) > 3000:
            return jsonify({"error": "Texto demasiado largo (máximo 3000 caracteres)"}), 400
        
        print(f"Procesando texto de {len(texto)} caracteres")
        
        # Detectar área científica y términos clave
        area, terminos = detectar_area_y_tema(texto)
        print(f"Área detectada: {area}")
        print(f"Términos clave: {terminos}")
        
        # Buscar artículos de calidad
        articulos_pubmed = []
        articulos_scholar = []
        
        if terminos:
            try:
                articulos_pubmed = buscar_pubmed_mejorado(area, terminos)
            except Exception as e:
                print(f"Error en búsqueda PubMed: {e}")
            
            try:
                articulos_scholar = buscar_google_scholar_mejorado(area, terminos)
            except Exception as e:
                print(f"Error en búsqueda Google Scholar: {e}")
        
        # Combinar resultados priorizando PubMed
        todos_articulos = articulos_pubmed + articulos_scholar
        
        if not todos_articulos:
            return jsonify({
                "area_detectada": area,
                "terminos_clave": terminos,
                "texto_original": texto,
                "texto_citado": texto,
                "mensaje": "No se encontraron artículos científicos de calidad para los términos detectados",
                "referencias": [],
                "recomendacion": "Intenta con un texto más específico o técnico del área científica"
            })
        
        # Insertar citas inteligentemente
        texto_citado = insertar_citas_inteligente(texto, todos_articulos)
        
        # Preparar referencias organizadas
        referencias = [art["referencia"] for art in todos_articulos]
        
        return jsonify({
            "area_detectada": area,
            "terminos_clave": terminos,
            "texto_original": texto,
            "texto_citado": texto_citado,
            "referencias": referencias,
            "total_citas": len(referencias),
            "fuentes": {
                "pubmed": len(articulos_pubmed),
                "google_scholar": len(articulos_scholar)
            },
            "calidad": "Se priorizaron artículos científicos de journals reconocidos y publicaciones recientes"
        })
    
    except Exception as e:
        print(f"Error general: {e}")
        return jsonify({
            "error": "Error interno del servidor",
            "mensaje": "Error al procesar la solicitud",
            "recomendacion": "Verifica que el texto sea claro y contenga términos científicos específicos"
        }), 500


@app.route("/test", methods=["GET"])
def test():
    return jsonify({"mensaje": "Servidor funcionando - Sistema de citas científicas mejorado"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
