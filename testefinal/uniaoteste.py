import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime

# --- CONFIGURAÇÕES ---
__version__ = "0.2.0"
CAMINHO_MAC = '/Users/leonardorcarvalho/Library/CloudStorage/OneDrive-Pessoal/Documentos/GitHub/ts-para-alteracao'

# Siglas e nomes próprios protegidos
PRESERVAR = ['UnB', 'IBICT', 'Brasília', 'Distrito Federal', 'Brasil', 'PMDF', 'DF', 'Mestrado', 'Doutorado', 'MEC', 'CAPES', 'MDF', 'PP', 'PEAD']

TEXTO_LICENCA = (
    "A concessão da licença deste item refere-se ao termo de autorização impresso assinado pelo autor com as seguintes condições: "
    "Na qualidade de titular dos direitos de autor da publicação, autorizo a Universidade de Brasília e o IBICT a disponibilizar "
    "por meio dos sites www.unb.br, www.ibict.br, www.ndltd.org sem ressarcimento dos direitos autorais, de acordo com a Lei nº 9610/98, "
    "o texto integral da obra supracitada, conforme permissões assinaladas, para fins de leitura, impressão e/ou download, "
    "a título de divulgação da produção científica brasileira, a partir desta data."
)

def aplicar_regra_caracteres(texto):
    """Regra: até 3 caracteres = minúsculo (xxx). Mais de 3 = Capitalizado (Xxxxx)."""
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
    """Sentence Case padrão para Títulos."""
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
    """Extrai o nome do curso de dentro dos parênteses, removendo prefixos de titulação."""
    match = re.search(r'\((.*?)\)', texto_citacao)
    if match:
        conteudo = match.group(1)
        # Remove "Mestrado em" ou "Doutorado em" se já existirem na origem para isolar o curso
        limpo = re.sub(r'^(Mestrado|Doutorado)\s+em\s+', '', conteudo, flags=re.IGNORECASE)
        return aplicar_regra_caracteres(limpo)
    return None

def ajustar_autor_citacao(autor_tratado):
    if ',' not in autor_tratado: return autor_tratado.upper()
    sobrenome, resto = autor_tratado.split(',', 1)
    return f"{sobrenome.upper()},{resto}"

