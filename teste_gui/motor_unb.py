import os
import re
import csv
import xml.etree.ElementTree as ET
from datetime import datetime
from rapidfuzz import process, fuzz, utils

# --- CONFIGURAÇÕES ---
THRESHOLD_ADVISOR = 90
THRESHOLD_KEYWORD = 90

PRESERVAR = [
    'UnB', 'IBICT', 'Brasília', 'Distrito Federal', 'Brasil', 'PMDF', 'DF', 
    'Mestrado', 'Doutorado', 'MEC', 'CAPES', 'MDF', 'PP', 'PEAD', 'eMulti',
    'SUS', 'COVID-19', 'TI', 'TIC'
]

TEXTO_LICENCA = (
    "A concessão da licença deste item refere-se ao termo de autorização impresso assinado pelo autor com as seguintes condições: "
    "Na qualidade de titular dos direitos de autor da publicação, autorizo a Universidade de Brasília e o IBICT a disponibilizar "
    "por meio dos sites www.unb.br, www.ibict.br, www.ndltd.org sem ressarcimento dos direitos autorais, de acordo com a Lei nº 9610/98, "
    "o texto integral da obra supracitada, conforme permissões assinaladas, para fins de leitura, impressão e/ou download, "
    "a título de divulgação da produção científica brasileira, a partir desta data."
)

def carregar_bases_globais(base_dir):
    """Carrega CSVs tratando separação de termo e frequência de forma robusta."""
    def carregar_csv(nome, com_freq=False):
        caminho = os.path.join(base_dir, nome)
        dados = {}
        if not os.path.exists(caminho): return {}
        try:
            with open(caminho, mode='r', encoding='utf-8') as f:
                # Tenta ler com ponto e vírgula primeiro
                reader = csv.reader(f, delimiter=';')
                
                # Se parecer vazio ou mal formatado, tenta vírgula
                pos_inicial = f.tell()
                try:
                    teste = next(reader)
                    f.seek(pos_inicial)
                except:
                    f.seek(0)
                    reader = csv.reader(f, delimiter=',')

                for linha in reader:
                    if not linha: continue
                    if linha[0].lower() in ['termo', 'orientador', 'nome', 'keyword', 'assunto']: continue
                    
                    raw_text = linha[0].strip()
                    termo = raw_text
                    freq = 1
                    
                    # CORREÇÃO: Verifica se o número veio grudado na string (ex: "Biologia,10")
                    # Isso acontece se o delimitador falhar
                    if com_freq:
                        # Caso 1: Veio em colunas separadas (Correto) -> ["Biologia", "10"]
                        if len(linha) > 1 and linha[1].strip().isdigit():
                            termo = raw_text
                            freq = int(linha[1].strip())
                        
                        # Caso 2: Veio grudado com virgula -> ["Biologia,10"]
                        elif ',' in raw_text:
                            partes = raw_text.rsplit(',', 1)
                            if len(partes) == 2 and partes[1].isdigit():
                                termo = partes[0].strip()
                                freq = int(partes[1])
                    
                    dados[termo] = freq
        except: pass
        return dados

    return {
        'advisors': carregar_csv("base_orientadores_unb.csv", com_freq=True) or carregar_csv("advisor-ppg.csv", com_freq=True),
        'keywords': carregar_csv("base_assuntos_unb.csv", com_freq=True) or carregar_csv("keywords.csv", com_freq=True)
    }

def aplicar_regra_caracteres(texto):
    """Capitalização inteligente preservando siglas."""
    if not texto: return ""
    palavras = texto.strip().split()
    resultado = []
    for i, p in enumerate(palavras):
        p_limpa = re.sub(r'[^\w\-]', '', p)
        correta = next((fixo for fixo in PRESERVAR if fixo.lower() == p_limpa.lower()), None)
        
        if correta:
            resultado.append(p.replace(p_limpa, correta))
        elif len(p_limpa) <= 3 and i > 0: # Preposições no meio
            resultado.append(p.lower())
        else:
            resultado.append(p.capitalize())
    return " ".join(resultado)

