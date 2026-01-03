import os
import re
import csv
import xml.etree.ElementTree as ET
from datetime import datetime
from thefuzz import fuzz, process

# --- CONFIGURAÇÕES DE CAMINHO ---
__version__ = "0.2"
CAMINHO_MAC = '/Users/leonardorcarvalho/Library/CloudStorage/OneDrive-Pessoal/Documentos/GitHub/ts-para-alteracao'
CAMINHO_CSV_ADVISORS = '/Users/leonardorcarvalho/Library/CloudStorage/OneDrive-Pessoal/Documentos/GitHub/gid-docs/testefinal/advisor-ppg.csv'
CAMINHO_CSV_KEYWORDS = '/Users/leonardorcarvalho/Library/CloudStorage/OneDrive-Pessoal/Documentos/GitHub/gid-docs/testefinal/keywords.csv'

# Limiares de similaridade (0-100)
THRESHOLD_ADVISOR = 90
THRESHOLD_KEYWORD = 90

# Siglas e nomes próprios protegidos
PRESERVAR = ['UnB', 'IBICT', 'Brasília', 'Distrito Federal', 'Brasil', 'PMDF', 'DF', 'Mestrado', 'Doutorado', 'MEC', 'CAPES', 'MDF', 'PP', 'PEAD']

TEXTO_LICENCA = (
    "A concessão da licença deste item refere-se ao termo de autorização impresso assinado pelo autor com as seguintes condições: "
    "Na qualidade de titular dos direitos de autor da publicação, autorizo a Universidade de Brasília e o IBICT a disponibilizar "
    "por meio dos sites www.unb.br, www.ibict.br, www.ndltd.org sem ressarcimento dos direitos autorais, de acordo com a Lei nº 9610/98, "
    "o texto integral da obra supracitada, conforme permissões assinaladas, para fins de leitura, impressão e/ou download, "
    "a título de divulgação da produção científica brasileira, a partir desta data."
)

DATA_EXECUCAO = datetime.now().strftime("%Y-%m-%d")

# Listas globais para relatórios
RELATORIO_ADVISORS = []
RELATORIO_KEYWORDS = []

# --- FUNÇÕES DE APOIO ---

