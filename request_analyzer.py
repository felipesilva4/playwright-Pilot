#!/usr/bin/env python3
"""
Módulo para analisar viabilidade de requisições HTTP para crawlers
"""

from typing import Dict, List
from ollama_client import OllamaClient


class RequestAnalyzer:
    """Analisa requisições HTTP e determina viabilidade para crawler"""
    
    def __init__(self, ollama_client: OllamaClient):
        self.ollama = ollama_client
    
    def analyze_requests(self, requests: List[Dict]) -> Dict:
        """
        Analisa lista de requisições e determina quais são viáveis
        
        Args:
            requests: Lista de requisições capturadas
        
        Returns:
            Dict com análise completa
        """
        if not requests:
            return {
                "viable": False,
                "reason": "Nenhuma requisição capturada",
                "viable_requests": [],
                "non_viable_requests": []
            }
        
        viable_requests = []
        non_viable_requests = []
        
        # Analisa cada requisição
        for req in requests:
            analysis = self.ollama.analyze_request(req)
            
            if analysis.get("viable", False):
                req["analysis"] = analysis
                viable_requests.append(req)
            else:
                req["analysis"] = analysis
                non_viable_requests.append(req)
        
        # Determina se pelo menos uma requisição é viável
        overall_viable = len(viable_requests) > 0
        
        return {
            "viable": overall_viable,
            "total_requests": len(requests),
            "viable_count": len(viable_requests),
            "non_viable_count": len(non_viable_requests),
            "viable_requests": viable_requests,
            "non_viable_requests": non_viable_requests,
            "reason": self._generate_reason(viable_requests, non_viable_requests)
        }
    
    def _generate_reason(self, viable: List[Dict], non_viable: List[Dict]) -> str:
        """Gera explicação sobre a viabilidade"""
        if len(viable) > 0:
            return f"{len(viable)} requisição(ões) viável(is) para crawler HTTP puro"
        elif len(non_viable) > 0:
            reasons = [req.get("analysis", {}).get("reason", "Desconhecido") for req in non_viable[:3]]
            return f"Nenhuma requisição viável. Motivos: {', '.join(set(reasons))}"
        else:
            return "Nenhuma requisição para analisar"

