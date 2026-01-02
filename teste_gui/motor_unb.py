import os
import re
import csv
import xml.etree.ElementTree as ET
from datetime import datetime
from rapidfuzz import process, fuzz, utils

# --- CONFIGURAÇÕES E CONSTANTES ---
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
    """Carrega os CSVs uma única vez para memória."""
    def carregar_csv(nome, com_freq=False):
        caminho = os.path.join(base_dir, nome)
        dados = {}
        if not os.path.exists(caminho): return {}
        try:
            with open(caminho, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=';') # Ou ',' dependendo do seu CSV. O script v0.2 usava ',' default
                # Tentativa de detectar delimitador se falhar
                if not reader: 
                     f.seek(0)
                     reader = csv.reader(f, delimiter=',')
                     
                for linha in reader:
                    if not linha or len(linha) < 1: continue
                    # Pula cabeçalhos comuns
                    if linha[0].lower() in ['termo', 'orientador', 'nome']: continue
                    
                    termo = linha[0].strip()
                    if com_freq:
                        # Tenta pegar frequencia da coluna 2, ou do split da coluna 1
                        partes = termo.rsplit(',', 1)
                        if len(linha) > 1 and linha[1].strip().isdigit():
                            dados[termo] = int(linha[1].strip())
                        elif len(partes) == 2 and partes[1].isdigit():
                            dados[partes[0].strip()] = int(partes[1])
                        else: 
                            dados[termo] = 1
                    else: 
                        dados[termo] = 0
        except: pass
        return dados

    return {
        'advisors': carregar_csv("base_orientadores_unb.csv", com_freq=True), # Ajuste se seu CSV tem frequencia
        'keywords': carregar_csv("base_assuntos_unb.csv", com_freq=True)
    }

def aplicar_regra_caracteres(texto):
    if not texto: return ""
    palavras = texto.strip().split()
    resultado = []
    for p in palavras:
        p_limpa = re.sub(r'[^\w]', '', p)
        # Verifica se a palavra limpa está na lista de preservar (case insensitive)
        correta = next((f for f in PRESERVAR if f.lower() == p_limpa.lower()), None)
        
        if correta:
            # Mantém a pontuação original mas usa a grafia correta (ex: unb, -> UnB,)
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
        p_limpa = re.sub(r'[^\w]', '', p)
        correta = next((f for f in PRESERVAR if f.lower() == p_limpa.lower()), None)
        
        if correta:
            res.append(p.replace(p_limpa, correta))
        else:
            # Capitaliza apenas a primeira palavra do título, o resto lowercase (exceto preservados)
            res.append(p.capitalize() if i == 0 else p.lower())
            
    # Corrige espaços em volta de dois pontos
    final = " ".join(res)
    return re.sub(r'\s*:\s*', ' : ', final)

