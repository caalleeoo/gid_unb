#!/usr/bin/env python3
import FreeSimpleGUI as sg
import os
import shutil
import sys
import threading
import queue
import time
from datetime import datetime
import motor_unb as core

# --- FUNÇÕES UTILITÁRIAS ---

def log_central(mensagem, q=None, tipo="INFO"):
    """Gera log em arquivo e envia para a fila da interface gráfica."""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    path_log = os.path.join(base_path, "LOG_PRO_UNB.txt")
    
    timestamp = datetime.now().strftime('%H:%M:%S')
    icone = "🔴" if tipo == "ERRO" else "✅" if tipo == "SUCESSO" else "ℹ️"
    texto_log = f"[{timestamp}] {icone} {mensagem}"
    
    try:
        with open(path_log, "a", encoding="utf-8") as f:
            f.write(texto_log + "\n")
    except:
        pass 

    if q:
        q.put(("LOG", texto_log))

def contar_total_xml(pastas):
    """Conta quantos XMLs existem para definir a barra de progresso."""
    total = 0
    for p in pastas:
        for raiz, _, arquivos in os.walk(p):
            # Ignora pastas de backup ou processamento antigo se existirem
            if "Arquivos_Processados_XML" in raiz: continue
            
            for f in arquivos:
                if f.lower() == "dublin_core.xml":
                    total += 1
    return total

def executor_pro(pastas, q, bases):
    """Função worker que roda em segundo plano."""
    q.put(("STATUS", "🔍 Analisando volume de dados..."))
    total_arquivos = contar_total_xml(pastas)
    
    if total_arquivos == 0:
        q.put(("ERRO_FATAL", "Nenhum arquivo 'dublin_core.xml' encontrado nas pastas!"))
        return

    q.put(("CONFIG_BARRA", total_arquivos))
    log_central(f"Iniciando processamento (SOBRESCREVENDO) de {total_arquivos} arquivos...", q)
    
    processados = 0
    
    for p_origem in pastas:
        if not os.path.exists(p_origem): continue
            
        # Percorre a estrutura de pastas
        for raiz, _, arquivos in os.walk(p_origem):
            # Proteção para não processar backups antigos se existirem na pasta
            if "Arquivos_Processados_XML" in raiz: continue
                
            for arq in arquivos:
                if arq.lower() == "dublin_core.xml":
                    caminho_xml = os.path.join(raiz, arq)
                    nome_pasta_pai = os.path.basename(raiz)
                    
                    try:
                        # --- MODIFICAÇÃO: Processa DIRETAMENTE o arquivo original ---
                        # O motor_unb abre, modifica e salva no mesmo caminho
                        ok, msg = core.processar_arquivo_direto(caminho_xml, bases)
                        tipo_log = "SUCESSO" if ok else "ERRO"
                        
                        log_central(f"{nome_pasta_pai}: {msg}", q, tipo_log)
                        
                    except Exception as e:
                        log_central(f"Erro crítico em {arq}: {str(e)}", q, "ERRO")
                    
                    processados += 1
                    q.put(("PROGRESSO", processados))
    
    q.put(("FINALIZADO", processados))

# --- INTERFACE GRÁFICA ---

