Considerando
gid_unb/
│
├── data/                    # O ARMAZÉM
│   ├── raw/                 # Dados brutos (Somente Leitura - ex: dados originais do Scopus)
│   ├── processed/           # O Produto Final (ex: relatorios limpos e analisados)
│   └── temp/                # Arquivos temporários e descartáveis
│
├── src/                     # A OFICINA (Código Fonte)
│   ├── __init__.py          # Transforma a pasta num pacote importável
│   ├── harvesters/          # Os Coletores (Scripts que buscam dados externos)
│   ├── processors/          # Os Artesãos (Scripts de limpeza, deduplicação e análise)
│   └── utils/               # Caixa de Ferramentas (Funções auxiliares genéricas)
│
├── playground/              # O LABORATÓRIO
│   ├── _archived/           # O Museu (Scripts antigos/backups)
│   └── experiments/         # A Bancada (Testes de conceitos, rascunhos)
│
├── main.py                  # O MAESTRO (Ponto de entrada único da aplicação)
├── .gitignore               # O SEGURANÇA (Define o que não vai para o Git)
├── README.md                # O MANUAL (Instruções gerais)
└── requirements.txt         # A RECEITA (Lista de bibliotecas necessárias)