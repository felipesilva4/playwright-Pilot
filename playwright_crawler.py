#!/usr/bin/env python3
"""
Script principal CLI para automação web com Playwright e Ollama
"""

import argparse
import sys
import time
import logging
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path
from PIL import Image

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from ollama_client import OllamaClient
from http_capture import HTTPCapture
from request_analyzer import RequestAnalyzer
from bash_generator import BashGenerator
from report_generator import ReportGenerator


class TeeLogger:
    """Logger que escreve tanto no console quanto em arquivo"""
    def __init__(self, log_file: str):
        self.log_file = log_file
        # Reescreve o arquivo a cada execução
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"=== LOG INICIADO EM {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
        self.file = open(log_file, 'a', encoding='utf-8')
    
    def write(self, message: str):
        """Escreve no console e no arquivo"""
        # Remove quebra de linha dupla
        if message.strip():
            # Escreve no arquivo e faz flush imediato
            self.file.write(message)
            self.file.flush()
            # Escreve no console
            sys.stdout.write(message)
            sys.stdout.flush()
    
    def flush(self):
        """Garante que tudo foi escrito"""
        self.file.flush()
        sys.stdout.flush()
    
    def close(self):
        """Fecha o arquivo"""
        if self.file:
            self.file.close()


def normalize_site_name(url: str) -> str:
    """Extrai e normaliza nome do site da URL"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        # Remove www. e porta
        domain = domain.replace('www.', '').split(':')[0]
        # Substitui pontos por hífens
        domain = domain.replace('.', '-')
        return domain
    except:
        return "site-desconhecido"


def extract_page_info(page) -> dict:
    """Extrai informações estruturadas da página para análise"""
    print("   [1/5] Obtendo URL e título...")
    try:
        # Verifica se página está válida antes de continuar
        try:
            current_url = page.url
            if current_url == "about:blank" or not current_url or current_url.startswith("about:"):
                print("      ⚠️  Página está em 'about:blank' - página não carregou")
                print("      ⚠️  Retornando informações mínimas")
                return {
                    "url": current_url,
                    "title": "",
                    "visible_text": "Página não carregou (about:blank)",
                    "inputs": [],
                    "buttons": [],
                    "links": [],
                    "forms": []
                }
        except Exception as e:
            print(f"      ⚠️  Erro ao verificar URL: {e}")
            return {
                "url": "unknown",
                "title": "",
                "visible_text": "Erro ao acessar página",
                "inputs": [],
                "buttons": [],
                "links": [],
                "forms": []
            }
        
        info = {
            "url": current_url,
            "title": "",
            "visible_text": "",
            "inputs": [],
            "buttons": [],
            "links": [],
            "forms": []
        }
        
        print("   [2/5] Extraindo título...")
        try:
            if page.is_closed():
                print("      ⚠️  Página foi fechada")
                return info
            info["title"] = page.title()
            print(f"      ✅ Título: {info['title'][:50]}")
        except Exception as e:
            print(f"      ⚠️  Erro ao obter título: {e}")
        
        # Extrai texto visível
        print("   [3/5] Extraindo texto visível...")
        try:
            info["visible_text"] = page.locator("body").inner_text(timeout=5000)[:2000]
            print(f"      ✅ Texto extraído ({len(info['visible_text'])} caracteres)")
        except Exception as e:
            print(f"      ⚠️  Erro ao extrair texto: {e}")
            try:
                # Fallback sem timeout
                info["visible_text"] = page.locator("body").inner_text()[:2000]
                print(f"      ✅ Texto extraído (fallback, {len(info['visible_text'])} caracteres)")
            except:
                info["visible_text"] = ""
        
        # Extrai todos os inputs
        print("   [4/5] Extraindo campos de entrada...")
        try:
            # Verifica se página ainda está aberta
            if page.is_closed():
                print("      ⚠️  Página foi fechada, pulando extração de inputs")
                return info
            
            print("      🔍 Buscando elementos input/textarea/select...")
            inputs = page.locator("input, textarea, select").all()
            print(f"      📊 Total de elementos encontrados: {len(inputs)}")
            
            for i, inp in enumerate(inputs[:20], 1):  # Limita a 20 inputs
                try:
                    if i % 3 == 0 or i == 1:  # Log mais frequente
                        print(f"      ⏳ Processando input {i}/{min(20, len(inputs))}...")
                    
                    input_info = {
                        "type": "",
                        "name": "",
                        "id": "",
                        "placeholder": "",
                        "label": ""
                    }
                    
                    # Timeout curto para cada operação
                    try:
                        input_info["type"] = inp.get_attribute("type", timeout=2000) or "text"
                    except:
                        try:
                            input_info["type"] = inp.get_attribute("type") or "text"
                        except:
                            pass
                    
                    try:
                        input_info["name"] = inp.get_attribute("name", timeout=2000) or ""
                    except:
                        try:
                            input_info["name"] = inp.get_attribute("name") or ""
                        except:
                            pass
                    
                    try:
                        input_info["id"] = inp.get_attribute("id", timeout=2000) or ""
                    except:
                        try:
                            input_info["id"] = inp.get_attribute("id") or ""
                        except:
                            pass
                    
                    try:
                        input_info["placeholder"] = inp.get_attribute("placeholder", timeout=2000) or ""
                    except:
                        try:
                            input_info["placeholder"] = inp.get_attribute("placeholder") or ""
                        except:
                            pass
                    
                    # Tenta encontrar label associado (com timeout)
                    if input_info["id"]:
                        try:
                            label_elem = page.locator(f'label[for="{input_info["id"]}"]').first
                            if label_elem.count() > 0:
                                label = label_elem.inner_text(timeout=2000)
                                input_info["label"] = label.strip()
                        except:
                            pass
                    # Se não tem label por for, procura label próximo (múltiplas estratégias)
                    if not input_info["label"]:
                        try:
                            # Tenta label antes do input
                            label_elem = inp.locator("xpath=preceding::label[1] | preceding-sibling::label[1]").first
                            if label_elem.count() > 0:
                                label = label_elem.inner_text(timeout=2000)
                                if label:
                                    input_info["label"] = label.strip()
                        except:
                            pass
                        
                        # Se ainda não tem, procura por texto visível próximo
                        if not input_info["label"]:
                            try:
                                # Procura texto visível próximo que pode ser um label
                                parent = inp.locator("xpath=ancestor::*[contains(@class, 'form') or contains(@class, 'field') or contains(@class, 'input') or contains(@class, 'row')][1]").first
                                if parent.count() > 0:
                                    all_text = parent.inner_text(timeout=2000)
                                    # Procura por palavras-chave comuns de labels
                                    keywords = ["nome da parte", "nome parte", "parte", "advogado", "cpf", "cnpj", "data", "autuação"]
                                    for keyword in keywords:
                                        if keyword.lower() in all_text.lower():
                                            # Tenta extrair o texto antes do input
                                            lines = all_text.split('\n')
                                            for line in lines:
                                                if keyword.lower() in line.lower() and len(line.strip()) < 50:
                                                    input_info["label"] = line.strip()
                                                    break
                                            if input_info["label"]:
                                                break
                            except:
                                pass
                    
                    info["inputs"].append(input_info)
                    if i % 5 == 0:
                        print(f"      ✅ Processados {i} inputs até agora...")
                except Exception as e:
                    print(f"      ⚠️  Erro ao processar input {i}: {type(e).__name__}: {e}")
                    # Continua mesmo com erro
                    info["inputs"].append(input_info)  # Adiciona o que conseguiu
                    continue
            
            print(f"      ✅ {len(info['inputs'])} campos processados")
        except Exception as e:
            print(f"      ❌ Erro ao extrair inputs: {e}")
            import traceback
            traceback.print_exc()
        
        # Extrai todos os botões
        print("   [5/5] Extraindo botões...")
        try:
            # Verifica se página ainda está aberta
            if page.is_closed():
                print("      ⚠️  Página foi fechada, pulando extração de botões")
                return info
            
            print("      🔍 Buscando elementos button/input[type=submit]...")
            buttons = page.locator("button, input[type='submit'], input[type='button'], a[role='button']").all()
            print(f"      📊 Total de botões encontrados: {len(buttons)}")
            
            for i, btn in enumerate(buttons[:20], 1):  # Limita a 20 botões
                try:
                    if i % 3 == 0 or i == 1:  # Log mais frequente
                        print(f"      ⏳ Processando botão {i}/{min(20, len(buttons))}...")
                    
                    button_text = ""
                    button_id = ""
                    button_class = ""
                    
                    try:
                        button_text = btn.inner_text(timeout=2000).strip()
                    except:
                        try:
                            button_text = btn.inner_text().strip()
                        except:
                            pass
                    
                    try:
                        button_id = btn.get_attribute("id", timeout=2000) or ""
                    except:
                        try:
                            button_id = btn.get_attribute("id") or ""
                        except:
                            pass
                    
                    try:
                        button_class = btn.get_attribute("class", timeout=2000) or ""
                    except:
                        try:
                            button_class = btn.get_attribute("class") or ""
                        except:
                            pass
                    
                    if button_text or button_id:
                        info["buttons"].append({
                            "text": button_text,
                            "id": button_id,
                            "class": button_class[:100]  # Limita tamanho
                        })
                    if i % 5 == 0:
                        print(f"      ✅ Processados {i} botões até agora...")
                except Exception as e:
                    print(f"      ⚠️  Erro ao processar botão {i}: {type(e).__name__}: {e}")
                    # Continua mesmo com erro
                    if button_text or button_id:
                        info["buttons"].append({
                            "text": button_text,
                            "id": button_id,
                            "class": ""
                        })
                    continue
            
            print(f"      ✅ {len(info['buttons'])} botões processados")
        except Exception as e:
            print(f"      ❌ Erro ao extrair botões: {e}")
            import traceback
            traceback.print_exc()
        
        print("   ✅ Extração de informações concluída!")
        return info
    except Exception as e:
        print(f"   ❌ Erro geral ao extrair informações da página: {e}")
        import traceback
        traceback.print_exc()
        return {"url": page.url, "title": "", "visible_text": "", "inputs": [], "buttons": [], "links": []}


class PlaywrightCrawler:
    """Orquestrador principal da automação"""
    
    def __init__(self, model: str = "aliafshar/gemma3-it-qat-tools:4b"):
        self.ollama = OllamaClient(model=model)
        self.capture = HTTPCapture()
        self.analyzer = RequestAnalyzer(self.ollama)
        self.bash_gen = BashGenerator()
        self.report_gen = ReportGenerator()
        self.max_iterations = 20  # Limite de iterações para evitar loops
        self.action_timeout = 60000  # 60 segundos (1 minuto) por ação
        self.current_state = {}  # Rastreia estado da automação
        self.results_html = None  # Armazena HTML dos resultados
    
    def _extract_value_from_goal(self, goal: str) -> str:
        """Extrai valor mencionado no objetivo (ex: nome para pesquisar, número de processo)"""
        import re
        
        # Padrões mais robustos para extrair valores
        patterns = [
            # "pesquisar pelo processo 0001333-58.2010.4.03.6000"
            r'pesquisar\s+pelo\s+processo\s+([0-9\-\.]+)',
            # "pesquisar por processo 0001333-58.2010.4.03.6000"
            r'pesquisar\s+por\s+processo\s+([0-9\-\.]+)',
            # "processo 0001333-58.2010.4.03.6000"
            r'processo\s+([0-9\-\.]+)',
            # "pesquisar por nome da parte felipe alves da silva"
            r'pesquisar\s+por\s+(?:nome\s+(?:da\s+)?parte\s+)?([a-záàâãéêíóôõúç\s]+?)(?:\s+e\s+retornar|\s+e\s+mostrar|\s*$)',
            # "pesquisar por felipe alves da silva"
            r'pesquisar\s+por\s+([a-záàâãéêíóôõúç\s]+?)(?:\s+e\s+retornar|\s+e\s+mostrar|\s*$)',
            # "nome da parte felipe alves da silva"
            r'nome\s+(?:da\s+)?parte\s+([a-záàâãéêíóôõúç\s]+?)(?:\s+e\s+retornar|\s+e\s+mostrar|\s*$)',
            # "buscar por X"
            r'buscar\s+por\s+([a-záàâãéêíóôõúç\s0-9\-\.]+?)(?:\s+e\s+retornar|\s+e\s+mostrar|\s*$)',
            # "por X e retornar"
            r'por\s+([a-záàâãéêíóôõúç\s0-9\-\.]+?)(?:\s+e\s+retornar|\s+e\s+mostrar|\s*$)',
            # Qualquer texto entre aspas
            r'["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, goal, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                # Remove palavras comuns que não são parte do valor
                value = re.sub(r'\s+(e|retornar|mostrar|os|resultados)\s*$', '', value, flags=re.IGNORECASE)
                value = value.strip()
                # Valor deve ter pelo menos 3 caracteres e não ser apenas palavras comuns
                if len(value) > 2 and value.lower() not in ['por', 'nome', 'parte', 'da', 'do', 'de']:
                    return value
        
        # Fallback: procura qualquer sequência de palavras que pareça um nome
        # Procura padrões como "palavra palavra palavra" (nomes geralmente têm 2-4 palavras)
        words = goal.split()
        for i in range(len(words) - 1):
            # Procura sequências de 2-4 palavras que podem ser nomes
            for length in [4, 3, 2]:
                if i + length <= len(words):
                    candidate = ' '.join(words[i:i+length])
                    # Verifica se não são palavras comuns
                    if not any(word.lower() in ['por', 'nome', 'parte', 'pesquisar', 'buscar', 'retornar', 'mostrar', 'e', 'os', 'resultados'] 
                              for word in candidate.split()):
                        if len(candidate) > 5:  # Nome deve ter pelo menos 6 caracteres
                            return candidate
        
        return ""
    
    def _execute_click(self, page, target: str) -> bool:
        """Tenta clicar usando seletor CSS ou XPath"""
        try:
            print(f"   🔍 Método: Seletor CSS/XPath")
            print(f"   🎯 Target: '{target}'")
            print(f"   ⏱️  Timeout: {self.action_timeout/1000}s")
            
            # Verifica se elemento existe antes de clicar
            locator = page.locator(target).first
            count = locator.count()
            print(f"   📊 Elementos encontrados: {count}")
            
            if count == 0:
                print(f"   ❌ Nenhum elemento encontrado com seletor '{target}'")
                return False
            
            print(f"   ✅ Elemento encontrado, clicando...")
            locator.click(timeout=self.action_timeout)
            print(f"   ✅ Clique executado com sucesso!")
            return True
        except PlaywrightTimeout:
            print(f"   ❌ Timeout ({self.action_timeout/1000}s) ao clicar em '{target}'")
            return False
        except Exception as e:
            print(f"   ❌ Erro ao clicar: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _click_by_text(self, page, text: str) -> bool:
        """Tenta clicar em elemento pelo texto visível"""
        try:
            print(f"   🔍 Método: Busca por texto")
            print(f"   🎯 Texto procurado: '{text}'")
            
            # Tenta encontrar botão ou link com o texto
            print(f"   🔎 Tentativa 1: Buscando button/link/input com texto exato...")
            locator = page.locator(f"button:has-text('{text}'), a:has-text('{text}'), input[value*='{text}']").first
            count = locator.count()
            print(f"   📊 Elementos encontrados: {count}")
            
            if count > 0:
                print(f"   ✅ Elemento encontrado, clicando...")
                locator.click(timeout=self.action_timeout)
                print(f"   ✅ Clique executado com sucesso!")
                return True
            
            # Tenta com texto parcial (case insensitive)
            print(f"   🔎 Tentativa 2: Buscando por texto parcial (case insensitive)...")
            locator = page.get_by_text(text, exact=False).first
            count = locator.count()
            print(f"   📊 Elementos encontrados: {count}")
            
            if count > 0:
                print(f"   ✅ Elemento encontrado, clicando...")
                locator.click(timeout=self.action_timeout)
                print(f"   ✅ Clique executado com sucesso!")
                return True
            
            print(f"   ❌ Nenhum elemento encontrado com texto '{text}'")
        except Exception as e:
            print(f"   ❌ Erro ao buscar por texto '{text}': {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    def _execute_fill(self, page, target: str, value: str) -> bool:
        """Tenta preencher campo usando seletor CSS ou XPath"""
        try:
            print(f"   🔍 Método: Seletor CSS/XPath")
            print(f"   🎯 Target: '{target}'")
            print(f"   📝 Value: '{value}'")
            print(f"   ⏱️  Timeout: {self.action_timeout/1000}s")
            
            # Se target parece ser um name ou ID (contém : ou começa com letra), tenta como atributo
            if ':' in target or (target and target[0].isalnum() and not target.startswith('#')):
                print(f"   🔎 Target parece ser name/ID, tentando como atributo...")
                # Tenta como name primeiro
                try:
                    locator = page.locator(f"input[name='{target}'], textarea[name='{target}']").first
                    count = locator.count()
                    if count > 0:
                        print(f"   ✅ Campo encontrado por name='{target}'")
                        locator.fill(value, timeout=self.action_timeout)
                        print(f"   ✅ Campo preenchido com sucesso!")
                        return True
                except:
                    pass
                # Tenta com XPath (mais flexível para IDs com :)
                try:
                    locator = page.locator(f"xpath=//input[@name='{target}'] | //textarea[@name='{target}'] | //input[@id='{target}']").first
                    count = locator.count()
                    if count > 0:
                        print(f"   ✅ Campo encontrado por XPath (name/id)")
                        locator.fill(value, timeout=self.action_timeout)
                        print(f"   ✅ Campo preenchido com sucesso!")
                        return True
                except:
                    pass
            
            # Tenta como seletor CSS normal
            try:
                locator = page.locator(target).first
                count = locator.count()
                print(f"   📊 Elementos encontrados: {count}")
                
                if count == 0:
                    print(f"   ❌ Nenhum elemento encontrado com seletor '{target}'")
                    return False
                
                print(f"   ✅ Elemento encontrado, preenchendo...")
                locator.fill(value, timeout=self.action_timeout)
                print(f"   ✅ Campo preenchido com sucesso!")
                return True
            except Exception as e:
                print(f"   ⚠️  Erro com seletor CSS: {type(e).__name__}: {e}")
                return False
        except Exception as e:
            print(f"   ❌ Erro ao preencher: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _fill_by_label(self, page, label_text: str, value: str) -> bool:
        """Tenta encontrar e preencher campo pelo label"""
        try:
            print(f"   🔍 Método: Busca por label/placeholder/name/id/texto")
            print(f"   🎯 Label procurado: '{label_text}'")
            print(f"   📝 Value: '{value}'")
            
            # Normaliza o texto para busca (remove acentos, espaços, etc)
            normalized = label_text.lower().replace(" ", "").replace("da", "").replace("de", "").replace("do", "")
            
            # Procura label com o texto (exato e parcial)
            print(f"   🔎 Tentativa 1: Buscando label com texto exato...")
            try:
                label = page.locator(f"label:has-text('{label_text}')").first
                label_count = label.count()
                print(f"   📊 Labels encontrados (exato): {label_count}")
                
                if label_count > 0:
                    # Tenta pegar o for do label
                    for_attr = label.get_attribute("for")
                    if for_attr:
                        print(f"   ✅ Label encontrado com 'for'='{for_attr}', preenchendo campo...")
                        page.fill(f"#{for_attr}", value, timeout=self.action_timeout)
                        print(f"   ✅ Campo preenchido via label 'for'")
                        return True
                    # Se não tem for, procura input próximo
                    print(f"   🔎 Label sem 'for', procurando input próximo...")
                    input_field = label.locator("xpath=following::input[1] | following::textarea[1]").first
                    if input_field.count() > 0:
                        input_field.fill(value, timeout=self.action_timeout)
                        print(f"   ✅ Campo preenchido próximo ao label")
                        return True
            except:
                pass
            
            # Tenta busca parcial no label
            print(f"   🔎 Tentativa 2: Buscando label com texto parcial...")
            try:
                # Divide o texto em palavras e busca cada uma
                words = label_text.lower().split()
                for word in words:
                    if len(word) > 2:  # Ignora palavras muito curtas
                        label = page.locator(f"label:has-text('{word}')").first
                        if label.count() > 0:
                            for_attr = label.get_attribute("for")
                            if for_attr:
                                print(f"   ✅ Label encontrado por palavra '{word}', preenchendo...")
                                page.fill(f"#{for_attr}", value, timeout=self.action_timeout)
                                print(f"   ✅ Campo preenchido")
                                return True
            except:
                pass
            
            # Tenta encontrar por placeholder
            print(f"   🔎 Tentativa 3: Buscando por placeholder...")
            try:
                input_field = page.locator(f"input[placeholder*='{label_text}'], textarea[placeholder*='{label_text}']").first
                count = input_field.count()
                print(f"   📊 Campos com placeholder encontrados: {count}")
                if count > 0:
                    input_field.fill(value, timeout=self.action_timeout)
                    print(f"   ✅ Campo preenchido por placeholder")
                    return True
            except:
                pass
            
            # Tenta encontrar por name ou id contendo o texto normalizado
            print(f"   🔎 Tentativa 4: Buscando por name/id normalizado: '{normalized}'...")
            try:
                input_field = page.locator(f"input[name*='{normalized}'], input[id*='{normalized}']").first
                count = input_field.count()
                print(f"   📊 Campos com name/id encontrados: {count}")
                if count > 0:
                    input_field.fill(value, timeout=self.action_timeout)
                    print(f"   ✅ Campo preenchido por name/id")
                    return True
            except:
                pass
            
            # Tenta buscar por texto visível próximo ao campo
            print(f"   🔎 Tentativa 5: Buscando campo próximo a texto visível...")
            try:
                # Busca por texto que contém palavras do label
                words = label_text.lower().split()
                for word in words:
                    if len(word) > 3:
                        # Procura input próximo a texto que contém a palavra
                        text_elem = page.get_by_text(word, exact=False).first
                        if text_elem.count() > 0:
                            # Procura input próximo (tenta várias posições)
                            for xpath in [
                                "following::input[1]",
                                "following::input[@type='text'][1]",
                                "following::textarea[1]",
                                "xpath=ancestor::*[1]//following::input[1]"
                            ]:
                                try:
                                    input_field = text_elem.locator(f"xpath={xpath}").first
                                    if input_field.count() > 0:
                                        # Verifica se não é um campo hidden ou de sistema
                                        field_type = input_field.get_attribute("type") or "text"
                                        if field_type not in ["hidden", "submit", "button"]:
                                            print(f"   ✅ Campo encontrado próximo ao texto '{word}', preenchendo...")
                                            input_field.fill(value, timeout=self.action_timeout)
                                            print(f"   ✅ Campo preenchido")
                                            return True
                                except:
                                    continue
            except:
                pass
            
            # Tentativa 6: Busca direta por texto "Nome da Parte" e input próximo
            if "nome" in label_text.lower() and "parte" in label_text.lower():
                print(f"   🔎 Tentativa 6: Busca específica para 'Nome da Parte'...")
                try:
                    # Procura texto "Nome da Parte" ou variações
                    for search_text in ["Nome da Parte", "Nome da parte", "nome da parte"]:
                        text_elem = page.get_by_text(search_text, exact=False).first
                        if text_elem.count() > 0:
                            # Procura input de texto próximo
                            input_field = text_elem.locator("xpath=following::input[@type='text'][1] | following::input[not(@type) or @type='text'][1]").first
                            if input_field.count() > 0:
                                print(f"   ✅ Campo 'Nome da Parte' encontrado, preenchendo...")
                                input_field.fill(value, timeout=self.action_timeout)
                                print(f"   ✅ Campo preenchido")
                                return True
                except:
                    pass
            
            print(f"   ❌ Nenhum campo encontrado para label '{label_text}' após todas tentativas")
        except Exception as e:
            print(f"   ❌ Erro ao buscar campo por label '{label_text}': {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        return False
    
    def _wait_for_search_results(self, page, timeout: int = 60000) -> bool:
        """
        Aguarda o carregamento dos resultados da pesquisa
        
        Args:
            page: Página do Playwright
            timeout: Timeout em milissegundos (padrão: 60 segundos)
            
        Returns:
            True se resultados foram encontrados, False caso contrário
        """
        try:
            print("⏳ Aguardando carregamento dos resultados da pesquisa...")
            print("   ⏱️  Aguardando até 60 segundos...")
            
            # PRIMEIRO: Aguarda um tempo fixo mínimo (15 segundos) para o site processar
            print("   ⏳ Aguardando tempo inicial (15 segundos) para processamento...")
            time.sleep(15)
            
            # Verifica se resultados já apareceram (verificação rápida antes de estratégias complexas)
            print("   🔍 Verificando se resultados já apareceram...")
            try:
                content = page.content()
                result_indicators = [
                    "processo", "resultado", "tabela", "lista", "dados",
                    "última movimentação", "movimentação", "autuação",
                    "sua consulta retornou", "primeiros serão exibidos"
                ]
                found_indicators = [ind for ind in result_indicators if ind in content.lower()]
                if found_indicators:
                    print(f"   ✅ Resultados detectados no HTML após espera inicial!")
                    print(f"   📊 Indicadores encontrados: {', '.join(found_indicators[:3])}")
                    time.sleep(3)  # Aguarda mais um pouco para garantir
                    return True
            except:
                pass
            
            # SEGUNDO: Tenta detectar elementos de resultados (com timeouts menores para não travar)
            wait_strategies = [
                # Tabela de resultados (mais comum) - timeout curto
                lambda: page.locator("table").first.wait_for(state="visible", timeout=5000),
                # Elementos com texto "processo" ou "resultado" - timeout curto
                lambda: page.get_by_text("processo", exact=False).first.wait_for(state="visible", timeout=5000),
                lambda: page.get_by_text("resultado", exact=False).first.wait_for(state="visible", timeout=5000),
            ]
            
            for i, strategy in enumerate(wait_strategies, 1):
                try:
                    print(f"   🔍 Tentativa {i}/{len(wait_strategies)}: Aguardando resultados...")
                    strategy()
                    print(f"   ✅ Resultados detectados via estratégia {i}!")
                    time.sleep(3)
                    return True
                except Exception as e:
                    print(f"   ⚠️  Estratégia {i} não funcionou: {type(e).__name__}")
                    continue
            
            # Se nenhuma estratégia funcionou, verifica conteúdo novamente
            print("   ⏳ Estratégias automáticas não funcionaram, verificando conteúdo HTML...")
            time.sleep(5)  # Aguarda mais 5 segundos
            
            try:
                content = page.content()
                result_indicators = [
                    "processo", "resultado", "tabela", "lista", "dados",
                    "última movimentação", "movimentação", "autuação",
                    "sua consulta retornou", "primeiros serão exibidos"
                ]
                found_indicators = [ind for ind in result_indicators if ind in content.lower()]
                if found_indicators:
                    print(f"   ✅ Conteúdo de resultados detectado no HTML: {', '.join(found_indicators[:3])}")
                    time.sleep(2)
                    return True
            except Exception as e:
                print(f"   ⚠️  Erro ao verificar conteúdo: {e}")
            
            # Mesmo sem confirmação, retorna True para não bloquear
            # O HTML será salvo mesmo assim
            print("   ⏳ Não foi possível confirmar resultados, mas continuando...")
            print("   ℹ️  HTML será salvo mesmo assim para verificação")
            return True  # Retorna True para não bloquear
            
        except Exception as e:
            print(f"   ⚠️  Erro ao aguardar resultados: {type(e).__name__}: {e}")
            # Mesmo com erro, retorna True para não bloquear
            print("   ℹ️  Continuando mesmo com erro - HTML será salvo")
            return True
    
    def _take_validation_screenshot(self, page, site_name: str) -> str:
        """
        Tira screenshot redimensionado para validação com Ollama
        
        Args:
            page: Página do Playwright
            site_name: Nome do site (para nome do arquivo)
            
        Returns:
            Caminho do arquivo salvo
        """
        try:
            screenshot_dir = Path("outputs/screenshots")
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            temp_screenshot = screenshot_dir / f"{site_name}_validation_{timestamp}_temp.png"
            final_screenshot = screenshot_dir / f"{site_name}_validation_{timestamp}.png"
            
            # Tira screenshot em resolução menor (800x600 para economizar)
            page.screenshot(path=str(temp_screenshot), full_page=False)
            
            # Redimensiona para reduzir tamanho (máximo 800px de largura)
            try:
                img = Image.open(temp_screenshot)
                # Redimensiona mantendo proporção
                max_size = 800
                if img.width > max_size or img.height > max_size:
                    ratio = min(max_size / img.width, max_size / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    print(f"   📐 Screenshot redimensionado: {img.width}x{img.height}")
                
                img.save(final_screenshot, optimize=True, quality=85)
                temp_screenshot.unlink()  # Remove arquivo temporário
                
                print(f"   📸 Screenshot salvo: {final_screenshot}")
                return str(final_screenshot)
            except Exception as e:
                print(f"   ⚠️  Erro ao redimensionar screenshot: {e}")
                # Se falhar, usa o original
                temp_screenshot.rename(final_screenshot)
                return str(final_screenshot)
                
        except Exception as e:
            print(f"   ❌ Erro ao tirar screenshot: {e}")
            return ""
    
    def _save_results_html(self, page, site_name: str) -> str:
        """
        Salva o HTML completo da página de resultados
        
        Args:
            page: Página do Playwright
            site_name: Nome do site (para nome do arquivo)
            
        Returns:
            Caminho do arquivo salvo
        """
        try:
            print("💾 Salvando HTML dos resultados...")
            
            # Cria diretório para HTMLs
            html_dir = Path("outputs/html")
            html_dir.mkdir(parents=True, exist_ok=True)
            
            # Gera nome do arquivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{site_name}_results_{timestamp}.html"
            filepath = html_dir / filename
            
            # Extrai HTML completo
            html_content = page.content()
            self.results_html = html_content
            
            # Salva em arquivo
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"✅ HTML salvo em: {filepath}")
            print(f"   📊 Tamanho: {len(html_content)} caracteres")
            
            # Tenta salvar screenshot também para validação visual
            try:
                screenshot_dir = Path("outputs/screenshots")
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                screenshot_file = screenshot_dir / f"{site_name}_results_{timestamp}.png"
                page.screenshot(path=str(screenshot_file), full_page=True)
                print(f"📸 Screenshot salvo em: {screenshot_file}")
            except Exception as e:
                print(f"   ⚠️  Não foi possível salvar screenshot: {e}")
            
            return str(filepath)
            
        except Exception as e:
            print(f"❌ Erro ao salvar HTML: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def run(self, url: str, goal: str, headless: bool = False):
        """
        Executa automação completa
        
        Args:
            url: URL inicial
            goal: Objetivo da automação
            headless: Se True, executa sem interface gráfica
        """
        site_name = normalize_site_name(url)
        
        # Configura logging em arquivo
        log_dir = Path("outputs/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{site_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # Cria logger que escreve em arquivo e console
        tee_logger = TeeLogger(str(log_file))
        
        # Redireciona print para o logger
        import builtins
        original_print = builtins.print
        
        def logged_print(*args, **kwargs):
            message = ' '.join(str(arg) for arg in args)
            if kwargs.get('end', '\n') == '\n':
                message += '\n'
            tee_logger.write(message)
        
        # Substitui print temporariamente
        builtins.print = logged_print
        
        # Inicia timer de execução
        start_time_total = time.time()
        search_start_time = None  # Timer para quando pesquisa começar
        MAX_EXECUTION_TIME = 60  # 1 minuto máximo de execução
        
        print("=" * 60)
        print(f"🚀 INICIANDO AUTOMAÇÃO")
        print("=" * 60)
        print(f"🌐 URL: {url}")
        print(f"🎯 Objetivo: {goal}")
        print(f"📝 Site: {site_name}")
        print(f"🤖 Modelo: {self.ollama.model}")
        print(f"📄 Log: {log_file}")
        print(f"⏱️  Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏰ Timeout máximo: {MAX_EXECUTION_TIME} segundos")
        print("=" * 60)
        print()
        
        try:
            with sync_playwright() as p:
                # Inicia navegador com configurações para evitar problemas HTTP2
                browser = p.chromium.launch(
                    headless=headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-http2',  # Desabilita HTTP/2 para evitar erros
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )
                # Cria contexto com configurações mais tolerantes
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    ignore_https_errors=True
                )
                page = context.new_page()
                
                # Configura captura de requisições
                page.on("request", self.capture.on_request)
                page.on("response", self.capture.on_response)
                
                try:
                    # Navega para URL inicial (com retry e estratégias alternativas)
                    print(f"📍 Navegando para: {url}")
                    navigation_success = False
                    last_error = None
                    navigation_start = time.time()
                    NAVIGATION_MAX_TIME = 25  # Máximo 25 segundos para navegação
                    
                    for attempt in range(3):  # Reduz para 3 tentativas
                        # Verifica timeout antes de cada tentativa
                        elapsed = time.time() - start_time_total
                        if elapsed >= MAX_EXECUTION_TIME:
                            print(f"⏰ TIMEOUT DE {MAX_EXECUTION_TIME}s ATINGIDO DURANTE NAVEGAÇÃO!")
                            raise Exception(f"Timeout de {MAX_EXECUTION_TIME} segundos atingido")
                        
                        nav_elapsed = time.time() - navigation_start
                        if nav_elapsed >= NAVIGATION_MAX_TIME:
                            print(f"⏰ TIMEOUT DE NAVEGAÇÃO ({NAVIGATION_MAX_TIME}s) ATINGIDO!")
                            print(f"   Tentando continuar mesmo assim...")
                            break
                        
                        try:
                            if attempt > 0:
                                print(f"   🔄 Tentativa {attempt + 1}/3...")
                                time.sleep(1)  # Reduz tempo de espera
                            
                            # Tenta diferentes estratégias de navegação (com timeouts menores)
                            strategies = [
                                ("domcontentloaded", 12000),
                                ("load", 8000),
                                ("commit", 5000),
                            ]
                            
                            for strategy_name, strategy_timeout in strategies:
                                # Verifica timeout antes de cada estratégia
                                elapsed = time.time() - start_time_total
                                if elapsed >= MAX_EXECUTION_TIME:
                                    print(f"⏰ TIMEOUT DE {MAX_EXECUTION_TIME}s ATINGIDO!")
                                    raise Exception(f"Timeout de {MAX_EXECUTION_TIME} segundos atingido")
                                
                                try:
                                    print(f"   🔍 Tentando com wait_until='{strategy_name}'...")
                                    page.goto(url, wait_until=strategy_name, timeout=strategy_timeout)
                                    
                                    # Verifica se realmente carregou
                                    current_url = page.url
                                    if "chrome-error" not in current_url and "error" not in current_url.lower():
                                        print(f"   ✅ Navegação bem-sucedida com '{strategy_name}'")
                                        print(f"   📍 URL atual: {current_url}")
                                        time.sleep(1)  # Reduz tempo de espera
                                        navigation_success = True
                                        break
                                    else:
                                        print(f"   ⚠️  URL indica erro: {current_url}")
                                        raise Exception(f"URL de erro detectada: {current_url}")
                                except Exception as e:
                                    last_error = e
                                    if strategy_name != strategies[-1][0]:
                                        continue
                                    raise
                            
                            if navigation_success:
                                break
                                
                        except Exception as e:
                            last_error = e
                            if attempt == 4:  # Última tentativa
                                print(f"   ⚠️  Erro na navegação após 5 tentativas: {e}")
                                print(f"   🔄 Tentando continuar com navegação básica...")
                                try:
                                    page.goto(url, timeout=30000)
                                    time.sleep(10)
                                    current_url = page.url
                                    if "chrome-error" not in current_url:
                                        navigation_success = True
                                        print(f"   ✅ Navegação básica funcionou")
                                except Exception as e2:
                                    print(f"   ❌ Navegação básica também falhou: {e2}")
                    
                    if navigation_success:
                        final_url = page.url
                        print(f"✅ Página carregada: {final_url}")
                        # Verifica se página tem conteúdo
                        try:
                            title = page.title()
                            if title:
                                print(f"   📄 Título: {title[:50]}")
                        except:
                            pass
                    else:
                        print(f"⚠️  Navegação não completou totalmente, mas tentando continuar...")
                        print(f"   Último erro: {last_error}")
                        # Tenta continuar mesmo assim - pode ser que a página tenha carregado parcialmente
                        try:
                            current_url = page.url
                            print(f"   📍 URL atual: {current_url}")
                            if "chrome-error" not in current_url:
                                navigation_success = True
                                print(f"   ✅ Continuando com página parcialmente carregada")
                        except:
                            pass
                        
                        if not navigation_success:
                            print(f"❌ Não foi possível continuar")
                            raise Exception(f"Não foi possível carregar a página: {last_error}")
                    print()
                    
                    # Loop de automação
                    iteration = 0
                    field_filled = False  # Rastreia se campo já foi preenchido
                    force_search_click = False  # Força clique em pesquisar após preencher
                    search_completed = False  # Rastreia se pesquisa já foi executada
                    execution_timeout_reached = False  # Flag para timeout
                    
                    while iteration < self.max_iterations:
                        # Verifica timeout de 1 minuto
                        elapsed_time = time.time() - start_time_total
                        if elapsed_time >= MAX_EXECUTION_TIME:
                            print(f"\n⏰ TIMEOUT DE {MAX_EXECUTION_TIME} SEGUNDOS ATINGIDO!")
                            print(f"   Tempo decorrido: {elapsed_time:.2f} segundos")
                            print(f"   🛑 FORÇANDO FINALIZAÇÃO...")
                            execution_timeout_reached = True
                            
                            # Tenta salvar HTML se ainda não salvou
                            if not self.results_html:
                                try:
                                    print("   💾 Tentando salvar HTML antes de finalizar...")
                                    html_path = self._save_results_html(page, site_name)
                                    if html_path:
                                        print(f"   ✅ HTML salvo: {html_path}")
                                except Exception as e:
                                    print(f"   ⚠️  Não foi possível salvar HTML: {e}")
                            
                            # Força ação extract para finalizar
                            action = {
                                "action": "extract",
                                "target": "",
                                "value": "",
                                "reason": f"Timeout de {MAX_EXECUTION_TIME} segundos atingido - finalizando automação"
                            }
                            print(f"   ✅ Ação forçada: {action['action']}")
                            break
                        
                        iteration += 1
                        elapsed_seconds = int(time.time() - start_time_total)
                        remaining_seconds = MAX_EXECUTION_TIME - elapsed_seconds
                        print(f"\n{'='*60}")
                        print(f"🔄 ITERAÇÃO {iteration}/{self.max_iterations} | ⏱️  Tempo: {elapsed_seconds}s / {MAX_EXECUTION_TIME}s (restam {remaining_seconds}s)")
                        print(f"{'='*60}\n")
                        
                        # Extrai informações estruturadas da página
                        print("📋 Extraindo informações da página...")
                        page_info = extract_page_info(page)
                        
                        # Adiciona informação sobre estado (se campo já foi preenchido)
                        if field_filled:
                            page_info["state"] = "Campo já foi preenchido. Próxima ação deve ser clicar no botão de pesquisar."
                        
                        # Verifica timeout ANTES de processar
                        elapsed_time = time.time() - start_time_total
                        if elapsed_time >= MAX_EXECUTION_TIME:
                            print(f"\n⏰ TIMEOUT DE {MAX_EXECUTION_TIME} SEGUNDOS ATINGIDO!")
                            print(f"   Tempo decorrido: {elapsed_time:.2f} segundos")
                            print(f"   🛑 FORÇANDO FINALIZAÇÃO...")
                            execution_timeout_reached = True
                            
                            # Tenta salvar HTML se ainda não salvou
                            if not self.results_html:
                                try:
                                    print("   💾 Tentando salvar HTML antes de finalizar...")
                                    html_path = self._save_results_html(page, site_name)
                                    if html_path:
                                        print(f"   ✅ HTML salvo: {html_path}")
                                except Exception as e:
                                    print(f"   ⚠️  Não foi possível salvar HTML: {e}")
                            
                            # Força ação extract para finalizar
                            action = {
                                "action": "extract",
                                "target": "",
                                "value": "",
                                "reason": f"Timeout de {MAX_EXECUTION_TIME} segundos atingido - finalizando automação"
                            }
                            print(f"   ✅ Ação forçada: {action['action']}")
                            # Pula para execução da ação extract
                            action_type = "extract"
                            target = ""
                            value = ""
                            reason = action["reason"]
                            break
                        
                        # Verifica se pesquisa já foi executada e resultados foram retornados
                        if search_completed:
                            page_info["state"] = "✅ PESQUISA JÁ FOI EXECUTADA! Resultados foram retornados. Ação: 'extract' para finalizar. NÃO pesquise novamente!"
                            page_info["has_results"] = True
                            print("   ✅ Pesquisa já foi executada - aguardando finalização...")
                        elif self.results_html:
                            try:
                                # Verifica se página atual tem resultados E se correspondem ao objetivo
                                current_content = page.content()
                                
                                # Extrai valor do objetivo para verificar se está nos resultados
                                value_from_goal = self._extract_value_from_goal(goal)
                                
                                # Verifica se há tabela de resultados (mais específico)
                                has_results_table = "processostable" in current_content.lower() or "<table" in current_content.lower()
                                
                                # Verifica se há mensagem específica de resultados
                                has_results_message = any(kw in current_content.lower() for kw in [
                                    "sua consulta retornou", "primeiros serão exibidos",
                                    "resultados encontrados"
                                ])
                                
                                # Se há tabela E mensagem de resultados, verifica se o valor do objetivo está presente
                                if has_results_table and has_results_message:
                                    # Se há valor específico no objetivo, verifica se está nos resultados
                                    if value_from_goal:
                                        value_in_results = value_from_goal.lower() in current_content.lower()
                                        if value_in_results:
                                            page_info["state"] = "✅ RESULTADOS JÁ FORAM RETORNADOS! A pesquisa foi executada com sucesso. Ação: 'extract' para finalizar. NÃO pesquise novamente!"
                                            page_info["has_results"] = True
                                            search_completed = True  # Marca como concluída
                                            print(f"   ✅ Resultados detectados na página atual e correspondem ao objetivo ('{value_from_goal}')!")
                                        else:
                                            print(f"   ⚠️  Resultados detectados, mas não correspondem ao objetivo ('{value_from_goal}'). Continuando pesquisa...")
                                            search_completed = False  # Força nova pesquisa
                                    else:
                                        # Se não há valor específico, assume que resultados são válidos
                                        page_info["state"] = "✅ RESULTADOS JÁ FORAM RETORNADOS! A pesquisa foi executada com sucesso. Ação: 'extract' para finalizar. NÃO pesquise novamente!"
                                        page_info["has_results"] = True
                                        search_completed = True
                                        print("   ✅ Resultados detectados na página atual!")
                            except:
                                pass
                        
                        # Log detalhado do que foi encontrado
                        print(f"\n📊 INFORMAÇÕES EXTRAÍDAS:")
                        print(f"   URL: {page_info.get('url', 'N/A')}")
                        print(f"   Título: {page_info.get('title', 'N/A')}")
                        print(f"   Campos de entrada encontrados: {len(page_info.get('inputs', []))}")
                        for i, inp in enumerate(page_info.get('inputs', [])[:5], 1):
                            print(f"      {i}. Label: '{inp.get('label', '')}' | Placeholder: '{inp.get('placeholder', '')}' | Name: '{inp.get('name', '')}' | ID: '{inp.get('id', '')}'")
                        print(f"   Botões encontrados: {len(page_info.get('buttons', []))}")
                        for i, btn in enumerate(page_info.get('buttons', [])[:5], 1):
                            print(f"      {i}. Texto: '{btn.get('text', '')}' | ID: '{btn.get('id', '')}'")
                        print()
                    
                        # Extrai valor do objetivo se mencionado (ex: "pesquisar por jose alves")
                        value_from_goal = self._extract_value_from_goal(goal)
                        if value_from_goal:
                            print(f"💡 Valor extraído do objetivo: '{value_from_goal}'")
                            print(f"   ✅ Este valor será usado para preencher o campo")
                        else:
                            print("⚠️  Nenhum valor específico extraído do objetivo")
                            print("   ℹ️  Ollama tentará identificar o valor do objetivo")
                        print()
                        
                        # Se pesquisa já foi concluída, FORÇA finalização imediata
                        if search_completed:
                            print("✅ Pesquisa já foi concluída! Forçando finalização...")
                            action = {
                                "action": "extract",
                                "target": "",
                                "value": "",
                                "reason": "Pesquisa já foi executada e validada - finalizando automação"
                            }
                            print("   🛑 Não continuará pesquisando - pesquisa já foi concluída!")
                        # Se campo foi preenchido, força ação de clique em pesquisar
                        elif force_search_click:
                            print("🔍 Campo já preenchido! Forçando ação: CLICAR EM PESQUISAR")
                            action = {
                                "action": "click",
                                "target": "PESQUISAR",
                                "value": "",
                                "reason": "Campo foi preenchido, agora precisa clicar em pesquisar"
                            }
                            force_search_click = False  # Reseta flag
                        else:
                            # Pergunta ao Ollama qual a próxima ação
                            print("🤖 Enviando informações para Ollama...")
                            print(f"   Modelo: {self.ollama.model}")
                            print(f"   Objetivo: {goal}")
                            action = self.ollama.analyze_page(page_info, goal, value_from_goal, self.current_state)
                        
                        print(f"\n📥 RESPOSTA DO OLLAMA (RAW):")
                        print(f"   {action}")
                        print()
                        
                        action_type = action.get("action", "wait")
                        target = action.get("target", "")
                        # Limpa o target removendo prefixos comuns
                        if target:
                            target = target.replace("Label: ", "").replace("label: ", "").replace("'", "").replace('"', "").strip()
                        
                        # Detecta se target é um ID interno JSF (como j_id28, javax.faces, etc)
                        is_jsf_internal_id = False
                        if target:
                            jsf_patterns = ["j_id", "javax.faces", "fPP:", "form:", "input:"]
                            is_jsf_internal_id = any(target.startswith(pattern) or pattern in target for pattern in jsf_patterns)
                            if is_jsf_internal_id:
                                print(f"⚠️  Target detectado como ID interno JSF: '{target}'")
                                print(f"   🔄 Convertendo para busca por label 'Nome da Parte'...")
                                target = "Nome da Parte"  # Força busca por label
                        
                        value = action.get("value", "") or value_from_goal  # Usa valor extraído se Ollama não forneceu
                        reason = action.get("reason", "")
                        
                        print(f"💡 AÇÃO DECIDIDA:")
                        print(f"   Tipo: {action_type}")
                        print(f"   Target: '{target}'")
                        print(f"   Value: '{value}'")
                        print(f"   Motivo: {reason}")
                        print()
                        
                        # Executa ação
                        print(f"⚙️  EXECUTANDO AÇÃO: {action_type}")
                        print()
                        
                        if action_type == "extract":
                            print("✅ Objetivo alcançado! Resultados encontrados, finalizando...")
                            
                            # Se ainda não salvou o HTML, salva agora
                            if not self.results_html:
                                print("   💾 Salvando HTML dos resultados...")
                                html_path = self._save_results_html(page, site_name)
                                if html_path:
                                    print(f"📄 HTML dos resultados salvo com sucesso!")
                                    print(f"   📁 Arquivo: {html_path}")
                            
                            # Retorna o HTML salvo
                            if self.results_html:
                                print(f"📊 HTML extraído: {len(self.results_html)} caracteres")
                                # Verifica se contém resultados
                                result_keywords = ["processo", "resultado", "sua consulta retornou"]
                                has_results = any(kw in self.results_html.lower() for kw in result_keywords)
                                if has_results:
                                    print(f"   ✅ HTML contém resultados da pesquisa!")
                            
                            # Calcula tempo total de execução
                            total_elapsed = time.time() - start_time_total
                            end_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            
                            print("🎉 Automação concluída com sucesso!")
                            print("=" * 60)
                            print("📊 RESUMO FINAL:")
                            print(f"🕐 Início: {datetime.fromtimestamp(start_time_total).strftime('%Y-%m-%d %H:%M:%S')}")
                            print(f"🕐 Fim: {end_time_str}")
                            print(f"⏱️  TEMPO TOTAL DE EXECUÇÃO: {total_elapsed:.2f} segundos ({total_elapsed/60:.2f} minutos)")
                            
                            # Se pesquisa foi executada, mostra tempo da pesquisa
                            if search_start_time:
                                search_elapsed = time.time() - search_start_time
                                print(f"⏱️  TEMPO DE PESQUISA: {search_elapsed:.2f} segundos ({search_elapsed/60:.2f} minutos)")
                                print(f"   📍 Pesquisa iniciou em: {datetime.fromtimestamp(search_start_time).strftime('%H:%M:%S')}")
                            
                            if self.results_html:
                                print(f"📊 HTML extraído: {len(self.results_html)} caracteres")
                            
                            print("=" * 60)
                            
                            search_completed = True  # Garante que está marcado
                            break  # FINALIZA IMEDIATAMENTE
                        
                        elif action_type == "click":
                            if target:
                                print(f"🎯 Tentando clicar em: '{target}'")
                                
                                # Se target é "PESQUISAR" ou similar, tenta múltiplas variações
                                if "pesquisar" in target.lower() or "buscar" in target.lower() or field_filled:
                                    print(f"🔍 Buscando botão de pesquisa...")
                                    search_button_found = False
                                    
                                    # Lista de possíveis textos/IDs do botão de pesquisa
                                    search_targets = [
                                        "PESQUISAR",
                                        "Pesquisar",
                                        "pesquisar",
                                        "BUSCAR",
                                        "Buscar",
                                        "buscar",
                                        "fPP:searchProcessos",  # ID específico do site
                                        "Search",
                                        "search"
                                    ]
                                    
                                    for search_target in search_targets:
                                        print(f"   🔎 Tentando: '{search_target}'")
                                        success = self._execute_click(page, search_target)
                                        if not success:
                                            success = self._click_by_text(page, search_target)
                                        if success:
                                            print(f"   ✅ Botão encontrado e clicado: '{search_target}'")
                                            search_button_found = True
                                            field_filled = False  # Reseta flag
                                            self.current_state = {}  # Reseta estado
                                            
                                            # Marca início da pesquisa para medir tempo
                                            search_start_time = time.time()
                                            print(f"   ⏱️  Pesquisa iniciada em: {datetime.now().strftime('%H:%M:%S')}")
                                            
                                            # Aguarda carregamento dos resultados (com tempo suficiente)
                                            print(f"   ⏳ Aguardando processamento da pesquisa...")
                                            
                                            # SEMPRE tenta aguardar, mas não bloqueia se der timeout
                                            try:
                                                results_detected = self._wait_for_search_results(page)
                                            except Exception as e:
                                                print(f"   ⚠️  Erro ao aguardar resultados: {e}")
                                                print(f"   ℹ️  Continuando para salvar HTML mesmo assim...")
                                                results_detected = False
                                            
                                            # SEMPRE salva HTML, independente de ter detectado ou não
                                            # Se deu timeout mas a pesquisa já foi executada, o HTML terá os resultados
                                            print(f"   💾 Salvando HTML dos resultados...")
                                            html_path = self._save_results_html(page, site_name)
                                            
                                            # Tira screenshot redimensionado e valida com Ollama
                                            print(f"   📸 Tirando screenshot para validação visual...")
                                            screenshot_path = self._take_validation_screenshot(page, site_name)
                                            
                                            validation_confirmed = False
                                            if screenshot_path:
                                                print(f"   🔍 Enviando screenshot para Ollama validar se pesquisa terminou...")
                                                validation = self.ollama.validate_search_results(screenshot_path)
                                                
                                                if validation.get("completed", False):
                                                    print(f"   ✅ Ollama CONFIRMOU: Pesquisa concluída!")
                                                    print(f"   📝 Motivo: {validation.get('reason', '')}")
                                                    validation_confirmed = True
                                                    search_completed = True
                                                    
                                                    # Calcula tempo de pesquisa
                                                    if search_start_time:
                                                        search_elapsed = time.time() - search_start_time
                                                        print(f"   ⏱️  TEMPO DE PESQUISA: {search_elapsed:.2f} segundos")
                                                else:
                                                    print(f"   ⚠️  Ollama não confirmou conclusão: {validation.get('reason', '')}")
                                            
                                            if html_path:
                                                print(f"📄 HTML dos resultados salvo com sucesso!")
                                                print(f"   📁 Arquivo: {html_path}")
                                                
                                                # Verifica se HTML contém resultados (fallback se screenshot não confirmou)
                                                if not validation_confirmed:
                                                    try:
                                                        if self.results_html:
                                                            result_keywords = ["processo", "resultado", "tabela", "sua consulta retornou", "última movimentação"]
                                                            has_results = any(kw in self.results_html.lower() for kw in result_keywords)
                                                            if has_results:
                                                                print(f"   ✅ HTML contém resultados da pesquisa!")
                                                                print(f"   🎯 Pesquisa concluída com sucesso!")
                                                                search_completed = True
                                                                
                                                                # Calcula tempo de pesquisa
                                                                if search_start_time:
                                                                    search_elapsed = time.time() - search_start_time
                                                                    print(f"   ⏱️  TEMPO DE PESQUISA: {search_elapsed:.2f} segundos")
                                                    except:
                                                        pass
                                            else:
                                                print(f"   ❌ Falha ao salvar HTML")
                                            
                                            # Se validação confirmou (screenshot ou HTML), FORÇA finalização IMEDIATA
                                            if search_completed:
                                                print(f"   🛑 Pesquisa validada - FINALIZANDO automação IMEDIATAMENTE!")
                                                print(f"   ✅ Não continuará pesquisando - pesquisa já foi concluída!")
                                                
                                                # Calcula tempo de pesquisa
                                                if search_start_time:
                                                    search_elapsed = time.time() - search_start_time
                                                    print(f"   ⏱️  TEMPO DE PESQUISA: {search_elapsed:.2f} segundos")
                                                
                                                field_filled = False
                                                # FORÇA ação extract - na próxima iteração o check no início vai finalizar
                                                time.sleep(1)  # Pequena pausa
                                            else:
                                                # Não quebra aqui - deixa continuar para Ollama detectar resultados e finalizar
                                                # Mas reseta flags para não pesquisar novamente
                                                field_filled = False
                                                time.sleep(2)  # Pequena pausa
                                            
                                            break  # Quebra apenas o loop de tentativas de clique
                                    
                                    if not search_button_found:
                                        print(f"❌ Nenhum botão de pesquisa encontrado após tentar todas variações")
                                else:
                                    # Clique normal em outros elementos
                                    success = self._execute_click(page, target)
                                    if not success:
                                        # Tenta encontrar por texto se seletor CSS falhar
                                        print(f"🔄 Método 1 falhou. Tentando método alternativo (buscar por texto)...")
                                        success = self._click_by_text(page, target)
                                    
                                    if success:
                                        print(f"✅ Clique executado com sucesso!")
                                        time.sleep(3)  # Aguarda carregamento
                                    else:
                                        print(f"❌ Falha ao clicar após tentar todos os métodos")
                            else:
                                print(f"⚠️  Target vazio, não é possível clicar")
                        
                        elif action_type == "fill":
                            if target and value:
                                print(f"🎯 Tentando preencher campo: '{target}' com valor: '{value}'")
                                
                                # Verifica se target não é um ID de campo interno (como j_id28)
                                if target.startswith('j_id') or target.startswith('javax.faces'):
                                    print(f"⚠️  Target parece ser ID interno JSF, tentando buscar por texto 'Nome da Parte'...")
                                    # Força busca por label
                                    success = self._fill_by_label(page, "Nome da Parte", value)
                                else:
                                    success = self._execute_fill(page, target, value)
                                    if not success:
                                        # Tenta encontrar por label ou placeholder
                                        print(f"🔄 Método 1 falhou. Tentando método alternativo (buscar por label/placeholder)...")
                                        success = self._fill_by_label(page, target, value)
                                
                                if success:
                                    print(f"✅ Campo preenchido com sucesso!")
                                    field_filled = True  # Marca que campo foi preenchido
                                    force_search_click = True  # FORÇA clique em pesquisar na próxima iteração
                                    self.current_state = {"last_action": "fill", "last_target": target, "last_value": value}
                                    print(f"📝 Estado atualizado: campo preenchido")
                                    print(f"🔍 PRÓXIMA AÇÃO: Clicar em botão PESQUISAR")
                                    time.sleep(2)
                                else:
                                    print(f"❌ Falha ao preencher após tentar todos os métodos")
                            else:
                                print(f"⚠️  Target ou value vazio. Target: '{target}', Value: '{value}'")
                        
                        elif action_type == "navigate":
                            if target:
                                try:
                                    print(f"🔗 Navegando para: {target}")
                                    page.goto(target, wait_until="networkidle", timeout=60000)
                                    print(f"✅ Navegação concluída")
                                    time.sleep(3)
                                except Exception as e:
                                    print(f"❌ Erro ao navegar: {e}")
                                    import traceback
                                    traceback.print_exc()
                        
                        elif action_type == "wait":
                            print("⏳ Aguardando 3 segundos...")
                            time.sleep(3)
                        
                        else:
                            print(f"⚠️  Ação desconhecida: {action_type}")
                            print("⏳ Aguardando 2 segundos...")
                            time.sleep(2)
                        
                    # Verifica se objetivo foi alcançado (pode ser melhorado)
                    try:
                        if page and not page.is_closed():
                            content = page.content()
                            if "resultado" in content.lower() or "dados" in content.lower():
                                print("✅ Possíveis resultados encontrados na página")
                    except Exception as e:
                        print(f"⚠️  Não foi possível verificar conteúdo: {e}")
                        
                        print()
                        time.sleep(1)  # Pequena pausa entre iterações
                    
                    # Após automação, analisa requisições capturadas
                    print("=" * 60)
                    print("📊 ANALISANDO REQUISIÇÕES CAPTURADAS")
                    print("=" * 60)
                    
                    all_requests = self.capture.get_requests()
                    api_requests = self.capture.get_api_requests()
                    
                    print(f"Total de requisições capturadas: {len(all_requests)}")
                    print(f"Requisições de API: {len(api_requests)}")
                    print()
                    
                    # Salva requisições brutas
                    requests_file = f"outputs/requests/{site_name}_requests.json"
                    Path("outputs/requests").mkdir(parents=True, exist_ok=True)
                    self.capture.save_to_file(requests_file)
                    
                    # Analisa requisições (foca nas de API)
                    requests_to_analyze = api_requests if api_requests else all_requests[:10]
                    analysis = self.analyzer.analyze_requests(requests_to_analyze)
                    
                    print(f"📈 Análise: {analysis.get('reason', '')}")
                    print()
                    
                    # Gera output baseado na análise
                    if analysis.get('viable', False):
                        print("✅ Gerando script Bash...")
                        viable_reqs = analysis.get('viable_requests', [])
                        script_path = self.bash_gen.generate_script(viable_reqs, site_name, goal)
                        print(f"✅ Script gerado: {script_path}")
                    else:
                        print("❌ Gerando relatório...")
                        report_path = self.report_gen.generate_report(analysis, site_name, url, goal)
                        print(f"✅ Relatório gerado: {report_path}")
                
                except Exception as e:
                    print(f"❌ Erro durante automação: {e}")
                    import traceback
                    traceback.print_exc()
                
                finally:
                    browser.close()
        
        except Exception as e:
            # Restaura print antes de mostrar erro
            import builtins
            builtins.print = original_print
            print(f"❌ Erro fatal: {e}")
            import traceback
            traceback.print_exc()
            tee_logger.close()
            raise
        
        finally:
            # Restaura print original
            import builtins
            builtins.print = original_print
            
            # Fecha arquivo de log
            tee_logger.close()
            
            # Calcula tempo total final
            total_elapsed = time.time() - start_time_total
            end_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            print()
            print("=" * 60)
            print("✅ AUTOMAÇÃO CONCLUÍDA")
            print("=" * 60)
            print(f"📄 Log salvo em: {log_file}")
            print(f"🕐 Início: {datetime.fromtimestamp(start_time_total).strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"🕐 Fim: {end_time_str}")
            print(f"⏱️  TEMPO TOTAL DE EXECUÇÃO: {total_elapsed:.2f} segundos")
            print(f"⏱️  TEMPO TOTAL: {total_elapsed/60:.2f} minutos")
            
            if search_start_time:
                search_elapsed = time.time() - search_start_time
                print(f"⏱️  TEMPO DE PESQUISA: {search_elapsed:.2f} segundos ({search_elapsed/60:.2f} minutos)")
                print(f"   📍 Pesquisa iniciou em: {datetime.fromtimestamp(search_start_time).strftime('%H:%M:%S')}")
            
            # Estatísticas finais
            if self.results_html:
                print(f"📊 HTML extraído: {len(self.results_html)} caracteres")
                result_keywords = ["processo", "resultado", "sua consulta retornou"]
                has_results = any(kw in self.results_html.lower() for kw in result_keywords)
                if has_results:
                    print(f"✅ Resultados encontrados no HTML")
            
            print("=" * 60)


def main():
    """Função principal CLI"""
    parser = argparse.ArgumentParser(
        description="Automação web com Playwright e Ollama para criação de crawlers"
    )
    parser.add_argument(
        "--url",
        required=True,
        help="URL inicial para automação"
    )
    parser.add_argument(
        "--goal",
        required=True,
        help="Objetivo da automação (ex: 'pesquisar por jose alves e retornar resultados')"
    )
    parser.add_argument(
        "--model",
        default="aliafshar/gemma3-it-qat-tools:4b",
        help="Modelo Ollama a usar (padrão: ministral-3:3b)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Executar navegador em modo headless (padrão: False - mostrar navegador)"
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Mostrar navegador (sobrescreve --headless)"
    )
    
    args = parser.parse_args()
    
    headless = not args.show_browser if args.show_browser else args.headless
    
    crawler = PlaywrightCrawler(model=args.model)
    crawler.run(args.url, args.goal, headless=headless)


if __name__ == "__main__":
    main()

