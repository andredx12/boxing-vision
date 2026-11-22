# ADR 004: Correspondência por programação dinâmica em vez do algoritmo húngaro

**Status:** aceita
**Data:** 2026-11-22

## Contexto

Os critérios de aceitação definem a regra de correspondência entre detecções e jabs rotulados: um para um, global, com centros a no máximo 200 ms, primeiro maximizando o número de pares, depois minimizando a soma das diferenças, com empates resolvidos pela ordem de `inicio_ms`. O texto também fixava a implementação: algoritmo húngaro com penalidade `M` para pares inválidos.

A implementação de referência do húngaro em Python é `scipy.optimize.linear_sum_assignment`, que não está nas dependências do projeto. Um clipe do Marco 0 tem de 10 a 30 segundos e poucas dezenas de eventos, então desempenho não justifica uma dependência nova.

O húngaro com penalidade `M` resolve as duas primeiras prioridades, mas não tem desempate definido: com custos iguais, a solução escolhida depende de detalhes internos do algoritmo. Para cumprir a regra de empate seria preciso perturbar os custos, o que adiciona código difícil de verificar.

## Decisão

1. A correspondência é feita por programação dinâmica sobre as duas listas ordenadas no tempo, em `boxing_vision/evaluate.py`, sem dependência nova.
2. Fundamento: todos os eventos estão na mesma linha do tempo. Se duas correspondências se cruzam (detecção de centro mais cedo com rótulo de centro mais tarde e vice-versa), trocar os pares não aumenta nenhuma distância além da maior das duas originais, então os pares continuam dentro de 200 ms, a soma não aumenta e o desempate melhora. Logo, a solução ótima não tem cruzamentos e pode ser encontrada percorrendo as listas em ordem, com custo proporcional a detecções vezes rótulos.
3. As três prioridades ficam explícitas na comparação entre soluções: (número de pares, soma das distâncias, desempate). Distâncias são calculadas em inteiros com o dobro do centro (`inicio_ms + fim_ms`), sem arredondamento de ponto flutuante.
4. A ordem usada é a do centro do evento, depois `inicio_ms`. O argumento do item 2 vale para a ordem dos centros e falha para a ordem de `inicio_ms` quando eventos de durações diferentes se sobrepõem; isso foi encontrado pelo teste de busca exaustiva durante a implementação. Para eventos que não se sobrepõem, as duas ordens são idênticas, e o protocolo de rotulagem proíbe jabs rotulados sobrepostos.
5. Desempate: entre soluções com o mesmo número de pares e a mesma soma, vence a que pareia primeiro os rótulos mais cedo e, depois, as detecções mais cedo, nessa ordem.
6. A correção é verificada por um teste que compara o resultado com uma busca exaustiva de todas as correspondências possíveis em milhares de casos pequenos gerados com semente fixa, e por um teste de que a ordem da entrada não muda o resultado.

Os critérios de aceitação passam a citar a programação dinâmica na ordem do tempo (este ADR) no lugar do algoritmo húngaro, e a regra de empate passa a citar a ordem do centro e depois `inicio_ms`.

## Alternativas consideradas

| Alternativa | Motivo para não usar |
|-------------|----------------------|
| `scipy.optimize.linear_sum_assignment` com penalidade `M` | Dependência nova para um problema de poucas dezenas de eventos, e o desempate continuaria indefinido |
| Húngaro implementado em Python puro | Cerca do dobro de código para o mesmo resultado; o desempate exigiria perturbar os custos |
| Escolha gulosa (par mais próximo primeiro) | Não é ótima: há casos em que deixa um jab sem par mesmo existindo solução com todos pareados (coberto por teste) |
| Busca exaustiva | Correta, mas cresce de forma exponencial; serve apenas como referência nos testes |

## Consequências

**Positivas**
- Nenhuma dependência nova
- Desempate determinístico e documentado
- Correção verificada contra uma referência independente

**Negativas**
- O fundamento depende de os eventos estarem numa única linha do tempo com custo igual à distância entre centros. Se o custo mudar (por exemplo, considerar início e fim separadamente), o argumento precisa ser revisto e o teste de busca exaustiva vai indicar a quebra