def processar_arquivo_direto(caminho_xml, bases):
    """Lógica completa do Organizador v0.2 adaptada para o Motor."""
    log_mudancas = []
    
    try:
        # Leitura tolerante a erros de encoding
        try:
            parser = ET.XMLParser(encoding="utf-8")
            tree = ET.parse(caminho_xml, parser=parser)
            root = tree.getroot()
        except ET.ParseError:
            with open(caminho_xml, 'rb') as f:
                data = f.read()
            clean_data = re.sub(rb'[^\x09\x0A\x0D\x20-\x7E\x80-\xFF]', b'', data)
            root = ET.fromstring(clean_data)
            tree = ET.ElementTree(root)

        lista_advisors = list(bases['advisors'].keys())
        lista_keywords = list(bases['keywords'].keys())
        
        # --- FASE 1: DESCOBERTA (Extrair dados para usar nas regras complexas) ---
        dados_sinc = {'autor': '', 'titulo': '', 'curso_ppg': '', 'tipo_doc': ''}
        elementos_originais = root.findall("dcvalue")
        
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
                    # Remove "Mestrado em" ou "Doutorado em" para pegar só o curso
                    curso = re.sub(r'^(Mestrado|Doutorado)\s+em\s+', '', m.group(1), flags=re.IGNORECASE)
                    dados_sinc['curso_ppg'] = aplicar_regra_caracteres(curso)

        # --- FASE 2: TRANSFORMAÇÃO E FILTRAGEM ---
        novos_elementos = []
        
        for elem in elementos_originais:
            el, qu, txt_original = elem.get("element"), elem.get("qualifier"), elem.text or ""
            lang = elem.get("language")
            
            # 1. Remoção de Lixo
            if (qu and ("referees" in qu or qu.endswith("ID"))) or (el == "publisher" and qu in ["country", "initials"]):
                continue # Pula este elemento (não adiciona à lista final)

            # 2. Renomeação de Tags (Resumos e Abstratos)
            if el == "description" and qu == "resumo":
                elem.set("qualifier", "abstract"); qu = "abstract"
                log_mudancas.append("Tag: description.resumo -> abstract")
            elif el == "description" and qu == "abstract":
                elem.set("qualifier", "abstract1"); qu = "abstract1"
                log_mudancas.append("Tag: description.abstract -> abstract1")

            # 3. Tratamento de Programa de Pós-Graduação
            if (el == "publisher" and qu == "program") or (el == "description" and qu == "ppg"):
                elem.set("element", "description")
                elem.set("qualifier", "ppg")
                txt_novo = f"Programa de Pós-Graduação em {dados_sinc['curso_ppg']}"
                if txt_original != txt_novo:
                    elem.text = txt_novo
                    log_mudancas.append(f"PPG normalizado: {txt_novo}")
                novos_elementos.append(elem)
                continue # Já processou, vai pro próximo

            # 4. Troca de Data (Issued -> Submitted)
            if el == "date" and qu == "issued":
                elem.set("qualifier", "submitted"); qu = "submitted"
                novos_elementos.append(elem)
                continue

            # 5. Assuntos (Keywords) - Lógica Fuzzy
            if el == "subject" and qu in ["none", "keyword"]:
                termos = re.split(r'[;,\.]', txt_original)
                for t in [term.strip() for term in termos if term.strip()]:
                    t_limpo = re.sub(r'[\{\}\[\]\<\>\\\/]', '', t)
                    
                    # RapidFuzz match
                    matches = process.extract(t_limpo, lista_keywords, limit=3, scorer=fuzz.token_sort_ratio, processor=utils.default_process)
                    validos = [m for m in matches if m[1] >= THRESHOLD_KEYWORD]
                    
                    if validos:
                        # Escolhe o mais frequente na base
                        escolhido = max(validos, key=lambda x: bases['keywords'].get(x[0], 0))[0]
                        if t != escolhido:
                            log_mudancas.append(f"Assunto: '{t}' -> '{escolhido}'")
                    else:
                        escolhido = aplicar_regra_caracteres(t_limpo)
                    
                    # Cria novo elemento para cada assunto separado
                    item = ET.Element("dcvalue", element="subject", qualifier="keyword")
                    if lang: item.set("language", lang)
                    item.text = escolhido.capitalize() # Regra do script v0.2
                    novos_elementos.append(item)
                continue

            # 6. Orientadores
            if el == "contributor" and qu == "advisor":
                m_a = process.extractOne(txt_original, lista_advisors, scorer=fuzz.token_sort_ratio, processor=utils.default_process)
                if m_a and m_a[1] >= THRESHOLD_ADVISOR:
                    txt_final = m_a[0]
                    if txt_original != txt_final:
                        log_mudancas.append(f"Orientador: '{txt_original}' -> '{txt_final}'")
                else:
                    txt_final = aplicar_regra_caracteres(txt_original)
                elem.text = txt_final
                novos_elementos.append(elem)
                continue
            
            # 7. Co-Orientadores
            if el == "contributor" and qu and qu.startswith("advisor-co"):
                elem.set("qualifier", "advisorco")
                elem.text = aplicar_regra_caracteres(txt_original)
                novos_elementos.append(elem)
                continue

            # 8. Autor (Padronização)
            if el == "contributor" and qu == "author":
                elem.text = dados_sinc['autor']
                novos_elementos.append(elem)
                continue

            # 9. Título (Padronização)
            if el == "title":
                elem.text = dados_sinc['titulo']
                novos_elementos.append(elem)
                continue

            # 10. Citação (Citation) - A Regra Complexa
            if qu == "citation":
                txt_citacao = txt_original
                # Tenta formatar ABNT: SOBRENOME, Nome. Titulo.
                if ',' in dados_sinc['autor']:
                    try:
                        partes_autor = dados_sinc['autor'].split(',')
                        sob = partes_autor[0].upper()
                        nme = partes_autor[1].strip()
                        # Reconstrói a citação mantendo a paginação (parte final após o titulo)
                        # Assume que a citação original tem o formato antigo para tentar aproveitar o final
                        partes_citacao = txt_original.split('.')
                        resto = ".".join(partes_citacao[2:]) if len(partes_citacao) > 2 else ""
                        txt_citacao = f"{sob}, {nme}. {dados_sinc['titulo']}. {resto}"
                    except:
                        pass # Falha na formatação, mantém o melhor esforço
                
                # Ajusta (Mestrado/Doutorado em X)
                pref = "Mestrado em" if dados_sinc['tipo_doc'] == "masterThesis" else "Doutorado em"
                txt_citacao = re.sub(r'\((.*?)\)', f"({pref} {dados_sinc['curso_ppg']})", txt_citacao)
                
                # Ajusta paginação "123f."
                txt_citacao = re.sub(r'(\d+)f\.', r'\1 f.', txt_citacao)
                
                # Remove duplicação de "Universidade de Brasília"
                txt_citacao = re.sub(r'Universidade de Brasília,\s*Universidade de Brasília', '— Universidade de Brasília', txt_citacao, flags=re.IGNORECASE)
                txt_citacao = txt_citacao.replace("- —", "—").replace("— —", "—")
                txt_citacao = txt_citacao.replace("— Universidade de Brasília, Brasília, Brasília", "— Universidade de Brasília, Brasília")
                
                elem.text = txt_citacao
                log_mudancas.append("Citação padronizada")
                novos_elementos.append(elem)
                continue

            # 11. Tipo de Documento
            if el == "type":
                mapa_tipo = {"masterThesis": "Dissertação", "doctoralThesis": "Tese"}
                elem.text = mapa_tipo.get(txt_original, txt_original)
                novos_elementos.append(elem)
                continue

            # 12. Direitos / Licença
            if el == "rights" and qu == "license":
                elem.text = TEXTO_LICENCA
                novos_elementos.append(elem)
                continue

            # Se não caiu em nenhuma regra acima, mantém o elemento (apenas limpo de erros)
            novos_elementos.append(elem)

        # --- FASE 3: ELEMENTOS OBRIGATÓRIOS E NOVOS ---
        
        # Insere a data de hoje como "issued"
        data_hj = ET.Element("dcvalue", element="date", qualifier="issued")
        data_hj.text = datetime.now().strftime("%Y-%m-%d")
        novos_elementos.append(data_hj)
        
        # Verifica obrigatórios
        obrigatorios = {
            ('rights', 'license'): TEXTO_LICENCA,
            ('language', 'iso'): "por",
            ('description', 'unidade'): "Faculdade de Ciência da Informação" # Default ou vazio se preferir
        }
        
        atuais_tags = [(e.get("element"), e.get("qualifier")) for e in novos_elementos]
        
        for (e, q), v in obrigatorios.items():
            if (e, q) not in atuais_tags:
                novo = ET.Element("dcvalue", element=e, qualifier=q)
                if e != 'date': novo.set("language", "pt_BR")
                novo.text = v
                novos_elementos.append(novo)

        # --- GRAVAÇÃO ---
        root.clear()
        root.set("schema", "dc")
        for el in novos_elementos: root.append(el)
        
        tree.write(caminho_xml, encoding="utf-8", xml_declaration=True)
        
        msg_final = " | ".join(log_mudancas) if log_mudancas else "OK (Processado completo)"
        return True, msg_final

    except Exception as e:
        return False, f"Erro: {str(e)}"