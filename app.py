from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import re
import time
from collections import Counter

# Inicializar NLTK de manera segura
try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    
    # Descargar recursos de NLTK si no están disponibles
    try:
        nltk.data.find('tokenizers/punkt')
        nltk.data.find('corpora/stopwords')
    except LookupError:
        print("Descargando recursos de NLTK...")
        nltk.download('punkt', quiet=True)
        nltk.download('stopwords', quiet=True)
    
    NLTK_AVAILABLE = True
except ImportError:
    print("NLTK no disponible, usando tokenización básica")
    NLTK_AVAILABLE = False

app = Flask(__name__)
CORS(app)  # Permitir CORS para GPT

# Claves API - usar variables de entorno en producción
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY", "d65daf8493357bd078d3abe98d1860dd9608")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "4656512120f4468e4bbc0ea857a2db17af9b68eb301e50f940529c3a3073674a")

# Areas científicas especializadas (enfocado en fisioterapia y ciencias de la salud)
AREAS_CIENTIFICAS = {
    'fisioterapia': ['fisioterapia', 'rehabilitación', 'kinesioterapia', 'ejercicio', 'movilidad', 'kinesiología', 'terapia física', 'movimiento'],
    'respiratorio': ['respiración', 'pulmonar', 'ventilación', 'pulmón', 'respiratorio', 'oxígeno', 'co2', 'espirometría'],
    'musculoesquelético': ['músculo', 'hueso', 'articulación', 'tendón', 'ligamento', 'esquelético', 'biomecánica', 'postura'],
    'neurología': ['neurológico', 'cerebro', 'neurona', 'sistema nervioso', 'motor', 'sensorial', 'rehabilitación neurológica'],
    'cardiaco': ['corazón', 'cardíaco', 'cardiovascular', 'circulación', 'presión arterial', 'rehabilitación cardíaca'],
    'medicina': ['salud', 'enfermedad', 'tratamiento', 'diagnóstico', 'síntoma', 'terapia', 'clínico', 'médico', 'paciente'],
    'biomecánica': ['biomecánica', 'movimiento', 'fuerza', 'análisis del movimiento', 'cinemática', 'cinética', 'gait'],
    'dolor': ['dolor', 'analgesia', 'nociceptivo', 'crónico', 'agudo', 'manejo del dolor', 'algología']
}

def tokenizar_texto(texto):
    """Tokenizar texto con o sin NLTK"""
    if NLTK_AVAILABLE:
        try:
            return word_tokenize(texto, language='spanish')
        except:
            return word_tokenize(texto)
    else:
        # Tokenización básica sin NLTK
        texto = re.sub(r'[^\w\s]', ' ', texto)
        return texto.split()

def obtener_stopwords():
    """Obtener stopwords con o sin NLTK"""
    if NLTK_AVAILABLE:
        try:
            return set(stopwords.words('spanish'))
        except:
            pass
    
    # Stopwords básicas en español si NLTK no está disponible
    return {'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se', 'no', 'te', 'lo', 'le', 'da', 'su', 'por', 'son', 'con', 'para', 'al', 'del', 'los', 'las', 'una', 'como', 'pero', 'sus', 'han', 'ser', 'está', 'este', 'más', 'todo', 'tiene', 'muy', 'bien', 'puede', 'sin', 'hasta', 'entre', 'hacer', 'sobre', 'también', 'donde', 'cuando', 'después', 'todos', 'aunque', 'antes', 'cual', 'cada', 'mismo', 'otros', 'así', 'desde', 'durante', 'mientras', 'tanto', 'según', 'sino', 'vez', 'tal', 'caso', 'forma', 'parte', 'tipo', 'manera', 'través', 'contra'}

def detectar_area_cientifica(texto):
    """Detecta el área científica del texto"""
    try:
        texto_limpio = re.sub(r'[^\w\s]', ' ', texto.lower())
        palabras = tokenizar_texto(texto_limpio)
        
        stop_words = obtener_stopwords()
        
        palabras_relevantes = [p for p in palabras if len(p) > 3 and p not in stop_words]
        
        # Detectar área científica
        area_scores = {}
        for area, keywords in AREAS_CIENTIFICAS.items():
            score = sum(1 for palabra in palabras_relevantes if any(keyword in palabra or palabra in keyword for keyword in keywords))
            area_scores[area] = score
        
        return max(area_scores.items(), key=lambda x: x[1])[0] if max(area_scores.values()) > 0 else 'general'
        
    except Exception as e:
        print(f"Error en detectar_area_cientifica: {e}")
        return 'general'

