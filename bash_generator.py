#!/usr/bin/env python3
"""
Gera scripts Bash com curl baseados em requisições HTTP capturadas
"""

import json
from typing import List, Dict
from urllib.parse import urlencode
from pathlib import Path


class BashGenerator:
    """Gera scripts Bash com comandos curl"""
    
    def __init__(self, output_dir: str = "outputs/crawlers"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_script(self, requests: List[Dict], site_name: str, goal: str) -> str:
        """
        Gera script Bash com curl para as requisições
        
        Args:
            requests: Lista de requisições viáveis
            site_name: Nome do site (para nome do arquivo)
            goal: Objetivo da automação
        
        Returns:
            Caminho do arquivo gerado
        """
        filename = self._get_filename(site_name)
        filepath = self.output_dir / filename
        
        script_content = self._build_script(requests, goal)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            # Torna o arquivo executável
            filepath.chmod(0o755)
            
            print(f"✅ Script Bash gerado: {filepath}")
            return str(filepath)
            
        except Exception as e:
            print(f"❌ Erro ao gerar script: {e}")
            return ""
    
    def _get_filename(self, site_name: str) -> str:
        """Gera nome do arquivo baseado no nome do site"""
        # Normaliza nome do site
        normalized = site_name.lower().replace(' ', '-').replace('.', '-')
        # Remove caracteres inválidos
        normalized = ''.join(c for c in normalized if c.isalnum() or c in ['-', '_'])
        return f"{normalized}.sh"
    
    def _build_script(self, requests: List[Dict], goal: str) -> str:
        """Constrói conteúdo do script Bash"""
        # SEMPRE precisa de GET inicial para obter sessão e ViewState
        # Procura primeiro POST relevante para extrair URL base
        base_url = None
        for req in requests:
            if req.get('method') == 'POST':
                url = req.get('url', '')
                # Ignora URLs de tracking
                if 'akam' not in url.lower() and 'pixel' not in url.lower():
                    # Remove jsessionid e parâmetros da URL
                    base_url = url.split(';jsessionid')[0].split('?')[0]
                    break
        
        # Se não encontrou POST relevante, procura GET document
        if not base_url:
            for req in requests:
                if req.get('method') == 'GET' and req.get('resource_type') == 'document':
                    url = req.get('url', '')
                    # Ignora URLs de tracking/pixel (akam, analytics, etc)
                    if 'akam' not in url.lower() and 'pixel' not in url.lower() and 'analytics' not in url.lower():
                        base_url = url.split(';jsessionid')[0].split('?')[0]
                        break
        
        # Cria GET inicial com URL base encontrada
        initial_get = None
        if base_url:
            # Pega headers do primeiro POST ou GET relevante
            sample_req = None
            for req in requests:
                if req.get('method') in ['POST', 'GET']:
                    url = req.get('url', '')
                    if 'akam' not in url.lower() and 'pixel' not in url.lower():
                        sample_req = req
                        break
            
            if sample_req:
                initial_get = {
                    'url': base_url,
                    'method': 'GET',
                    'headers': sample_req.get('headers', {}),
                    'params': {},
                    'body': None,
                    'resource_type': 'document'
                }
        
        script = f"""#!/bin/bash
# Script gerado automaticamente para crawler HTTP
# Objetivo: {goal}
# Total de requisições: {len(requests) + (1 if initial_get else 0)}

# set -e  # Comentado para não parar em caso de erro (permite continuar mesmo com warnings)

# Cores para output
GREEN='\\033[0;32m'
BLUE='\\033[0;34m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# Arquivo para armazenar cookies
COOKIE_JAR="cookies.txt"

echo -e "${{BLUE}}Iniciando crawler...${{NC}}"

# Limpa cookie jar anterior
rm -f "$COOKIE_JAR"

"""
        
        # SEMPRE adiciona requisição GET inicial (obrigatória para JSF)
        if initial_get:
            script += self._request_to_curl(initial_get, 0, is_initial=True)
            script += "\n"
            
            # Adiciona função para extrair ViewState do HTML
            script += """
# Função para extrair ViewState do HTML
extract_viewstate() {
    local html_file="$1"
    if [ ! -f "$html_file" ]; then
        echo "j_id1"  # Fallback
        return
    fi
    
    # Tenta extrair ViewState do HTML
    VIEWSTATE=$(grep -oP 'name="javax.faces.ViewState"[^>]*value="\\K[^"]*' "$html_file" 2>/dev/null | head -1)
    
    if [ -z "$VIEWSTATE" ]; then
        # Tenta método alternativo
        VIEWSTATE=$(grep -oP 'id="javax.faces.ViewState"[^>]*value="\\K[^"]*' "$html_file" 2>/dev/null | head -1)
    fi
    
    if [ -z "$VIEWSTATE" ]; then
        # Tenta método mais simples
        VIEWSTATE=$(grep -o 'value="[^"]*"' "$html_file" 2>/dev/null | grep -A 1 'ViewState' | grep -o 'value="[^"]*"' | sed 's/value="\\(.*\\)"/\\1/' | head -1)
    fi
    
    if [ -z "$VIEWSTATE" ]; then
        echo "j_id1"  # Fallback padrão
    else
        echo "$VIEWSTATE"
    fi
}

"""
        
        # Adiciona cada requisição como função curl
        for i, req in enumerate(requests, 1):
            script += self._request_to_curl(req, i, is_initial=False)
            script += "\n"
        
        # Adiciona função de verificação de resultados
        if len(requests) > 0:
            last_output = f"output_{len(requests)}.json"
        elif initial_get:
            last_output = "output_initial.html"
        else:
            last_output = "output_1.json"
        
        script += f"""
# Função para verificar resultados
verify_results() {{
    echo -e "${{BLUE}}Verificando resultados da última requisição...${{NC}}"
    echo ""
    
    LAST_OUTPUT="{last_output}"
    
    if [ ! -f "$LAST_OUTPUT" ]; then
        echo -e "${{YELLOW}}⚠️  Arquivo de saída não encontrado: $LAST_OUTPUT${{NC}}"
        return 1
    fi
    
    FILE_SIZE=$(stat -f%z "$LAST_OUTPUT" 2>/dev/null || stat -c%s "$LAST_OUTPUT" 2>/dev/null || echo "0")
    echo -e "${{BLUE}}📄 Arquivo: $LAST_OUTPUT${{NC}}"
    echo -e "${{BLUE}}📊 Tamanho: $FILE_SIZE bytes${{NC}}"
    echo ""
    
    # Verifica se é HTML ou JSON/XML
    if grep -q "<html\\|<\!DOCTYPE\\|<?xml" "$LAST_OUTPUT" 2>/dev/null; then
        echo -e "${{BLUE}}📋 Tipo: HTML/XML${{NC}}"
        echo ""
        
        # Verifica se foi redirecionado para login
        if grep -qi "login\\|entrar\\|autenticação" "$LAST_OUTPUT" 2>/dev/null; then
            echo -e "${{YELLOW}}⚠️  ATENÇÃO: Página pode ter redirecionado para login${{NC}}"
            echo -e "${{YELLOW}}   Isso pode indicar que a sessão expirou${{NC}}"
            echo ""
        fi
        
        # Procura por resultados da pesquisa
        echo -e "${{BLUE}}🔍 Procurando resultados da pesquisa...${{NC}}"
        
        # Procura por termos relacionados à pesquisa
        SEARCH_TERMS="felipe|processo|resultado|consulta|encontrado|retornou"
        MATCHES=$(grep -iE "$SEARCH_TERMS" "$LAST_OUTPUT" 2>/dev/null | wc -l)
        
        if [ "$MATCHES" -gt 0 ]; then
            echo -e "${{GREEN}}✅ Encontrados $MATCHES trechos com termos relacionados${{NC}}"
            echo ""
            echo -e "${{BLUE}}📝 Trechos encontrados (primeiros 5):${{NC}}"
            grep -iE "$SEARCH_TERMS" "$LAST_OUTPUT" 2>/dev/null | head -5 | sed 's/^/   /'
        else
            echo -e "${{YELLOW}}⚠️  Nenhum termo relacionado encontrado${{NC}}"
        fi
        
        # Verifica se tem tabela de resultados
        if grep -qi "<table\\|<tbody\\|<tr.*<td" "$LAST_OUTPUT" 2>/dev/null; then
            echo ""
            echo -e "${{GREEN}}✅ Tabela de resultados encontrada!${{NC}}"
        fi
        
        # Verifica ViewState (importante para JSF)
        if grep -qi "viewstate\\|javax.faces.ViewState" "$LAST_OUTPUT" 2>/dev/null; then
            echo -e "${{GREEN}}✅ ViewState encontrado (sessão JSF ativa)${{NC}}"
        fi
        
    else
        echo -e "${{BLUE}}📋 Tipo: JSON/Outro${{NC}}"
        echo ""
        echo -e "${{BLUE}}📄 Primeiras linhas do conteúdo:${{NC}}"
        head -10 "$LAST_OUTPUT" | sed 's/^/   /'
    fi
    
    echo ""
    echo -e "${{BLUE}}📄 Conteúdo completo (últimas 20 linhas):${{NC}}"
    tail -20 "$LAST_OUTPUT" 2>/dev/null | sed 's/^/   /' || echo "   (arquivo vazio ou erro ao ler)"
    
    echo ""
    echo -e "${{BLUE}}📊 Resumo:${{NC}}"
    echo -e "   Arquivo: $LAST_OUTPUT"
    echo -e "   Tamanho: $FILE_SIZE bytes"
    echo -e "   Linhas: $(wc -l < "$LAST_OUTPUT" 2>/dev/null || echo 0)"
    
    # Verifica se o arquivo tem conteúdo significativo
    if [ "$FILE_SIZE" -lt 100 ]; then
        echo ""
        echo -e "${{YELLOW}}⚠️  Arquivo muito pequeno - pode indicar erro ou resposta vazia${{NC}}"
    elif [ "$FILE_SIZE" -gt 1000 ]; then
        echo ""
        echo -e "${{GREEN}}✅ Arquivo tem tamanho significativo - provavelmente contém dados${{NC}}"
    fi
    
    echo ""
}}

"""
        
        # Adiciona função principal
        script += """
# Função principal
main() {
"""
        
        if initial_get:
            script += "    request_0  # Requisição GET inicial para obter sessão\n"
        
        for i in range(1, len(requests) + 1):
            script += f"    request_{i}\n"
        
        script += """}

# Executa função principal
main

# Verifica resultados
verify_results

# Limpa cookie jar
rm -f "$COOKIE_JAR"

echo -e "${GREEN}Crawler concluído!${NC}"
"""
        
        return script
    
    def _request_to_curl(self, request: Dict, index: int, is_initial: bool = False) -> str:
        """Converte uma requisição em comando curl"""
        url = request.get('url', '')
        method = request.get('method', 'GET').upper()
        headers = request.get('headers', {})
        params = request.get('params', {})
        body = request.get('body', '')
        cookies = request.get('cookies', {})
        
        # Constrói URL com parâmetros se for GET
        if method == 'GET' and params:
            query_string = urlencode(params, doseq=True)
            if '?' in url:
                full_url = f"{url}&{query_string}"
            else:
                full_url = f"{url}?{query_string}"
        else:
            full_url = url
        
        # Remove jsessionid da URL se estiver presente (será gerenciado via cookies)
        if ';jsessionid' in full_url:
            full_url = full_url.split(';jsessionid')[0]
        
        # Inicia função
        func_name = "request_0" if index == 0 else f"request_{index}"
        func = f"{func_name}() {{\n"
        func += f"    echo -e \"${{BLUE}}Executando requisição {index if index > 0 else 'inicial'}: {method} {url[:80]}...${{NC}}\"\n"
        func += "    \n"
        
        # Constrói comando curl
        curl_cmd = "    curl -X "
        curl_cmd += method
        
        # Adiciona cookie jar para gerenciar cookies
        if is_initial:
            curl_cmd += ' \\\n        -c "$COOKIE_JAR"'
        else:
            curl_cmd += ' \\\n        -b "$COOKIE_JAR"'
            curl_cmd += ' \\\n        -c "$COOKIE_JAR"'
        
        # Adiciona cookies explícitos se houver
        if cookies:
            cookie_string = '; '.join([f"{k}={v}" for k, v in cookies.items()])
            if is_initial:
                curl_cmd += f' \\\n        -H "Cookie: {cookie_string}"'
            else:
                # Cookies já serão enviados via cookie jar, mas pode adicionar extras
                pass
        
        # Adiciona headers
        for key, value in headers.items():
            # Pula alguns headers que não são necessários ou que curl gerencia
            if key.lower() in ['host', 'connection', 'content-length', 'accept-encoding', 'cookie']:
                continue
            # Escapa aspas no valor
            escaped_value = str(value).replace('"', '\\"')
            curl_cmd += f' \\\n        -H "{key}: {escaped_value}"'
        
        # Adiciona headers essenciais se não estiverem presentes
        if is_initial:
            # Headers essenciais para GET inicial
            if 'accept' not in {k.lower(): v for k, v in headers.items()}:
                curl_cmd += ' \\\n        -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"'
            if 'accept-language' not in {k.lower(): v for k, v in headers.items()}:
                curl_cmd += ' \\\n        -H "Accept-Language: pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"'
        
        # Adiciona body se for POST/PUT/PATCH
        if method in ['POST', 'PUT', 'PATCH'] and body:
            # Se body contém ViewState, precisa substituir dinamicamente
            if 'javax.faces.ViewState' in body and not is_initial:
                # Para requisições POST após GET inicial, substitui ViewState dinamicamente
                func += "    # Extrai ViewState do HTML inicial\n"
                func += "    VIEWSTATE=$(extract_viewstate \"output_initial.html\")\n"
                func += "    echo -e \"${YELLOW}📋 ViewState extraído: $VIEWSTATE${NC}\"\n"
                func += "    \n"
                func += "    # Substitui ViewState no body\n"
                # Escapa o body e substitui ViewState
                body_escaped = body.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
                # Substitui ViewState por variável
                body_with_var = body_escaped.replace('javax.faces.ViewState=j_id1', 'javax.faces.ViewState=$VIEWSTATE')
                body_with_var = body_with_var.replace('javax.faces.ViewState%3Dj_id1', 'javax.faces.ViewState%3D$VIEWSTATE')
                func += f"    BODY=\"{body_with_var}\"\n"
                func += "    \n"
                curl_cmd += '        -d "$BODY"'
            else:
                # Se body é JSON, mantém como está
                if body.strip().startswith('{') or body.strip().startswith('['):
                    escaped_body = body.replace('"', '\\"').replace('$', '\\$')
                    curl_cmd += f' \\\n        -d "{escaped_body}"'
                else:
                    # Se não, trata como form data
                    # Escapa caracteres especiais
                    escaped_body = body.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
                    curl_cmd += f' \\\n        -d "{escaped_body}"'
        elif method in ['POST', 'PUT', 'PATCH'] and params:
            # Se tem params mas não body, usa form data
            form_data = urlencode(params, doseq=True)
            curl_cmd += f' \\\n        -d "{form_data}"'
        
        # Adiciona URL
        escaped_url = full_url.replace('"', '\\"')
        curl_cmd += f' \\\n        "{escaped_url}"'
        
        # Adiciona output
        output_file = "output_initial.html" if is_initial else f"output_{index}.json"
        curl_cmd += f' \\\n        -o "{output_file}"'
        curl_cmd += ' \\\n        -s'  # Silent mode
        curl_cmd += ' \\\n        -w "\\nHTTP Status: %{http_code}\\n"'
        curl_cmd += ' \\\n        -L'  # Segue redirects
        
        func += curl_cmd
        func += "\n    \n"
        func += "    if [ $? -eq 0 ]; then\n"
        if is_initial:
            func += f"        echo -e \"${{GREEN}}Requisição inicial concluída - cookies salvos${{NC}}\"\n"
            func += "        echo -e \"${YELLOW}Verificando cookies salvos...${NC}\"\n"
            func += '        if [ -f "$COOKIE_JAR" ]; then\n'
            func += '            echo -e "${GREEN}Cookies salvos com sucesso!${NC}"\n'
            func += "        fi\n"
        else:
            func += f"        echo -e \"${{GREEN}}Requisição {index} concluída com sucesso${{NC}}\"\n"
        func += "    else\n"
        func += f"        echo -e \"Erro na requisição {index if index > 0 else 'inicial'}\"\n"
        func += "        exit 1\n"
        func += "    fi\n"
        func += "}\n"
        
        return func

