from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import re
import time
from collections import Counter
import json

# Inicializar NLTK de manera segura
try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize, sent_tokenize
    
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
CORS(app)

# Claves API - usar variables de entorno en producción
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY", "d65daf8493357bd078d3abe98d1860dd9608")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "4656512120f4468e4bbc0ea857a2db17af9b68eb301e50f940529c3a3073674a")

# Términos MeSH y DeCS para fisioterapia y ciencias de la salud
MESH_DECS_MAPPING = {
    'fisioterapia': {
        'mesh': ['Physical Therapy Modalities', 'Physical Therapy Specialty', 'Physical Therapists'],
        'decs': ['Modalidades de Fisioterapia', 'Especialidad de Fisioterapia', 'Fisioterapeutas'],
        'keywords': ['physiotherapy', 'physical therapy', 'rehabilitation therapy']
    },
    'respiratorio': {
        'mesh': ['Respiratory Therapy', 'Breathing Exercises', 'Pulmonary Rehabilitation'],
        'decs': ['Terapia Respiratoria', 'Ejercicios Respiratorios', 'Rehabilitación Pulmonar'],
        'keywords': ['respiratory rehabilitation', 'pulmonary therapy', 'breathing therapy']
    },
    'musculoesquelético': {
        'mesh': ['Musculoskeletal System', 'Exercise Therapy', 'Muscle Strengthening'],
        'decs': ['Sistema Musculoesquelético', 'Terapia por Ejercicio', 'Fortalecimiento Muscular'],
        'keywords': ['musculoskeletal rehabilitation', 'exercise therapy', 'muscle strengthening']
    },
    'neurologia': {
        'mesh': ['Neurological Rehabilitation', 'Motor Skills', 'Neural Plasticity'],
        'decs': ['Rehabilitación Neurológica', 'Destreza Motora', 'Plasticidad Neuronal'],
        'keywords': ['neurological rehabilitation', 'neurorehabilitation', 'motor recovery']
    },
    'cardiaco': {
        'mesh': ['Cardiac Rehabilitation', 'Exercise Therapy', 'Cardiovascular System'],
        'decs': ['Rehabilitación Cardiaca', 'Terapia por Ejercicio', 'Sistema Cardiovascular'],
        'keywords': ['cardiac rehabilitation', 'cardiovascular rehabilitation', 'heart rehabilitation']
    },
    'dolor': {
        'mesh': ['Pain Management', 'Chronic Pain', 'Pain Therapy'],
        'decs': ['Manejo del Dolor', 'Dolor Crónico', 'Terapia del Dolor'],
        'keywords': ['pain management', 'pain therapy', 'chronic pain treatment']
    }
}

def tokenizar_texto(texto):
    """Tokenizar texto con o sin NLTK"""
    if NLTK_AVAILABLE:
        try:
            return word_tokenize(texto, language='spanish')
        except:
            return word_tokenize(texto)
    else:
        texto = re.sub(r'[^\w\s]', ' ', texto)
        return texto.split()

def obtener_stopwords():
    """Obtener stopwords con o sin NLTK"""
    if NLTK_AVAILABLE:
        try:
            return set(stopwords.words('spanish'))
        except:
            pass
    
    return {'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se', 'no', 'te', 'lo', 'le', 'da', 'su', 'por', 'son', 'con', 'para', 'al', 'del', 'los', 'las', 'una', 'como', 'pero', 'sus', 'han', 'ser', 'está', 'este', 'más', 'todo', 'tiene', 'muy', 'bien', 'puede', 'sin', 'hasta', 'entre', 'hacer', 'sobre', 'también', 'donde', 'cuando', 'después', 'todos', 'aunque', 'antes', 'cual', 'cada', 'mismo', 'otros', 'así', 'desde', 'durante', 'mientras', 'tanto', 'según', 'sino', 'vez', 'tal', 'caso', 'forma', 'parte', 'tipo', 'manera', 'través', 'contra'}

