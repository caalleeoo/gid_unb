import FreeSimpleGUI as sg
import os
import shutil
import sys
import traceback
import subprocess 
import multiprocessing
import threading

# --- LOGICA DE CAMINHOS PARA EXECUTÁVEL ---
# Garante que o App encontre os arquivos dentro do pacote descompactado pelo PyInstaller
if getattr(sys, 'frozen', False):
    pasta_raiz = sys._MEIPASS
else:
    pasta_raiz = os.path.dirname(os.path.abspath(__file__))

if pasta_raiz not in sys.path: 
    sys.path.append(pasta_raiz)

# --- IMPORTAÇÃO DO MOTOR ---
try:
    import motor_unb as core
except ImportError:
    sg.popup_error("ERRO CRÍTICO: 'motor_unb.py' não encontrado!")
    sys.exit()

def rodar_script_auxiliar(nome_script, pasta_alvo, window, titulo_log):
    """Executa auditorias externas sem abrir novas janelas do App."""
    caminho_script = os.path.join(pasta_raiz, nome_script)
    window['-LOG-'].update(f"   ⏳ Iniciando {titulo_log}...\n", append=True)

    if os.path.exists(caminho_script):
        try:
            # O parâmetro "-u" (unbuffered) força o log a aparecer imediatamente
            # env=os.environ.copy() evita bloqueios de segurança do macOS
            processo = subprocess.run(
                [sys.executable, "-u", caminho_script, pasta_alvo],
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=os.environ.copy()
            )
            
            if processo.stdout:
                window['-LOG-'].update(f"\n📋 RELATÓRIO ({titulo_log}):\n{processo.stdout}\n", append=True)
            if processo.stderr:
                window['-LOG-'].update(f"⚠️ LOG INTERNO:\n{processo.stderr}\n", append=True)
        except Exception as e:
            window['-LOG-'].update(f"   ❌ Falha ao rodar {nome_script}: {e}\n", append=True)
    else:
         window['-LOG-'].update(f"   ❌ ERRO: Script não encontrado: {nome_script}\n", append=True)

def executor_principal(pastas, window):
    """Roda o processamento em Thread para não travar a interface do Mac."""
    total_pastas = len(pastas)
    for idx, pasta_origem in enumerate(pastas):
        try:
            window['-LOG-'].update("\n" + "#" * 60 + "\n", append=True)
            window['-LOG-'].update(f"📂 PASTA [{idx+1}/{total_pastas}]: {pasta_origem}\n", append=True)
            window['-LOG-'].update("#" * 60 + "\n", append=True)
            
            pasta_destino = os.path.join(pasta_origem, "Arquivos_Processados_XML")
            if not os.path.exists(pasta_destino): 
                os.makedirs(pasta_destino)
                window['-LOG-'].update(f"   📁 Pasta criada: {pasta_destino}\n", append=True)
            
            lista_xmls = [f for f in os.listdir(pasta_origem) if f.lower().endswith('.xml')]
            if not lista_xmls:
                window['-LOG-'].update("   ⚠️ AVISO: Nenhum XML encontrado. Pulando...\n", append=True)
                continue

            window['-LOG-'].update(f"   🚀 Processando {len(lista_xmls)} arquivos (Motor Principal)...\n", append=True)
            sucessos = 0

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
                except Exception as e:
                    window['-LOG-'].update(f"\n   ❌ Erro em {nome_arquivo}: {e}\n", append=True)

            window['-LOG-'].update(f"\n   ✅ Motor finalizado.\n", append=True)
            
            # Chama as auditorias de forma assíncrona
            rodar_script_auxiliar("checagem_de_base.py", pasta_destino, window, "Auditoria de Orientadores")
            rodar_script_auxiliar("checagem_assuntos.py", pasta_destino, window, "Auditoria de Assuntos")

        except Exception as e:
            window['-LOG-'].update(f"\n ❌ ERRO GERAL NA PASTA: {e}\n", append=True)
    
    window['-START-'].update(disabled=False)
    sg.popup_ok("Processamento Concluído!")

def main():
    # Vital para o PyInstaller não abrir múltiplas janelas
    multiprocessing.freeze_support() 
    
    sg.theme('DarkBlue3')
    layout = [
        [sg.Text('Sistema Integrado UnB (v5.3)', font=('Helvetica', 14, 'bold'))],
        [sg.Text('1. Estrutura -> 2. Orientadores -> 3. Assuntos', text_color='yellow')],
        [sg.HorizontalSeparator()],
        [sg.Text('Selecione uma pasta:', font=('Helvetica', 10, 'bold'))],
        [sg.Input(key='-INPUT_PATH-', expand_x=True), sg.FolderBrowse('Buscar...')],
        [sg.Button('⬇️ Adicionar à Fila', key='-ADD-', size=(20, 1), button_color=('white', '#004080')), 
         sg.Button('Limpar Fila', key='-CLEAR-', size=(15, 1))],
        [sg.Listbox(values=[], size=(90, 6), key='-LISTA-', background_color='#FFF', text_color='#000')],
        [sg.HorizontalSeparator()],
        [sg.ProgressBar(100, orientation='h', size=(20, 20), key='-PROG-', expand_x=True)],
        [sg.Multiline(size=(90, 15), key='-LOG-', autoscroll=True, disabled=True, background_color='#1c1e23', text_color='white', font=('Consolas', 9))],
        [sg.Button('PROCESSAR FILA COMPLETA', key='-START-', size=(30, 2), button_color=('white', 'green')), sg.Button('Sair')]
    ]

    window = sg.Window('UnB Automator v5.3', layout)
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

        if event == '-CLEAR-':
            pastas_selecionadas = []
            window['-LISTA-'].update([])

        if event == '-START-':
            if not pastas_selecionadas:
                sg.popup_error("A fila está vazia!")
                continue
            
            window['-START-'].update(disabled=True)
            window['-LOG-'].update("🚀 INICIANDO FLUXO (THREAD MODE)...\n", append=True)
            
            # Executa em segundo plano para não travar a janela
            thread = threading.Thread(target=executor_principal, args=(pastas_selecionadas, window), daemon=True)
            thread.start()

    window.close()

if __name__ == '__main__':
    main()