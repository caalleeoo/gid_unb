import pandas as pd
from rapidfuzz import process, fuzz, utils
from unidecode import unidecode
import time
import sys

class IndexadorArtesanal:
    def __init__(self, caminho_arquivo, threshold=70):
        self.caminho_arquivo = caminho_arquivo
        self.threshold = threshold
        self.df_bruto = None
        self.df_reduzido = None
        self.relatorio = []

    def normalizar(self, texto):
        """Cria a 'impressão digital' do termo para comparação rápida."""
        if not isinstance(texto, str):
            return ""
        # Remove acentos, minúsculas, remove espaços extras
        return unidecode(texto.lower().strip())

    def carregar_e_agrupar(self):
        print("--- Fase 1: Carregamento e Compressão Inicial ---")
        try:
            # Lendo sem cabeçalho e atribuindo nomes manuais
            # Assumimos: Coluna 0 = Termo, Coluna 1 = Frequência
            self.df_bruto = pd.read_csv(
                self.caminho_arquivo, 
                header=None, 
                names=['Termo_Original', 'Frequencia'],
                dtype={'Termo_Original': str, 'Frequencia': float} # float para garantir caso venha numero quebrado
            )
            
            total_linhas = len(self.df_bruto)
            print(f"✓ Dados brutos carregados: {total_linhas} linhas.")

            # Preenchendo vazios para evitar erros
            self.df_bruto['Termo_Original'] = self.df_bruto['Termo_Original'].fillna('')
            self.df_bruto['Frequencia'] = self.df_bruto['Frequencia'].fillna(0)

            # Criando coluna normalizada
            self.df_bruto['Termo_Normalizado'] = self.df_bruto['Termo_Original'].apply(self.normalizar)

            # Agrupamento Exato: Soma frequências de termos que são iguais após normalização simples
            # Ex: "Artes", "artes ", "ARTES" viram um só registro aqui.
            self.df_reduzido = self.df_bruto.groupby('Termo_Normalizado').agg({
                'Termo_Original': 'first', # Pega a primeira grafia encontrada como representativa
                'Frequencia': 'sum'
            }).reset_index()

            novas_linhas = len(self.df_reduzido)
            reducao = total_linhas - novas_linhas
            print(f"✓ Compressão concluída. De {total_linhas} para {novas_linhas} termos únicos.")
            print(f"  (Isso significa que {reducao} erros eram apenas espaços ou maiúsculas/minúsculas)\n")

        except Exception as e:
            print(f"✗ Erro fatal no carregamento: {e}")
            sys.exit(1)

    def analisar_profundidade(self):
        print("--- Fase 2: Análise Profunda (Fuzzy Logic) ---")
        print("Buscando variações, erros de grafia e qualificadores...")
        print("Nota: Com 50k linhas, esta etapa pode demorar alguns minutos. Tenha paciência.\n")

        termos_unicos = self.df_reduzido['Termo_Normalizado'].tolist()
        mapa_termo_original = pd.Series(
            self.df_reduzido.Termo_Original.values, 
            index=self.df_reduzido.Termo_Normalizado
        ).to_dict()
        
        # Dicionário para marcar o que já foi agrupado para não repetir
        ja_processados = set()
        total = len(termos_unicos)
        
        # Otimização: rapidfuzz processa muito mais rápido se passarmos a lista toda de uma vez
        # mas precisamos iterar para formatar o relatório.
        
        for i, termo_foco in enumerate(termos_unicos):
            # Barra de progresso visual
            if i % 100 == 0:
                progresso = (i / total) * 100
                print(f"Analisando: {progresso:.1f}% concluído...", end='\r')

            if termo_foco in ja_processados:
                continue

            # Extrai os top 10 candidatos similares (limitamos para performance)
            # score_cutoff=self.threshold garante que só pegamos o que importa
            matches = process.extract(
                termo_foco, 
                termos_unicos, 
                scorer=fuzz.token_set_ratio, # O melhor para "Termo" vs "Termo qualificado"
                score_cutoff=self.threshold,
                limit=20 
            )

            # Se encontrou mais de 1 match (o primeiro é sempre ele mesmo)
            if len(matches) > 1:
                grupo_duplicatas = []
                freq_total_grupo = 0
                
                # matches retorna tuplas: (termo, score, index)
                for match in matches:
                    termo_encontrado = match[0]
                    score = match[1]
                    
                    # Recupera o termo original (com maiusculas etc) e a frequencia
                    original = mapa_termo_original.get(termo_encontrado, "Erro")
                    freq = self.df_reduzido.loc[self.df_reduzido['Termo_Normalizado'] == termo_encontrado, 'Frequencia'].values[0]
                    
                    grupo_duplicatas.append(f"{original} [Score:{score:.0f} | Freq:{int(freq)}]")
                    freq_total_grupo += freq
                    
                    # Marca como processado para não criar grupos duplicados (A=B e B=A)
                    # Nota: Isso é agressivo. Em 'false positive mode', talvez quiséssemos ver tudo,
                    # mas para 50k linhas, se não marcarmos, o relatório fica ilegível.
                    ja_processados.add(termo_encontrado)

                self.relatorio.append({
                    'Termo Principal (Representante)': mapa_termo_original[termo_foco],
                    'Variações Encontradas': " || ".join(grupo_duplicatas),
                    'Total de Variações': len(grupo_duplicatas),
                    'Frequência Somada do Grupo': int(freq_total_grupo)
                })
            else:
                # Se não tem duplicata, marcamos ele como processado
                ja_processados.add(termo_foco)

        print(f"\n\n✓ Análise finalizada. {len(self.relatorio)} grupos suspeitos identificados.")

    def salvar(self):
        if not self.relatorio:
            print("Nenhum padrão suspeito encontrado.")
            return

        df_final = pd.DataFrame(self.relatorio)
        # Ordenar pelos que têm mais variações (os casos mais graves)
        df_final = df_final.sort_values(by='Total de Variações', ascending=False)
        
        arquivo_saida = 'relatorio_analise_termos.csv'
        df_final.to_csv(arquivo_saida, index=False, sep=';', encoding='utf-8-sig')
        print(f"✓ Arquivo '{arquivo_saida}' criado com sucesso.")

if __name__ == "__main__":
    # --- CONFIGURAÇÃO ---
    ARQUIVO = 'dados.csv' # Mude para o nome do seu arquivo
    SENSIBILIDADE = 70    # 0 a 100. Quanto menor, mais "falsos positivos"
    # --------------------

    app = IndexadorArtesanal(ARQUIVO, threshold=SENSIBILIDADE)
    app.carregar_e_agrupar()
    app.analisar_profundidade()
    app.salvar()