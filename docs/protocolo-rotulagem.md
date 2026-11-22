# Protocolo de rotulagem

Regras para criar os rótulos manuais dos vídeos de calibração e de teste do Marco 0. Os rótulos são a referência contra a qual o detector é avaliado (ver [critérios de aceitação](criterios-aceitacao.md)), então dois rotuladores seguindo este documento devem chegar a tempos parecidos para o mesmo vídeo.

Base do Marco 0: atleta canhoto (southpaw). **Jab = mão direita**, a mão da frente. O direto é dado com a mão esquerda. Ver [ADR 003](adr/003-base-canhota-no-marco-0.md).

## Regras gerais

- Rotular **antes** de rodar o detector no clipe e sem olhar a saída dele. Ver a detecção antes induz a ajustar o rótulo ao que o algoritmo achou.
- Rotular sempre em pausa, avançando frame a frame nos trechos de início e fim de cada evento.
- Usar sempre a mesma ferramenta e a mesma versão dentro de um conjunto de dados, e registrar qual foi no arquivo.
- Um jab tecnicamente ruim (extensão incompleta, sem retorno à guarda) continua sendo `jab`. A qualidade técnica é registrada em `marcacoes`, não no `tipo`.
- Na dúvida entre um jab e uma finta, aplicar a regra de casos limite e adicionar a marcação `duvida`. Nunca deixar um movimento sem rótulo por dúvida.

## Formato do arquivo

Um arquivo por vídeo em `labels/<nome do vídeo sem extensão>.json`. Exemplo para `videos/treino_2026-11-27_01.mp4`:

```json
{
  "video": "treino_2026-11-27_01.mp4",
  "conjunto": "calibracao",
  "base": "southpaw",
  "ferramenta": "mpv 0.39.0",
  "rotulador": "andre",
  "data_rotulagem": "2026-11-28",
  "trecho_analisado": { "inicio_ms": 2100, "fim_ms": 27850 },
  "eventos": [
    {
      "inicio_ms": 2100,
      "fim_ms": 4050,
      "tipo": "guarda_parada",
      "mao": null,
      "marcacoes": [],
      "grupo": null,
      "observacao": ""
    },
    {
      "inicio_ms": 4317,
      "fim_ms": 4550,
      "tipo": "jab",
      "mao": "direita",
      "marcacoes": ["sem_retorno"],
      "grupo": null,
      "observacao": ""
    },
    {
      "inicio_ms": 6083,
      "fim_ms": 6250,
      "tipo": "jab",
      "mao": "direita",
      "marcacoes": [],
      "grupo": "g1",
      "observacao": ""
    },
    {
      "inicio_ms": 6417,
      "fim_ms": 6617,
      "tipo": "jab",
      "mao": "direita",
      "marcacoes": ["extensao_parcial"],
      "grupo": "g1",
      "observacao": ""
    },
    {
      "inicio_ms": 8200,
      "fim_ms": 8433,
      "tipo": "direto",
      "mao": "esquerda",
      "marcacoes": [],
      "grupo": null,
      "observacao": ""
    },
    {
      "inicio_ms": 10050,
      "fim_ms": 10150,
      "tipo": "finta_jab",
      "mao": "direita",
      "marcacoes": ["duvida"],
      "grupo": "g2",
      "observacao": "punho avançou pouco, mas rápido"
    },
    {
      "inicio_ms": 10283,
      "fim_ms": 10517,
      "tipo": "jab",
      "mao": "direita",
      "marcacoes": [],
      "grupo": "g2",
      "observacao": ""
    }
  ]
}
```

No exemplo, o grupo `g1` é um double jab (dois `jab`) e o grupo `g2` é uma finta seguida de jab (`finta_jab` e `jab`).

### Campos do arquivo

| Campo | Obrigatório | Significado |
|-------|-------------|-------------|
| `video` | sim | Nome do arquivo de vídeo, com extensão |
| `conjunto` | sim | `calibracao` ou `teste` |
| `base` | sim | `southpaw` no Marco 0 |
| `ferramenta` | sim | Nome e versão do player usado para ler os tempos |
| `rotulador` | sim | Quem rotulou |
| `data_rotulagem` | sim | Data em que o rótulo foi feito (AAAA-MM-DD) |
| `trecho_analisado` | sim | Intervalo do vídeo que entra na avaliação. Começa depois que o atleta entrou em guarda e termina antes de ele sair dela, excluindo o manuseio da câmera (ver [protocolo de gravação](protocolo-gravacao.md)). Detecções fora desse trecho são ignoradas |
| `eventos` | sim | Lista de eventos, ordenada por `inicio_ms` |