def extraer_terminos_clave_especificos(texto):
    """Extrae términos clave más específicos y relevantes para el tema exacto"""
    try:
        texto_limpio = re.sub(r'[^\w\s]', ' ', texto.lower())
        palabras = tokenizar_texto(texto_limpio)
        
        # Stopwords expandidas para eliminar palabras muy generales
        stop_words = obtener_stopwords()
        stop_words.update({'sistema', 'proceso', 'función', 'área', 'nivel', 'importante', 'general', 'principal', 'mayor', 'mejor', 'gran', 'diferentes', 'varios', 'muchos'})
        
        # Filtrar palabras relevantes (mínimo 4 caracteres, no stopwords)
        palabras_relevantes = [p for p in palabras if len(p) >= 4 and p not in stop_words]
        
        # Buscar términos compuestos específicos (frases de 2-3 palabras)
        terminos_compuestos = []
        for i in range(len(palabras) - 1):
            if palabras[i] not in stop_words and palabras[i+1] not in stop_words:
                termino_compuesto = f"{palabras[i]} {palabras[i+1]}"
                if len(termino_compuesto) > 8:  # Solo términos compuestos significativos
                    terminos_compuestos.append(termino_compuesto)
        
        # Buscar términos de 3 palabras para conceptos muy específicos
        for i in range(len(palabras) - 2):
            if (palabras[i] not in stop_words and 
                palabras[i+1] not in stop_words and 
                palabras[i+2] not in stop_words and
                len(palabras[i]) > 3 and len(palabras[i+1]) > 3):
                termino_triple = f"{palabras[i]} {palabras[i+1]} {palabras[i+2]}"
                if len(termino_triple) > 12:
                    terminos_compuestos.append(termino_triple)
        
        # Priorizar términos técnicos y específicos
        terminos_tecnicos = []
        for palabra in palabras_relevantes:
            # Términos que suelen ser técnicos/específicos
            if (len(palabra) > 6 or 
                any(sufijo in palabra for sufijo in ['ción', 'sión', 'tivo', 'osis', 'itis', 'logía', 'patía', 'tomía']) or
                any(prefijo in palabra for prefijo in ['bio', 'fisio', 'neuro', 'cardio', 'pulmo', 'mio', 'osteo', 'artro'])):
                terminos_tecnicos.append(palabra)
        
        # Combinar y priorizar términos
        contador_simples = Counter(palabras_relevantes)
        contador_compuestos = Counter(terminos_compuestos)
        
        # Seleccionar los mejores términos
        mejores_terminos = []
        
        # 1. Priorizar términos compuestos específicos
        for termino, freq in contador_compuestos.most_common(2):
            mejores_terminos.append(termino)
        
        # 2. Agregar términos técnicos únicos
        for termino in terminos_tecnicos[:2]:
            if termino not in ' '.join(mejores_terminos):
                mejores_terminos.append(termino)
        
        # 3. Completar con términos frecuentes si hace falta
        for termino, freq in contador_simples.most_common(5):
            if len(mejores_terminos) < 4 and termino not in ' '.join(mejores_terminos) and len(termino) > 4:
                mejores_terminos.append(termino)
        
        # Si no hay suficientes términos específicos, tomar los más largos
        if len(mejores_terminos) < 2:
            terminos_largos = [p for p in palabras_relevantes if len(p) > 5]
            mejores_terminos.extend(terminos_largos[:3])
        
        return mejores_terminos[:4] if mejores_terminos else [texto.split()[0] if texto.split() else "fisioterapia"]
        
    except Exception as e:
        print(f"Error en extraer_terminos_clave_especificos: {e}")
        return [texto.split()[0] if texto.split() else "fisioterapia"]

