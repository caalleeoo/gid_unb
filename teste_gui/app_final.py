import FreeSimpleGUI as sg
import os
import shutil
import sys
import traceback
import subprocess 

# --- IMPORTAÇÃO SEGURA DO MOTOR ---
pasta_atual = os.path.dirname(os.path.abspath(__file__))
if pasta_atual not in sys.path: sys.path.append(pasta_atual)

try:
    import motor_unb as core
except ImportError:
    sg.popup_error("ERRO CRÍTICO: 'motor_unb.py' não encontrado na pasta!")
    sys.exit()
# -------------------------

def rodar_script_auxiliar(nome_script, pasta_alvo, window, titulo_log):
    """
    Função genérica para rodar scripts de checagem (subprocess).
    """
    caminho_script = os.path.join(pasta_atual, nome_script)
    window['-LOG-'].update(f"   ⏳ Iniciando {titulo_log}...\n", append=True)

    if os.path.exists(caminho_script):
        try:
            processo = subprocess.run(
                [sys.executable, caminho_script, pasta_alvo],
                capture_output=True,
                text=True,
                encoding='utf-8',
                cwd=pasta_atual 
            )
            # Mostra o log
            window['-LOG-'].update(f"\n📋 RELATÓRIO ({titulo_log}):\n{processo.stdout}\n", append=True)
            if processo.stderr:
                window['-LOG-'].update(f"⚠️ ERROS TÉCNICOS:\n{processo.stderr}\n", append=True)
        except Exception as e:
            window['-LOG-'].update(f"   ❌ Falha ao rodar {nome_script}: {e}\n", append=True)
    else:
         window['-LOG-'].update(f"   ❌ ERRO: Script '{nome_script}' não encontrado.\n", append=True)

def processar_uma_pasta(pasta_origem, window, contador_pasta, total_pastas):
    try:
        window['-LOG-'].update("\n" + "#" * 60 + "\n", append=True)
        window['-LOG-'].update(f" PASTA [{contador_pasta}/{total_pastas}]: {pasta_origem}\n", append=True)
        window['-LOG-'].update("#" * 60 + "\n", append=True)
        
        # 1. Cria pasta de destino
        pasta_destino = os.path.join(pasta_origem, "Arquivos_Processados_XML")
        if not os.path.exists(pasta_destino): 
            os.makedirs(pasta_destino)
            window['-LOG-'].update(f"    Pasta criada: {pasta_destino}\n", append=True)
        
        # 2. Lista XMLs
        lista_xmls = [f for f in os.listdir(pasta_origem) if f.lower().endswith('.xml')]
        
        if not lista_xmls:
            window['-LOG-'].update("    AVISO: Nenhum XML encontrado. Pulando...\n", append=True)
            return 0

        window['-LOG-'].update(f"    Processando {len(lista_xmls)} arquivos (Motor Principal)...\n", append=True)
        sucessos = 0

        # 3. ETAPA 1: MOTOR UNB (Estrutura e Limpeza)
        for i, nome_arquivo in enumerate(lista_xmls):
            origem = os.path.join(pasta_origem, nome_arquivo)
            destino = os.path.join(pasta_destino, nome_arquivo)
            window['-PROG-'].update(current_count=i+1, max=len(lista_xmls))
            
            try:
                shutil.copy2(origem, destino)
                if hasattr(core, 'processar_arquivo_direto'):
                    if core.processar_arquivo_direto(destino):
                        sucessos += 1
                        window['-LOG-'].update(".", append=True) 
                    else:
                        window['-LOG-'].update("x", append=True)
                else:
                    window['-LOG-'].update("E", append=True)
            except Exception as e:
                window['-LOG-'].update(f"\n    Erro arquivo {nome_arquivo}: {e}\n", append=True)

        window['-LOG-'].update(f"\n    Motor finalizado ({sucessos} arqs).\n", append=True)

        # 4. ETAPA 2: CHECAGEM DE ORIENTADORES
        rodar_script_auxiliar("checagem_de_base.py", pasta_destino, window, "Auditoria de Orientadores")

        # 5. ETAPA 3: CHECAGEM DE ASSUNTOS (NOVO!)
        rodar_script_auxiliar("checagem_assuntos.py", pasta_destino, window, "Auditoria de Assuntos")

        return sucessos

    except Exception as e:
        window['-LOG-'].update(f"\n ERRO GERAL NA PASTA: {e}\n", append=True)
        traceback.print_exc()
        return 0

def main():
    sg.theme('DarkBlue3')
    layout = [
        [sg.Text('Sistema Integrado UnB (3 Etapas)', font=('Helvetica', 14, 'bold'))],
        [sg.Text('1. Estrutura  ->  2. Orientadores  ->  3. Assuntos', text_color='yellow')],
        [sg.HorizontalSeparator()],
        
        [sg.Text('Selecione uma pasta:', font=('Helvetica', 10, 'bold'))],
        [sg.Input(key='-INPUT_PATH-', expand_x=True), sg.FolderBrowse('Buscar...', target='-INPUT_PATH-')],
        [sg.Button('⬇️ Adicionar à Fila', key='-ADD-', size=(20, 1), button_color=('white', '#004080')), 
         sg.Button('Limpar Fila', key='-CLEAR-', size=(15, 1))],
        
        [sg.Text('Fila de Processamento:', font=('Helvetica', 10))],
        [sg.Listbox(values=[], size=(90, 6), key='-LISTA-', enable_events=True, background_color='#FFF', text_color='#000')],
        
        [sg.HorizontalSeparator()],
        
        [sg.Text('Progresso:', font=('Helvetica', 10))],
        [sg.ProgressBar(100, orientation='h', size=(20, 20), key='-PROG-', expand_x=True)],
        [sg.Multiline(size=(90, 15), key='-LOG-', autoscroll=True, disabled=True, background_color='#1c1e23', text_color='white', font=('Consolas', 9))],
        
        [sg.Button('PROCESSAR FILA COMPLETA', key='-START-', size=(30, 2), button_color=('white', 'green')), sg.Button('Sair')]
    ]

    window = sg.Window('UnB Automator v5.1', layout)
    pastas_selecionadas = []

    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, 'Sair'): break
        
        if event == '-ADD-':
            caminho = values['-INPUT_PATH-']
            if caminho and os.path.exists(caminho):
                if caminho not in pastas_selecionadas:
                    pastas_selecionadas.append(caminho)
                    window['-LISTA-'].update(pastas_selecionadas)
                    window['-INPUT_PATH-'].update('')
                else:
                    sg.popup_error("Esta pasta já está na lista!")

        if event == '-CLEAR-':
            pastas_selecionadas = []
            window['-LISTA-'].update([])

        if event == '-START-':
            if not pastas_selecionadas:
                sg.popup_error("A fila está vazia!")
                continue
            
            window['-LOG-'].update(" INICIANDO FLUXO DE 3 ETAPAS...\n", append=True)
            total = len(pastas_selecionadas)
            
            for i, pasta in enumerate(pastas_selecionadas):
                processar_uma_pasta(pasta, window, i+1, total)
            
            sg.popup_ok(f"Processamento Concluído!")

    window.close()

if __name__ == '__main__':
    main()