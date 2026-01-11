import sys
import time

# --- VERIFICAÇÃO DE BIBLIOTECAS ---
try:
    import pandas as pd
    from fuzzywuzzy import fuzz
    from fuzzywuzzy import process
except ImportError as e:
    print("\nERRO: Falta uma biblioteca necessária.")
    print("Por favor, instale rodando: python3 -m pip install pandas fuzzywuzzy python-Levenshtein")
    sys.exit()

# --- CONFIGURAÇÕES ---
LIMITE_SIMILARIDADE = 90  # Ajustado para 90% para capturar pequenas variações

def pontuacao_gramatical(nome):
    """Critério de desempate para o nome oficial."""
    pontos = 0
    nome_str = str(nome)
    
    # Prefere nomes formatados como Título (Ex: Ana Silva)
    if nome_str.istitle():
        pontos += 2
    # Penaliza TUDO MAIÚSCULO ou tudo minúsculo
    if not nome_str.isupper() and not nome_str.islower():
        pontos += 1
    
    return (pontos, len(nome_str))

def barra_progresso(atual, total, tamanho=30):
    percentual = float(atual) / total if total > 0 else 1
    setas = '-' * int(round(percentual * tamanho) - 1) + '>'
    espacos = ' ' * (tamanho - len(setas))
    sys.stdout.write(f"\rProgresso: [{setas}{espacos}] {int(percentual * 100)}%")
    sys.stdout.flush()

def processar_nomes_v4(caminho_arquivo):
    print(f"\n--- Iniciando Análise Otimizada: {caminho_arquivo} ---")
    
    # 1. Carregamento e Limpeza Inicial
    try:
        df = pd.read_csv(caminho_arquivo, header=None, names=['nome', 'frequencia'])
        
        # Converte frequência para números e nomes para texto limpo
        df['frequencia'] = pd.to_numeric(df['frequencia'], errors='coerce').fillna(0).astype(int)
        df['nome'] = df['nome'].astype(str).str.strip() # Remove espaços invisíveis nas pontas
        
        qtd_inicial = len(df)
        print(f"Linhas carregadas: {qtd_inicial}")

        # --- PRÉ-AGREGAÇÃO ---
        # Soma as frequências de nomes EXATAMENTE iguais antes de começar o Fuzzy
        print("Etapa 0/3: Unificando duplicatas exatas...")
        df_agrupado = df.groupby('nome', as_index=False)['frequencia'].sum()
        
        dados = df_agrupado.to_dict('records')
        print(f"Nomes únicos exatos: {len(dados)} (Redução de {qtd_inicial - len(dados)} linhas)")
        
    except FileNotFoundError:
        print("ERRO: Arquivo não encontrado.")
        return
    except Exception as e:
        print(f"ERRO Crítico: {e}")
        return

    # Preparação para filtragem
    dados_filtrados = []
    # Cria uma lista auxiliar só com nomes para o 'process.extractOne' usar
    nomes_apenas = [d['nome'] for d in dados]
    total = len(dados)
    
    # 2. Filtragem Inteligente
    print("\nEtapa 1/3: Filtrando ruído (nomes únicos sem similares)...")
    
    for i, item in enumerate(dados):
        if i % 5 == 0: barra_progresso(i+1, total) # Atualiza a barra a cada 5 itens
        
        if item['frequencia'] > 1:
            dados_filtrados.append(item)
        else:
            # Item tem frequência 1. Vamos ver se ele parece com ALGUÉM.
            # Removemos o próprio item da busca
            lista_busca = nomes_apenas[:i] + nomes_apenas[i+1:]
            
            if not lista_busca:
                continue

            # WRatio combina várias estratégias
            melhor_match = process.extractOne(item['nome'], lista_busca, scorer=fuzz.WRatio)
            
            # --- CORREÇÃO AQUI ---
            if melhor_match and melhor_match[1] >= LIMITE_SIMILARIDADE:
                dados_filtrados.append(item)
            else:
                pass # Exclui

    print(f"\nNomes mantidos para análise: {len(dados_filtrados)}")
    
    # 3. Agrupamento (Clustering)
    print("\nEtapa 2/3: Agrupando por similaridade fuzzy...")
    
    # Ordena: Maiores frequências primeiro (serão os líderes dos grupos)
    dados_filtrados.sort(key=lambda x: x['frequencia'], reverse=True)
    
    grupos = []
    visitados = set()
    total_filtrados = len(dados_filtrados)
    
    for i, item_principal in enumerate(dados_filtrados):
        if i % 10 == 0: barra_progresso(i+1, total_filtrados)

        nome_principal = item_principal['nome']
        
        if nome_principal in visitados:
            continue
            
        grupo_atual = {'membros': []}
        
        # Adiciona o líder ao grupo
        item_principal['score_fuzzy'] = 100
        grupo_atual['membros'].append(item_principal)
        visitados.add(nome_principal)
        
        # Busca membros similares na lista restante
        for item_comparacao in dados_filtrados:
            nome_comparacao = item_comparacao['nome']
            
            if nome_comparacao in visitados:
                continue
            
            # Usa WRatio aqui também para consistência
            score = fuzz.WRatio(nome_principal, nome_comparacao)
            
            if score >= LIMITE_SIMILARIDADE:
                item_comparacao['score_fuzzy'] = score
                grupo_atual['membros'].append(item_comparacao)
                visitados.add(nome_comparacao)
        
        grupos.append(grupo_atual)

    # 4. Relatório Final
    print("\n\nEtapa 3/3: Gerando CSV final...")
    resultado_final = []
    
    for grupo in grupos:
        membros = grupo['membros']
        
        # Escolhe o oficial: maior frequência, depois melhor gramática
        oficial = max(membros, key=lambda x: (x['frequencia'], pontuacao_gramatical(x['nome'])))
        
        # Cálculo da certeza média
        scores = [m['score_fuzzy'] for m in membros]
        certeza = sum(scores) / len(scores)
        
        # Formata a lista de 'parentes' encontrados
        lista_str = " | ".join([f"{m['nome']} (Freq:{m['frequencia']}, Sim:{m['score_fuzzy']}%)" for m in membros])
        
        resultado_final.append({
            'Nome Escolhido': oficial['nome'],
            'Certeza (%)': f"{certeza:.1f}",
            'Frequencia Final': oficial['frequencia'], # Frequência do termo oficial
            'Nomes Agrupados': lista_str
        })
    
    # Salva o arquivo
    df_resultado = pd.DataFrame(resultado_final)
    # Ordena resultado final alfabeticamente
    df_resultado.sort_values('Nome Escolhido', inplace=True)
    
    nome_saida = "resultado_deduplicado_final.csv"
    df_resultado.to_csv(nome_saida, index=False, encoding='utf-8-sig', sep=';')
    
    print(f"Concluído! Resultado salvo em: {nome_saida}")

# --- EXECUÇÃO ---
if __name__ == "__main__":
    if len(sys.argv) > 1:
        caminho = sys.argv[1]
    else:
        caminho = input("Digite o caminho do csv (ex: nomes.csv): ").strip().strip('"')
    processar_nomes_v4(caminho)