def buscar_pubmed_apa_especifico(terminos, max_results=3):
    """Búsqueda ultra-específica en PubMed para temas de fisioterapia"""
    citas = []
    try:
        # Construir query muy específica
        if len(terminos) > 1:
            # Para términos múltiples, usar combinaciones más estrictas
            query_principal = f'("{" ".join(terminos)}"[Title/Abstract])'
            
            # Query alternativa con términos individuales más específicos
            terminos_especificos = [f'"{t}"[Title/Abstract]' for t in terminos if len(t) > 4]
            query_alternativa = " AND ".join(terminos_especificos) if terminos_especificos else f'"{terminos[0]}"[Title/Abstract]'
            
            # Combinar ambas queries
            query = f"({query_principal}) OR ({query_alternativa})"
        else:
            # Para un solo término, ser muy específico
            query = f'"{terminos[0]}"[Title/Abstract]'
        
        # Agregar filtros de calidad y especialización
        filtros_fisioterapia = [
            '"physical therapy"[MeSH Terms]',
            '"rehabilitation"[MeSH Terms]', 
            '"exercise therapy"[MeSH Terms]',
            '"musculoskeletal system"[MeSH Terms]',
            '"respiratory therapy"[MeSH Terms]'
        ]
        
        # Detectar si es específicamente de fisioterapia para agregar filtros
        tema_fisio = any(term in ' '.join(terminos).lower() for term in 
                        ['fisioterapia', 'rehabilitación', 'ejercicio', 'terapia', 'movimiento', 'respiración', 'músculo'])
        
        if tema_fisio:
            query += f" AND ({' OR '.join(filtros_fisioterapia[:3])})"
        
        # Filtros adicionales de calidad
        query += ' AND ("last 10 years"[PDat] OR "last 5 years"[PDat])'
        
        print(f"Query PubMed específica: {query}")
        
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "api_key": PUBMED_API_KEY,
            "retmax": max_results * 3,  # Buscar más para filtrar por relevancia
            "sort": "relevance"
        }
        
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            print(f"Error en búsqueda PubMed: {response.status_code}")
            return citas
        
        data = response.json()
        ids = data.get("esearchresult", {}).get("idlist", [])
        print(f"IDs encontrados: {len(ids)}")
        
        articulos_evaluados = []
        
        for pmid in ids[:max_results * 2]:  # Procesar más para seleccionar mejores
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
                if s_response.status_code != 200:
                    continue
                
                s = s_response.json()
                info = s.get("result", {}).get(pmid, {})
                
                if not info or not info.get("title"):
                    continue
                
                title = info.get("title", "").lower()
                
                # EVALUACIÓN DE RELEVANCIA ESPECÍFICA
                relevance_score = 0
                
                # 1. Verificar que el título contenga términos específicos
                for termino in terminos:
                    termino_clean = termino.lower().strip()
                    if len(termino_clean) > 3:
                        if termino_clean in title:
                            relevance_score += 10  # Puntuación alta por coincidencia exacta en título
                        elif any(word in title for word in termino_clean.split()):
                            relevance_score += 5   # Puntuación media por palabras del término
                
                # 2. Verificar especificidad del tema
                combined_text = title
                
                # Contar coincidencias específicas en título
                for termino in terminos:
                    coincidencias = combined_text.count(termino.lower())
                    relevance_score += coincidencias * 3
                
                # 3. Filtrar artículos poco relevantes
                if relevance_score < 8:  # Umbral mínimo de relevancia
                    print(f"Artículo {pmid} descartado por baja relevancia: {relevance_score}")
                    continue
                
                # Extraer información para formato APA
                autores = info.get("authors", [])
                title_original = info.get("title", "").strip()
                if title_original.endswith('.'):
                    title_original = title_original[:-1]
                
                # Procesar autores para APA
                if autores:
                    if len(autores) == 1:
                        autor_apa = autores[0].get("name", "").replace(" ", ", ", 1)
                    elif len(autores) <= 6:
                        autor_list = []
                        for i, autor in enumerate(autores):
                            nombre = autor.get("name", "")
                            if i == 0:
                                autor_list.append(nombre.replace(" ", ", ", 1))
                            else:
                                autor_list.append(nombre)
                        if len(autor_list) > 1:
                            autor_apa = ", ".join(autor_list[:-1]) + ", & " + autor_list[-1]
                        else:
                            autor_apa = autor_list[0]
                    else:
                        primer_autor = autores[0].get("name", "").replace(" ", ", ", 1)
                        autor_apa = f"{primer_autor}, et al."
                else:
                    autor_apa = "Autor desconocido"
                
                # Año y journal
                pubdate = info.get("pubdate", "")
                año = pubdate.split(" ")[0] if pubdate else "s.f."
                journal = info.get("fulljournalname", info.get("source", "Journal desconocido"))
                
                articulo = {
                    "cita_apa": f"{autor_apa} ({año}). {title_original}. *{journal}*. https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "relevance_score": relevance_score,
                    "pmid": pmid
                }
                
                articulos_evaluados.append(articulo)
                
            except Exception as e:
                print(f"Error procesando PMID {pmid}: {e}")
                continue
        
        # Ordenar por relevancia y seleccionar los mejores
        articulos_evaluados.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        for articulo in articulos_evaluados[:max_results]:
            citas.append(articulo["cita_apa"])
            print(f"Seleccionado - Score: {articulo['relevance_score']}, PMID: {articulo['pmid']}")
    
    except Exception as e:
        print(f"Error en buscar_pubmed_apa_especifico: {e}")
    
    return citas

