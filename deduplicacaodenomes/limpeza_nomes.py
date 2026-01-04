import pandas as pd
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import sys

# --- CONFIGURAÇÕES ---
LIMITE_SIMILARIDADE = 93  # Porcentagem mínima para considerar similar

def pontuacao_gramatical(nome):
    """
    Atribui uma pontuação baseada na 'qualidade' da escrita do nome.
    Critérios (desempate):
    1. Está em formato de Título (Ex: Joao Silva)? (+2 pontos)
    2. Não é tudo maiúscula nem minúscula? (+1 ponto)
    3. Comprimento do nome (nomes mais longos tendem a ser menos abreviados).
    """
    pontos = 0
    nome_str = str(nome)
    
    if nome_str.istitle():
        pontos += 2
    if not nome_str.isupper() and not nome_str.islower():
        pontos += 1
    
    # Retorna uma tupla: (pontos, tamanho) para usar no desempate
    return (pontos, len(nome_str))

def processar_nomes_abnt(caminho_arquivo):
    print("--- Iniciando Processamento ---")
    
    # 1. Carregamento do CSV
    try:
        # Lê o CSV sem cabeçalho (header=None), assumindo col 0=Nome, col 1=Frequência
        df = pd.read_csv(caminho_arquivo, header=None, names=['nome', 'frequencia'])
        # Garante que frequencia é número e preenche vazios com 0
        df['frequencia'] = pd.to_numeric(df['frequencia'], errors='coerce').fillna(0).astype(int)
        df['nome'] = df['nome'].astype(str)
        print(f"Total de nomes carregados: {len(df)}")
    except Exception as e:
        print(f"Erro ao ler o arquivo: {e}")
        return

    # Lista de dicionários para facilitar a iteração
    dados = df.to_dict('records')
    
    # 2. Filtragem: Remover Frequência 1 sem similares
    # Isso pode ser demorado se a lista for muito grande (milhares de nomes)
    print("Etapa 1/3: Filtrando nomes únicos sem similaridade (isso pode demorar um pouco)...")
    dados_filtrados = []
    nomes_apenas = [d['nome'] for d in dados]
    
    total = len(dados)
    for i, item in enumerate(dados):
        if i % 100 == 0:
            print(f"Verificando item {i}/{total}...", end='\r')
            
        if item['frequencia'] > 1:
            dados_filtrados.append(item)
        else:
            # Se frequencia é 1, verifica se existe ALGUÉM similar na lista inteira (exceto ele mesmo)
            # Usamos extractOne para achar o melhor match
            # Removemos o próprio nome da lista de busca temporariamente ou ignoramos match exato de indice
            melhor_match = process.extractOne(item['nome'], nomes_apenas[:i] + nomes_apenas[i+1:], scorer=fuzz.token_sort_ratio)
            
            if melhor_match and melhor_match[1] >= LIMITE_SIMILARIDADE:
                dados_filtrados.append(item)
            else:
                # Exclui (não adiciona à lista filtrada)
                pass
    
    print(f"\nNomes restantes após filtro: {len(dados_filtrados)}")

    # 3. Agrupamento e Definição do Nome Oficial
    print("Etapa 2/3: Agrupando nomes similares...")
    
    # Ordena por frequência decrescente. Isso ajuda a eleger o nome mais comum como "centro" do grupo.
    dados_filtrados.sort(key=lambda x: x['frequencia'], reverse=True)
    
    grupos = []
    visitados = set() # Para não processar o mesmo nome duas vezes
    
    for item_principal in dados_filtrados:
        nome_principal = item_principal['nome']
        
        if nome_principal in visitados:
            continue
            
        # Cria um novo grupo começando com este nome
        grupo_atual = {
            'membros': [],
            'freq_total': 0
        }
        
        # Adiciona o próprio item ao grupo
        # Calculamos a similaridade dele com ele mesmo (100) para registro
        item_principal['score_fuzzy'] = 100
        grupo_atual['membros'].append(item_principal)
        visitados.add(nome_principal)
        
        # Procura outros membros para este grupo nos dados restantes
        # Nota: Iterar sobre a lista filtrada novamente
        for item_comparacao in dados_filtrados:
            nome_comparacao = item_comparacao['nome']
            
            if nome_comparacao in visitados:
                continue
            
            # Compara
            score = fuzz.token_sort_ratio(nome_principal, nome_comparacao)
            
            if score >= LIMITE_SIMILARIDADE:
                item_comparacao['score_fuzzy'] = score
                grupo_atual['membros'].append(item_comparacao)
                visitados.add(nome_comparacao)
        
        grupos.append(grupo_atual)

    # 4. Consolidando Resultados
    print("Etapa 3/3: Gerando relatório final...")
    resultado_final = []
    
    for grupo in grupos:
        membros = grupo['membros']
        
        # Regra de Escolha do Nome Oficial:
        # 1. Maior frequência
        # 2. Melhor gramática (Título, tamanho)
        oficial = max(membros, key=lambda x: (x['frequencia'], pontuacao_gramatical(x['nome'])))
        
        # Cálculo da porcentagem de certeza (média dos scores fuzzy do grupo em relação ao líder)
        # Se só tem 1 membro, certeza é 100%
        scores = [m['score_fuzzy'] for m in membros]
        certeza = sum(scores) / len(scores)
        
        # Cria string formatada da lista de nomes analisados
        lista_analisados_str = " | ".join([f"{m['nome']} (Freq:{m['frequencia']}, Sim:{m['score_fuzzy']}%)" for m in membros])
        
        resultado_final.append({
            'Nome Escolhido': oficial['nome'],
            'Porcentagem Certeza': f"{certeza:.1f}%",
            'Frequencia do Escolhido': oficial['frequencia'],
            'Lista de Nomes Analisados': lista_analisados_str
        })
    
    # Cria DataFrame final e salva
    df_resultado = pd.DataFrame(resultado_final)
    nome_saida = "resultado_analise_nomes.csv"
    df_resultado.to_csv(nome_saida, index=False, encoding='utf-8-sig') # utf-8-sig para abrir bem no Excel
    print(f"Concluído! Arquivo salvo como: {nome_saida}")

# --- EXECUÇÃO ---
if __name__ == "__main__":
    caminho = input("Digite o caminho do arquivo CSV (ex: nomes.csv): ").strip('"')
    processar_nomes_abnt(caminho)