def tratar_titulo(texto):
    if not texto: return ""
    txt = texto.strip()
    palavras = txt.split()
    res = []
    for i, p in enumerate(palavras):
        p_l = re.sub(r'[^\w]', '', p)
        correta = next((f for f in PRESERVAR if f.lower() == p_l.lower()), None)
        if correta: res.append(p.replace(p_l, correta))
        else: res.append(p.capitalize() if i == 0 else p.lower())
    return re.sub(r'\s*:\s*', ' : ', " ".join(res))

def processar_arquivo_direto(caminho_xml, bases):
    """Processa o XML e retorna lista de alterações detalhadas."""
    relatorio_alteracoes = [] 
    
    try:
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
        
        dados_sinc = {'autor': '', 'titulo': '', 'curso_ppg': '', 'tipo_doc': ''}
        elementos_originais = root.findall("dcvalue")
        novos_elementos = []

        # FASE 1: DESCOBERTA
        for elem in elementos_originais:
            el, qu, txt = elem.get("element"), elem.get("qualifier"), elem.text or ""
            if el == "contributor" and qu == "author":
                dados_sinc['autor'] = aplicar_regra_caracteres(txt)
            elif el == "title":
                dados_sinc['titulo'] = tratar_titulo(txt)
            elif el == "type":
                dados_sinc['tipo_doc'] = txt
            elif qu == "citation":
                m = re.search(r'\((.*?)\)', txt)
                if m:
                    raw_curso = m.group(1)
                    curso_limpo = re.sub(r'(Mestrado|Doutorado)\s+em\s+', '', raw_curso, flags=re.IGNORECASE).strip()
                    dados_sinc['curso_ppg'] = aplicar_regra_caracteres(curso_limpo)

        # FASE 2: TRANSFORMAÇÃO
        for elem in elementos_originais:
            el, qu, txt = elem.get("element"), elem.get("qualifier"), elem.text or ""
            lang = elem.get("language")
            txt_original = txt

            if (qu and ("referees" in qu or qu.endswith("ID"))) or (el == "publisher" and qu in ["country", "initials"]):
                continue

            # KEYWORDS (ASSUNTOS)
            if el == "subject" and qu in ["none", "keyword"]:
                termos = re.split(r'[;,\.]', txt)
                for t in [term.strip() for term in termos if term.strip()]:
                    t_limpo = re.sub(r'[\{\}\[\]\<\>\\\/]', '', t)
                    
                    # Lógica Híbrida: Base vs Gramática
                    matches = process.extract(t_limpo, lista_keywords, limit=3, scorer=fuzz.token_sort_ratio, processor=utils.default_process)
                    validos = [m for m in matches if m[1] >= THRESHOLD_KEYWORD]
                    
                    origem = "GRAMÁTICA"
                    escolhido = ""

                    if validos:
                        # Ordena por frequência (maior freq primeiro) e pega APENAS o termo [0]
                        melhor_match = sorted(validos, key=lambda x: bases['keywords'].get(x[0], 0), reverse=True)[0]
                        escolhido = melhor_match[0] # Pega o texto, ignora score e index
                        origem = "BASE"
                    else:
                        escolhido = aplicar_regra_caracteres(t_limpo)

                    # Garante que não há números residuais no escolhido se vier da base
                    if origem == "BASE" and "," in escolhido and escolhido.split(",")[-1].isdigit():
                         escolhido = escolhido.rsplit(",", 1)[0]

                    if escolhido != t:
                        relatorio_alteracoes.append(f"🔑 Assunto [{origem}]: '{t}' -> '{escolhido}'")

                    item = ET.Element("dcvalue", element="subject", qualifier="keyword")
                    if lang: item.set("language", lang)
                    item.text = escolhido
                    novos_elementos.append(item)
                continue

            # ORIENTADORES
            if el == "contributor" and qu == "advisor":
                matches = process.extract(txt, lista_advisors, limit=3, scorer=fuzz.token_sort_ratio, processor=utils.default_process)
                validos = [m for m in matches if m[1] >= THRESHOLD_ADVISOR]
                
                if validos:
                    # Desempate por frequência
                    escolhido = sorted(validos, key=lambda x: bases['advisors'].get(x[0], 0), reverse=True)[0][0]
                    
                    # Garante limpeza extra caso o CSV esteja sujo na chave
                    if "," in escolhido and escolhido.split(",")[-1].isdigit():
                        escolhido = escolhido.rsplit(",", 1)[0]
                        
                    if escolhido != txt:
                        relatorio_alteracoes.append(f"👤 Orientador [BASE]: '{txt}' -> '{escolhido}'")
                    txt = escolhido
                else:
                    novo_txt = aplicar_regra_caracteres(txt)
                    txt = novo_txt
            
            elif el == "contributor" and qu and qu.startswith("advisor-co"):
                elem.set("qualifier", "advisorco")
                txt = aplicar_regra_caracteres(txt)
            
            elif el == "contributor" and qu == "author": txt = dados_sinc['autor']
            elif el == "title": txt = dados_sinc['titulo']
            
            # Normalizações diversas
            elif el == "description" and qu == "resumo": elem.set("qualifier", "abstract"); qu = "abstract"
            elif el == "date" and qu == "issued": elem.set("qualifier", "submitted"); qu = "submitted"
            
            if el == "rights" and qu == "license": txt = TEXTO_LICENCA
            
            # CITAÇÃO
            elif qu == "citation":
                if ',' in dados_sinc['autor']:
                    parts = dados_sinc['autor'].split(',')
                    if len(parts) >= 2:
                        sob = parts[0].upper(); nme = parts[1]
                        resto = ".".join(txt_original.split('.')[2:]) if len(txt_original.split('.')) > 2 else ""
                        txt = f"{sob},{nme}. {dados_sinc['titulo']}. {resto}"
                pref = "Mestrado em" if dados_sinc['tipo_doc'] == "masterThesis" else "Doutorado em"
                curso_f = dados_sinc['curso_ppg'] if dados_sinc['curso_ppg'] else "PREENCHER"
                txt = re.sub(r'\((.*?)\)', f"({pref} {curso_f})", txt)
                txt = re.sub(r'Universidade de Brasília,\s*Universidade de Brasília', '— Universidade de Brasília', txt, flags=re.IGNORECASE)

            elem.text = txt
            novos_elementos.append(elem)

        # FASE 3: OBRIGATÓRIOS
        data_i = ET.Element("dcvalue", element="date", qualifier="issued"); data_i.text = datetime.now().strftime("%Y-%m-%d"); novos_elementos.append(data_i)
        
        obrigatorios = {('rights', 'license'): TEXTO_LICENCA, ('language', 'iso'): "por", ('description', 'unidade'): "PREENCHER"}
        if not any(e.get("qualifier") == "ppg" for e in novos_elementos):
             ppg_n = ET.Element("dcvalue", element="description", qualifier="ppg"); ppg_n.set("language", "pt_BR"); ppg_n.text = "PREENCHER"; novos_elementos.append(ppg_n)

        atuais = [(e.get("element"), e.get("qualifier")) for e in novos_elementos]
        for (e, q), v in obrigatorios.items():
            if (e, q) not in atuais:
                n = ET.Element("dcvalue", element=e, qualifier=q); n.set("language", "pt_BR"); n.text = v; novos_elementos.append(n)

        root.clear(); root.set("schema", "dc")
        for el in novos_elementos: root.append(el)
        tree.write(caminho_xml, encoding="utf-8", xml_declaration=True)
        
        return True, relatorio_alteracoes 

    except Exception as e:
        return False, [f"Erro Fatal: {str(e)}"]