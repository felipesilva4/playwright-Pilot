#!/usr/bin/env python3
"""
Módulo para capturar requisições HTTP durante navegação com Playwright
"""

import json
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs
from datetime import datetime


class HTTPCapture:
    """Captura e armazena requisições HTTP do Playwright"""
    
    def __init__(self):
        self.requests: List[Dict] = []
        self.responses: List[Dict] = []
        self.cookies: Dict[str, str] = {}  # Armazena cookies por domínio
    
    def on_request(self, request):
        """Callback para capturar requisições"""
        try:
            # Extrai dados da requisição
            url = request.url
            method = request.method
            headers = request.headers
            post_data = request.post_data
            
            # Extrai cookies do header Cookie se existir
            cookie_header = headers.get('cookie', '')
            request_cookies = {}
            if cookie_header:
                for cookie_pair in cookie_header.split(';'):
                    if '=' in cookie_pair:
                        name, value = cookie_pair.strip().split('=', 1)
                        request_cookies[name.strip()] = value.strip()
            
            # Extrai parâmetros da URL
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            
            # Converte query_params de listas para valores únicos
            params = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}
            
            request_data = {
                "timestamp": datetime.now().isoformat(),
                "url": url,
                "method": method,
                "headers": dict(headers),
                "params": params,
                "body": post_data if post_data else None,
                "resource_type": request.resource_type,
                "cookies": request_cookies  # Cookies enviados na requisição
            }
            
            self.requests.append(request_data)
            
        except Exception as e:
            print(f"⚠️  Erro ao capturar requisição: {e}")
    
    def on_response(self, response):
        """Callback para capturar respostas"""
        try:
            # Extrai cookies da resposta
            set_cookie_headers = response.headers.get('set-cookie', [])
            if isinstance(set_cookie_headers, str):
                set_cookie_headers = [set_cookie_headers]
            
            # Processa cookies
            parsed_url = urlparse(response.url)
            domain = parsed_url.netloc
            
            for cookie_header in set_cookie_headers:
                # Extrai nome e valor do cookie (formato: nome=valor; atributos)
                if '=' in cookie_header:
                    cookie_parts = cookie_header.split(';')[0].strip()
                    if '=' in cookie_parts:
                        cookie_name, cookie_value = cookie_parts.split('=', 1)
                        self.cookies[cookie_name.strip()] = cookie_value.strip()
            
            response_data = {
                "timestamp": datetime.now().isoformat(),
                "url": response.url,
                "status": response.status,
                "headers": dict(response.headers),
                "request_url": response.request.url if response.request else None,
                "cookies": dict(self.cookies)  # Inclui cookies acumulados
            }
            
            self.responses.append(response_data)
            
        except Exception as e:
            print(f"⚠️  Erro ao capturar resposta: {e}")
    
    def get_requests(self) -> List[Dict]:
        """Retorna todas as requisições capturadas"""
        return self.requests
    
    def get_responses(self) -> List[Dict]:
        """Retorna todas as respostas capturadas"""
        return self.responses
    
    def get_requests_by_type(self, resource_type: str) -> List[Dict]:
        """Filtra requisições por tipo de recurso"""
        return [req for req in self.requests if req.get("resource_type") == resource_type]
    
    def get_api_requests(self) -> List[Dict]:
        """Retorna apenas requisições que parecem ser APIs (JSON, XML, etc)"""
        api_types = ["xhr", "fetch", "websocket"]
        api_requests = []
        
        for req in self.requests:
            if req.get("resource_type") in api_types:
                api_requests.append(req)
            # Também verifica por extensões comuns de API
            url = req.get("url", "").lower()
            if any(ext in url for ext in [".json", "/api/", "/ajax/", "/rest/"]):
                api_requests.append(req)
        
        return api_requests
    
    def save_to_file(self, filename: str):
        """Salva requisições capturadas em arquivo JSON"""
        data = {
            "requests": self.requests,
            "responses": self.responses,
            "total_requests": len(self.requests),
            "total_responses": len(self.responses)
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ Requisições salvas em: {filename}")
        except Exception as e:
            print(f"❌ Erro ao salvar requisições: {e}")
    
    def clear(self):
        """Limpa requisições e respostas capturadas"""
        self.requests = []
        self.responses = []

