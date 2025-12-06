#!/usr/bin/env python3
"""
Cliente para comunicação com API do Ollama
"""

import requests
import json
import base64
from typing import Dict, Optional, List
from pathlib import Path


class OllamaClient:
    """Cliente para interagir com Ollama API local"""
    
    def __init__(self, model: str = "aliafshar/gemma3-it-qat-tools:4b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
    
    def generate(self, prompt: str, system: Optional[str] = None, stream: bool = False) -> str:
        """
        Gera resposta do modelo Ollama
        
        Args:
            prompt: Prompt para o modelo
            system: Prompt de sistema (opcional)
            stream: Se True, retorna stream (não implementado ainda)
        
        Returns:
            Resposta do modelo como string
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream
        }
        
        if system:
            payload["system"] = system
        
        import time
        start_time = time.time()
        try:
            # Timeout reduzido para 60 segundos
            response = requests.post(self.api_url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            elapsed = time.time() - start_time
            print(f"   ⏱️  Ollama respondeu em {elapsed:.2f}s")
            return data.get("response", "")
        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            print(f"   ❌ Timeout ao comunicar com Ollama após {elapsed:.2f}s")
            return ""
        except requests.exceptions.RequestException as e:
            elapsed = time.time() - start_time
            print(f"   ❌ Erro ao comunicar com Ollama após {elapsed:.2f}s: {e}")
            return ""
    
    def validate_search_results(self, screenshot_path: str) -> Dict:
        """
        Valida se a pesquisa foi concluída analisando um screenshot
        
        Args:
            screenshot_path: Caminho para o arquivo de screenshot
            
        Returns:
            Dict com validação: {"completed": bool, "reason": str}
        """
        try:
            print("   📸 Validando screenshot com Ollama...")
            
            # Lê e codifica imagem em base64
            try:
                with open(screenshot_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                image_size_kb = len(image_data) / 1024
                print(f"   📊 Tamanho da imagem: {image_size_kb:.1f} KB")
            except Exception as e:
                print(f"   ⚠️  Erro ao ler screenshot: {e}")
                return {"completed": False, "reason": f"Erro ao ler imagem: {e}"}
            
            # Prompt para validação (mesmo sem suporte direto a imagem, o modelo pode inferir)
            system_prompt = """Você é um assistente que valida se uma pesquisa web foi concluída com sucesso.
Analise a descrição da página e determine se a pesquisa terminou e resultados estão visíveis."""
            
            prompt = f"""Uma pesquisa foi executada em uma página web e um screenshot foi capturado.

INFORMAÇÕES DO SCREENSHOT:
- Arquivo: {screenshot_path}
- Tamanho: {image_size_kb:.1f} KB
- A imagem foi capturada após clicar no botão de pesquisa

Você precisa determinar se:
1. A pesquisa foi executada com sucesso
2. Os resultados estão visíveis na página
3. A pesquisa está completa (não está mais carregando)

INDICADORES DE SUCESSO:
- Tabelas ou listas de resultados visíveis
- Mensagens como "sua consulta retornou", "resultados encontrados", "primeiros serão exibidos"
- Texto indicando que a pesquisa terminou
- Ausência de indicadores de carregamento (spinners)
- Presença de dados estruturados (processos, listas, tabelas)

INDICADORES DE FALHA:
- Página ainda carregando (spinners visíveis)
- Mensagens de erro
- Campos de formulário vazios sem resultados

Baseado no fato de que um screenshot foi capturado após a pesquisa, e considerando que o sistema aguardou tempo suficiente, responda:

Responda APENAS em JSON válido:
{{
    "completed": true/false,
    "reason": "explicação breve"
}}

Se o screenshot foi capturado após pesquisa e aguardo, é provável que a pesquisa tenha terminado. Responda com completed: true se você acredita que resultados estão visíveis."""
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False
            }
            
            try:
                response = requests.post(self.api_url, json=payload, timeout=30)
                response.raise_for_status()
                data = response.json()
                response_text = data.get("response", "")
                
                # Tenta parsear JSON da resposta
                try:
                    # Remove markdown se houver
                    cleaned = response_text
                    if '```json' in cleaned:
                        start = cleaned.find('```json') + 7
                        end = cleaned.find('```', start)
                        cleaned = cleaned[start:end].strip()
                    elif '```' in cleaned:
                        start = cleaned.find('```') + 3
                        end = cleaned.find('```', start)
                        cleaned = cleaned[start:end].strip()
                    
                    # Extrai JSON
                    json_start = cleaned.find('{')
                    json_end = cleaned.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = cleaned[json_start:json_end]
                        result = json.loads(json_str)
                        completed = result.get('completed', False)
                        reason = result.get('reason', '')
                        print(f"   ✅ Validação: completed={completed}")
                        print(f"   📝 Motivo: {reason}")
                        return result
                except json.JSONDecodeError as e:
                    print(f"   ⚠️  Erro ao parsear JSON: {e}")
                
                # Fallback: analisa texto da resposta
                response_lower = response_text.lower()
                if "completed" in response_lower and "true" in response_lower:
                    print(f"   ✅ Validação positiva pela resposta do modelo")
                    return {"completed": True, "reason": "Modelo confirmou que pesquisa está completa"}
                elif "false" in response_lower or "não" in response_lower or "no" in response_lower:
                    print(f"   ⚠️  Validação negativa pela resposta do modelo")
                    return {"completed": False, "reason": "Modelo não confirmou conclusão"}
                else:
                    # Se não conseguiu determinar, assume que está completo (screenshot foi capturado)
                    print(f"   ℹ️  Resposta ambígua, assumindo conclusão (screenshot capturado)")
                    return {"completed": True, "reason": "Screenshot capturado após pesquisa, assumindo conclusão"}
                    
            except Exception as e:
                print(f"   ⚠️  Erro ao validar com Ollama: {e}")
                # Fallback: assume que está completo se screenshot existe
                print(f"   ℹ️  Assumindo conclusão (screenshot capturado)")
                return {"completed": True, "reason": "Screenshot capturado, assumindo conclusão"}
                
        except Exception as e:
            print(f"   ⚠️  Erro ao validar screenshot: {e}")
            return {"completed": False, "reason": f"Erro: {e}"}
    
    def analyze_page(self, page_info: dict, goal: str, suggested_value: str = "", current_state: Dict = None) -> Dict:
        """
        Analisa informações da página e sugere próximas ações
        
        Args:
            page_info: Dict com informações estruturadas da página
            goal: Objetivo da automação
            suggested_value: Valor sugerido para preencher (opcional)
            current_state: Estado atual da automação (opcional)
        
        Returns:
            Dict com análise e sugestões
        """
        system_prompt = """Você é um assistente de automação web. Analise a página e sugira a próxima ação.
Responda APENAS em JSON:
{
    "action": "click|fill|navigate|extract|wait",
    "target": "label/placeholder do campo ou texto do botão",
    "value": "valor para preencher (se fill)",
    "reason": "explicação breve"
}

REGRAS IMPORTANTES:
1. Use LABEL/PLACEHOLDER para campos, TEXTO para botões
2. SEQUÊNCIA DE AÇÕES:
   - Primeiro: Preencha o campo necessário (action: "fill")
   - Depois: Clique no botão de pesquisar/buscar (action: "click")
   - Finalmente: Extraia os resultados (action: "extract")
3. Após preencher um campo, SEMPRE clique no botão correspondente (Pesquisar, Buscar, Submit, etc)
4. Procure botões com texto como: "Pesquisar", "Buscar", "Search", "Submit", "Enviar"
5. Se já preencheu o campo, a próxima ação DEVE ser clicar no botão de pesquisa"""
        
        # Monta descrição estruturada da página (otimizada para ser mais curta)
        page_desc = f"URL: {page_info.get('url', '')}\n"
        page_desc += f"Título: {page_info.get('title', '')}\n"
        
        # Adiciona estado se disponível
        state_info = ""
        if page_info.get('state'):
            state_info = f"\n⚠️ ESTADO ATUAL: {page_info.get('state')}\n"
        
        # Adiciona estado do current_state se disponível
        if current_state and current_state.get("last_action") == "fill":
            state_info = f"\n⚠️ ESTADO ATUAL: O campo '{current_state.get('last_target')}' foi preenchido com '{current_state.get('last_value')}'. A próxima ação deve ser CLICAR no botão de pesquisa ou submissão do formulário.\n"
        
        # Verifica se resultados já foram retornados
        if page_info.get("has_results") or page_info.get("state", "").startswith("✅ RESULTADOS"):
            state_info = "\n✅ RESULTADOS JÁ FORAM RETORNADOS! A pesquisa foi executada com sucesso. Você DEVE usar action: 'extract' para finalizar. NÃO pesquise novamente!\n"
        
        if state_info:
            page_desc += state_info
        
        page_desc += "\n"
        
        # Limita texto visível
        visible_text = page_info.get('visible_text', '')[:1000]
        if visible_text:
            page_desc += f"Texto visível na página:\n{visible_text}\n\n"
        
        # Campos (com mais detalhes para melhor identificação)
        inputs = page_info.get('inputs', [])[:15]
        if inputs:
            page_desc += "CAMPOS DISPONÍVEIS:\n"
            for i, inp in enumerate(inputs, 1):
                label = inp.get('label', '') or inp.get('placeholder', '')
                name = inp.get('name', '')
                inp_id = inp.get('id', '')
                inp_type = inp.get('type', 'text')
                
                # Monta descrição do campo
                field_desc = f"{i}. "
                if label:
                    field_desc += f"Label: '{label}'"
                if name:
                    if label:
                        field_desc += f" | Name: '{name}'"
                    else:
                        field_desc += f"Name: '{name}'"
                if inp_id:
                    field_desc += f" | ID: '{inp_id}'"
                if inp_type != 'text':
                    field_desc += f" | Tipo: {inp_type}"
                
                page_desc += f"{field_desc}\n"
        
        # Botões (com mais detalhes)
        buttons = page_info.get('buttons', [])[:10]
        if buttons:
            page_desc += "\nBOTÕES DISPONÍVEIS:\n"
            for i, btn in enumerate(buttons, 1):
                text = btn.get('text', '')
                btn_id = btn.get('id', '')
                if text or btn_id:
                    btn_desc = f"{i}. "
                    if text:
                        btn_desc += f"Texto: '{text}'"
                    if btn_id:
                        if text:
                            btn_desc += f" | ID: '{btn_id}'"
                        else:
                            btn_desc += f"ID: '{btn_id}'"
                    page_desc += f"{btn_desc}\n"
        
        value_hint = ""
        if suggested_value:
            value_hint = f"\nVALOR SUGERIDO PARA PREENCHER: '{suggested_value}'\nUse este valor no campo 'value' se a ação for 'fill'.\n"
        
        # Analisa o objetivo para dar dicas sobre qual campo usar
        goal_hints = ""
        goal_lower = goal.lower()
        
        if "nome" in goal_lower and "parte" in goal_lower:
            goal_hints = "\n💡 DICA: O objetivo menciona 'nome da parte'. Procure por campos com labels como 'Nome da Parte', 'Nome Parte', 'Parte', ou similar no texto visível.\n"
        elif "processo" in goal_lower:
            goal_hints = "\n💡 DICA: O objetivo menciona 'processo'. Procure por campos relacionados a número de processo.\n"
        elif "data" in goal_lower or "data" in goal_lower:
            goal_hints = "\n💡 DICA: O objetivo menciona data. Procure por campos de data.\n"
        
        prompt = f"""Você é um assistente de automação web inteligente. Sua tarefa é analisar a página e executar ações como um humano faria.

OBJETIVO DO USUÁRIO: {goal}
{value_hint}
{goal_hints}
{state_info}

INFORMAÇÕES DA PÁGINA:
{page_desc}

REGRAS CRÍTICAS:
1. VOCÊ JÁ ESTÁ NA PÁGINA CORRETA - NÃO use "navigate"
2. IDENTIFIQUE O CAMPO CORRETO:
   - Leia o OBJETIVO cuidadosamente
   - Procure nos CAMPOS DISPONÍVEIS o campo que corresponde ao objetivo
   - Use o LABEL do campo (não ID interno como "j_id28")
   - Exemplo: Se objetivo é "pesquisar por nome da parte X", procure campo com label "Nome da Parte"
3. USE O VALOR CORRETO:
   - Se há VALOR SUGERIDO, use EXATAMENTE esse valor
   - NÃO invente valores, NÃO use IDs internos, NÃO use placeholders
   - Use apenas o valor mencionado no objetivo
4. SEQUÊNCIA DE AÇÕES:
   - PASSO 1: Se campo não foi preenchido → action: "fill" (preencha com o valor correto)
   - PASSO 2: Se campo foi preenchido → action: "click" (clique no botão de pesquisa)
   - PASSO 3: Se já pesquisou → action: "extract" (extraia resultados)

EXEMPLOS:
- Objetivo: "pesquisar por nome da parte felipe alves da silva"
  → Ação 1: {{"action": "fill", "target": "Nome da Parte", "value": "felipe alves da silva"}}
  → Ação 2: {{"action": "click", "target": "PESQUISAR"}}

- Objetivo: "buscar processo 1234567"
  → Ação 1: {{"action": "fill", "target": "Processo", "value": "1234567"}}
  → Ação 2: {{"action": "click", "target": "Pesquisar"}}

IMPORTANTE:
- SEMPRE use o LABEL do campo (ex: "Nome da Parte"), NUNCA use IDs internos (ex: "j_id28")
- SEMPRE use o valor EXATO mencionado no objetivo
- SEMPRE clique no botão de pesquisa após preencher
- Seja GENÉRICO - funcione em qualquer site, não apenas neste

Qual a próxima ação? Responda APENAS JSON válido, sem markdown, sem comentários:
{{"action": "fill|click|extract", "target": "label do campo ou texto do botão", "value": "valor para preencher (se fill)"}}"""
        
        import time
        print(f"   📤 Enviando prompt para Ollama...")
        print(f"   🤖 Modelo: {self.model}")
        print(f"   ⏱️  Aguardando resposta (timeout: 60s)...")
        start_time = time.time()
        response = self.generate(prompt, system=system_prompt)
        elapsed = time.time() - start_time
        print(f"   ⏱️  Tempo total de resposta: {elapsed:.2f}s")
        
        print(f"   📥 Resposta recebida ({len(response)} caracteres)")
        print(f"   📄 Resposta completa:\n{response}\n")
        
        try:
            # Remove blocos markdown se existirem
            cleaned_response = response
            if '```json' in cleaned_response:
                # Extrai apenas o conteúdo entre ```json e ```
                start_marker = cleaned_response.find('```json')
                end_marker = cleaned_response.find('```', start_marker + 7)
                if end_marker > start_marker:
                    cleaned_response = cleaned_response[start_marker + 7:end_marker].strip()
                    print(f"   🔧 Removido bloco markdown")
            elif '```' in cleaned_response:
                # Tenta remover blocos de código genéricos
                start_marker = cleaned_response.find('```')
                end_marker = cleaned_response.find('```', start_marker + 3)
                if end_marker > start_marker:
                    cleaned_response = cleaned_response[start_marker + 3:end_marker].strip()
                    print(f"   🔧 Removido bloco de código")
            
            # Tenta extrair JSON da resposta
            json_start = cleaned_response.find('{')
            json_end = cleaned_response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = cleaned_response[json_start:json_end]
                print(f"   ✅ JSON extraído da resposta")
                # Tenta parsear
                parsed = json.loads(json_str)
                print(f"   ✅ JSON parseado com sucesso")
                return parsed
            else:
                print(f"   ⚠️  Não encontrou JSON na resposta")
        except json.JSONDecodeError as e:
            print(f"   ❌ Erro ao parsear JSON: {e}")
            # Tenta extrair JSON de forma mais agressiva
            try:
                import re
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    parsed = json.loads(json_str)
                    print(f"   ✅ JSON extraído via regex")
                    return parsed
            except:
                pass
            print(f"   📄 JSON tentado: {json_str[:200] if 'json_str' in locals() else 'N/A'}")
        except Exception as e:
            print(f"   ❌ Erro inesperado: {e}")
        
        # Fallback se não conseguir parsear JSON
        print(f"   ⚠️  Usando resposta fallback")
        return {
            "action": "wait",
            "target": "",
            "value": "",
            "reason": response
        }
    
    def analyze_request(self, request_data: Dict) -> Dict:
        """
        Analisa se uma requisição HTTP é viável para crawler puro
        
        Args:
            request_data: Dados da requisição (URL, headers, params, etc)
        
        Returns:
            Dict com análise de viabilidade
        """
        system_prompt = """Você é um especialista em web scraping e análise de requisições HTTP.
Analise se a requisição pode ser replicada com curl/HTTP puro.
Responda APENAS em JSON:
{
    "viable": true|false,
    "reason": "explicação",
    "complexity": "low|medium|high",
    "requirements": ["requisito1", "requisito2"]
}"""
        
        prompt = f"""Analise esta requisição HTTP:

URL: {request_data.get('url', '')}
Method: {request_data.get('method', 'GET')}
Headers: {json.dumps(request_data.get('headers', {}), indent=2)}
Params: {json.dumps(request_data.get('params', {}), indent=2)}
Body: {request_data.get('body', '')}

É viável criar um crawler HTTP puro (curl) para esta requisição?"""
        
        response = self.generate(prompt, system=system_prompt)
        
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
        except:
            pass
        
        return {
            "viable": False,
            "reason": "Não foi possível analisar a requisição",
            "complexity": "high",
            "requirements": []
        }