### Campos de cada evento

| Campo | Tipo | Significado |
|-------|------|-------------|
| `inicio_ms` | inteiro | Tempo do primeiro frame do evento, em milissegundos, lido no player |
| `fim_ms` | inteiro | Tempo do último frame do evento, em milissegundos, lido no player |
| `tipo` | texto | Um dos valores da tabela de tipos abaixo |
| `mao` | texto ou `null` | Mão anatômica que executa o movimento: `direita`, `esquerda` ou `null` quando nenhuma mão é o foco (guarda parada, movimentação de pés). É a mão do atleta, não o lado da imagem |
| `marcacoes` | lista de texto | Zero ou mais valores da tabela de marcações abaixo. Lista vazia quando não há nenhuma |
| `grupo` | texto ou `null` | Identificador que liga eventos de uma mesma sequência (double jab, finta seguida de jab). `null` para eventos isolados |
| `observacao` | texto | Apenas texto livre. Pode ser vazio, exceto quando houver a marcação `duvida` |

Os nomes `inicio_ms`, `fim_ms`, `tipo` e `mao` são os mesmos da saída do detector (CA-08), o que permite comparar rótulo e detecção campo a campo.

### Tipos de evento

| `tipo` | Conta como | `mao` |
|--------|------------|-------|
| `jab` | positivo | `direita` |
| `direto` | negativo | `esquerda` |
| `guarda_parada` | negativo | `null` |
| `movimentacao_pes` | negativo | `null` |
| `extensao_sem_golpe` | negativo | `direita` |
| `ajuste_guarda` | negativo | `direita` (ou `esquerda`, se for a mão de trás) |
| `finta_jab` | negativo | `direita` |

O jab com extensão parcial e o double jab não têm tipo próprio: são eventos `jab`, identificados pela marcação `extensao_parcial` e pelo campo `grupo` (ver casos limite).

### Marcações

| Valor em `marcacoes` | Quando usar | Tipos permitidos |
|----------------------|-------------|------------------|
| `sem_retorno` | A mão não voltou corretamente à guarda depois do golpe (necessário para o CA-05) | `jab`, `direto` |
| `extensao_parcial` | Jab completo (avanço, pico e recolhimento com velocidade de golpe), mas com o cotovelo claramente dobrado no pico | `jab` |
| `duvida` | O rotulador não tem certeza do tipo ou dos tempos. O motivo é obrigatório em `observacao` | todos |
| `oclusao` | Braço parcialmente escondido, borrado ou fora do quadro durante o evento | todos |

Com essas marcações, o relatório pode mostrar à parte o recall dos jabs com `extensao_parcial` e com `sem_retorno`, sem retirá-los da métrica principal.

### Efeito da marcação `duvida` na avaliação

A avaliação reporta precisão e recall em duas versões, para medir o quanto a incerteza da rotulagem afeta o resultado:

| Versão | Eventos usados |
|--------|----------------|
| Com dúvida (métrica principal) | Todos os eventos rotulados |
| Sem dúvida (métrica secundária) | Todos, exceto os marcados com `duvida` |

Na versão sem dúvida:

- A correspondência é feita primeiro com todos os eventos, pela regra dos critérios de aceitação
- Jabs rotulados com `duvida` saem da conta, junto com a detecção que tiver formado par com eles. Se não tiverem par, também não contam como falso negativo
- Detecções sem par classificadas como duplicadas de um jab com `duvida` (centro a até 200 ms dele, fora de qualquer evento negativo) também saem da conta, em vez de contar como falso positivo
- Detecções sem par cujo centro cai dentro do intervalo de um evento negativo com `duvida` também saem da conta, em vez de contar como falso positivo

O relatório informa quantos eventos têm `duvida` e mostra as duas versões lado a lado. A métrica principal é sempre a versão com dúvida, pelo mesmo motivo que os jabs perdidos por falha de pose continuam no recall principal: retirar os casos difíceis inflaria o resultado. Uma diferença grande entre as duas versões indica que as regras deste protocolo precisam ficar mais claras antes de gravar mais dados.

