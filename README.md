# Boxing Vision

Sistema de visão computacional que analisa vídeos de treino de boxe, identifica golpes, postura e movimentação, e gera observações técnicas para ajudar o atleta a evoluir.

> **Status:** em desenvolvimento (Marco 0). Implementado até agora: extração de landmarks de vídeo. A detecção de jab e as demais funcionalidades descritas abaixo **ainda não existem**.

## Objetivo

Construir um "treinador virtual" de apoio, com foco futuro no estilo defensivo de Floyd Mayweather, **sem substituir um treinador humano**.

Prioridades do projeto:

1. Portfólio profissional (engenharia de software, visão computacional e machine learning)
2. Uso pessoal nos treinos
3. Possível evolução para produto

## O que o v0.1 vai fazer

Entrada: um vídeo gravado (30 s a 3 min) de uma pessoa fazendo shadowboxing, com câmera fixa.

Saída:

- Vídeo MP4 anotado com esqueleto e eventos detectados
- Arquivo JSON com golpes, timestamps e nível de confiança
- Contagem de jabs e diretos por mão
- Observações de retorno à guarda após cada golpe

Interface: linha de comando (CLI).

```bash
boxing-vision analyze treino.mp4 --stance orthodox --output resultados/
```

## O que o v0.1 não faz

- Sparring ou mais de uma pessoa no vídeo
- Saber se um golpe acertou
- Análise em tempo real
- Score geral do atleta
- Comparação com Floyd Mayweather

## Roadmap

| Versão | Entrega principal |
|--------|-------------------|
| Marco 0 | Provar, com testes reproduzíveis, que o sistema identifica corretamente o jab em vídeos reais |
| v0.1 | CLI: pose, jab/direto, retorno à guarda, vídeo anotado e JSON |
| v0.2 | Interface web (React) + API (FastAPI) + histórico (PostgreSQL) |
| v0.3 | Mais golpes, esquivas, movimentação de pés e comparação entre sessões |
| v1.0 | Comparação com padrões defensivos de Mayweather |


## Stack

| Camada | Tecnologia |
|--------|------------|
| Visão computacional | Python, OpenCV, MediaPipe Pose |
| Detecção (v0.1) | Regras e máquina de estados sobre landmarks |
| Backend (v0.2+) | FastAPI |
| Frontend (v0.2+) | React, TypeScript, Vite |
| Banco (v0.2+) | PostgreSQL |
| Infra | Docker (backend e banco) |

## Setup

Requer Python 3.11 ou 3.12.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Baixe o modelo [pose_landmarker_full.task](https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task) e salve em `models/`.

Extrair landmarks de um vídeo:

```bash
python -m boxing_vision.extract videos/treino.mp4 --preview
```

Rodar os testes:

```bash
python -m pytest
```

## Limitações conhecidas

- A análise usa vídeo 2D de uma câmera só. Profundidade, força e distribuição de peso não são medidas.
- Velocidades são relativas (pixels por segundo normalizados), não velocidade física real.
- As regras ainda não foram validadas por um treinador de boxe. Toda observação vem com nível de confiança e deve ser tratada como sugestão.
- Trechos em que o atleta sai do quadro ou fica oculto são marcados como não analisáveis.

## Dados e privacidade

- Vídeos de treino não são versionados neste repositório.
- Trechos de lutas profissionais não são republicados sem licença.
- Vídeos de terceiros só com consentimento, seguindo a LGPD.

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| [`docs/criterios-aceitacao.md`](docs/criterios-aceitacao.md) | Como saber que cada funcionalidade está pronta |
| [`docs/adr/001-maquina-de-estados-no-marco-0.md`](docs/adr/001-maquina-de-estados-no-marco-0.md) | Máquina de estados em vez de modelo treinado |
| [`docs/adr/002-azure-como-nuvem-alvo.md`](docs/adr/002-azure-como-nuvem-alvo.md) | Azure como nuvem alvo, Marco 0 local |

Planejados: protocolo de gravação e rotulagem, arquitetura e relatório de resultados do Marco 0.

## Autor

**André Quintino**
[GitHub](https://github.com/andredx12) · [LinkedIn](https://linkedin.com/in/andre-quintino-dev)
