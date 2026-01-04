import os
import re
import csv
import xml.etree.ElementTree as ET
from datetime import datetime
from rapidfuzz import process, fuzz, utils

# --- 1. CONFIGURAÇÕES E CONSTANTES ---
THRESHOLD_ADVISOR = 90
THRESHOLD_KEYWORD = 90

# Termos que devem manter a grafia exata (Case Sensitive)
PRESERVAR = [
    'UnB', 'IBICT', 'Brasília', 'Distrito Federal', 'Brasil', 'PMDF', 'DF', 
    'Mestrado', 'Doutorado', 'MEC', 'CAPES', 'MDF', 'PP', 'PEAD', 'eMulti',
    'SUS', 'COVID-19', 'TI', 'TIC', 'CNPq', 'FAPDF'
]

TEXTO_LICENCA = (
    "A concessão da licença deste item refere-se ao termo de autorização impresso assinado pelo autor com as seguintes condições: "
    "Na qualidade de titular dos direitos de autor da publicação, autorizo a Universidade de Brasília e o IBICT a disponibilizar "
    "por meio dos sites www.unb.br, www.ibict.br, www.ndltd.org sem ressarcimento dos direitos autorais, de acordo com a Lei nº 9610/98, "
    "o texto integral da obra supracitada, conforme permissões assinaladas, para fins de leitura, impressão e/ou download, "
    "a título de divulgação da produção científica brasileira, a partir desta data."
)

# --- 2. FUNÇÃO DE CARREGAMENTO DE BASES (CSVs) ---
def carregar_bases_globais(base_dir):
    """
    Carrega CSVs tratando separação de termo e frequência.
    Usa 'utf-8-sig' para remover o BOM do Excel que quebrava os matches.
    """
    def carregar_csv(nome, com_freq=False):
        caminho = os.path.join(base_dir, nome)
        dados = {}
        if not os.path.exists(caminho): 
            return {}
        
        try:
            # 'utf-8-sig' é CRUCIAL para arquivos vindos do Windows/Excel
            with open(caminho, mode='r', encoding='utf-8-sig') as f:
                # Tenta ler com ponto e vírgula primeiro (padrão Excel PT-BR)
                reader = csv.reader(f, delimiter=';')
                
                # Verificação de segurança do delimitador
                pos_inicial = f.tell()
                try:
                    primeira_linha = next(reader)
                    f.seek(pos_inicial)
                    # Se a primeira linha não tiver separação, provável que seja vírgula
                    if len(primeira_linha) < 2 and ',' in primeira_linha[0]:
                        raise ValueError("Trocar delimitador")
                except:
                    f.seek(0)
                    reader = csv.reader(f, delimiter=',')

                for linha in reader:
                    if not linha: continue
                    
                    # Normaliza o texto removendo espaços extras
                    raw_text = linha[0].strip()
                    
                    # Pula cabeçalhos
                    if raw_text.lower() in ['termo', 'orientador', 'nome', 'keyword', 'assunto', 'palavra-chave']: 
                        continue
                    
                    termo = raw_text
                    freq = 1
                    
                    # Lógica para separar termo e frequência
                    if com_freq:
                        # Caso Perfeito: ["Biologia", "10"]
                        if len(linha) > 1 and linha[1].strip().isdigit():
                            termo = raw_text
                            freq = int(linha[1].strip())
                        
                        # Caso "Grudado": ["Biologia,10"]
                        elif ',' in raw_text:
                            partes = raw_text.rsplit(',', 1)
                            if len(partes) == 2 and partes[1].isdigit():
                                termo = partes[0].strip()
                                freq = int(partes[1])
                    
                    # Guarda apenas se o termo não for vazio
                    if termo:
                        dados[termo] = freq

        except Exception as e:
            # Em produção, pode-se logar o erro, mas aqui silenciamos para não travar
            print(f"Erro ao ler base {nome}: {str(e)}")
            pass
            
        return dados

    # Tenta carregar com os nomes padrão
    advisors = carregar_csv("base_orientadores_unb.csv", com_freq=True)
    if not advisors: advisors = carregar_csv("advisor-ppg.csv", com_freq=True)

    keywords = carregar_csv("base_assuntos_unb.csv", com_freq=True)
    if not keywords: keywords = carregar_csv("keywords.csv", com_freq=True)

    return {'advisors': advisors, 'keywords': keywords}

