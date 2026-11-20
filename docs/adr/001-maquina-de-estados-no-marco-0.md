# ADR 001: Máquina de estados em vez de modelo treinado no Marco 0

**Status:** aceita
**Data:** 2026-11-20

## Contexto

O Marco 0 precisa provar que o sistema identifica o jab em vídeos reais. Temos poucos dados (cerca de 10 clipes), nenhum treinador para validar rótulos, 3 horas por semana de desenvolvimento e um PC com 8 GB de RAM sem GPU dedicada.

## Decisão

A detecção de jab no Marco 0 usa uma máquina de estados baseada em regras sobre os landmarks do MediaPipe Pose:

```
REPOUSO -> EXTENSAO -> PICO -> RECOLHIMENTO -> REPOUSO
                         |
                         v
                   emite evento "jab"
```

O evento `jab` é emitido quando o pico de extensão é confirmado e o braço começa a recolher. O retorno completo à guarda **não** é condição para o jab existir; ele será avaliado por um detector separado (`retorno_guarda`) no Marco 1.

As transições dependem de ângulo do cotovelo, distância punho/ombro normalizada, velocidade do punho e tempo. Todos os limiares ficam em arquivo de configuração.

Pipeline do Marco 0:

```
Vídeo MP4
  -> OpenCV + MediaPipe: landmarks e qualidade da pose
  -> Processamento temporal: suavização, ângulos, normalização, velocidade
  -> Máquina de estados: eventos de jab
  -> Saídas: JSON de eventos + MP4 anotado
```

## Alternativas consideradas

| Alternativa | Motivo para não usar agora |
|-------------|----------------------------|
| Classificador temporal (LSTM, 1D CNN) | Exige muito mais dados rotulados do que temos |
| Modelo de ação pré-treinado | Pesado para o hardware e difícil de explicar cada decisão |

## Consequências

**Positivas**
- Cada detecção é explicável (dá pra dizer qual regra disparou)
- Funciona com poucos dados
- Fácil de testar de forma unitária e determinística
- Roda bem em CPU

**Negativas**
- Limiares podem não generalizar para outros ângulos, pessoas ou estilos
- Exige ajuste manual

## Quando revisar

Se, depois de calibrada, a máquina de estados não atingir as metas do Marco 0, ou quando houver dados rotulados suficientes para treinar um classificador e comparar com esta baseline. Qualquer mudança motivada pelo resultado do teste exige um novo conjunto de teste independente (ver `criterios-aceitacao.md`, Disciplina experimental).