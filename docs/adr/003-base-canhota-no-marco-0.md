# ADR 003: Base canhota no Marco 0 e base explícita na extração

**Status:** aceita
**Data:** 2026-11-20

## Contexto

A primeira versão dos critérios de aceitação assumiu um atleta ortodoxo (jab = mão esquerda), e o extrator de landmarks media e desenhava apenas o braço esquerdo, sem nenhum parâmetro de base.

Na primeira execução com o MediaPipe real, o vídeo de amostra mostrou pares de golpes em que o primeiro saía do lado esquerdo da imagem e o segundo do lado direito, onde estava o braço desenhado (`left_*`). Duas hipóteses foram verificadas:

| Hipótese | Verificação | Resultado |
|----------|-------------|-----------|
| Vídeo espelhado (câmera frontal do celular), invertendo esquerda e direita do MediaPipe | Texto da camiseta nos frames do preview | Texto legível da esquerda para a direita: vídeo **não** espelhado |
| MediaPipe rotulando o braço errado | Posição do punho `left_*` na imagem nos 8 golpes rotulados manualmente | `left_*` sempre no braço esquerdo anatômico: rótulo correto |

Conclusão: o rastreamento estava correto, e a suposição errada estava na especificação. O autor luta em base canhota, com a mão direita na frente. Os jabs do vídeo foram dados com a mão direita, que o extrator não media.

Esta descoberta aconteceu antes de qualquer gravação de calibração ou de teste, então nenhum conjunto de dados foi contaminado.

## Decisão

1. **O Marco 0 avalia apenas atleta canhoto.** Jab = mão direita, a mão da frente. A base ortodoxa sai do escopo por falta de dados, e nenhum resultado para ela pode ser reivindicado sem um conjunto de teste próprio.
2. **A base é um parâmetro obrigatório da extração** (`--stance orthodox|southpaw`), sem valor padrão. O erro original veio de um padrão silencioso ("braço esquerdo"). Exigir a base torna impossível gerar métricas do braço errado por esquecimento.
3. **A base é interpretação, não dado bruto.** O CSV de landmarks continua com os 33 pontos e os nomes anatômicos (`left_*`, `right_*`), idêntico para qualquer base. Apenas o preview e as métricas do `_meta.json` usam a base para escolher o braço da frente.
4. **Os documentos usam "braço da frente"** em vez de "braço esquerdo" ou "braço direito". O lado é definido uma única vez, pela base.
5. **O ângulo padrão de gravação passa a ser a diagonal de ~45° pelo lado da mão da frente** (ver `docs/protocolo-gravacao.md`). No vídeo frontal, o jab vai na direção da lente e quase não aparece em 2D: a razão entre a distância ombro/punho e o comprimento do braço, medida na imagem, ficou entre 0,04 e 0,27 na maioria dos picos de golpe.

## Alternativas consideradas

| Alternativa | Motivo para não usar |
|-------------|----------------------|
| Manter ortodoxo e gravar em base trocada | O sistema existe para o treino real do autor. Gravar fora da própria base geraria dados que não representam o uso |
| Espelhar o vídeo de canhoto e tratar como ortodoxo | Esconde a base real nos dados e introduz uma transformação que precisa ser lembrada em toda a pipeline |
| `--stance` com padrão `southpaw` | Repete o problema original: um padrão silencioso que pode estar errado para outro atleta |

## Consequências

**Positivas**
- A especificação passa a corresponder ao atleta real dos dados
- O mesmo código atende as duas bases, e o CSV continua reaproveitável
- A troca de braço fica visível no preview, que passa a desenhar os dois braços

**Negativas**
- Resultados do Marco 0 valem só para base canhota
- O vídeo de amostra atual (frontal, sem corpo inteiro) deixa de servir para os testes reais, que ficam pulados até uma nova gravação em diagonal

## Quando revisar

Quando houver vídeos de atletas ortodoxos com consentimento, para montar um conjunto de teste próprio dessa base.