def detectar_conceptos_mesh_decs(texto):
    """Detecta conceptos relevantes y mapea a términos MeSH/DeCS"""
    try:
        texto_limpio = re.sub(r'[^\w\s]', ' ', texto.lower())
        palabras = tokenizar_texto(texto_limpio)
        stop_words = obtener_stopwords()
        palabras_relevantes = [p for p in palabras if len(p) > 3 and p not in stop_words]
        
        conceptos_encontrados = {}
        mesh_terms = []
        decs_terms = []
        keywords = []
        
        # Buscar coincidencias con las áreas definidas
        for area, terminos in MESH_DECS_MAPPING.items():
            score = 0
            for palabra in palabras_relevantes:
                # Verificar coincidencias con keywords del área
                for keyword in terminos.get('keywords', []):
                    if keyword.lower() in texto.lower() or any(k in palabra for k in keyword.split()):
                        score += 5
                
                # Verificar coincidencias directas
                area_keywords = [area] + terminos.get('keywords', [])
                for ak in area_keywords:
                    if ak.lower() in palabra or palabra in ak.lower():
                        score += 3
            
            if score > 0:
                conceptos_encontrados[area] = score
                mesh_terms.extend(terminos.get('mesh', []))
                decs_terms.extend(terminos.get('decs', []))
                keywords.extend(terminos.get('keywords', []))
        
        # Si no se encuentran conceptos específicos, usar términos generales
        if not conceptos_encontrados:
            mesh_terms = ['Physical Therapy Modalities', 'Rehabilitation']
            keywords = ['physical therapy', 'rehabilitation']
        
        return {
            'conceptos': conceptos_encontrados,
            'mesh_terms': list(set(mesh_terms)),
            'decs_terms': list(set(decs_terms)),
            'keywords': list(set(keywords))
        }
        
    except Exception as e:
        print(f"Error en detectar_conceptos_mesh_decs: {e}")
        return {
            'conceptos': {},
            'mesh_terms': ['Physical Therapy Modalities'],
            'decs_terms': ['Modalidades de Fisioterapia'],
            'keywords': ['physical therapy']
        }

def obtener_mesh_relacionados(termino):
    """Obtiene términos MeSH relacionados usando la API de MeSH"""
    mesh_relacionados = []
    try:
        # Buscar en la base de datos MeSH
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "mesh",
            "term": f"{termino}[MH]",
            "retmode": "json",
            "retmax": 5
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            mesh_ids = data.get("esearchresult", {}).get("idlist", [])
            
            # Obtener detalles de los términos MeSH encontrados
            if mesh_ids:
                summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                summary_params = {
                    "db": "mesh",
                    "id": ",".join(mesh_ids),
                    "retmode": "json"
                }
                
                s_response = requests.get(summary_url, params=summary_params, timeout=10)
                if s_response.status_code == 200:
                    s_data = s_response.json()
                    for mesh_id in mesh_ids:
                        mesh_info = s_data.get("result", {}).get(mesh_id, {})
                        mesh_term = mesh_info.get("ds_meshterms", [""])[0]
                        if mesh_term:
                            mesh_relacionados.append(mesh_term)
        
    except Exception as e:
        print(f"Error obteniendo MeSH relacionados: {e}")
    
    return mesh_relacionados

