import pandas as pd

# Carregar o arquivo original
df = pd.read_csv('LISTAORIENTADOR-PPG.csv')

# 1. Remover linhas com valores ausentes
df_cleaned = df.dropna().copy()

# 2. Limpar espaços em branco extras (strip)
df_cleaned['dc.contributor.advisor[pt_BR]'] = df_cleaned['dc.contributor.advisor[pt_BR]'].str.strip()
df_cleaned['dc.description.ppg[pt_BR]'] = df_cleaned['dc.description.ppg[pt_BR]'].str.strip()

# 3. Remover duplicatas (gerar lista única de Orientador por PPG)
df_cleaned = df_cleaned.drop_duplicates()

# 4. Ordenar por nome do orientador
df_cleaned = df_cleaned.sort_values(by=['dc.contributor.advisor[pt_BR]', 'dc.description.ppg[pt_BR]'])

# Salvar o resultado
df_cleaned.to_csv('LISTAORIENTADOR-PPG_LIMPO.csv', index=False, encoding='utf-8')

print(f"Limpeza concluída! Linhas originais: {len(df)} | Linhas após limpeza: {len(df_cleaned)}")