### Grupos

O campo `grupo` liga eventos que formam uma sequência. O valor é um identificador curto e único dentro do arquivo (`g1`, `g2`, ...). O tipo da sequência é deduzido dos tipos dos eventos do grupo, na ordem de `inicio_ms`:

| Eventos do grupo | Sequência |
|------------------|-----------|
| `jab`, `jab` | Double jab |
| `finta_jab`, `jab` | Finta seguida de jab |

Outras combinações não são usadas no Marco 0. Um-dois (jab seguido de direto) não leva grupo: são dois eventos isolados.

### Validações do arquivo

- `inicio_ms` < `fim_ms` em todo evento
- Todos os eventos dentro de `trecho_analisado`
- Eventos `jab` não se sobrepõem entre si
- `tipo` e `mao` seguem a tabela de tipos
- Cada valor de `marcacoes` existe na tabela de marcações e é permitido para o `tipo` do evento
- `observacao` não é vazia quando `marcacoes` contém `duvida`
- Cada `grupo` tem exatamente dois eventos, numa das combinações da tabela de grupos

## Como marcar início e fim de um jab

A referência é o punho direito em relação ao ombro direito. O critério segue a definição operacional dos critérios de aceitação: o evento vai do começo da extensão até o pico, e **termina no início do recolhimento**. O retorno à guarda não faz parte do jab.

**Início (`inicio_ms`):** primeiro frame em que o punho da frente sai da posição de guarda em direção ao alvo e continua avançando nos frames seguintes.

Procedimento:

1. Achar visualmente o golpe em velocidade normal.
2. Voltar alguns frames até a mão estar parada na guarda.
3. Avançar frame a frame. O início é o primeiro frame em que o punho está visivelmente mais à frente do que no frame anterior **e** segue avançando nos dois frames seguintes. Um deslocamento que não continua é tremor ou ajuste e não marca início.

**Fim (`fim_ms`):** frame de maior extensão do braço, ou seja, o último frame antes de o punho começar a voltar em direção ao ombro.

Procedimento:

1. A partir do início, avançar frame a frame enquanto o punho se afasta do ombro.
2. O fim é o frame em que o punho está mais longe do ombro. No frame seguinte ele já está mais perto.
3. Se dois ou mais frames seguidos parecerem iguais no pico, marcar o **primeiro** deles. Se o braço ficar parado estendido por mais de **300 ms (valor provisório)**, marcar o primeiro frame do pico e adicionar a marcação `duvida` com a observação "braço parado no pico", porque o detector pode tratar esse caso como `ambiguo`.

Precisão esperada: a 30 FPS cada frame dura cerca de 33 ms. Um erro de um frame no início ou no fim é aceitável e fica bem abaixo da tolerância de 200 ms da regra de correspondência.

## Como rotular os 8 movimentos da tabela de negativos

A tabela de movimentos negativos obrigatórios dos critérios de aceitação tem 8 itens. Seis deles são rotulados com tipos negativos. Os outros dois (jab com extensão parcial e double jab) são rotulados como `jab`, porque são jabs reais, e entram no conjunto de teste para medir casos difíceis.

### 1. Direto (mão de trás)

- `tipo`: `direto`, `mao`: `esquerda`
- Início e fim com a mesma regra do jab, aplicada ao punho e ombro esquerdos
- Se o direto vier logo depois de um jab (um-dois), rotular os dois eventos separadamente, sem grupo

### 2. Guarda parada

- `tipo`: `guarda_parada`, `mao`: `null`
- Trecho de pelo menos **1 segundo (valor provisório)** com o atleta em guarda, sem golpe e sem deslocamento dos pés
- Início: primeiro frame em que o corpo está parado na guarda. Fim: último frame antes de qualquer movimento de golpe, finta ou pés
- Pequenas oscilações naturais do corpo (respiração, balanço leve) continuam sendo guarda parada
- Os 2 segundos de guarda do começo e do fim do clipe podem ser rotulados como `guarda_parada`, desde que estejam dentro de `trecho_analisado`

### 3. Movimentação de pés

