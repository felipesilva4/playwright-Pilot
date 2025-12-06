#!/usr/bin/env python3
"""
Gera relatórios quando crawler HTTP não é viável
"""

from typing import Dict, List
from pathlib import Path
from datetime import datetime


class ReportGenerator:
    """Gera relatórios explicativos sobre viabilidade de crawler"""
    
    def __init__(self, output_dir: str = "outputs/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_report(self, analysis: Dict, site_name: str, url: str, goal: str) -> str:
        """
        Gera relatório markdown sobre a análise
        
        Args:
            analysis: Resultado da análise de viabilidade
            site_name: Nome do site
            url: URL analisada
            goal: Objetivo da automação
        
        Returns:
            Caminho do arquivo gerado
        """
        filename = self._get_filename(site_name)
        filepath = self.output_dir / filename
        
        content = self._build_report(analysis, url, goal)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ Relatório gerado: {filepath}")
            return str(filepath)
            
        except Exception as e:
            print(f"❌ Erro ao gerar relatório: {e}")
            return ""
    
    def _get_filename(self, site_name: str) -> str:
        """Gera nome do arquivo do relatório"""
        normalized = site_name.lower().replace(' ', '-').replace('.', '-')
        normalized = ''.join(c for c in normalized if c.isalnum() or c in ['-', '_'])
        return f"{normalized}_report.md"
    
    def _build_report(self, analysis: Dict, url: str, goal: str) -> str:
        """Constrói conteúdo do relatório"""
        report = f"""# Relatório de Análise de Crawler HTTP

**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**URL:** {url}  
**Objetivo:** {goal}

## Resumo

"""
        
        if analysis.get('viable', False):
            report += f"✅ **Crawler HTTP viável**\n\n"
            report += f"Encontradas {analysis.get('viable_count', 0)} requisição(ões) que podem ser replicadas com curl/HTTP puro.\n\n"
        else:
            report += f"❌ **Crawler HTTP não viável**\n\n"
            report += f"Motivo: {analysis.get('reason', 'Desconhecido')}\n\n"
        
        report += f"""
## Estatísticas

- **Total de requisições capturadas:** {analysis.get('total_requests', 0)}
- **Requisições viáveis:** {analysis.get('viable_count', 0)}
- **Requisições não viáveis:** {analysis.get('non_viable_count', 0)}

"""
        
        # Detalhes das requisições viáveis
        viable_requests = analysis.get('viable_requests', [])
        if viable_requests:
            report += "## Requisições Viáveis\n\n"
            for i, req in enumerate(viable_requests, 1):
                req_analysis = req.get('analysis', {})
                report += f"### Requisição {i}\n\n"
                report += f"- **URL:** `{req.get('url', '')}`\n"
                report += f"- **Método:** {req.get('method', '')}\n"
                report += f"- **Complexidade:** {req_analysis.get('complexity', 'unknown')}\n"
                report += f"- **Motivo:** {req_analysis.get('reason', '')}\n"
                
                requirements = req_analysis.get('requirements', [])
                if requirements:
                    report += f"- **Requisitos:**\n"
                    for req_item in requirements:
                        report += f"  - {req_item}\n"
                
                report += "\n"
        
        # Detalhes das requisições não viáveis
        non_viable_requests = analysis.get('non_viable_requests', [])
        if non_viable_requests:
            report += "## Requisições Não Viáveis\n\n"
            for i, req in enumerate(non_viable_requests, 1):
                req_analysis = req.get('analysis', {})
                report += f"### Requisição {i}\n\n"
                report += f"- **URL:** `{req.get('url', '')}`\n"
                report += f"- **Método:** {req.get('method', '')}\n"
                report += f"- **Motivo:** {req_analysis.get('reason', '')}\n"
                
                requirements = req_analysis.get('requirements', [])
                if requirements:
                    report += f"- **Requisitos necessários:**\n"
                    for req_item in requirements:
                        report += f"  - {req_item}\n"
                
                report += "\n"
        
        # Recomendações
        report += "## Recomendações\n\n"
        
        if analysis.get('viable', False):
            report += "✅ É possível criar um crawler HTTP puro usando os scripts Bash gerados.\n\n"
            report += "**Próximos passos:**\n"
            report += "1. Execute o script Bash gerado em `outputs/crawlers/`\n"
            report += "2. Verifique os arquivos de output gerados\n"
            report += "3. Adapte os scripts conforme necessário\n"
        else:
            report += "❌ Não é recomendado criar um crawler HTTP puro para este caso.\n\n"
            report += "**Alternativas:**\n"
            report += "1. Use automação com Playwright/Selenium (mantenha o navegador)\n"
            report += "2. Analise se há APIs públicas disponíveis\n"
            report += "3. Considere usar ferramentas de scraping mais avançadas\n"
            report += "4. Verifique se há documentação de API oficial\n"
        
        report += "\n---\n"
        report += f"\n*Relatório gerado automaticamente em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        
        return report

