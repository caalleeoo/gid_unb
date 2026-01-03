# motor_unb.py
import os
import re
import csv
import xml.etree.ElementTree as ET
from datetime import datetime
from rapidfuzz import process, fuzz, utils

# --- CONFIGURAÇÕES E CONSTANTES ---
THRESHOLD_ADVISOR = 90
THRESHOLD_KEYWORD = 90

PRESERVAR = [
    'UnB', 'IBICT', 'Brasília', 'Distrito Federal', 'Brasil', 'PMDF', 'DF', 
    'Mestrado', 'Doutorado', 'MEC', 'CAPES', 'MDF', 'PP', 'PEAD', 'eMulti'
]

TEXTO_LICENCA = (
    "A concessão da licença deste item refere-se ao termo de autorização impresso assinado pelo autor com as seguintes condições: "
    "Na qualidade de titular dos direitos de autor da publicação, autorizo a Universidade de Brasília e o IBICT a disponibilizar "
    "por meio dos sites www.unb.br, www.ibict.br, www.ndltd.org sem ressarcimento dos direitos autorais, de acordo com a Lei nº 9610/98, "
    "o texto integral da obra supracitada, conforme permissões assinaladas, para fins de leitura, impressão e/ou download, "
    "a título de divulgação da produção científica brasileira, a partir desta data."
)

def carregar_bases_globais(base_dir):
    """
    Carrega os CSVs uma única vez para memória.
    Chamado pelo app_final.py no início.
    """
    def carregar_csv(nome, com_freq=False):
        caminho = os.path.join(base_dir, nome)
        dados = {}
        if not os.path.exists(caminho): return {}
        try:
            with open(caminho, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=';') # Assume delimitador ; padrão do Excel/Calc
                if not reader: 
                    # Fallback para virgula se necessário
                    f.seek(0)
                    reader = csv.reader(f, delimiter=',')
                
                for linha in reader:
                    if not linha: continue
                    # Ignora cabeçalhos comuns
                    if linha[0].lower() in ['termo', 'orientador', 'nome', 'keyword']: continue
                    
                    termo = linha[0].strip()
                    if com_freq and len(linha) > 1 and linha[1].isdigit():
                        dados[termo] = int(linha[1])
                    else: 
                        dados[termo] = 1
        except: pass
        return dados

    # Tenta carregar, ajustando nomes se necessário
    advisors = carregar_csv("base_orientadores_unb.csv", com_freq=True)
    # Se falhar, tenta o nome do script v0.2
    if not advisors: advisors = carregar_csv("advisor-ppg.csv", com_freq=False)

    keywords = carregar_csv("base_assuntos_unb.csv", com_freq=True)
    if not keywords: keywords = carregar_csv("keywords.csv", com_freq=True)

    return {
        'advisors': advisors,
        'keywords': keywords
    }

def aplicar_regra_caracteres(texto):
    """Normaliza Capitalização preservando siglas."""
    if not texto: return ""
    palavras = texto.strip().split()
    resultado = []
    for p in palavras:
        p_limpa = re.sub(r'[^\w]', '', p)
        # Verifica se é uma palavra preservada (case insensitive)
        correta = next((fixo for fixo in PRESERVAR if fixo.lower() == p_limpa.lower()), None)
        
        if correta:
            resultado.append(p.replace(p_limpa, correta))
        elif len(p_limpa) <= 3:
            resultado.append(p.lower())
        else:
            resultado.append(p.capitalize())
    return " ".join(resultado)

def tratar_titulo(texto):
    """Tratamento específico para títulos (primeira letra maiúscula, resto minúsculo, exceto siglas)."""
    if not texto: return ""
    txt = texto.strip()
    palavras = txt.split()
    res = []
    for i, p in enumerate(palavras):
        p_l = re.sub(r'[^\w]', '', p)
        correta = next((f for f in PRESERVAR if f.lower() == p_l.lower()), None)
        
        if correta:
            res.append(p.replace(p_l, correta))
        else:
            # Apenas a primeira palavra da frase recebe Capitalize, o resto lower
            res.append(p.capitalize() if i == 0 else p.lower())
            
    # Corrige espaçamento de dois pontos
    return re.sub(r'\s*:\s*', ' : ', " ".join(res))