def buscar_google_scholar_apa_especifico(terminos, max_results=2):
    """Búsqueda ultra-específica en Google Scholar para fisioterapia"""
    citas = []
    try:
        # Construir query muy específica para Scholar
        if len(terminos) > 1:
            # Usar comillas para búsquedas exactas de términos compuestos
            query_principal = f'"{" ".join(terminos)}"'
            terminos_individuales = " AND ".join([f'"{t}"' for t in terminos if len(t) > 4])
            query = f'({query_principal}) OR ({terminos_individuales})'
        else:
            query = f'"{terminos[0]}"'
        
        # Agregar filtros específicos para fisioterapia y ciencias de la salud
        query += ' AND ("physical therapy" OR "physiotherapy" OR "rehabilitation" OR "exercise therapy")'
        
        # Filtrar por dominios académicos de calidad
        query += ' AND (site:pubmed.ncbi.nlm.nih.gov OR site:researchgate.net OR site:springer.com OR site:sciencedirect.com OR filetype:pdf)'
        
        print(f"Query Google Scholar específica: {query}")
        
        url = "https://serpapi.com/search"
        params = {
            "engine": "google_scholar",
            "q": query,
            "api_key": SERPAPI_KEY,
            "num": max_results * 3,  # Buscar más para filtrar
            "as_ylo": 2018  # Solo artículos desde 2018
        }
        
        response = requests.get(url, params=params, timeout=20)
        if response.status_code != 200:
            print(f"Error en Google Scholar: {response.status_code}")
            return citas
        
        data = response.json()
        resultados = data.get("organic_results", [])
        print(f"Resultados Scholar encontrados: {len(resultados)}")
        
        articulos_evaluados = []
        
        for art in resultados:
            try:
                title = art.get("title", "").strip()
                if not title or len(title) < 15:
                    continue
                
                # EVALUACIÓN DE RELEVANCIA ESPECÍFICA
                snippet = art.get("snippet", "")
                combined_text = f"{title} {snippet}".lower()
                
                relevance_score = 0
                
                # 1. Verificar coincidencias exactas de términos en título
                for termino in terminos:
                    termino_clean = termino.lower().strip()
                    if len(termino_clean) > 3:
                        if termino_clean in title.lower():
                            relevance_score += 15  # Alta puntuación por término en título
                        elif termino_clean in snippet.lower():
                            relevance_score += 8   # Puntuación media por término en snippet
                        
                        # Verificar palabras individuales del término
                        palabras_termino = termino_clean.split()
                        for palabra in palabras_termino:
                            if len(palabra) > 3 and palabra in combined_text:
                                relevance_score += 3
                
                # 2. Verificar que sea de fuente académica confiable
                link = art.get("link", "")
                dominios_academicos = [
                    "pubmed", "researchgate", "springer", "sciencedirect", 
                    "wiley", "tandfonline", "sage", "nature", "science",
                    "ncbi", "plos", "bmj", "elsevier", "jstor"
                ]
                
                es_academico = any(dominio in link for dominio in dominios_academicos) or link.endswith('.pdf')
                if not es_academico:
                    relevance_score -= 5  # Penalizar fuentes no académicas
                
                # 3. Filtrar artículos poco relevantes
                if relevance_score < 10:  # Umbral más estricto
                    print(f"Artículo Scholar descartado por baja relevancia: {relevance_score}")
                    continue
                
                # Extraer información para APA
                pub_info = art.get("publication_info", {})
                
                if isinstance(pub_info, dict):
                    autores_info = pub_info.get("authors", [])
                    año = pub_info.get("year", "s.f.")
                    journal = pub_info.get("summary", "")
                else:
                    autores_info = []
                    año = "s.f."
                    journal = ""
                
                # Procesar autores
                if autores_info:
                    if isinstance(autores_info[0], dict):
                        primer_autor = autores_info[0].get("name", "")
                    else:
                        primer_autor = str(autores_info[0])
                    
                    if len(autores_info) == 1:
                        autor_apa = primer_autor
                    else:
                        autor_apa = f"{primer_autor}, et al."
                else:
                    autor_apa = "Autor desconocido"
                
                # Limpiar título
                if title.endswith('.'):
                    title = title[:-1]
                
                # Truncar título si es muy largo
                if len(title) > 120:
                    title = title[:120] + "..."
                
                # Determinar fuente para la cita
                if "pubmed" in link:
                    fuente = "PubMed"
                elif journal and len(journal) > 5:
                    fuente = f"*{journal}*"
                else:
                    fuente = "Recuperado de " + link
                
                articulo = {
                    "cita_apa": f"{autor_apa} ({año}). {title}. {fuente}",
                    "relevance_score": relevance_score,
                    "link": link
                }
                
                articulos_evaluados.append(articulo)
                
            except Exception as e:
                print(f"Error procesando resultado Scholar: {e}")
                continue
        
        # Ordenar por relevancia y seleccionar los mejores
        articulos_evaluados.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        for articulo in articulos_evaluados[:max_results]:
            citas.append(articulo["cita_apa"])
            print(f"Scholar seleccionado - Score: {articulo['relevance_score']}")
    
    except Exception as e:
        print(f"Error en buscar_google_scholar_apa_especifico: {e}")
    
    return citas