def processar_xml(caminho_arquivo):
    try:
        tree = ET.parse(caminho_arquivo)
        root = tree.getroot()
        
        # Dicionário de sincronização
        dados_sinc = {'autor': '', 'titulo': '', 'curso_limpo': '', 'tipo_doc': ''}
        elementos_originais = root.findall("dcvalue")
        novos_elementos = []

        # PASSO 1: Coleta e análise prévia
        for elem in elementos_originais:
            el, qu = elem.get("element"), elem.get("qualifier")
            txt = elem.text if elem.text else ""
            if el == "contributor" and qu == "author":
                dados_sinc['autor'] = aplicar_regra_caracteres(txt)
            elif el == "title":
                t_base = tratar_texto_com_preservacao(txt)
                dados_sinc['titulo'] = re.sub(r'\s*:\s*', ' : ', t_base)
            elif el == "type":
                dados_sinc['tipo_doc'] = txt # masterThesis ou doctoralThesis
            elif qu == "citation":
                dados_sinc['curso_limpo'] = extrair_apenas_nome_curso(txt)

        # PASSO 2: Transformação Geral
        for elem in elementos_originais:
            el, qu = elem.get("element"), elem.get("qualifier")
            txt = elem.text if elem.text else ""
            lang = elem.get("language")

            try:
                # Unificação de Co-orientadores
                if el == "contributor" and qu and qu.startswith("advisor-co"):
                    elem.set("qualifier", "advisorco")
                    qu = "advisorco"

                # Exclusões
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

                # Sincronização de Autor e Título
                if el == "contributor" and qu in ["advisor", "author", "advisorco"]:
                    elem.text = aplicar_regra_caracteres(txt)
                elif el == "title":
                    elem.text = dados_sinc['titulo']

                # Citação e Identificadores (Regra de Titulação Cruzada)
                elif el == "identifier" or qu == "citation":
                    if qu == "citation":
                        partes = txt.split('.')
                        if len(partes) > 2:
                            autor_cit = ajustar_autor_citacao(dados_sinc['autor'])
                            titulo_cit = dados_sinc['titulo']
                            txt = f"{autor_cit}. {titulo_cit}. " + ".".join(partes[2:])
                    
                    # Trata o curso dentro dos parênteses na citação
                    curso = dados_sinc['curso_limpo'] if dados_sinc['curso_limpo'] else "Não Informado"
                    prefixo = "Mestrado em" if dados_sinc['tipo_doc'] == "masterThesis" else "Doutorado em"
                    titulacao_completa = f"{prefixo} {curso}"
                    
                    # Substitui o conteúdo dos parênteses pelo padrão: (Mestrado em Nome do Curso)
                    txt = re.sub(r'\((.*?)\)', f"({titulacao_completa})", txt)
                    
                    # Correções de texto e espaços padrão UnB
                    txt = re.sub(r'(\d+)f\.', r'\1 f.', txt)
                    txt = txt.replace("Universidade De Brasília, Universidade de Brasília", "— Universidade de Brasília")
                    txt = txt.replace("- — Universidade de Brasília, Brasília", "— Universidade de Brasília, Brasília")
                    elem.text = txt

                # PPG (Apenas nome do curso, sem o prefixo da titulação)
                elif (el == "description" and qu == "ppg") or (el == "publisher" and qu == "program"):
                    elem.set("element", "description")
                    elem.set("qualifier", "ppg")
                    curso_ppg = dados_sinc['curso_limpo'] if dados_sinc['curso_limpo'] else aplicar_regra_caracteres(txt)
                    elem.text = f"Programa de Pós-Graduação em {curso_ppg}"
                
                # Mapeamentos e Licença
                elif qu == "resumo": elem.set("qualifier", "abstract")
                elif qu == "abstract": elem.set("qualifier", "abstract1")
                elif el == "date" and qu == "issued": elem.set("qualifier", "submitted")
                elif el == "type": elem.text = {"masterThesis": "Dissertação", "doctoralThesis": "Tese"}.get(txt, txt)
                elif el == "rights" and qu == "license": elem.text = TEXTO_LICENCA

                novos_elementos.append(elem)

            except Exception as e_inner:
                print(f"⚠️ Pulo no metadado {el}.{qu}: {e_inner}")
                novos_elementos.append(elem)

        # PASSO 3: Metadados Obrigatórios e Data Final
        data_f = ET.Element("dcvalue", element="date", qualifier="issued")
        data_f.text = datetime.now().strftime("%Y-%m-%d")
        novos_elementos.append(data_f)

        obrigatorios = {('rights', 'license'): TEXTO_LICENCA, ('language', 'iso'): "por", ('description', 'unidade'): ""}
        atuais = [(e.get("element"), e.get("qualifier")) for e in novos_elementos]
        for (el, qu), val in obrigatorios.items():
            if (el, qu) not in atuais:
                novo = ET.Element("dcvalue", element=el, qualifier=qu)
                if el != 'date': novo.set("language", "pt_BR")
                novo.text = val
                novos_elementos.append(novo)

        # Gravação final
        root.clear()
        for el in novos_elementos: root.append(el)
        tree.write(caminho_arquivo, encoding="utf-8", xml_declaration=True)
        print(f"✅ Organizado: {os.path.basename(caminho_arquivo)}")

    except Exception as e:
        print(f"❌ Erro crítico em {caminho_arquivo}: {e}")

def iniciar():
    if not os.path.exists(CAMINHO_MAC):
        print(f"❌ Pasta não encontrada: {CAMINHO_MAC}")
        return
    for raiz, _, arquivos in os.walk(CAMINHO_MAC):
        for arquivo in arquivos:
            if arquivo == "dublin_core.xml":
                processar_xml(os.path.join(raiz, arquivo))

if __name__ == "__main__":
    iniciar()