def buscar_articulos_mesh_avanzado(mesh_terms, keywords, conceptos_texto, max_results=5):
    """Búsqueda avanzada usando todas las capacidades de PubMed y MeSH"""
    articulos = []
    try:
        # 1. EXPANDIR TÉRMINOS MESH CON SINÓNIMOS Y RELACIONADOS
        mesh_expandidos = set(mesh_terms)
        
        # Obtener términos MeSH relacionados para mayor cobertura
        for term in mesh_terms[:2]:  # Solo para los términos principales
            relacionados = obtener_mesh_relacionados(term)
            mesh_expandidos.update(relacionados[:2])  # Máximo 2 relacionados por término
        
        print(f"MeSH expandidos: {list(mesh_expandidos)}")
        
        # 2. CONSTRUIR QUERY AVANZADA CON MÚLTIPLES ESTRATEGIAS
        queries = []
        
        # Estrategia 1: Términos MeSH principales con subheadings
        mesh_principales = []
        for term in list(mesh_expandidos)[:4]:  # Máximo 4 términos principales
            # Agregar término MeSH básico
            mesh_principales.append(f'"{term}"[MeSH Terms]')
            
            # Agregar con subheadings relevantes para fisioterapia
            subheadings = ['therapy', 'rehabilitation', 'methods', 'drug therapy']
            for subh in subheadings:
                mesh_principales.append(f'"{term}/{subh}"[MeSH Terms]')
        
        if mesh_principales:
            query_mesh = f"({' OR '.join(mesh_principales[:8])})"  # Limitar para evitar queries muy largas
            queries.append(query_mesh)
        
        # Estrategia 2: Búsqueda en Title/Abstract con términos específicos
        if keywords:
            # Términos exactos en título (alta precisión)
            title_terms = [f'"{keyword}"[Title]' for keyword in keywords[:3]]
            if title_terms:
                queries.append(f"({' OR '.join(title_terms)})")
            
            # Términos en abstract (mayor cobertura)
            abstract_terms = [f'"{keyword}"[Abstract]' for keyword in keywords[:4]]
            if abstract_terms:
                queries.append(f"({' OR '.join(abstract_terms)})")
        
        # Estrategia 3: Búsqueda por palabras clave del texto original
        if conceptos_texto:
            text_terms = []
            for concepto in list(conceptos_texto.keys())[:3]:
                text_terms.append(f'"{concepto}"[Title/Abstract]')
            if text_terms:
                queries.append(f"({' OR '.join(text_terms)})")
        
        # 3. COMBINAR ESTRATEGIAS CON OPERADORES BOOLEANOS
        if len(queries) >= 2:
            # Combinación principal: MeSH AND (Title OR Abstract)
            query_principal = f"({queries[0]}) AND ({queries[1]})"
            # Query alternativa: Solo términos más específicos
            query_alternativa = " OR ".join(queries[:2])
            query_final = f"({query_principal}) OR ({query_alternativa})"
        elif queries:
            query_final = queries[0]
        else:
            query_final = '"Physical Therapy Modalities"[MeSH Terms]'
        
        # 4. APLICAR FILTROS AVANZADOS DE PUBMED
        filtros_avanzados = []
        
        # Filtros por tipo de estudio (priorizando evidencia de alta calidad)
        filtros_avanzados.append(
            '(Clinical Trial[ptyp] OR Randomized Controlled Trial[ptyp] OR '
            'Systematic Review[ptyp] OR Meta-Analysis[ptyp] OR Review[ptyp] OR '
            'Comparative Study[ptyp])'
        )
        
        # Filtro temporal
        filtros_avanzados.append('("2014/01/01"[PDAT] : "2024/12/31"[PDAT])')
        
        # Filtros por idioma
        filtros_avanzados.append('(English[lang] OR Spanish[lang])')
        
        # Filtros por edad si es relevante para fisioterapia
        filtros_avanzados.append('(Adult[MeSH Terms] OR Middle Aged[MeSH Terms] OR Aged[MeSH Terms] OR Young Adult[MeSH Terms])')
        
        # Combinar query con filtros
        query_completa = f"({query_final}) AND {' AND '.join(filtros_avanzados)}"
        
        print(f"Query avanzada final: {query_completa}")
        
        # 5. REALIZAR BÚSQUEDA MÚLTIPLE CON DIFERENTES ORDENAMIENTOS
        resultados_combinados = []
        
        # Búsqueda 1: Por relevancia
        resultados_relevancia = realizar_busqueda_pubmed(query_completa, "relevance", max_results)
        resultados_combinados.extend(resultados_relevancia)
        
        # Búsqueda 2: Por fecha (más recientes)
        if len(resultados_combinados) < max_results:
            resultados_fecha = realizar_busqueda_pubmed(query_completa, "pub_date", max_results - len(resultados_combinados))
            resultados_combinados.extend(resultados_fecha)
        
        # 6. PROCESAMIENTO Y SCORING DE RELEVANCIA
        articulos_procesados = []
        for pmid in set(resultados_combinados):  # Eliminar duplicados
            articulo = procesar_articulo_pubmed(pmid, mesh_terms, keywords, conceptos_texto)
            if articulo:
                articulos_procesados.append(articulo)
        
        # Ordenar por score de relevancia
        articulos_procesados.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return articulos_procesados[:max_results]
        
    except Exception as e:
        print(f"Error en buscar_articulos_mesh_avanzado: {e}")
        return []

