import os
import xml.etree.ElementTree as ET

def modificar_xml(caminho_arquivo):
    print(f"✅ Tentando modificar: {caminho_arquivo}")

    try:
        tree = ET.parse(caminho_arquivo)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"❌ ERRO: Não foi possível ler o XML {caminho_arquivo}: {e}")
        return

    # Alterações solicitadas
    alteracoes = {
        "resumo": "abstract",
        "abstract": "abstract1",
        "subject": "keyword",
        "issued": "submitted"
    }

    alterado = False  # Flag para verificar se houve alteração

    # Percorrer os elementos e modificar os qualificadores conforme necessário
    for elem in root.findall("dcvalue"):
        qualifier = elem.get("qualifier")
        if qualifier in alteracoes:
            print(f"🔄 Alterando '{qualifier}' para '{alteracoes[qualifier]}'")
            elem.set("qualifier", alteracoes[qualifier])
            alterado = True

    # Salvar o arquivo modificado apenas se houve alteração
    if alterado:
        try:
            tree.write(caminho_arquivo, encoding="utf-8", xml_declaration=True)
            print(f"💾 Arquivo modificado e salvo: {caminho_arquivo}\n")
        except Exception as e:
            print(f"❌ ERRO ao salvar o arquivo {caminho_arquivo}: {e}")
    else:
        print(f"🔹 Nenhuma alteração necessária: {caminho_arquivo}\n")

def processar_pasta(diretorio):
    print(f"\n📂 Verificando diretório principal e subpastas: {diretorio}")

    if not os.path.exists(diretorio):
        print(f"❌ ERRO: A pasta '{diretorio}' não existe!\n")
        return

    arquivos_encontrados = False

    # Percorrer todas as subpastas
    for pasta_atual, subpastas, arquivos in os.walk(diretorio):
        print(f"📂 Verificando subpasta: {pasta_atual}")

        for arquivo in arquivos:
            if arquivo == "dublin_core.xml":  # Confirma se é o arquivo correto
                caminho_completo = os.path.join(pasta_atual, arquivo)
                arquivos_encontrados = True
                modificar_xml(caminho_completo)

    if not arquivos_encontrados:
        print(f"⚠️ Nenhum arquivo 'dublin_core.xml' encontrado em {diretorio} ou subpastas.\n")

# Defina o caminho da pasta principal onde os arquivos XML estão
caminho_da_pasta = "/Users/leonardorcarvalho/Downloads/Teste2/PROGRAMA_DE_POS-GRADUACAO_EM_CIENCIAS_BIOLOGICAS_(BIOLOGIA_MOLECULAR)"

# Executar o script
processar_pasta(caminho_da_pasta)

