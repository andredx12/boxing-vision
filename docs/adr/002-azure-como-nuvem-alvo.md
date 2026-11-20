# ADR 002: Azure como nuvem alvo, com Marco 0 100% local

**Status:** aceita
**Data:** 2026-11-20

## Contexto

O autor tem acesso ao Microsoft Azure for Students (créditos por 12 meses) e quer demonstrar competências em cloud no portfólio. Ao mesmo tempo, a prioridade é provar a detecção de jab, e qualquer dependência de nuvem antes disso aumenta custo e complexidade sem gerar evidência.

## Decisão

1. **Marco 0 roda 100% local** (Python, OpenCV, MediaPipe). Nenhuma dependência de nuvem.
2. **Azure é a nuvem alvo** a partir da v0.2, introduzida só quando houver necessidade real.
3. **Código preparado para nuvem sem reescrever o detector:**
   - O detector recebe dados (landmarks) e devolve eventos. Não lê nem grava arquivos.
   - Leitura e escrita de arquivos ficam nas bordas (CLI, futura API).
   - Quando a nuvem entrar, cria-se uma interface de armazenamento com duas implementações: local e Azure Blob.

## Serviços candidatos

| Necessidade | Serviço candidato | Quando |
|-------------|-------------------|--------|
| Vídeos, JSON e resultados | Azure Blob Storage | v0.2 |
| API FastAPI + processamento | Azure Container Apps | v0.2 |
| Frontend React | Azure Static Web Apps | v0.2 |
| Explicações em texto a partir dos eventos | Azure AI Foundry | v0.3 ou depois |

O uso de IA generativa fica restrito a explicar dados estruturados já calculados. Ela não pode criar métricas, diagnósticos ou eventos.

## Regras de custo

- Antes de provisionar qualquer serviço: verificar disponibilidade, limites e custo no Azure for Students e registrar em `docs/azure/custos.md`
- Priorizar camadas gratuitas ou de consumo
- Configurar alerta de orçamento antes do primeiro deploy
- Vídeos brutos com política de retenção (padrão proposto: 30 dias)

## Consequências

**Positivas**
- O Marco 0 não depende de conta, rede ou créditos
- A arquitetura mostra separação clara entre domínio e infraestrutura

**Negativas**
- Nenhuma evidência de cloud no portfólio até a v0.2
- Os créditos expiram em 12 meses, então a v0.2 não deve atrasar demais