def realizar_busqueda_pubmed(query, sort_order, max_results):
    """Realiza una búsqueda específica en PubMed"""
    try:
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "api_key": PUBMED_API_KEY,
            "retmax": max_results * 3,  # Buscar más para filtrar después
            "sort": sort_order,
            "usehistory": "y"
        }
        
        response = requests.get(url, params=params, timeout=20)
        if response.status_code == 200:
            data = response.json()
            return data.get("esearchresult", {}).get("idlist", [])
        
    except Exception as e:
        print(f"Error en realizar_busqueda_pubmed: {e}")
    
    return []

def procesar_articulo_pubmed(pmid, mesh_terms, keywords, conceptos_texto):
    """Procesa un artículo individual de PubMed con scoring de relevancia"""
    try:
        time.sleep(0.2)  # Rate limiting
        
        # Obtener resumen completo del artículo
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml",
            "api_key": PUBMED_API_KEY
        }
        
        fetch_response = requests.get(fetch_url, params=fetch_params, timeout=15)
        if fetch_response.status_code != 200:
            return None
        
        # También obtener el summary para información básica
        summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        summary_params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "json",
            "api_key": PUBMED_API_KEY
        }
        
        s_response = requests.get(summary_url, params=summary_params, timeout=10)
        if s_response.status_code != 200:
            return None
        
        s_data = s_response.json()
        info = s_data.get("result", {}).get(pmid, {})
        
        if not info or not info.get("title"):
            return None
        
        # CALCULAR SCORE DE RELEVANCIA AVANZADO
        title = info.get("title", "").lower()
        abstract_text = ""
        
        # Extraer abstract del XML si está disponible
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(fetch_response.text)
            abstract_elem = root.find(".//Abstract/AbstractText")
            if abstract_elem is not None:
                abstract_text = abstract_elem.text or ""
        except:
            pass
        
        combined_text = f"{title} {abstract_text}".lower()
        relevance_score = calcular_relevancia_avanzada(combined_text, mesh_terms, keywords, conceptos_texto)
        
        # Filtrar artículos con baja relevancia
        if relevance_score < 15:  # Umbral mínimo
            return None
        
        # Procesar información del artículo
        autores = info.get("authors", [])
        title_original = info.get("title", "").strip()
        if title_original.endswith('.'):
            title_original = title_original[:-1]
        
        # Procesar autores para formato APA
        autor_apa = procesar_autores_apa(autores)
        
        # Año y journal
        pubdate = info.get("pubdate", "")
        año = pubdate.split(" ")[0] if pubdate else "s.f."
        journal = info.get("fulljournalname", info.get("source", "Journal desconocido"))
        
        # Obtener DOI si está disponible
        doi = ""
        try:
            doi_elem = ET.fromstring(fetch_response.text).find(".//ELocationID[@EIdType='doi']")
            if doi_elem is not None:
                doi = doi_elem.text or ""
        except:
            pass
        
        # Construir URL preferencial (DOI si existe, sino PubMed)
        if doi:
            url_articulo = f"https://doi.org/{doi}"
        else:
            url_articulo = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        
        articulo = {
            "pmid": pmid,
            "autor": autor_apa,
            "año": año,
            "titulo": title_original,
            "journal": journal,
            "doi": doi,
            "url": url_articulo,
            "relevance_score": relevance_score,
            "cita_apa": f"{autor_apa} ({año}). {title_original}. *{journal}*. {url_articulo}"
        }
        
        return articulo
        
    except Exception as e:
        print(f"Error procesando PMID {pmid}: {e}")
        return None

