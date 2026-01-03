import os
import re
import csv
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from thefuzz import fuzz, process

# --- CONFIGURAÇÕES ---
__version__ = "0.5 (Memória de Caminho)"

# Arquivo para salvar o último caminho usado (criado automaticamente)
ARQUIVO_CONFIG = ".gid_last_path"

# OBS: Caminhos dos arquivos de referência
CAMINHO_CSV_ADVISORS = '/Users/leonardorcarvalho/Library/CloudStorage/OneDrive-Pessoal/Documentos/GitHub/gid-docs/testefinal/advisor-ppg.csv'
CAMINHO_CSV_KEYWORDS = '/Users/leonardorcarvalho/Library/CloudStorage/OneDrive-Pessoal/Documentos/GitHub/gid-docs/testefinal/keywords.csv'

# Limiares de Semelhança (0 a 100)
THRESHOLD_ADVISOR = 90
THRESHOLD_KEYWORD = 90

PRESERVAR = ['UnB', 'IBICT', 'Brasília', 'Distrito Federal', 'Brasil', 'PMDF', 'DF', 'Mestrado', 'Doutorado', 'MEC', 'CAPES', 'MDF', 'PP', 'PEAD']

TEXTO_LICENCA = (
    "A concessão da licença deste item refere-se ao termo de autorização impresso assinado pelo autor com as seguintes condições: "
    "Na qualidade de titular dos direitos de autor da publicação, autorizo a Universidade de Brasília e o IBICT a disponibilizar "
    "por meio dos sites www.unb.br, www.ibict.br, www.ndltd.org sem ressarcimento dos direitos autorais, de acordo com a Lei nº 9610/98, "
    "o texto integral da obra supracitada, conforme permissões assinaladas, para fins de leitura, impressão e/ou download, "
    "a título de divulgação da produção científica brasileira, a partir desta data."
)

DATA_EXECUCAO = datetime.now().strftime("%Y-%m-%d")
RELATORIO_ADVISORS = []
RELATORIO_KEYWORDS = []

# --- FUNÇÕES DE MEMÓRIA ---

def obter_caminho_salvo():
    """Lê o último caminho salvo no arquivo de configuração."""
    if os.path.exists(ARQUIVO_CONFIG):
        try:
            with open(ARQUIVO_CONFIG, 'r', encoding='utf-8') as f:
                caminho = f.read().strip()
                if os.path.exists(caminho):
                    return caminho
        except:
            pass
    return None

def salvar_caminho(caminho):
    """Salva o caminho válido para a próxima execução."""
    try:
        with open(ARQUIVO_CONFIG, 'w', encoding='utf-8') as f:
            f.write(caminho)
    except Exception as e:
        print(f"[AVISO] Não foi possível salvar a preferência de caminho: {e}")

# --- FUNÇÕES AUXILIARES ---

def carregar_csv_dict(caminho, com_frequencia=False):
    dados = {}
    if not os.path.exists(caminho): 
        print(f"[AVISO] CSV não encontrado: {caminho}")
        return {}
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
    except Exception as e:
        print(f"[ERRO] Falha ao ler CSV {caminho}: {e}")
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

# --- PROCESSAMENTO XML ---

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
                    raw_curso = m.group(1)
                    curso_limpo = re.sub(r'(Mestrado|Doutorado)\s+em\s+', '', raw_curso, flags=re.IGNORECASE).strip()
                    dados_sinc['curso_ppg'] = aplicar_regra_caracteres(curso_limpo)

        # FASE 2: TRANSFORMAÇÃO
        for elem in elementos_originais:
            el, qu, txt = elem.get("element"), elem.get("qualifier"), elem.text or ""
            lang = elem.get("language")

            try:
                # Exclusões
                if (qu and ("referees" in qu or qu.endswith("ID"))) or (el == "publisher" and qu in ["country", "initials"]):
                    continue

                if el == "description" and qu == "resumo": elem.set("qualifier", "abstract"); qu = "abstract"
                elif el == "description" and qu == "abstract": elem.set("qualifier", "abstract1"); qu = "abstract1"

                if (el == "publisher" and qu == "program") or (el == "description" and qu == "ppg"):
                    elem.set("element", "description"); elem.set("qualifier", "ppg")
                    el, qu = "description", "ppg"
                    txt = f"Programa de Pós-Graduação em {dados_sinc['curso_ppg']}" if dados_sinc['curso_ppg'] else "PREENCHER"

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
                        parts = dados_sinc['autor'].split(',')
                        if len(parts) >= 2:
                            sob = parts[0].upper()
                            nme = parts[1]
                            txt = f"{sob},{nme}. {dados_sinc['titulo']}. " + ".".join(txt.split('.')[2:])
                    pref = "Mestrado em" if dados_sinc['tipo_doc'] == "masterThesis" else "Doutorado em"
                    curso_f = dados_sinc['curso_ppg'] if dados_sinc['curso_ppg'] else "PREENCHER"
                    txt = re.sub(r'\((.*?)\)', f"({pref} {curso_f})", txt)
                    txt = re.sub(r'(\d+)f\.', r'\1 f.', txt)
                    txt = re.sub(r'Universidade de Brasília,\s*Universidade de Brasília', '— Universidade de Brasília', txt, flags=re.IGNORECASE)
                    txt = txt.replace("- —", "—").replace("— —", "—").replace("— Universidade de Brasília, Brasília, Brasília", "— Universidade de Brasília, Brasília")

                elif el == "type": txt = {"masterThesis": "Dissertação", "doctoralThesis": "Tese"}.get(txt, txt)
                elif el == "rights" and qu == "license": txt = TEXTO_LICENCA

                elem.text = txt
                novos_elementos.append(elem)
            except: novos_elementos.append(elem)

        # FASE 3: OBRIGATÓRIOS
        data_i = ET.Element("dcvalue", element="date", qualifier="issued"); data_i.text = DATA_EXECUCAO
        novos_elementos.append(data_i)
        
        obrigatorios = {('rights', 'license'): TEXTO_LICENCA, ('language', 'iso'): "por", ('description', 'unidade'): "PREENCHER"}
        if not any(e.get("qualifier") == "ppg" for e in novos_elementos):
             ppg_n = ET.Element("dcvalue", element="description", qualifier="ppg"); ppg_n.set("language", "pt_BR"); ppg_n.text = "PREENCHER"; novos_elementos.append(ppg_n)

        atuais = [(e.get("element"), e.get("qualifier")) for e in novos_elementos]
        for (e, q), v in obrigatorios.items():
            if (e, q) not in atuais:
                n = ET.Element("dcvalue", element=e, qualifier=q)
                if e != 'date': n.set("language", "pt_BR")
                n.text = v
                novos_elementos.append(n)

        # CORREÇÃO DA TAG RAIZ E GRAVAÇÃO
        root.clear()
        root.set("schema", "dc")
        for el in novos_elementos: root.append(el)
        
        tree.write(caminho_correto, encoding="utf-8", xml_declaration=True)
        if caminho_arquivo != caminho_correto: os.remove(caminho_arquivo)
            
        print(f"✅ {nome_pasta} processado.")
    except Exception as e: print(f"❌ Erro em {nome_pasta}: {e}")