- `tipo`: `movimentacao_pes`, `mao`: `null`
- Deslocamento do corpo (passo à frente, atrás, lateral ou giro) sem golpe
- Início: primeiro frame em que um pé sai do chão ou começa a deslizar. Fim: último frame antes de os dois pés estarem parados de novo
- Se houver um golpe durante o deslocamento (jab com passo), rotular o golpe como `jab` e **não** rotular aquele trecho como `movimentacao_pes`. O tipo `movimentacao_pes` é reservado para deslocamentos sem nenhum golpe

### 4. Estender a mão da frente sem golpear

- `tipo`: `extensao_sem_golpe`, `mao`: `direita`
- Extensão lenta e deliberada do braço da frente, sem intenção de golpe (medir distância, afastar o oponente, tocar a luva)
- Início e fim com a mesma regra do jab: do primeiro frame de avanço até o frame de maior extensão
- O que diferencia do jab é a velocidade: o movimento leva claramente mais tempo que os jabs do mesmo clipe. Se a diferença não for evidente, rotular como `extensao_sem_golpe` com a marcação `duvida`

### 5. Ajuste de guarda

- `tipo`: `ajuste_guarda`, `mao`: mão que se moveu
- Movimento curto da mão para reposicionar a guarda (subir, baixar, aproximar do rosto), sem extensão do braço na direção do alvo
- Início: primeiro frame em que a mão sai da posição anterior. Fim: frame em que ela fica parada na nova posição

### 6. Finta de jab

- `tipo`: `finta_jab`, `mao`: `direita`
- Início de jab interrompido de propósito: o braço começa a avançar e para cedo, sem chegar a um pico de golpe e sem o recolhimento típico do jab
- Início com a mesma regra do jab. Fim: frame em que o punho para de avançar (o mais longe que chegou)
- Finta também pode ser feita com ombro ou tronco sem mexer o braço. Nesse caso, rotular só se o punho da frente avançar visivelmente; caso contrário, o trecho é `guarda_parada` ou não recebe rótulo próprio

### 7. Jab com extensão parcial

`tipo`: `jab`, `mao`: `direita`, marcação `extensao_parcial`, tempos com a mesma regra do jab. Ver casos limite.

### 8. Dois jabs rápidos (double jab)

Dois eventos `jab` com o mesmo `grupo`. Ver casos limite.

### Trechos sem rótulo

Movimentos dentro de `trecho_analisado` que não se encaixam em nenhum tipo (coçar o rosto, ajustar a roupa, sair de quadro) recebem o tipo mais próximo com a marcação `duvida` e a descrição em `observacao`. Se não houver tipo próximo, o trecho deve ser excluído de `trecho_analisado` ou o clipe regravado.

## Casos limite

### Extensão parcial

Os critérios de aceitação pedem que o jab com extensão parcial seja rotulado como jab ou como negativo, com o critério documentado. **Decisão para o Marco 0: rotular como `jab` com a marcação `extensao_parcial`.**

Motivo: os critérios definem que um jab tecnicamente ruim continua sendo jab. Uma extensão incompleta é um defeito técnico, não a ausência de golpe. A marcação permite que o relatório mostre o recall desses jabs à parte, sem tirá-los da métrica principal.

Critério visual, olhando o movimento inteiro e o frame de maior extensão:

| Situação | Rótulo |
|----------|--------|
| Avanço, pico e recolhimento com velocidade de golpe, e braço quase reto no pico | `jab` |
| Avanço, pico e recolhimento com velocidade de golpe, mas cotovelo claramente dobrado no pico | `jab` + `extensao_parcial` |
| Avanço interrompido cedo, sem pico de golpe e sem recolhimento típico de jab | `finta_jab` |

O que separa o jab com extensão parcial da finta é o ciclo completo: no jab, o braço estende, chega a um pico e recolhe como num golpe; na finta, o avanço é cortado antes disso. A quantidade de extensão sozinha não decide.

A câmera em diagonal encurta o braço na imagem. Para decidir se o cotovelo está "quase reto", comparar com os jabs completos do mesmo clipe. Se não for possível decidir entre `jab` com `extensao_parcial` e `finta_jab`, usar `finta_jab` com a marcação `duvida`, seguindo a regra dos critérios de que extensão interrompida nunca é classificada automaticamente como jab. Esta regra deve ser revista quando houver validação de um treinador.

### Finta

