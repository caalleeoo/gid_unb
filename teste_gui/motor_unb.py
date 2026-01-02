import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime

# --- CONFIGURAÇÕES ---
__version__ = "0.3 (App Integration)"

# Siglas e nomes próprios protegidos
PRESERVAR = ['UnB', 'IBICT', 'Brasília', 'Distrito Federal', 'Brasil', 'PMDF', 'DF', 'Mestrado', 'Doutorado', 'MEC', 'CAPES', 'MDF', 'PP', 'PEAD']

TEXTO_LICENCA = (
    "A concessão da licença deste item refere-se ao termo de autorização impresso assinado pelo autor com as seguintes condições: "
    "Na qualidade de titular dos direitos de autor da publicação, autorizo a Universidade de Brasília e o IBICT a disponibilizar "
    "por meio dos sites www.unb.br, www.ibict.br, www.ndltd.org sem ressarcimento dos direitos autorais, de acordo com a Lei nº 9610/98, "
    "o texto integral da obra supracitada, conforme permissões assinaladas, para fins de leitura, impressão e/ou download, "
    "a título de divulgação da produção científica brasileira, a partir desta data."
)

# --- FUNÇÕES DE TEXTO (Sua lógica original) ---

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

def tratar_texto_com_preservacao(texto, forcar_primeira_maiuscula=True):
    if not texto: return texto
    palavras = texto.strip().split()
    resultado = []
    for i, p in enumerate(palavras):
        p_limpa = re.sub(r'[^\w]', '', p)
        if any(fixo.lower() == p_limpa.lower() for fixo in PRESERVAR):
            correta = [fixo for fixo in PRESERVAR if fixo.lower() == p_limpa.lower()][0]
            resultado.append(p.replace(p_limpa, correta))
        else:
            if i == 0 and forcar_primeira_maiuscula:
                resultado.append(p.capitalize())
            else:
                resultado.append(p.lower())
    return " ".join(resultado)

def extrair_apenas_nome_curso(texto_citacao):
    if not texto_citacao: return None
    match = re.search(r'\((.*?)\)', texto_citacao)
    if match:
        conteudo = match.group(1)
        limpo = re.sub(r'^(Mestrado|Doutorado)\s+em\s+', '', conteudo, flags=re.IGNORECASE)
        return aplicar_regra_caracteres(limpo)
    return None

def ajustar_autor_citacao(autor_tratado):
    if ',' not in autor_tratado: return autor_tratado.upper()
    sobrenome, resto = autor_tratado.split(',', 1)
    return f"{sobrenome.upper()},{resto}"

# --- MOTOR DE PROCESSAMENTO ---

