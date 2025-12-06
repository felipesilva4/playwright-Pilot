#!/usr/bin/env python3
"""
Script para monitorar mensagens do WhatsApp e enviar automaticamente
clicando, escrevendo e apertando enter (sem enviar para Cursor)
"""

import json
import time
import os
import pyautogui
from datetime import datetime
from pathlib import Path

# Configurações
LOG_FILE = "/var/www/zap_api/storage/logs/whatsapp.log"
STATE_FILE = "/var/www/PlaywrightPilot/last_message_id.txt"
CHECK_INTERVAL = 15  # Verificar a cada 15 segundos

# Configurações do PyAutoGUI
pyautogui.PAUSE = 1  # Pausa de 1 segundo entre ações
pyautogui.FAILSAFE = True  # Mover mouse para canto superior esquerdo para parar

def read_log_file():
    """Lê o arquivo de log e retorna a última mensagem (última linha)"""
    try:
        if not os.path.exists(LOG_FILE):
            print(f"Arquivo de log não encontrado: {LOG_FILE}")
            return None
        
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if not lines:
                return None
            
            # Lê a última linha não vazia do arquivo
            for line in reversed(lines):
                line = line.strip()
                if line:
                    try:
                        message = json.loads(line)
                        # Verifica se tem os campos necessários
                        if 'id' in message and 'body' in message:
                            return message
                    except json.JSONDecodeError:
                        continue
            
            return None
    except Exception as e:
        print(f"Erro ao ler arquivo de log: {e}")
        return None

def get_last_processed_id():
    """Obtém o ID da última mensagem processada"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception as e:
        print(f"Erro ao ler arquivo de estado: {e}")
    return None

def save_last_processed_id(message_id):
    """Salva o ID da última mensagem processada"""
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            f.write(message_id)
    except Exception as e:
        print(f"Erro ao salvar arquivo de estado: {e}")

def send_message(message_body):
    """Clica, escreve a mensagem e aperta enter"""
    try:
        print(f"💬 Preparando para enviar mensagem: {message_body}")
        
        print("⏳ Aguardando...")
        time.sleep(1)
        
        # IMPORTANTE: Primeiro, garante que não está editando um arquivo
        print("🔙 Saindo de qualquer modo de edição (Escape)...")
        pyautogui.press('escape')
        time.sleep(0.5)
        
        # Pega a posição atual do mouse (onde você deixou posicionado)
        mouse_x, mouse_y = pyautogui.position()
        print(f"🖱️  Mouse está em: ({mouse_x}, {mouse_y})")
        print("🖱️  Clicando na posição do mouse...")
        
        # Clica uma vez onde o mouse está
        pyautogui.click()
        time.sleep(0.5)
        
        # Limpa qualquer texto que possa estar no campo
        print("🧹 Limpando campo de texto...")
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.3)
        
        # Digita a mensagem
        print(f"⌨️  Digitando mensagem: {message_body}")
        pyautogui.write(message_body, interval=0.05)
        time.sleep(0.5)
        
        # Pressiona Enter para enviar
        print("📤 Enviando mensagem (Enter)...")
        pyautogui.press('enter')
        time.sleep(1)
        
        print("✅ Mensagem enviada com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao enviar mensagem: {e}")
        import traceback
        traceback.print_exc()
        return False

def monitor_messages():
    """Loop principal de monitoramento"""
    print("=" * 60)
    print("🚀 MONITORAMENTO PLAYWRIGHTPILOT INICIADO")
    print("=" * 60)
    print(f"📁 Arquivo WhatsApp: {LOG_FILE}")
    print(f"⏱️  Verificando a cada {CHECK_INTERVAL} segundos")
    print("Pressione Ctrl+C para parar")
    print("=" * 60)
    
    # Carrega o último ID processado
    last_id = get_last_processed_id()
    
    if last_id:
        print(f"📝 Último ID WhatsApp processado: {last_id}")
    else:
        print("📝 Primeira execução - processando primeira mensagem encontrada")
    
    print("=" * 60)
    print()
    
    while True:
        try:
            has_new_content = False
            
            # Verifica se há nova mensagem do WhatsApp
            message = read_log_file()
            if message and 'id' in message and 'body' in message:
                message_id = message['id']
                message_body = message['body']
                
                # Verifica se é uma mensagem nova
                if last_id is None or message_id != last_id:
                    # Nova mensagem detectada
                    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✨ NOVA MENSAGEM WHATSAPP DETECTADA!")
                    print(f"ID: {message_id}")
                    print(f"Mensagem: {message_body}")
                    print("-" * 60)
                    
                    # Clica, escreve e aperta enter
                    if send_message(message_body):
                        # Salva o ID da mensagem processada APENAS se enviou com sucesso
                        save_last_processed_id(message_id)
                        last_id = message_id
                        print(f"✅ Mensagem processada e ID salvo")
                        has_new_content = True
                    else:
                        print("❌ Falha ao processar mensagem, tentando novamente na próxima verificação")
            
            # Se não houve conteúdo novo, apenas aguarda silenciosamente
            if not has_new_content:
                # Não imprime nada para manter o log limpo
                pass
            
            # Aguarda antes da próxima verificação
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Monitoramento interrompido pelo usuário")
            break
        except Exception as e:
            print(f"❌ Erro no loop de monitoramento: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    monitor_messages()