# --- 3. FUNÇÕES AUXILIARES DE TEXTO ---
def aplicar_regra_caracteres(texto):
    """Capitalização inteligente (Title Case) preservando siglas."""
    if not texto: return ""
    
    # Divide preservando pontuação para não perder contexto
    palavras = texto.strip().split()
    resultado = []
    
    for i, p in enumerate(palavras):
        # Versão limpa para comparação (sem pontuação)
        p_limpa = re.sub(r'[^\w\-]', '', p)
        
        # Verifica se a palavra está na lista de preservar (ex: 'UnB' mantém 'UnB')
        correta = next((fixo for fixo in PRESERVAR if fixo.lower() == p_limpa.lower()), None)
        
        if correta:
            # Substitui o texto mas mantém a pontuação original (ex: "(unb)" vira "(UnB)")
            resultado.append(p.replace(p_limpa, correta))
        elif len(p_limpa) <= 3 and i > 0: 
            # Preposições curtas no meio da frase ficam em minúsculo
            resultado.append(p.lower())
        else:
            # Capitaliza a primeira letra
            resultado.append(p.capitalize())
            
    return " ".join(resultado)

def tratar_titulo(texto):
    """Formata títulos e corrige espaçamento de dois pontos."""
    if not texto: return ""
    
    # Aplica a regra geral primeiro
    texto_formatado = aplicar_regra_caracteres(texto)
    
    # Corrige espaçamento dos dois pontos: "Titulo:Subtitulo" -> "Titulo : Subtitulo"
    # A UnB geralmente pede espaço antes e depois, ou apenas depois.
    # O padrão aqui será garantir espaço: " : "
    texto_formatado = re.sub(r'\s*:\s*', ' : ', texto_formatado)
    
    return texto_formatado