def processar_arquivo_direto(caminho_xml, bases):
    """
    Processa o XML aplicando as regras de negócio do v0.2.
    Recebe o caminho do arquivo e as bases carregadas na memória.
    """
    try:
        # Tratamento robusto de parsing (caso existam bytes corrompidos)
        try:
            parser = ET.XMLParser(encoding="utf-8")
            tree = ET.parse(caminho_xml, parser=parser)
            root = tree.getroot()
        except ET.ParseError:
            with open(caminho_xml, 'rb') as f: data = f.read()
            clean_data = re.sub(rb'[^\x09\x0A\x0D\x20-\x7E\x80-\xFF]', b'', data)
            root = ET.fromstring(clean_data)
            tree = ET.ElementTree(root)

        lista_advisors = list(bases['advisors'].keys())
        lista_keywords = list(bases['keywords'].keys())
        
        # Variáveis de Estado
        dados_sinc = {'autor': '', 'titulo': '', 'curso_ppg': '', 'tipo_doc': ''}
        elementos_originais = root.findall("dcvalue")
        novos_elementos = []

        # =================================================
        # FASE 1: DESCOBERTA (Extrair dados para memória)
        # =================================================
        for elem in elementos_originais:
            el, qu, txt = elem.get("element"), elem.get("qualifier"), elem.text or ""
            
            if el == "contributor" and qu == "author":
                dados_sinc['autor'] = aplicar_regra_caracteres(txt)
            elif el == "title":
                dados_sinc['titulo'] = tratar_titulo(txt)
            elif el == "type":
                dados_sinc['tipo_doc'] = txt
            elif qu == "citation":
                # Tenta extrair o curso da citação antiga se existir
                m = re.search(r'\((.*?)\)', txt)
                if m:
                    raw_curso = m.group(1)
                    curso_limpo = re.sub(r'(Mestrado|Doutorado)\s+em\s+', '', raw_curso, flags=re.IGNORECASE).strip()
                    dados_sinc['curso_ppg'] = aplicar_regra_caracteres(curso_limpo)

        # =================================================
        # FASE 2: TRANSFORMAÇÃO E FILTRAGEM
        # =================================================
        for elem in elementos_originais:
            el, qu, txt = elem.get("element"), elem.get("qualifier"), elem.text or ""
            lang = elem.get("language")

            # --- 2.1 EXCLUSÕES ---
            # Remove referees, IDs e publisher:country/initials
            if (qu and ("referees" in qu or qu.endswith("ID"))) or \
               (el == "publisher" and qu in ["country", "initials"]):
                continue

            # --- 2.2 REGRAS DE NEGÓCIO ESPECÍFICAS ---
            
            # Normalização de Abstract/Resumo
            if el == "description" and qu == "resumo": 
                elem.set("qualifier", "abstract")
                qu = "abstract"
            elif el == "description" and qu == "abstract": 
                elem.set("qualifier", "abstract1")
                qu = "abstract1"

            # Normalização de Publisher/PPG
            if (el == "publisher" and qu == "program") or (el == "description" and qu == "ppg"):
                elem.set("element", "description")
                elem.set("qualifier", "ppg")
                el, qu = "description", "ppg"
                txt = f"Programa de Pós-Graduação em {dados_sinc['curso_ppg']}" if dados_sinc['curso_ppg'] else "PREENCHER"

            # Datas
            if el == "date" and qu == "issued":
                elem.set("qualifier", "submitted")
                qu = "submitted"

            # --- 2.3 KEYWORDS (ASSUNTOS) ---
            if el == "subject" and qu in ["none", "keyword"]:
                termos = re.split(r'[;,\.]', txt)
                for t in [term.strip() for term in termos if term.strip()]:
                    t_limpo = re.sub(r'[\{\}\[\]\<\>\\\/]', '', t)
                    
                    # Fuzzy Match RapidFuzz
                    matches = process.extract(
                        t_limpo, lista_keywords, limit=3, 
                        scorer=fuzz.token_sort_ratio, processor=utils.default_process
                    )
                    
                    # Verifica score e desempata por frequência
                    validos = [m for m in matches if m[1] >= THRESHOLD_KEYWORD]
                    if validos:
                        # Pega o match com maior score, ou desempata pela base
                        escolhido = validos[0][0] 
                    else:
                        escolhido = aplicar_regra_caracteres(t_limpo)
                    
                    item = ET.Element("dcvalue", element="subject", qualifier="keyword")
                    if lang: item.set("language", lang)
                    item.text = escolhido.capitalize()
                    novos_elementos.append(item)
                continue # Pula o append padrão, pois já adicionamos os novos itens

            # --- 2.4 ORIENTADORES ---
            if el == "contributor" and qu == "advisor":
                matches = process.extract(
                    txt, lista_advisors, limit=1, 
                    scorer=fuzz.token_sort_ratio, processor=utils.default_process
                )
                if matches and matches[0][1] >= THRESHOLD_ADVISOR:
                    txt = matches[0][0]
                else:
                    txt = aplicar_regra_caracteres(txt)
            
            elif el == "contributor" and qu and qu.startswith("advisor-co"):
                elem.set("qualifier", "advisorco") # Normaliza qualificador
                txt = aplicar_regra_caracteres(txt)
            
            elif el == "contributor" and qu == "author":
                txt = dados_sinc['autor']

            elif el == "title":
                txt = dados_sinc['titulo']

            # --- 2.5 CITAÇÃO ---
            elif qu == "citation":
                # Lógica complexa de reconstrução da citação
                if ',' in dados_sinc['autor']:
                    parts = dados_sinc['autor'].split(',')
                    if len(parts) >= 2:
                        sob = parts[0].upper()
                        nme = parts[1]
                        # Preserva final da citação original se possível, senão reconstrói
                        resto = ".".join(txt.split('.')[2:]) if len(txt.split('.')) > 2 else ""
                        txt = f"{sob},{nme}. {dados_sinc['titulo']}. {resto}"
                
                pref = "Mestrado em" if dados_sinc['tipo_doc'] == "masterThesis" else "Doutorado em"
                curso_f = dados_sinc['curso_ppg'] if dados_sinc['curso_ppg'] else "PREENCHER"
                
                txt = re.sub(r'\((.*?)\)', f"({pref} {curso_f})", txt)
                txt = re.sub(r'(\d+)f\.', r'\1 f.', txt)
                txt = re.sub(r'Universidade de Brasília,\s*Universidade de Brasília', '— Universidade de Brasília', txt, flags=re.IGNORECASE)
                txt = txt.replace("- —", "—").replace("— —", "—").replace("— Universidade de Brasília, Brasília, Brasília", "— Universidade de Brasília, Brasília")

            elif el == "type":
                txt = {"masterThesis": "Dissertação", "doctoralThesis": "Tese"}.get(txt, txt)
            
            elif el == "rights" and qu == "license":
                txt = TEXTO_LICENCA

            # Atualiza texto e adiciona à lista
            elem.text = txt
            novos_elementos.append(elem)

        # =================================================
        # FASE 3: OBRIGATÓRIOS E FINALIZAÇÃO
        # =================================================
        
        # Data de execução (issued)
        data_i = ET.Element("dcvalue", element="date", qualifier="issued")
        data_i.text = datetime.now().strftime("%Y-%m-%d")
        novos_elementos.append(data_i)
        
        # Campos obrigatórios se não existirem
        obrigatorios = {
            ('rights', 'license'): TEXTO_LICENCA, 
            ('language', 'iso'): "por", 
            ('description', 'unidade'): "PREENCHER"
        }

        # Garante PPG
        if not any(e.get("qualifier") == "ppg" for e in novos_elementos):
             ppg_n = ET.Element("dcvalue", element="description", qualifier="ppg")
             ppg_n.set("language", "pt_BR")
             ppg_n.text = "PREENCHER"
             novos_elementos.append(ppg_n)

        # Checa outros obrigatórios
        atuais = [(e.get("element"), e.get("qualifier")) for e in novos_elementos]
        for (e, q), v in obrigatorios.items():
            if (e, q) not in atuais:
                n = ET.Element("dcvalue", element=e, qualifier=q)
                if e != 'date': n.set("language", "pt_BR")
                n.text = v
                novos_elementos.append(n)

        # Gravação
        root.clear()
        root.set("schema", "dc")
        for el in novos_elementos: root.append(el)
        
        tree.write(caminho_xml, encoding="utf-8", xml_declaration=True)
        return True, "Processado com Regras v0.2"

    except Exception as e:
        return False, f"Erro Fatal: {str(e)}"