def main():
    sg.theme('LightBlue2') # Tema limpo e profissional
    sg.set_options(font=('Segoe UI', 10))

    # Layout da Coluna Esquerda (Controles)
    coluna_esquerda = [
        [sg.Text('📁 Seleção de Pastas', font=('Segoe UI', 11, 'bold'), text_color='#004b8d')],
        [sg.Text('Escolha a pasta raiz contendo os projetos:', font=('Segoe UI', 9))],
        [sg.Input(key='-IN-', expand_x=True), sg.FolderBrowse('Buscar', button_color=('#FFFFFF', '#5c5c5c'))],
        [sg.Button('➕ Adicionar à Fila', key='ADD', size=(20, 1), button_color=('#FFFFFF', '#0078D7'))],
        
        [sg.Text('_'*40, text_color='#cccccc')], # Separador visual
        
        [sg.Text('📂 Fila de Processamento', font=('Segoe UI', 11, 'bold'), text_color='#004b8d')],
        [sg.Listbox([], size=(40, 10), key='-LISTA-', select_mode=sg.LISTBOX_SELECT_MODE_SINGLE, enable_events=True)],
        [
            sg.Button('🗑️ Remover Selecionado', key='REM', size=(20, 1), button_color=('#FFFFFF', '#D9534F'), disabled=True),
            sg.Button('🧹 Limpar Tudo', key='CLR', size=(15, 1))
        ]
    ]

    # Layout da Coluna Direita (Logs e Ação)
    coluna_direita = [
        [sg.Text('📊 Status e Logs', font=('Segoe UI', 11, 'bold'), text_color='#004b8d')],
        [sg.Text('Aguardando início...', key='-STATUS-', size=(50, 1), text_color='grey')],
        [sg.ProgressBar(100, orientation='h', size=(40, 20), key='-BARRA-', bar_color=('#4CAF50', '#DDDDDD'), expand_x=True)],
        
        [sg.Multiline(size=(60, 15), key='-LOG-', autoscroll=True, font=('Consolas', 9), background_color='#FAFAFA', disabled=True)],
        
        [sg.Column([[
            sg.Button('🚀 PROCESSAR E SUBSTITUIR', key='INICIAR', font=('Segoe UI', 12, 'bold'), button_color=('white', '#D9534F'), size=(30, 2), pad=(0, 15))
        ]], justification='center')]
    ]

    layout = [
        [sg.Text('GID UnB Automator Pro', font=('Segoe UI', 18, 'bold'), text_color='#003366'), sg.Push(), sg.Text('v2.3 (Overwrite)', text_color='grey')],
        [sg.HorizontalSeparator()],
        [sg.Column(coluna_esquerda, element_justification='l', vertical_alignment='top', expand_y=True),
         sg.VSeparator(),
         sg.Column(coluna_direita, element_justification='l', vertical_alignment='top', expand_x=True, expand_y=True)]
    ]
    
    window = sg.Window('Automação de Metadados UnB', layout, finalize=True, resizable=True, size=(900, 600))
    
    lista_pastas = []
    q = queue.Queue()

    # Variável para armazenar o total de arquivos (Cache para evitar erro no Mac)
    total_arquivos_cache = 0

    # --- CARREGAMENTO INICIAL ---
    window.perform_long_operation(lambda: core.carregar_bases_globais(getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))), '-BASES_LOADED-')
    window['-STATUS-'].update("⏳ Carregando bases de dados (Orientadores/Assuntos)...")
    window['INICIAR'].update(disabled=True) # Bloqueia botão até carregar

    bases_carregadas = {}

    # --- LOOP DE EVENTOS ---
    while True:
        event, values = window.read(timeout=100)
        
        if event in (sg.WIN_CLOSED, 'Sair'):
            break

        # Evento de retorno do carregamento das bases
        if event == '-BASES_LOADED-':
            bases_carregadas = values[event]
            window['-STATUS-'].update("✔️ Sistema pronto. Adicione pastas para começar.")
            window['INICIAR'].update(disabled=False)
            window['-LOG-'].print(f"Bases carregadas: {len(bases_carregadas.get('advisors', []))} orientadores, {len(bases_carregadas.get('keywords', []))} assuntos.")

        # Gestão da Lista
        if event == 'ADD':
            pasta = values['-IN-']
            if pasta and os.path.exists(pasta) and pasta not in lista_pastas:
                lista_pastas.append(pasta)
                window['-LISTA-'].update(lista_pastas)
                window['-IN-'].update('') # Limpa input
            elif pasta in lista_pastas:
                sg.popup_quick_message("Esta pasta já está na lista!", background_color='orange')

        if event == 'REM':
            selecao = values['-LISTA-']
            if selecao:
                lista_pastas.remove(selecao[0])
                window['-LISTA-'].update(lista_pastas)
                window['REM'].update(disabled=True)

        if event == 'CLR':
            lista_pastas = []
            window['-LISTA-'].update(lista_pastas)
            window['REM'].update(disabled=True)
        
        # Habilita botão remover apenas se algo estiver selecionado
        if event == '-LISTA-' and values['-LISTA-']:
            window['REM'].update(disabled=False)

        # Início do Processamento
        if event == 'INICIAR':
            if not lista_pastas:
                sg.popup_error("A lista de pastas está vazia!")
                continue
            
            # Aviso de segurança para sobrescrita
            if sg.popup_ok_cancel("ATENÇÃO: Este modo irá SOBRESCREVER os arquivos originais 'dublin_core.xml'.\n\nVocê tem certeza?", title="Confirmação de Sobrescrita", icon='warning') != 'OK':
                continue

            window['INICIAR'].update(disabled=True)
            window['ADD'].update(disabled=True)
            window['CLR'].update(disabled=True)
            window['REM'].update(disabled=True)
            window['-BARRA-'].update(0, max=100)
            
            threading.Thread(
                target=executor_pro, 
                args=(lista_pastas, q, bases_carregadas), 
                daemon=True
            ).start()

        # --- GESTÃO DA FILA DE MENSAGENS (THREAD) ---
        try:
            while True:
                tipo, dados = q.get_nowait()
                
                if tipo == "LOG":
                    window['-LOG-'].print(dados)
                
                elif tipo == "STATUS":
                    window['-STATUS-'].update(dados)
                
                elif tipo == "CONFIG_BARRA":
                    total_arquivos_cache = dados  # Guarda o valor na variável local
                    window['-BARRA-'].update(0, max=dados)
                
                elif tipo == "PROGRESSO":
                    window['-BARRA-'].update(dados)
                    # Atualiza texto de status usando a variável cache
                    window['-STATUS-'].update(f"Processando: {dados}/{total_arquivos_cache} arquivos...")

                elif tipo == "ERRO_FATAL":
                    sg.popup_error(dados)
                    window['INICIAR'].update(disabled=False)

                elif tipo == "FINALIZADO":
                    window['-STATUS-'].update(f"Concluído! {dados} arquivos processados.")
                    if total_arquivos_cache > 0:
                         window['-BARRA-'].update(total_arquivos_cache) 
                    
                    sg.popup(f"Sucesso! \n{dados} arquivos foram atualizados (sobrescritos).", title="Fim")
                    
                    # Reabilita interface
                    window['INICIAR'].update(disabled=False)
                    window['ADD'].update(disabled=False)
                    window['CLR'].update(disabled=False)
                
                q.task_done()
        except queue.Empty:
            pass

    window.close()

if __name__ == "__main__":
    main()