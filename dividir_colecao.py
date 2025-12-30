import pandas as pd
import math
import os

# --- CONFIGURAÇÃO ---
nome_arquivo_entrada = '10482-45731.csv'  # Nome exato do seu arquivo
prefixo_saida = 'importacao_unb_parte_'   # Prefixo para os arquivos divididos
numero_de_partes = 4
# --------------------

print(f"-> Iniciando processamento de: {nome_arquivo_entrada}")

# Verificação se o arquivo existe na pasta
if not os.path.exists(nome_arquivo_entrada):
    print(f"ERRO: O arquivo '{nome_arquivo_entrada}' não foi encontrado nesta pasta.")
    exit()

# Leitura do CSV
# DSpace UnB geralmente exporta em UTF-8. Se der erro de encoding, mude para 'latin1'
# low_memory=False ajuda a carregar arquivos grandes mistos
print("-> Lendo o arquivo (isso pode levar alguns segundos)...")
try:
    df = pd.read_csv(nome_arquivo_entrada, low_memory=False)
except Exception as e:
    print("-> Tentativa com separador padrão falhou, tentando ponto e vírgula (;)...")
    try:
        df = pd.read_csv(nome_arquivo_entrada, sep=';', low_memory=False)
    except Exception as e2:
        print(f"Erro crítico ao ler o arquivo: {e2}")
        exit()

total_linhas = len(df)
print(f"-> Total de registros carregados: {total_linhas}")

# Cálculo da divisão
tamanho_parte = math.ceil(total_linhas / numero_de_partes)
print(f"-> Dividindo em {numero_de_partes} partes de aprox. {tamanho_parte} registros.")

# Divisão e Salvamento
for i in range(numero_de_partes):
    inicio = i * tamanho_parte
    fim = (i + 1) * tamanho_parte
    
    df_subset = df.iloc[inicio:fim]
    
    nome_saida = f'{prefixo_saida}{i+1}.csv'
    
    # Salva com aspas duplas (padrão CSV) para proteger os abstracts que têm quebras de linha
    df_subset.to_csv(nome_saida, index=False, quoting=1) 
    
    print(f"   [OK] {nome_saida} gerado com {len(df_subset)} linhas.")

print("\nProcesso concluído! Os 4 arquivos estão prontos para importação.")