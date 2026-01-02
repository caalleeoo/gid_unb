import os
import re
import csv
import xml.etree.ElementTree as ET
from datetime import datetime
from rapidfuzz import process, fuzz, utils

# --- CONFIGURAÇÕES ---
THRESHOLD_ADVISOR = 90
THRESHOLD_KEYWORD = 90
PRESERVAR = ['UnB', 'IBICT', 'Brasília', 'Distrito Federal', 'Brasil', 'PMDF', 'DF', 'Mestrado', 'Doutorado', 'MEC', 'CAPES', 'MDF', 'PP', 'PEAD', 'eMulti']

TEXTO_LICENCA = (
    "A concessão da licença deste item refere-se ao termo de autorização impresso assinado pelo autor com as seguintes condições: "
    "Na qualidade de titular dos direitos de autor da publicação, autorizo a Universidade de Brasília e o IBICT a disponibilizar "
    "por meio dos sites www.unb.br, www.ibict.br, www.ndltd.org sem ressarcimento dos direitos autorais, de acordo com a Lei nº 9610/98, "
    "o texto integral da obra supracitada, conforme permissões assinaladas, para fins de leitura, impressão e/ou download, "
    "a título de divulgação da produção científica brasileira, a partir desta data."
)

def carregar_bases_globais(base_dir):
    def carregar_csv(nome, com_freq=False):
        caminho = os.path.join(base_dir, nome)
        dados = {}
        if not os.path.exists(caminho): return {}
        try:
            with open(caminho, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=';')
                if not reader: 
                     f.seek(0); reader = csv.reader(f, delimiter=',')
                for linha in reader:
                    if not linha or len(linha) < 1: continue
                    if linha[0].lower() in ['termo', 'orientador', 'nome']: continue
                    termo = linha[0].strip()
                    if com_freq:
                        partes = termo.rsplit(',', 1)
                        if len(linha) > 1 and linha[1].strip().isdigit():
                            dados[termo] = int(linha[1].strip())
                        elif len(partes) == 2 and partes[1].isdigit():
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
        correta = next((f for f in PRESERVAR if f.lower() == p_limpa.lower()), None)
        if correta: resultado.append(p.replace(p_limpa, correta))
        elif len(p_limpa) <= 3: resultado.append(p.lower())
        else: resultado.append(p.capitalize())
    return " ".join(resultado)

def tratar_titulo(texto):
    if not texto: return ""
    txt = texto.strip()
    palavras = txt.split()
    res = []
    for i, p in enumerate(palavras):
        p_limpa = re.sub(r'[^\w]', '', p)
        correta = next((f for f in PRESERVAR if f.lower() == p_limpa.lower()), None)
        if correta: res.append(p.replace(p_limpa, correta))
        else: res.append(p.capitalize() if i == 0 else p.lower())
    return re.sub(r'\s*:\s*', ' : ', " ".join(res))

def escape_xml(texto):
    """Escapa caracteres especiais para não quebrar o XML."""
    if not texto: return ""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")