def carregar_csv_dict(caminho, com_frequencia=False):
    dados = {}
    if not os.path.exists(caminho): return {}
    try:
        with open(caminho, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for linha in reader:
                if not linha or len(linha) < 1: continue
                if linha[0].lower() in ['termo', 'orientador', 'nome'] or (len(linha) > 1 and not linha[1].strip().isdigit()):
                    continue
                termo = linha[0].strip()
                freq = int(linha[1].strip()) if com_frequencia and len(linha) > 1 else 0
                dados[termo] = freq
    except: pass
    return dados

BASE_ADVISORS = carregar_csv_dict(CAMINHO_CSV_ADVISORS)
BASE_KEYWORDS = carregar_csv_dict(CAMINHO_CSV_KEYWORDS, com_frequencia=True)

def aplicar_regra_caracteres(texto):
    if not texto: return texto
    palavras = texto.strip().split()
    resultado = []
    for p in palavras:
        p_limpa = re.sub(r'[^\w]', '', p)
        if any(fixo.lower() == p_limpa.lower() for fixo in PRESERVAR):
            correta = [fixo for fixo in PRESERVAR if fixo.lower() == p_limpa.lower()][0]
            resultado.append(p.replace(p_limpa, correta))
        elif len(p_limpa) <= 3:
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
        if any(f.lower() == p_l.lower() for f in PRESERVAR):
            correta = [f for f in PRESERVAR if f.lower() == p_l.lower()][0]
            res.append(p.replace(p_l, correta))
        else:
            res.append(p.capitalize() if i == 0 else p.lower())
    return re.sub(r'\s*:\s*', ' : ', " ".join(res))

# --- PROCESSAMENTO PRINCIPAL ---

def processar_xml(caminho_arquivo):
    diretorio_item = os.path.dirname(caminho_arquivo)
    nome_pasta = os.path.basename(diretorio_item)
    caminho_correto = os.path.join(diretorio_item, "dublin_core.xml")

    try:
        tree = ET.parse(caminho_arquivo)
        root = tree.getroot()
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
                    curso = re.sub(r'^(Mestrado|Doutorado)\s+em\s+', '', m.group(1), flags=re.IGNORECASE)
                    dados_sinc['curso_ppg'] = aplicar_regra_caracteres(curso)

        # FASE 2: TRANSFORMAÇÃO
        for elem in elementos_originais:
            el, qu, txt = elem.get("element"), elem.get("qualifier"), elem.text or ""
            lang = elem.get("language")

            try:
                if (qu and ("referees" in qu or qu.endswith("ID"))) or (el == "publisher" and qu in ["country", "initials"]):
                    continue

                if el == "description" and qu == "resumo": elem.set("qualifier", "abstract"); qu = "abstract"
                elif el == "description" and qu == "abstract": elem.set("qualifier", "abstract1"); qu = "abstract1"

                if (el == "publisher" and qu == "program") or (el == "description" and qu == "ppg"):
                    elem.set("element", "description"); elem.set("qualifier", "ppg")
                    txt = f"Programa de Pós-Graduação em {dados_sinc['curso_ppg']}"
                    el, qu = "description", "ppg"

                if el == "date" and qu == "issued":
                    elem.set("qualifier", "submitted"); qu = "submitted"

                if el == "subject" and qu in ["none", "keyword"]:
                    termos = re.split(r'[;,\.]', txt)
                    for t in [term.strip() for term in termos if term.strip()]:
                        t_limpo = re.sub(r'[\{\}\[\]\<\>\\\/]', '', t)
                        m_k = process.extract(t_limpo, list(BASE_KEYWORDS.keys()), limit=3, scorer=fuzz.token_sort_ratio)
                        validos = [m for m in m_k if m[1] >= THRESHOLD_KEYWORD]
                        escolhido = max(validos, key=lambda x: BASE_KEYWORDS[x[0]])[0] if validos else aplicar_regra_caracteres(t_limpo)
                        RELATORIO_KEYWORDS.append({'arquivo': nome_pasta, 'original': t, 'escolhido': escolhido, 'status': "CSV" if validos else "ORIGINAL"})
                        item = ET.Element("dcvalue", element="subject", qualifier="keyword")
                        if lang: item.set("language", lang)
                        item.text = escolhido.capitalize()
                        novos_elementos.append(item)
                    continue

                if el == "contributor" and qu == "advisor":
                    m_a = process.extract(txt, list(BASE_ADVISORS.keys()), limit=3, scorer=fuzz.token_sort_ratio)
                    res = m_a[0][0] if m_a and m_a[0][1] >= THRESHOLD_ADVISOR else aplicar_regra_caracteres(txt)
                    RELATORIO_ADVISORS.append({'arquivo': nome_pasta, 'original': txt, 'escolhido': res, 'status': "CSV" if m_a and m_a[0][1] >= THRESHOLD_ADVISOR else "ORIGINAL"})
                    txt = res
                elif el == "contributor" and qu and qu.startswith("advisor-co"):
                    elem.set("qualifier", "advisorco"); qu = "advisorco"
                    txt = aplicar_regra_caracteres(txt)
                elif el == "contributor" and qu == "author":
                    txt = dados_sinc['autor']

                elif el == "title": txt = dados_sinc['titulo']
                elif qu == "citation":
                    if ',' in dados_sinc['autor']:
                        sob = dados_sinc['autor'].split(',')[0].upper()
                        nme = dados_sinc['autor'].split(',')[1]
                        txt = f"{sob},{nme}. {dados_sinc['titulo']}. " + ".".join(txt.split('.')[2:])
                    pref = "Mestrado em" if dados_sinc['tipo_doc'] == "masterThesis" else "Doutorado em"
                    txt = re.sub(r'\((.*?)\)', f"({pref} {dados_sinc['curso_ppg']})", txt)
                    txt = re.sub(r'(\d+)f\.', r'\1 f.', txt)
                    txt = re.sub(r'Universidade de Brasília,\s*Universidade de Brasília', '— Universidade de Brasília', txt, flags=re.IGNORECASE)
                    txt = txt.replace("- —", "—").replace("— —", "—")
                    txt = txt.replace("— Universidade de Brasília, Brasília, Brasília", "— Universidade de Brasília, Brasília")

                elif el == "type": txt = {"masterThesis": "Dissertação", "doctoralThesis": "Tese"}.get(txt, txt)
                elif el == "rights" and qu == "license": txt = TEXTO_LICENCA

                elem.text = txt
                novos_elementos.append(elem)
            except Exception as e_field:
                novos_elementos.append(elem)

        # FASE 3: OBRIGATÓRIOS E GRAVAÇÃO
        data_i = ET.Element("dcvalue", element="date", qualifier="issued"); data_i.text = DATA_EXECUCAO
        novos_elementos.append(data_i)
        
        obrigatorios = {('rights', 'license'): TEXTO_LICENCA, ('language', 'iso'): "por", ('description', 'unidade'): ""}
        atuais = [(e.get("element"), e.get("qualifier")) for e in novos_elementos]
        for (e, q), v in obrigatorios.items():
            if (e, q) not in atuais:
                novo = ET.Element("dcvalue", element=e, qualifier=q)
                if e != 'date': novo.set("language", "pt_BR")
                novo.text = v
                novos_elementos.append(novo)

        # --- CORREÇÃO DA TAG RAIZ ---
        root.clear()
        root.set("schema", "dc") # Define o esquema dc explicitamente
        for el in novos_elementos: root.append(el)
        
        # Gravação final forçando UTF-8 e declaração XML
        tree.write(caminho_correto, encoding="utf-8", xml_declaration=True)
        if caminho_arquivo != caminho_correto:
            os.remove(caminho_arquivo)
            
        print(f"✅ {nome_pasta} organizado.")
    except Exception as e:
        print(f"❌ Erro crítico em {nome_pasta}: {e}")

# --- RELATÓRIOS E INÍCIO ---

def exibir_relatorios():
    print("\n" + "="*80 + "\n📊 RELATÓRIO DE SINCRONIZAÇÃO (GID/UnB)\n" + "="*80)
    print(f"\n[ ORIENTADORES ]")
    for a in RELATORIO_ADVISORS:
        print(f"📂 {a['arquivo']} | XML: '{a['original']}' -> {a['status']}: '{a['escolhido']}'")

    print(f"\n" + "-"*50 + "\n[ KEYWORDS / ASSUNTOS ]")
    for k in RELATORIO_KEYWORDS:
        print(f"📂 {k['arquivo']} | XML: '{k['original']}' -> {k['status']}: '{k['escolhido']}'")

def iniciar():
    print(f"🚀 Organizador v{__version__} | UnB\nData: {DATA_EXECUCAO}")
    if not os.path.exists(CAMINHO_MAC): return
    for raiz, _, arquivos in os.walk(CAMINHO_MAC):
        for arquivo in arquivos:
            if arquivo.lower() == "dublin_core.xml":
                processar_xml(os.path.join(raiz, arquivo))
    exibir_relatorios()

if __name__ == "__main__":
    iniciar()