- Só é `finta_jab` se o punho da frente avançar visivelmente. Finta só de ombro, tronco ou cabeça não gera evento de braço
- Se depois da finta vier um jab sem a mão voltar à guarda, rotular dois eventos com o mesmo `grupo`: `finta_jab` (do início até o ponto em que o punho parou) e `jab` (do primeiro frame em que o punho volta a avançar até o pico)

### Double jab

- Dois eventos `jab` separados, com o mesmo `grupo`, cada um com início e fim pela regra do jab
- O primeiro termina no pico dele. O segundo começa no primeiro frame em que o punho volta a avançar, **mesmo que a mão não tenha voltado à guarda** entre os dois
- O grupo permite verificar o CA-04 (um double jab gera exatamente dois eventos)
- Se o recolhimento entre os dois for tão curto que não dá para ver o punho voltando em pelo menos um frame, rotular como um único `jab` sem grupo, com a marcação `duvida` e a observação "possível double jab sem recolhimento visível"

### Jab sem retorno à guarda

Rotular normalmente como `jab`, com a marcação `sem_retorno`. O jab termina no pico, então o que acontece depois não muda os tempos do evento (CA-05).

## Tempo e FPS variável

Os vídeos de celular gravados até agora têm FPS médio não inteiro, sinal de taxa de quadros variável (ver [protocolo de gravação](protocolo-gravacao.md)). Nesses vídeos, o tempo de um frame não é exatamente o índice dividido pelo FPS.

Regras:

1. **Usar o tempo exibido pelo player**, não o número do frame. O player deve mostrar o tempo de apresentação gravado no próprio arquivo (o timestamp de cada frame), que é o tempo real do vídeo mesmo com FPS variável.
2. **Nunca calcular o tempo** a partir de um número de frame multiplicado ou dividido pelo FPS.
3. **Registrar a ferramenta e a versão** no campo `ferramenta`. Se a forma de calcular o tempo mudar no extrator, o registro permite saber como os rótulos foram medidos e convertê-los se necessário.
4. **Converter para milissegundos inteiros** o tempo exibido. Exemplo: `00:00:04.317` vira `4317`.
5. Não trocar de ferramenta no meio de um conjunto de dados.

Atenção: hoje o extrator calcula o tempo como índice do frame dividido pelo FPS médio. Em vídeo com FPS variável, esse tempo pode se afastar do tempo exibido pelo player ao longo do clipe. A decisão sobre como alinhar os dois ainda está pendente. Os rótulos ficam no tempo real do arquivo, que é a referência correta, e a diferença deve ser medida antes da primeira avaliação.

## Ferramenta sugerida

**mpv**: player de vídeo gratuito e de código aberto, disponível para Windows, sem cadastro. Mostra o tempo de cada frame a partir do timestamp gravado no arquivo, com precisão de milissegundos, e permite avançar e voltar frame a frame. Nada precisa ser instalado agora; a instalação fica para quando a rotulagem começar.

Uso previsto:

```bash
mpv --pause --osd-level=3 --osd-fractions videos/treino_2026-11-27_01.mp4
```

| Opção ou tecla | Efeito |
|----------------|--------|
| `--pause` | Abre o vídeo pausado |
| `--osd-level=3` | Mantém o tempo sempre visível na tela |
| `--osd-fractions` | Mostra o tempo com milissegundos |
| `.` | Avança um frame |
| `,` | Volta um frame |
| Espaço | Reproduz ou pausa |

Os tempos são anotados à mão no JSON. Para um conjunto de 10 clipes de até 30 segundos, isso é mais simples do que adotar uma ferramenta de anotação com interface própria.

## Valores provisórios

Estes valores foram definidos sem dados reais e devem ser revistos depois da primeira rotulagem real, com a justificativa registrada neste documento:

| Valor | Onde é usado |
|-------|--------------|
| 300 ms | Tempo de braço parado no pico a partir do qual o jab recebe a marcação `duvida` |
| 1 s | Duração mínima de um trecho `guarda_parada` |

## Verificação de consistência

Antes de usar os rótulos de teste:

- Rerrotular um clipe de calibração inteiro em outro dia, sem olhar o arquivo anterior, e comparar
- Se algum evento mudar de tipo ou algum tempo diferir em mais de 2 frames, revisar a regra correspondente neste documento antes de seguir
- Registrar no relatório do Marco 0 que todos os rótulos foram feitos por uma única pessoa, o que limita a validade da avaliação