# --- 4. FUNÇÃO PRINCIPAL ---
def processar_arquivo_direto(caminho_xml, bases):
    """
    Processa um arquivo XML Dublin Core.
    Retorna: (sucesso: bool, logs: list)
    """
    logs = []
    
    try:
        # PASSO A: Leitura Segura do XML (com fallback para binário)
        try:
            parser = ET.XMLParser(encoding="utf-8")
            tree = ET.parse(caminho_xml, parser=parser)
            root = tree.getroot()
        except ET.ParseError:
            with open(caminho_xml, 'rb') as f: 
                data = f.read()
            # Limpa caracteres de controle inválidos
            clean_data = re.sub(rb'[^\x09\x0A\x0D\x20-\x7E\x80-\xFF]', b'', data)
            root = ET.fromstring(clean_data)
            tree = ET.ElementTree(root)

        # Listas para Fuzzy Matching
        lista_advisors = list(bases['advisors'].keys())
        lista_keywords = list(bases['keywords'].keys())
        
        # Dicionário para sincronização de metadados
        dados_sinc = {'autor': '', 'titulo': '', 'curso_ppg': '', 'tipo_doc': ''}
        
        # PASSO B: Fase de Descoberta (Ler dados antes de alterar)
        for elem in root.findall("dcvalue"):
            el = elem.get("element")
            qu = elem.get("qualifier")
            txt = elem.text or ""

            if el == "contributor" and qu == "author":
                dados_sinc['autor'] = aplicar_regra_caracteres(txt)
            elif el == "title":
                dados_sinc['titulo'] = tratar_titulo(txt)
            elif el == "type":
                dados_sinc['tipo_doc'] = txt
            elif qu == "citation":
                # Tenta extrair o curso da citação antiga se possível
                m = re.search(r'\((.*?)\)', txt)
                if m:
                    raw_curso = m.group(1)
                    # Remove prefixos comuns para limpar o nome do curso
                    curso_limpo = re.sub(r'(Mestrado|Doutorado)\s+em\s+', '', raw_curso, flags=re.IGNORECASE).strip()
                    dados_sinc['curso_ppg'] = aplicar_regra_caracteres(curso_limpo)

        # PASSO C: Construção da Nova Estrutura (Evita erros de referência)
        # Vamos criar uma lista de novos elementos, em vez de modificar os antigos
        novos_elementos = []

        for elem in root.findall("dcvalue"):
            el = elem.get("element")
            qu = elem.get("qualifier")
            lang = elem.get("language")
            txt = elem.text or ""
            txt_original = txt

            # Ignora campos de controle interno que não devem ser duplicados/alterados
            if (qu and ("referees" in qu or qu.endswith("ID"))) or (el == "publisher" and qu in ["country", "initials"]):
                # Se quiser manter esses campos sem alteração, descomente abaixo:
                # novos_elementos.append(elem) 
                continue

            # --- PROCESSAMENTO DE ASSUNTOS (KEYWORDS) ---
            if el == "subject" and qu in ["none", "keyword"]:
                # Divide termos compostos (separados por ; , ou .)
                termos_split = re.split(r'[;,\.]', txt)
                
                for t in termos_split:
                    t = t.strip()
                    if not t: continue
                    
                    t_limpo = re.sub(r'[\{\}\[\]\<\>\\\/]', '', t)
                    escolhido = t_limpo
                    origem = "GRAMÁTICA"

                    # Tenta Fuzzy Match se houver base carregada
                    if lista_keywords:
                        matches = process.extract(
                            t_limpo, lista_keywords, limit=3, 
                            scorer=fuzz.token_sort_ratio, processor=utils.default_process
                        )
                        # Filtra por similaridade >= 90
                        validos = [m for m in matches if m[1] >= THRESHOLD_KEYWORD]
                        
                        if validos:
                            # Desempate por frequência (quem aparece mais na base ganha)
                            melhor = sorted(validos, key=lambda x: bases['keywords'].get(x[0], 0), reverse=True)[0]
                            escolhido = melhor[0]
                            origem = "BASE"
                        else:
                            escolhido = aplicar_regra_caracteres(t_limpo)
                    else:
                        escolhido = aplicar_regra_caracteres(t_limpo)

                    # Log se houve alteração
                    if escolhido != t:
                        logs.append(f"🔑 Assunto [{origem}]: '{t}' -> '{escolhido}'")

                    # Cria NOVO elemento
                    novo_item = ET.Element("dcvalue", element="subject", qualifier="keyword")
                    if lang: novo_item.set("language", lang)
                    novo_item.text = escolhido
                    novos_elementos.append(novo_item)
                
                # 'continue' para não processar este elemento 'subject' novamente
                continue

            # --- PROCESSAMENTO DE ORIENTADORES ---
            novo_txt = txt
            novo_qu = qu

            if el == "contributor" and qu == "advisor":
                if lista_advisors:
                    matches = process.extract(txt, lista_advisors, limit=3, scorer=fuzz.token_sort_ratio, processor=utils.default_process)
                    validos = [m for m in matches if m[1] >= THRESHOLD_ADVISOR]
                    
                    if validos:
                        escolhido = sorted(validos, key=lambda x: bases['advisors'].get(x[0], 0), reverse=True)[0][0]
                        if escolhido != txt:
                            logs.append(f"👤 Orientador [BASE]: '{txt}' -> '{escolhido}'")
                        novo_txt = escolhido
                    else:
                        novo_txt = aplicar_regra_caracteres(txt)
                else:
                    novo_txt = aplicar_regra_caracteres(txt)

            # --- CO-ORIENTADORES ---
            elif el == "contributor" and qu and "advisor-co" in qu:
                novo_qu = "advisorco" # Padronização
                novo_txt = aplicar_regra_caracteres(txt)

            # --- SINCRONIZAÇÃO DE AUTOR/TÍTULO ---
            elif el == "contributor" and qu == "author":
                novo_txt = dados_sinc['autor']
            elif el == "title":
                novo_txt = dados_sinc['titulo']
            
            # --- PADRONIZAÇÕES DIVERSAS ---
            elif el == "description" and qu == "resumo":
                novo_qu = "abstract"
            elif el == "date" and qu == "issued":
                novo_qu = "submitted" # Muda issued original para submitted
            
            elif el == "rights" and qu == "license":
                novo_txt = TEXTO_LICENCA

            # --- RECONSTRUÇÃO DA CITAÇÃO ---
            elif qu == "citation":
                # Formata autores: SOBRENOME, Nome
                autores_fmt = dados_sinc['autor']
                if ',' in dados_sinc['autor']:
                    parts = dados_sinc['autor'].split(',')
                    if len(parts) >= 2:
                        autores_fmt = f"{parts[0].strip().upper()}, {parts[1].strip()}"
                
                # Tenta manter o final da citação original (páginas, ano, etc.)
                resto_citacao = ""
                if len(txt_original.split('. ')) > 2:
                     resto_citacao = ". ".join(txt_original.split('. ')[2:])
                
                # Define o prefixo do grau
                tipo_grau = "Dissertação (Mestrado" if "master" in dados_sinc['tipo_doc'] or "Mestrado" in txt_original else "Tese (Doutorado"
                curso_nome = dados_sinc['curso_ppg'] if dados_sinc['curso_ppg'] else "PREENCHER CURSO"
                
                # Monta a nova citação
                novo_txt = f"{autores_fmt}. {dados_sinc['titulo']}. {tipo_grau} em {curso_nome}) — Universidade de Brasília, {datetime.now().year}. {resto_citacao}"
                
                # Limpeza final de duplicatas comuns
                novo_txt = novo_txt.replace("..", ".")
                novo_txt = re.sub(r'Universidade de Brasília,\s*Universidade de Brasília', '— Universidade de Brasília', novo_txt, flags=re.IGNORECASE)

            # Cria o elemento processado
            novo_elem = ET.Element("dcvalue", element=el, qualifier=novo_qu)
            if lang: novo_elem.set("language", lang)
            novo_elem.text = novo_txt
            novos_elementos.append(novo_elem)

        # PASSO D: Adição de Campos Obrigatórios
        # 1. Data Issued (Data de hoje)
        data_hj = ET.Element("dcvalue", element="date", qualifier="issued")
        data_hj.text = datetime.now().strftime("%Y-%m-%d")
        novos_elementos.append(data_hj)
        
        # 2. Verifica e adiciona faltantes
        tem_ppg = any(e.get("qualifier") == "ppg" for e in novos_elementos)
        if not tem_ppg:
            ppg = ET.Element("dcvalue", element="description", qualifier="ppg")
            ppg.set("language", "pt_BR")
            ppg.text = "PREENCHER"
            novos_elementos.append(ppg)

        # 3. Campos fixos obrigatórios
        campos_fixos = [
            ("rights", "license", TEXTO_LICENCA),
            ("language", "iso", "por"),
            ("description", "unidade", "PREENCHER")
        ]
        
        atuais = {(e.get("element"), e.get("qualifier")) for e in novos_elementos}
        
        for e, q, v in campos_fixos:
            if (e, q) not in atuais:
                fixo = ET.Element("dcvalue", element=e, qualifier=q)
                fixo.set("language", "pt_BR")
                fixo.text = v
                novos_elementos.append(fixo)

        # PASSO E: Escrita no Arquivo
        root.clear() # Limpa a árvore antiga
        root.set("schema", "dc")
        
        for item in novos_elementos:
            root.append(item)
            
        tree.write(caminho_xml, encoding="utf-8", xml_declaration=True)
        
        return True, logs

    except Exception as e:
        return False, [f"Erro Fatal ao processar: {str(e)}"]