def calcular_relevancia_avanzada(texto_completo, mesh_terms, keywords, conceptos_texto):
    """Calcula score de relevancia avanzado considerando múltiples factores"""
    score = 0
    
    try:
        # 1. Coincidencias exactas con términos MeSH (peso alto)
        for mesh_term in mesh_terms:
            if mesh_term.lower() in texto_completo:
                score += 20
            # Coincidencias parciales
            palabras_mesh = mesh_term.lower().split()
            for palabra in palabras_mesh:
                if len(palabra) > 3 and palabra in texto_completo:
                    score += 5
        
        # 2. Coincidencias con keywords (peso medio)
        for keyword in keywords:
            if keyword.lower() in texto_completo:
                score += 15
            # Variaciones del keyword
            if keyword.replace(' ', '') in texto_completo.replace(' ', ''):
                score += 10
        
        # 3. Coincidencias con conceptos del texto original (peso medio)
        for concepto in conceptos_texto.keys():
            if concepto.lower() in texto_completo:
                score += 12
        
        # 4. Términos técnicos específicos (peso medio)
        terminos_tecnicos = [
            'clinical trial', 'randomized', 'systematic review', 'meta-analysis',
            'efficacy', 'effectiveness', 'treatment', 'intervention', 'therapy',
            'rehabilitation', 'exercise', 'training', 'recovery'
        ]
        
        for termino in terminos_tecnicos:
            if termino in texto_completo:
                score += 8
        
        # 5. Bonus por densidad de términos relevantes
        total_palabras = len(texto_completo.split())
        if total_palabras > 0:
            densidad = sum(1 for word in texto_completo.split() 
                          if any(term in word for term in keywords + list(conceptos_texto.keys())))
            score += int((densidad / total_palabras) * 100)
        
        return score
        
    except Exception as e:
        print(f"Error calculando relevancia: {e}")
        return 0

def procesar_autores_apa(autores):
    """Procesa lista de autores para formato APA"""
    try:
        if not autores:
            return "Autor desconocido"
        
        if len(autores) == 1:
            nombre = autores[0].get("name", "")
            return nombre.replace(" ", ", ", 1) if " " in nombre else nombre
        elif len(autores) <= 6:
            autor_list = []
            for i, autor in enumerate(autores):
                nombre = autor.get("name", "")
                if i == 0:
                    autor_list.append(nombre.replace(" ", ", ", 1) if " " in nombre else nombre)
                else:
                    autor_list.append(nombre)
            if len(autor_list) > 1:
                return ", ".join(autor_list[:-1]) + ", & " + autor_list[-1]
            else:
                return autor_list[0]
        else:
            primer_autor = autores[0].get("name", "")
            nombre_formateado = primer_autor.replace(" ", ", ", 1) if " " in primer_autor else primer_autor
            return f"{nombre_formateado}, et al."
    except:
        return "Autor desconocido"