# =========================
# ENDPOINT PARA GPT
# =========================
@app.route("/buscar", methods=["GET"])
def buscar_citas_apa():
    """
    Endpoint compatible con GPT personalizado según especificación OpenAPI
    """
    try:
        # Obtener parámetro de query
        tema = request.args.get('q', '').strip()
        
        if not tema:
            return jsonify({
                "error": "Parámetro 'q' requerido",
                "tema": "",
                "citas": []
            }), 400
        
        if len(tema) > 200:
            return jsonify({
                "error": "Query demasiado largo (máximo 200 caracteres)",
                "tema": tema,
                "citas": []
            }), 400
        
        print(f"Buscando citas para: {tema}")
        
        # Detectar área y extraer términos específicos
        area = detectar_area_cientifica(tema)
        terminos = extraer_terminos_clave_especificos(tema)  # Función mejorada
        
        print(f"Área: {area}, Términos específicos: {terminos}")
        
        # Buscar citas con métodos ultra-específicos
        citas_pubmed = []
        citas_scholar = []
        
        try:
            citas_pubmed = buscar_pubmed_apa_especifico(terminos, max_results=3)  # Función mejorada
        except Exception as e:
            print(f"Error PubMed: {e}")
        
        try:
            citas_scholar = buscar_google_scholar_apa_especifico(terminos, max_results=2)  # Función mejorada
        except Exception as e:
            print(f"Error Google Scholar: {e}")
        
        # Combinar todas las citas (priorizar PubMed)
        todas_citas = citas_pubmed + citas_scholar
        
        # Filtro final de calidad - eliminar citas duplicadas o muy similares
        citas_filtradas = []
        for cita in todas_citas:
            es_duplicada = False
            for cita_existente in citas_filtradas:
                # Verificar similitud básica por título
                titulo_nuevo = cita.split('. ')[1] if '. ' in cita else cita
                titulo_existente = cita_existente.split('. ')[1] if '. ' in cita_existente else cita_existente
                if titulo_nuevo[:50].lower() == titulo_existente[:50].lower():
                    es_duplicada = True
                    break
            if not es_duplicada:
                citas_filtradas.append(cita)
        
        # Respuesta según especificación OpenAPI
        response = {
            "tema": tema,
            "citas": todas_citas
        }
        
        print(f"Devolviendo {len(todas_citas)} citas")
        
        return jsonify(response), 200
    
    except Exception as e:
        print(f"Error general en buscar_citas_apa: {e}")
        return jsonify({
            "error": "Error interno del servidor",
            "tema": tema if 'tema' in locals() else "",
            "citas": []
        }), 500

# Endpoint adicional para información de la API
@app.route("/", methods=["GET"])
def info_api():
    """Información básica de la API"""
    return jsonify({
        "title": "API de Citas APA",
        "description": "API para buscar artículos en PubMed y Google Scholar y devolver citas en formato APA.",
        "version": "1.0.0",
        "endpoints": {
            "buscar": {
                "method": "GET",
                "url": "/buscar?q=tema_de_busqueda",
                "description": "Buscar artículos científicos y devolver citas en formato APA"
            }
        },
        "ejemplo": "/buscar?q=diabetes%20tipo%202%20tratamiento"
    })

# Endpoint de salud para verificar que la API funciona
@app.route("/health", methods=["GET"])
def health_check():
    """Health check para verificar que la API está funcionando"""
    return jsonify({
        "status": "healthy",
        "message": "API funcionando correctamente"
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