# --- SANITIZAÇÃO DE PASTAS ---

def normalizar_nome_pasta(nome):
    """Remove caracteres que quebram o Linux."""
    nome_norm = unicodedata.normalize('NFC', nome)
    nome_norm = nome_norm.strip().replace(" ", "_")
    nome_norm = re.sub(r'[^\w\-]', '', nome_norm)
    return nome_norm

def sanitizar_diretorios(caminho_raiz):
    print(f"🧹 Verificando nomes de pastas em: {caminho_raiz}")
    for item in os.listdir(caminho_raiz):
        caminho_antigo = os.path.join(caminho_raiz, item)
        if os.path.isdir(caminho_antigo) and not item.startswith('.'):
            novo_nome = normalizar_nome_pasta(item)
            caminho_novo = os.path.join(caminho_raiz, novo_nome)
            
            if caminho_antigo != caminho_novo:
                try:
                    os.rename(caminho_antigo, caminho_novo)
                    print(f"   Corrigido: {item} -> {novo_nome}")
                except Exception as e:
                    print(f"   Erro ao renomear {item}: {e}")

def exibir_relatorios():
    print("\n" + "="*80 + "\n📊 RESUMO GID/UnB\n" + "="*80)
    print(f"Orientadores processados: {len(RELATORIO_ADVISORS)}")
    print(f"Keywords processadas: {len(RELATORIO_KEYWORDS)}")

def iniciar():
    print(f"🚀 Iniciando GID v{__version__} | {DATA_EXECUCAO}")
    
    # --- INPUT COM MEMÓRIA ---
    caminho_salvo = obter_caminho_salvo()
    prompt_texto = "\n>> Cole o caminho da pasta raiz"
    
    if caminho_salvo:
        prompt_texto += f" (Enter para usar: {caminho_salvo}): "
    else:
        prompt_texto += ": "
        
    entrada_usuario = input(prompt_texto).strip()
    
    # Limpa aspas
    entrada_usuario = entrada_usuario.replace('"', '').replace("'", "")
    
    # Decide qual caminho usar
    if not entrada_usuario and caminho_salvo:
        caminho_raiz = caminho_salvo
        print(f"   Usando caminho salvo: {caminho_raiz}")
    else:
        caminho_raiz = entrada_usuario

    # Validação
    if not caminho_raiz or not os.path.exists(caminho_raiz):
        print(f"\n[ERRO] Caminho inválido ou não encontrado: '{caminho_raiz}'")
        return
    
    # Salva para a próxima vez
    salvar_caminho(caminho_raiz)
    
    # Executa as funções
    sanitizar_diretorios(caminho_raiz)
    
    print("\n🔍 Buscando arquivos XML...")
    encontrados = 0
    for raiz, _, arquivos in os.walk(caminho_raiz):
        for arquivo in arquivos:
            if arquivo.lower().endswith(".xml"): 
                processar_xml(os.path.join(raiz, arquivo))
                encontrados += 1
                
    if encontrados == 0:
        print("[AVISO] Nenhum arquivo XML encontrado na pasta indicada.")
    
    exibir_relatorios()

if __name__ == "__main__":
    iniciar()