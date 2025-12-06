# Playwright Pilot

Sistema de automação web inteligente que utiliza Playwright e Ollama para criar crawlers HTTP automatizados. O sistema analisa sites, captura requisições HTTP e gera scripts Bash com `curl` para crawlers puros HTTP quando possível.

## 🎯 Objetivo

Automatizar a criação de crawlers web através de:
- **Análise inteligente** de páginas web usando modelos LLM locais (Ollama)
- **Captura automática** de requisições HTTP durante a navegação
- **Geração de scripts Bash** com comandos `curl` para crawlers HTTP puros
- **Validação visual** de resultados usando screenshots e análise por IA

## 🚀 Funcionalidades

- ✅ Automação web com Playwright
- ✅ Integração com Ollama para tomada de decisões inteligentes
- ✅ Captura de requisições HTTP (headers, cookies, parâmetros)
- ✅ Geração automática de scripts Bash com `curl`
- ✅ Suporte a sites JSF (ViewState dinâmico)
- ✅ Validação de resultados via screenshots
- ✅ Logs detalhados em tempo real
- ✅ Timeout configurável (padrão: 1 minuto)

## 📋 Requisitos

- Python 3.8+
- Playwright
- Ollama instalado e rodando localmente
- Modelo Ollama: `aliafshar/gemma3-it-qat-tools:4b` (ou outro compatível)

## 🔧 Instalação

```bash
# Clone o repositório
git clone git@github.com:felipesilva4/playwright-Pilot.git
cd playwright-Pilot

# Crie um ambiente virtual
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instale as dependências
pip install -r requirements.txt

# Instale os browsers do Playwright
playwright install chromium
```

## 📦 Dependências

- `playwright>=1.40.0` - Automação web
- `requests>=2.31.0` - Comunicação com Ollama API
- `Pillow` - Processamento de imagens

## 🎮 Uso

### Exemplo Básico

```bash
python playwright_crawler.py \
  --url "https://exemplo.com/pesquisa" \
  --goal "pesquisar por nome da parte jose silva e retornar os resultados"
```

### Pesquisar por Número de Processo

```bash
python playwright_crawler.py \
  --url "https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam" \
  --goal "pesquisar pelo processo 0001333-58.2010.4.03.6000 e retornar os resultados"
```

### Opções

- `--url`: URL inicial para automação (obrigatório)
- `--goal`: Objetivo da automação (obrigatório)
- `--model`: Modelo Ollama a usar (padrão: `aliafshar/gemma3-it-qat-tools:4b`)
- `--headless`: Executar navegador em modo headless (padrão: False)
- `--show-browser`: Mostrar navegador (sobrescreve --headless)

## 📁 Estrutura de Arquivos

```
PlaywrightPilot/
├── playwright_crawler.py      # Script principal CLI
├── ollama_client.py            # Cliente Ollama
├── http_capture.py             # Captura de requisições HTTP
├── request_analyzer.py         # Análise de viabilidade
├── bash_generator.py           # Geração de scripts Bash
├── report_generator.py         # Geração de relatórios
├── outputs/                    # Diretório para outputs
│   ├── crawlers/               # Scripts Bash gerados
│   │   └── <nome_site>.sh
│   ├── html/                   # HTML dos resultados
│   ├── screenshots/            # Screenshots de validação
│   ├── logs/                   # Logs de execução
│   └── requests/               # Requisições capturadas
├── requirements.txt
└── README.md
```

## 🔄 Fluxo de Execução

1. **Navegação**: Playwright navega para a URL fornecida
2. **Análise**: Ollama analisa a página e decide próximas ações
3. **Execução**: Playwright executa ações (preencher campos, clicar botões)
4. **Captura**: Sistema captura todas as requisições HTTP
5. **Validação**: Screenshots são analisados para confirmar resultados
6. **Geração**: Script Bash é gerado com comandos `curl`
7. **Verificação**: Script Bash inclui função para verificar resultados

## 📝 Exemplo de Script Bash Gerado

O sistema gera scripts Bash completos com:
- Gerenciamento de cookies (cookie jar)
- Extração dinâmica de ViewState (para sites JSF)
- Função de verificação de resultados
- Headers e parâmetros corretos
- Tratamento de erros

## 🛠️ Desenvolvimento

### Executar Testes

```bash
# Teste com site específico
python playwright_crawler.py \
  --url "https://exemplo.com" \
  --goal "pesquisar por X"
```

### Verificar Scripts Gerados

```bash
# Executar script Bash gerado
bash outputs/crawlers/<nome_site>.sh
```

## 📊 Logs

Os logs são salvos em tempo real em `outputs/logs/` com timestamp. Cada execução gera um novo arquivo de log.

## ⚙️ Configuração

### Modelos Ollama Suportados

- `aliafshar/gemma3-it-qat-tools:4b` (recomendado - rápido)
- `ministral-3:3b` (alternativa leve)

### Timeouts

- **Timeout total**: 60 segundos (configurável)
- **Timeout por ação**: 60 segundos
- **Timeout de navegação**: 25 segundos (com retry)

## 🐛 Troubleshooting

### Erro: "Modelo não responde"
- Verifique se Ollama está rodando: `ollama serve`
- Verifique se o modelo está instalado: `ollama list`

### Erro: "Navegação falhou"
- Tente executar sem `--headless` para ver o que está acontecendo
- Verifique a conectividade com o site

### Script Bash não funciona
- Verifique se o ViewState foi extraído corretamente
- Verifique se os cookies estão sendo gerenciados
- Execute o script manualmente para ver erros detalhados

## 📄 Licença

Este projeto é de código aberto.

## 👤 Autor

Felipe Silva

## 🤝 Contribuições

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues e pull requests.