def processar_arquivo_direto(caminho_xml, bases):
    """Gera XML manualmente para conformidade total com DSpace."""
    log_mudancas = []
    try:
        try:
            parser = ET.XMLParser(encoding="utf-8")
            tree = ET.parse(caminho_xml, parser=parser)
            root = tree.getroot()
        except ET.ParseError:
            with open(caminho_xml, 'rb') as f: data = f.read()
            clean_data = re.sub(rb'[^\x09\x0A\x0D\x20-\x7E\x80-\xFF]', b'', data)
            root = ET.fromstring(clean_data)

        lista_advisors, lista_keywords = list(bases['advisors'].keys()), list(bases['keywords'].keys())
        dados_sinc = {'autor': '', 'titulo': '', 'curso_ppg': '', 'tipo_doc': ''}
        elementos_originais = root.findall("dcvalue")

        # FASE 1: Extração
        for elem in elementos_originais:
            el, qu, txt = elem.get("element"), elem.get("qualifier"), elem.text or ""
            if el == "contributor" and qu == "author": dados_sinc['autor'] = aplicar_regra_caracteres(txt)
            elif el == "title": dados_sinc['titulo'] = tratar_titulo(txt)
            elif el == "type": dados_sinc['tipo_doc'] = txt
            elif qu == "citation":
                m = re.search(r'\((.*?)\)', txt)
                if m: dados_sinc['curso_ppg'] = aplicar_regra_caracteres(re.sub(r'^(Mestrado|Doutorado)\s+em\s+', '', m.group(1), flags=re.IGNORECASE))

        # FASE 2: Processamento
        novos_elementos = []
        for elem in elementos_originais:
            el, qu, txt_original = elem.get("element"), elem.get("qualifier"), elem.text or ""
            lang = elem.get("language")

            if (qu and ("referees" in qu or qu.endswith("ID"))) or (el == "publisher" and qu in ["country", "initials"]): continue

            # Regras de Negócio
            if el == "description" and qu == "resumo": el="description"; qu="abstract"; log_mudancas.append("resumo->abstract")
            elif el == "description" and qu == "abstract": el="description"; qu="abstract1"; log_mudancas.append("abstract->abstract1")
            
            if (el == "publisher" and qu == "program") or (el == "description" and qu == "ppg"):
                el="description"; qu="ppg"; txt_original=f"Programa de Pós-Graduação em {dados_sinc['curso_ppg']}"
            
            if el == "date" and qu == "issued": qu="submitted"

            if el == "subject" and qu in ["none", "keyword"]:
                termos = re.split(r'[;,\.]', txt_original)
                for t in [x.strip() for x in termos if x.strip()]:
                    t_limpo = re.sub(r'[\{\}\[\]\<\>\\\/]', '', t)
                    matches = process.extract(t_limpo, lista_keywords, limit=3, scorer=fuzz.token_sort_ratio, processor=utils.default_process)
                    valido = max(matches, key=lambda x: bases['keywords'].get(x[0],0))[0] if matches and matches[0][1] >= THRESHOLD_KEYWORD else aplicar_regra_caracteres(t_limpo)
                    if t != valido: log_mudancas.append(f"Subject: {t}->{valido}")
                    novos_elementos.append({'el': 'subject', 'qu': 'keyword', 'lang': lang, 'txt': valido.capitalize()})
                continue

            if el == "contributor" and qu == "advisor":
                match = process.extractOne(txt_original, lista_advisors, scorer=fuzz.token_sort_ratio, processor=utils.default_process)
                txt_final = match[0] if match and match[1] >= THRESHOLD_ADVISOR else aplicar_regra_caracteres(txt_original)
                if txt_original != txt_final: log_mudancas.append(f"Advisor: {txt_original}->{txt_final}")
                novos_elementos.append({'el': el, 'qu': qu, 'lang': lang, 'txt': txt_final}); continue

            if el == "contributor" and qu and qu.startswith("advisor-co"):
                novos_elementos.append({'el': el, 'qu': 'advisorco', 'lang': lang, 'txt': aplicar_regra_caracteres(txt_original)}); continue

            if el == "contributor" and qu == "author": txt_original = dados_sinc['autor']
            elif el == "title": txt_original = dados_sinc['titulo']
            elif el == "type": txt_original = {"masterThesis": "Dissertação", "doctoralThesis": "Tese"}.get(txt_original, txt_original)
            elif el == "rights" and qu == "license": txt_original = TEXTO_LICENCA
            
            elif qu == "citation":
                try:
                    if ',' in dados_sinc['autor']:
                        p = dados_sinc['autor'].split(',')
                        t_cit = f"{p[0].upper()}, {p[1].strip()}. {dados_sinc['titulo']}."
                        if len(txt_original.split('.')) > 2: t_cit += ".".join(txt_original.split('.')[2:])
                        txt_original = t_cit
                except: pass
                pref = "Mestrado em" if dados_sinc['tipo_doc'] == "masterThesis" else "Doutorado em"
                txt_original = re.sub(r'\((.*?)\)', f"({pref} {dados_sinc['curso_ppg']})", txt_original)
                txt_original = re.sub(r'(\d+)f\.', r'\1 f.', txt_original)
                txt_original = re.sub(r'Universidade de Brasília,\s*Universidade de Brasília', '— Universidade de Brasília', txt_original, flags=re.IGNORECASE)
                txt_original = txt_original.replace("- —", "—").replace("— —", "—").replace("— Universidade de Brasília, Brasília, Brasília", "— Universidade de Brasília, Brasília")

            novos_elementos.append({'el': el, 'qu': qu, 'lang': lang, 'txt': txt_original})

        # FASE 3: Obrigatórios
        novos_elementos.append({'el': 'date', 'qu': 'issued', 'lang': None, 'txt': datetime.now().strftime("%Y-%m-%d")})
        obrigatorios = [
            {'el': 'rights', 'qu': 'license', 'lang': 'pt_BR', 'txt': TEXTO_LICENCA},
            {'el': 'language', 'qu': 'iso', 'lang': 'pt_BR', 'txt': 'por'},
            {'el': 'description', 'qu': 'unidade', 'lang': 'pt_BR', 'txt': 'Faculdade de Ciência da Informação'}
        ]
        
        tags_existentes = [(x['el'], x['qu']) for x in novos_elementos]
        for ob in obrigatorios:
            if (ob['el'], ob['qu']) not in tags_existentes:
                novos_elementos.append(ob)

        # --- GRAVAÇÃO MANUAL E SEGURA (STRING BUILDER) ---
        # Isso evita qualquer erro de biblioteca XML ou cabeçalho incorreto
        xml_lines = ['<?xml version="1.0" encoding="utf-8" standalone="no"?>']
        xml_lines.append('<dublin_core schema="dc">')
        
        for item in novos_elementos:
            if not item['txt']: continue # DSpace não gosta de tags vazias
            
            # Escapa caracteres proibidos no XML (&, <, >)
            texto_seguro = escape_xml(item['txt'])
            qualifier = item['qu'] if item['qu'] else "none"
            lang_attr = f' language="{item["lang"]}"' if item.get('lang') else ''
            
            line = f'  <dcvalue element="{item["el"]}" qualifier="{qualifier}"{lang_attr}>{texto_seguro}</dcvalue>'
            xml_lines.append(line)
            
        xml_lines.append('</dublin_core>')
        
        with open(caminho_xml, "w", encoding="utf-8") as f:
            f.write("\n".join(xml_lines))

        msg = " | ".join(log_mudancas) if log_mudancas else "OK"
        return True, msg

    except Exception as e:
        return False, f"Erro: {str(e)}"