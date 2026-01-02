import os
import re
import csv
import xml.etree.ElementTree as ET
from rapidfuzz import process, fuzz, utils

# --- CONFIGURAÇÕES ---
THRESHOLD_ADVISOR = 90
THRESHOLD_KEYWORD = 90
PRESERVAR = {'UnB', 'IBICT', 'Brasília', 'Distrito Federal', 'Brasil', 'PMDF', 'DF', 'Mestrado', 'Doutorado', 'MEC', 'CAPES', 'MDF', 'PP', 'PEAD', 'eMulti'}

def carregar_bases_globais(base_dir):
    """Carrega os CSVs uma única vez para memória."""
    def carregar_csv(nome, com_freq=False):
        caminho = os.path.join(base_dir, nome)
        dados = {}
        if not os.path.exists(caminho): return {}
        try:
            with open(caminho, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=';')
                for linha in reader:
                    if not linha: continue
                    termo = linha[0].strip()
                    if com_freq:
                        partes = termo.rsplit(',', 1)
                        if len(partes) == 2 and partes[1].isdigit():
                            dados[partes[0].strip()] = int(partes[1])
                        else: dados[termo] = 1
                    else: dados[termo] = 0
        except: pass
        return dados

    return {
        'advisors': carregar_csv("base_orientadores_unb.csv", com_freq=True),
        'keywords': carregar_csv("base_assuntos_unb.csv", com_freq=True)
    }

def aplicar_regra_caracteres(texto):
    if not texto: return ""
    palavras = texto.strip().split()
    resultado = []
    for p in palavras:
        p_limpa = re.sub(r'[^\w]', '', p)
        upper_p = p_limpa.upper()
        correta = next((f for f in PRESERVAR if f.upper() == upper_p), None)
        if correta:
            resultado.append(p.replace(p_limpa, correta))
        elif len(p_limpa) <= 3: resultado.append(p.lower())
        else: resultado.append(p.capitalize())
    return " ".join(resultado)

def processar_arquivo_direto(caminho_xml, bases):
    """Processa o XML com RapidFuzz e tratamento de erros robusto."""
    try:
        # Tenta ler o arquivo tratando possíveis erros de codificação ou caracteres ilegais
        try:
            parser = ET.XMLParser(encoding="utf-8")
            tree = ET.parse(caminho_xml, parser=parser)
            root = tree.getroot()
        except ET.ParseError:
            # Se falhar, tenta uma limpeza bruta de caracteres de controle
            with open(caminho_xml, 'rb') as f:
                data = f.read()
            # Remove caracteres não-imprimíveis (resiliência contra XML corrompido)
            clean_data = re.sub(rb'[^\x09\x0A\x0D\x20-\x7E\x80-\xFF]', b'', data)
            root = ET.fromstring(clean_data)
            tree = ET.ElementTree(root)

        lista_advisors = list(bases['advisors'].keys())
        lista_keywords = list(bases['keywords'].keys())
        dados_sinc = {'autor': '', 'titulo': '', 'curso_ppg': ''}
        elementos_originais = root.findall("dcvalue")
        novos_elementos = []

        # FASE 1: Sincronização
        for elem in elementos_originais:
            el, qu, txt = elem.get("element"), elem.get("qualifier"), elem.text or ""
            if el == "contributor" and qu == "author":
                dados_sinc['autor'] = aplicar_regra_caracteres(txt)
            elif el == "title":
                dados_sinc['titulo'] = txt.strip().capitalize()
            elif qu == "citation":
                m = re.search(r'\((.*?)\)', txt)
                if m:
                    curso = re.sub(r'^(Mestrado|Doutorado)\s+em\s+', '', m.group(1), flags=re.IGNORECASE)
                    dados_sinc['curso_ppg'] = aplicar_regra_caracteres(curso)

        # FASE 2: Transformação (CORRIGIDO: token_sort_ratio)
        for elem in elementos_originais:
            el, qu, txt = elem.get("element"), elem.get("qualifier"), elem.text or ""
            lang = elem.get("language")

            if (qu and ("referees" in qu or qu.endswith("ID"))) or (el == "publisher" and qu in ["country", "initials"]):
                continue

            if el == "subject" and qu in ["none", "keyword"]:
                termos = re.split(r'[;,\.]', txt)
                for t in [term.strip() for term in termos if term.strip()]:
                    # O RapidFuzz usa snake_case: token_sort_ratio
                    matches = process.extract(t, lista_keywords, limit=3, scorer=fuzz.token_sort_ratio, processor=utils.default_process)
                    validos = [m for m in matches if m[1] >= THRESHOLD_KEYWORD]
                    escolhido = max(validos, key=lambda x: bases['keywords'].get(x[0], 0))[0] if validos else aplicar_regra_caracteres(t)
                    
                    item = ET.Element("dcvalue", element="subject", qualifier="keyword")
                    if lang: item.set("language", lang)
                    item.text = escolhido
                    novos_elementos.append(item)
                continue

            if el == "contributor" and qu == "advisor":
                # Uso do extractOne para performance máxima em orientadores
                m_a = process.extractOne(txt, lista_advisors, scorer=fuzz.token_sort_ratio, processor=utils.default_process)
                txt = m_a[0] if m_a and m_a[1] >= THRESHOLD_ADVISOR else aplicar_regra_caracteres(txt)
            
            elif el == "contributor" and qu == "author": txt = dados_sinc['autor']
            elif el == "title": txt = dados_sinc['titulo']

            elem.text = txt
            novos_elementos.append(elem)

        # FASE 3: Gravação Final
        root.clear()
        root.set("schema", "dc")
        for el in novos_elementos: root.append(el)
        tree.write(caminho_xml, encoding="utf-8", xml_declaration=True)
        return True, "OK"

    except Exception as e:
        return False, f"Erro: {str(e)}"