def processar_arquivo_direto(caminho_arquivo):
    """
    Função BLINDADA: Abre o ficheiro no caminho, altera e salva no mesmo lugar.
    Retorna True se funcionou, False se falhou.
    """
    try:
        print(f"⚙️ MOTOR: A trabalhar em {os.path.basename(caminho_arquivo)}...")
        
        # 1. Abre o XML
        tree = ET.parse(caminho_arquivo)
        root = tree.getroot()
        
        # 2. Prepara variáveis de análise
        dados_sinc = {'autor': '', 'titulo': '', 'curso_limpo': '', 'tipo_doc': ''}
        elementos_originais = root.findall("dcvalue")
        novos_elementos = []

        # 3. Análise Prévia (Scan)
        for elem in elementos_originais:
            el, qu = elem.get("element"), elem.get("qualifier")
            txt = elem.text if elem.text else ""
            
            if el == "contributor" and qu == "author":
                dados_sinc['autor'] = aplicar_regra_caracteres(txt)
            elif el == "title":
                t_base = tratar_texto_com_preservacao(txt)
                dados_sinc['titulo'] = re.sub(r'\s*:\s*', ' : ', t_base)
            elif el == "type":
                dados_sinc['tipo_doc'] = txt 
            elif qu == "citation":
                dados_sinc['curso_limpo'] = extrair_apenas_nome_curso(txt)

        # 4. Aplicação das Regras
        for elem in elementos_originais:
            el, qu = elem.get("element"), elem.get("qualifier")
            txt = elem.text if elem.text else ""
            lang = elem.get("language")

            try:
                # Pular elementos indesejados
                if qu and ("referees" in qu or qu.endswith("ID")): continue
                if el == "publisher" and qu in ["country", "initials"]: continue

                # Keywords
                if el == "subject" and qu in ["none", "keyword"]:
                    for t in [term.strip() for term in re.split(r'[;,\.]', txt) if term.strip()]:
                        item = ET.Element("dcvalue", element="subject", qualifier="keyword")
                        if lang: item.set("language", lang)
                        item.text = t.capitalize()
                        novos_elementos.append(item)
                    continue

                # Normalização de Texto
                if el == "contributor" and qu in ["advisor", "author", "advisorco"]:
                    elem.text = aplicar_regra_caracteres(txt)
                elif el == "title":
                    elem.text = dados_sinc['titulo']
                
                # Citação complexa
                elif el == "identifier" or qu == "citation":
                    if qu == "citation":
                        partes = txt.split('.')
                        if len(partes) > 2:
                            autor_cit = ajustar_autor_citacao(dados_sinc['autor'])
                            titulo_cit = dados_sinc['titulo']
                            txt = f"{autor_cit}. {titulo_cit}. " + ".".join(partes[2:])
                    
                    curso = dados_sinc['curso_limpo'] if dados_sinc['curso_limpo'] else "Não Informado"
                    prefixo = "Doutorado em" if dados_sinc['tipo_doc'] == "doctoralThesis" else "Mestrado em"
                    titulacao_completa = f"{prefixo} {curso}"
                    txt = re.sub(r'\((.*?)\)', f"({titulacao_completa})", txt)
                    txt = re.sub(r'(\d+)f\.', r'\1 f.', txt)
                    txt = txt.replace("Universidade De Brasília, Universidade de Brasília", "— Universidade de Brasília")
                    elem.text = txt

                # PPG
                elif (el == "description" and qu == "ppg") or (el == "publisher" and qu == "program"):
                    elem.set("element", "description")
                    elem.set("qualifier", "ppg")
                    curso_ppg = dados_sinc['curso_limpo'] if dados_sinc['curso_limpo'] else aplicar_regra_caracteres(txt)
                    elem.text = f"Programa de Pós-Graduação em {curso_ppg}"

                # Outros metadados
                elif qu == "resumo": elem.set("qualifier", "abstract")
                elif qu == "abstract": elem.set("qualifier", "abstract1")
                elif el == "date" and qu == "issued": elem.set("qualifier", "submitted")
                elif el == "type": elem.text = "Tese" if "doctoral" in txt else "Dissertação"
                elif el == "rights" and qu == "license": elem.text = TEXTO_LICENCA

                novos_elementos.append(elem)

            except:
                novos_elementos.append(elem)

        # 5. Metadados Obrigatórios
        data_f = ET.Element("dcvalue", element="date", qualifier="issued")
        data_f.text = datetime.now().strftime("%Y-%m-%d")
        novos_elementos.append(data_f)

        obrigatorios = {('rights', 'license'): TEXTO_LICENCA, ('language', 'iso'): "por"}
        atuais = [(e.get("element"), e.get("qualifier")) for e in novos_elementos]
        for (el, qu), val in obrigatorios.items():
            if (el, qu) not in atuais:
                novo = ET.Element("dcvalue", element=el, qualifier=qu)
                if el != 'date': novo.set("language", "pt_BR")
                novo.text = val
                novos_elementos.append(novo)

        # 6. Gravação (Sobrescreve o arquivo com segurança)
        root.clear()
        root.set("schema", "dc")
        for el in novos_elementos: root.append(el)
        
        # Adiciona marca d'água oculta para sabermos que funcionou
        root.set("app_version", "v3.0_fixed")
        
        tree.write(caminho_arquivo, encoding="utf-8", xml_declaration=True)
        return True

    except Exception as e:
        print(f"❌ ERRO NO MOTOR: {e}")
        return False

# Bloco vazio para evitar execução automática na importação
if __name__ == "__main__":
    pass