def integrar_citas_en_texto(texto, articulos):
    """Integra citas en el texto de manera inteligente"""
    try:
        if NLTK_AVAILABLE:
            oraciones = sent_tokenize(texto, language='spanish')
        else:
            # Tokenización básica de oraciones
            oraciones = re.split(r'[.!?]+', texto)
            oraciones = [o.strip() for o in oraciones if o.strip()]
        
        if not articulos:
            return texto, []
        
        texto_citado = ""
        referencias_usadas = []
        contador_citas = 1
        
        # Mapear artículos a números de referencia
        mapa_referencias = {}
        for i, articulo in enumerate(articulos):
            mapa_referencias[articulo['pmid']] = i + 1
        
        for i, oracion in enumerate(oraciones):
            # Agregar la oración
            texto_citado += oracion
            
            # Determinar si agregar cita basándose en contenido y posición
            debe_citar = False
            
            # Criterios para citar:
            # 1. Cada 2-3 oraciones
            # 2. Oraciones con afirmaciones científicas
            # 3. Datos, estadísticas o resultados
            
            palabras_cientificas = [
                'estudio', 'investigación', 'resultado', 'evidencia', 'datos',
                'análisis', 'tratamiento', 'terapia', 'eficacia', 'efectividad',
                'paciente', 'clínico', 'mejora', 'reduce', 'aumenta', 'demuestra',
                'indica', 'sugiere', 'reporta', 'encuentra', 'observa'
            ]
            
            # Verificar si la oración contiene términos que requieren citación
            oracion_lower = oracion.lower()
            if any(palabra in oracion_lower for palabra in palabras_cientificas):
                debe_citar = True
            
            # También citar cada 2-3 oraciones para mantener respaldo científico
            if (i + 1) % 2 == 0 and len(oraciones) > 3:
                debe_citar = True
            
            # Agregar cita si corresponde
            if debe_citar and contador_citas <= len(articulos):
                # Seleccionar artículo más relevante disponible
                articulo_seleccionado = articulos[contador_citas - 1]
                numero_ref = mapa_referencias[articulo_seleccionado['pmid']]
                
                # Agregar cita en formato APA (Autor, año)
                cita_autor_año = f"({articulo_seleccionado['autor'].split(',')[0]}, {articulo_seleccionado['año']})"
                texto_citado += f" {cita_autor_año}"
                
                if articulo_seleccionado not in referencias_usadas:
                    referencias_usadas.append(articulo_seleccionado)
                
                contador_citas += 1
            
            # Agregar punto final si no lo tiene
            if not texto_citado.endswith(('.', '!', '?')):
                texto_citado += "."
            
            # Agregar espacio para la siguiente oración
            if i < len(oraciones) - 1:
                texto_citado += " "
        
        return texto_citado, referencias_usadas
        
    except Exception as e:
        print(f"Error en integrar_citas_en_texto: {e}")
        return texto, []

def generar_lista_referencias(referencias):
    """Genera la lista de referencias en formato APA"""
    try:
        if not referencias:
            return ""
        
        lista_referencias = "\n\n**REFERENCIAS:**\n\n"
        
        for i, ref in enumerate(referencias, 1):
            lista_referencias += f"{i}. {ref['cita_apa']}\n\n"
        
        return lista_referencias
        
    except Exception as e:
        print(f"Error en generar_lista_referencias: {e}")
        return ""

# =========================
# ENDPOINTS
# =========================

@app.route("/citar_texto", methods=["POST"])
def citar_texto():
    """
    Endpoint principal para citar texto automáticamente
    Recibe texto y devuelve el mismo texto con citas integradas + lista de referencias
    """
    try:
        data = request.get_json()
        
        if not data or 'texto' not in data:
            return jsonify({
                "error": "Se requiere el campo 'texto' en el JSON"
            }), 400
        
        texto_original = data['texto'].strip()
        
        if not texto_original:
            return jsonify({
                "error": "El texto no puede estar vacío"
            }), 400
        
        if len(texto_original) > 5000:
            return jsonify({
                "error": "Texto demasiado largo (máximo 5000 caracteres)"
            }), 400
        
        print(f"Procesando texto de {len(texto_original)} caracteres")
        
        # 1. Detectar conceptos y mapear a MeSH/DeCS
        conceptos_info = detectar_conceptos_mesh_decs(texto_original)
        print(f"Conceptos detectados: {conceptos_info['conceptos']}")
        print(f"Términos MeSH: {conceptos_info['mesh_terms']}")
        
        # 2. Buscar artículos científicos usando búsqueda avanzada MeSH
        articulos = buscar_articulos_mesh_avanzado(
            conceptos_info['mesh_terms'], 
            conceptos_info['keywords'],
            conceptos_info['conceptos'],
            max_results=5
        )
        print(f"Artículos encontrados: {len(articulos)}")
        
        if not articulos:
            return jsonify({
                "texto_original": texto_original,
                "texto_citado": texto_original,
                "conceptos_detectados": conceptos_info['conceptos'],
                "numero_articulos": 0,
                "referencias": "",
                "mensaje": "No se encontraron artículos científicos para este tema"
            })
        
        # 3. Integrar citas en el texto
        texto_citado, referencias_usadas = integrar_citas_en_texto(texto_original, articulos)
        
        # 4. Generar lista de referencias
        lista_referencias = generar_lista_referencias(referencias_usadas)
        
        # 5. Combinar texto citado con referencias
        resultado_final = texto_citado + lista_referencias
        
        response = {
            "texto_original": texto_original,
            "texto_citado": resultado_final,
            "conceptos_detectados": conceptos_info['conceptos'],
            "numero_articulos": len(referencias_usadas),
            "referencias": lista_referencias,
            "articulos_utilizados": [
                {
                    "autor": art['autor'],
                    "año": art['año'],
                    "titulo": art['titulo'],
                    "journal": art['journal'],
                    "url": art['url']
                }
                for art in referencias_usadas
            ]
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        print(f"Error en citar_texto: {e}")
        return jsonify({
            "error": "Error interno del servidor",
            "detalle": str(e)
        }), 500

@app.route("/buscar", methods=["GET"])
def buscar_citas_apa():
    """
    Endpoint de compatibilidad con versión anterior
    """
    try:
        tema = request.args.get('q', '').strip()
        
        if not tema:
            return jsonify({
                "error": "Parámetro 'q' requerido",
                "tema": "",
                "citas": []
            }), 400
        
        # Usar nuevo sistema de búsqueda avanzada
        conceptos_info = detectar_conceptos_mesh_decs(tema)
        articulos = buscar_articulos_mesh_avanzado(
            conceptos_info['mesh_terms'], 
            conceptos_info['keywords'],
            conceptos_info['conceptos'],
            max_results=5
        )
        
        citas = [art['cita_apa'] for art in articulos]
        
        return jsonify({
            "tema": tema,
            "citas": citas,
            "conceptos_detectados": conceptos_info['conceptos']
        }), 200
    
    except Exception as e:
        print(f"Error en buscar_citas_apa: {e}")
        return jsonify({
            "error": "Error interno del servidor",
            "tema": tema if 'tema' in locals() else "",
            "citas": []
        }), 500

@app.route("/", methods=["GET"])
def info_api():
    """Información de la API actualizada"""
    return jsonify({
        "title": "API de Citación Automática",
        "description": "API para integrar citas científicas automáticamente en textos usando términos MeSH/DeCS",
        "version": "2.0.0",
        "endpoints": {
            "citar_texto": {
                "method": "POST",
                "url": "/citar_texto",
                "description": "Integra citas automáticamente en un texto proporcionado",
                "body": {
                    "texto": "Texto a citar..."
                }
            },
            "buscar": {
                "method": "GET", 
                "url": "/buscar?q=tema",
                "description": "Buscar artículos por tema (compatibilidad)"
            }
        },
        "ejemplo_uso": {
            "endpoint": "/citar_texto",
            "metodo": "POST",
            "body": {
                "texto": "La fisioterapia respiratoria es efectiva para mejorar la función pulmonar. Los ejercicios respiratorios pueden reducir la disnea en pacientes con EPOC."
            }
        }
    })

@app.route("/health", methods=["GET"])
def health_check():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "message": "API de citación funcionando correctamente",
        "version": "2.0.0"
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
