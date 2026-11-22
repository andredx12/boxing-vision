# Desempenho da extração (CA-09)

Medição do tempo de processamento do pipeline de extração no PC de desenvolvimento, comparando o modelo full com o lite e a entrada do MediaPipe no tamanho original com a entrada reduzida. Data da medição: 2026-11-22, das 18:17 às 18:35 (horário local). Nenhuma alteração foi feita no extrator; o padrão continua sendo o modelo full com o frame no tamanho original.

## Pergunta

O CA-09 exige que 1 minuto de vídeo seja processado em no máximo 3 minutos (180 s) no PC de desenvolvimento (8 GB de RAM, sem GPU dedicada). Medições anteriores, feitas com a máquina carregada, deram de 215 a 246 s por minuto de vídeo (2026-11-20), 380 s/min sem preview e cerca de 1765 s/min com preview (2026-11-22). As perguntas desta medição:

1. Com a máquina o mais ociosa possível, o extrator atende ao CA-09?
2. Em quais etapas o tempo é gasto?
3. Trocar o modelo full pelo lite ou reduzir o frame antes do MediaPipe reduz o tempo, e quanto isso muda os landmarks do braço da frente?

## Método

Script `saida/desempenho/medir.py` (fora do versionamento). Ele reaproveita as funções públicas de `boxing_vision/extract.py` (`create_landmarker`, `LANDMARKER_OPTIONS`, `frame_timestamp_ms`, `landmarks_to_row`, `build_header`, `draw_arms`, `ARMS`) num laço próprio, na mesma ordem do `extract()`, e cronometra cada etapa com `time.perf_counter_ns`:

| Etapa | O que mede |
|---|---|
| decodificação | `cap.read()`, leitura de `CAP_PROP_POS_MSEC` e cálculo do `timestamp_ms` |
| redimensionamento | `cv2.resize` com `INTER_AREA` no frame BGR, só quando há redução; no tamanho original mede apenas o desvio condicional e o próprio cronômetro |
| conversão de cor | `cv2.cvtColor` BGR para RGB e criação do `mp.Image` |
| inferência | `detect_for_video` do MediaPipe |
| escrita do CSV | `landmarks_to_row` e `writerow` |
| desenho do preview | `draw_arms` no frame original |
| escrita do preview | `VideoWriter.write` (codec mp4v, tamanho original) |

O tempo total de cada execução vai da abertura dos arquivos de saída até o fechamento deles e inclui a carga do modelo. Ele não inclui o que o extrator faz depois do laço (SHA-256 do vídeo e do modelo, gravação dos JSON e renomeação dos arquivos). Além das execuções completas, cada repetição tem uma passada só de decodificação (`cap.read()` e `CAP_PROP_POS_MSEC`, sem nenhuma outra etapa).

Os valores em s por minuto de vídeo são o tempo medido dividido pela duração do vídeo (28,422 s) e multiplicado por 60.

Na redução, o frame é reduzido só na entrada do MediaPipe. O preview continua no tamanho original, como no extrator. Os landmarks são normalizados (0 a 1), então as coordenadas dos dois tamanhos são diretamente comparáveis.

Protocolo:

- Bloco A: modelos full e lite, entrada com lado maior original (1080x1920), 960 (540x960) e 640 (360x640), com escrita do CSV e sem preview. 6 configurações, 3 repetições.
- Bloco B: modelo full, tamanho original, CSV e preview. 2 repetições.
- Aquecimento: uma passada de 2 s de vídeo por modelo no início de cada bloco, descartada.
- Ordem: a lista de configurações é rotacionada a cada repetição, para que nenhuma configuração fique sempre na mesma posição.
- O resumo de cada configuração é a mediana das repetições.
- Base `southpaw` (braço da frente = mão direita, [ADR 003](../adr/003-base-canhota-no-marco-0.md)), limite de visibilidade 0,5, opções do landmarker iguais às do extrator (`VIDEO`, 1 pose, confianças 0,5).

Vídeo e modelos:

| Arquivo | SHA-256 | Observação |
|---|---|---|
| `amostra_externo.mp4` | `bb415a147307be4b9af4b820f9977a05a647d83e5598d8b3f9f1e1d21ec44c15` | 851 frames, 28,422 s, 1080x1920 |
| `pose_landmarker_full.task` | `4eaa5eb7a98365221087693fcc286334cf0858e2eb6e15b506aa4a7ecdcec4ad` | 9.398.198 bytes |
| `pose_landmarker_lite.task` | `59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a` | 5.777.746 bytes, mesma origem do full (`storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/`) |

Ambiente: Intel Core i3-1005G1 a 1,20 GHz, 2 núcleos físicos e 4 lógicos, 7,79 GB de RAM, Windows 11 (10.0.26200), Python 3.12.10, MediaPipe 0.10.32, OpenCV 5.1.0 (4 threads). Código no commit `74d6b0c`, com `boxing_vision/extract.py` sem alterações locais nos dois blocos.

Resultados brutos: `saida/desempenho/bloco_A/resultado_20261122_181738.json`, `saida/desempenho/bloco_B/resultado_20261122_183342.json` e os logs `bloco_A.log` e `bloco_B.log`. Os CSV gerados no bloco A ficaram em `saida/desempenho/bloco_A/tmp/`.

## Ambiente no início de cada bloco (limitação)

Antes da medição o Docker Desktop foi fechado e o WSL desligado. A máquina não estava ociosa: o mysqld seguia ativo, e o Edge e outras sessões de ferramentas de desenvolvimento estavam abertos. Dados dos snapshots (`ambiente_bloco_A.txt`, `ambiente_bloco_B.txt`, `ambiente_fim.txt`) e da `LoadPercentage` gravada pelo script:

| Momento | RAM livre | Carga da CPU (snapshot) | Carga da CPU (script) | Processos relevantes |
|---|---|---|---|---|
| Início do bloco A (18:17) | 2414 MB de 7974 MB | 25% | 25% no início, 5% no fim | outras sessões de ferramentas de desenvolvimento: 17 processos, 1355 MB; msedge: 7 processos, 483 MB; msedgewebview2: 12 processos, 220 MB; mysqld: 2 processos, 14 MB; node: 8 processos, 13 MB; vmmem: 26 MB |
| Início do bloco B (18:33) | 2279 MB | 12% | 7% no início, 22% no fim | mesmas sessões: 1005 MB; msedge: 476 MB; msedgewebview2: 13 processos, 308 MB; mysqld: 14 MB; node: 15 MB; vmmem: 13 MB |
| Fim (18:35) | 2486 MB | 7% | | mesmas sessões: 879 MB; msedge: 471 MB; msedgewebview2: 228 MB; mysqld: 14 MB; node: 15 MB; vmmem: 14 MB |

A compressão de memória do Windows passou de 496 MB no início do bloco A para 909 MB no início do bloco B e 918 MB no fim. A carga da CPU é uma leitura pontual no início e no fim; não há registro contínuo durante as execuções.

## Resultados

### Tempo total por configuração (bloco A, CSV, sem preview)

Segundos de processamento por minuto de vídeo, em cada repetição e na mediana. Limite do CA-09: 180 s/min.

| Modelo | Entrada | Rep. 1 | Rep. 2 | Rep. 3 | Mediana | CA-09 (mediana) |
|---|---|---|---|---|---|---|
| full | original 1080x1920 | 72,79 | 109,26 | 68,52 | **72,79** | atende |
| full | 960 (540x960) | 68,65 | 178,34 | 65,30 | **68,65** | atende |
| full | 640 (360x640) | 69,29 | 183,75 | 70,60 | **70,60** | atende |
| lite | original 1080x1920 | 152,26 | 120,20 | 56,90 | **120,20** | atende |
| lite | 960 (540x960) | 151,70 | 142,43 | 54,52 | **142,43** | atende |
| lite | 640 (360x640) | 155,59 | 144,49 | 54,01 | **144,49** | atende |
| só decodificação | original | 19,4 | 46,9 | 19,0 | 19,4 | |

Das 18 execuções completas, só uma passou do limite: full 640 na repetição 2 (183,75 s/min).

### Variação entre repetições

A variação não acompanha a configuração. Ela acompanha o momento da execução. Ordem de execução segundo o `bloco_A.log`:

- Repetição 1: full original, full 960, full 640, lite original, lite 960, lite 640.
- Repetição 2: full 960, full 640, lite original, lite 960, lite 640, full original.
- Repetição 3: full 640, lite original, lite 960, lite 640, full original, full 960.

As três primeiras execuções da repetição 1 ficaram entre 68,65 e 72,79 s/min. As três seguintes (lite) e toda a repetição 2 ficaram entre 109,26 e 183,75 s/min. Toda a repetição 3 ficou entre 54,01 e 70,60 s/min. A passada só de decodificação, que não usa o MediaPipe, também mais que dobrou na repetição 2 (46,9 contra 19,4 e 19,0 s/min). Nessas execuções lentas o tempo subiu em todas as etapas, inclusive na decodificação. Isso indica uma disputa por CPU vinda de fora do script durante esse intervalo. O script não registra a carga contínua da máquina, então a causa não pode ser identificada com estes dados.

Consequência: as medianas do lite (120,20 a 144,49 s/min) usam duas execuções feitas na janela lenta. As do full usam só uma. **As medianas não servem para comparar full e lite.** A única repetição em que todas as configurações rodaram na janela rápida é a 3, e as comparações de tempo abaixo usam essa repetição.

Os landmarks foram idênticos entre as repetições em todas as configurações (`identico_entre_repeticoes` verdadeiro no JSON). Só o tempo variou.

### Tempo por etapa (bloco A, repetição 3)

Segundos por minuto de vídeo. "Resto" é o tempo total menos a soma das etapas: carga do modelo, contagem de pose e o próprio laço.

| Modelo | Entrada | Decodificação | Redimensionamento | Conversão de cor | Inferência | Escrita do CSV | Resto | Total |
|---|---|---|---|---|---|---|---|---|
| full | original | 16,1 | 0,8 | 8,1 | 42,9 | 0,4 | 0,3 | 68,52 |
| full | 960 | 19,6 | 2,1 | 2,6 | 40,1 | 0,4 | 0,5 | 65,30 |
| full | 640 | 19,4 | 5,4 | 0,7 | 44,2 | 0,4 | 0,5 | 70,60 |
| lite | original | 15,6 | 0,8 | 8,0 | 31,9 | 0,4 | 0,3 | 56,90 |
| lite | 960 | 17,5 | 2,1 | 2,5 | 31,7 | 0,4 | 0,4 | 54,52 |
| lite | 640 | 17,7 | 4,6 | 0,7 | 30,4 | 0,4 | 0,3 | 54,01 |

Inferência por frame na repetição 3: full 23,855 ms (original), 22,334 ms (960) e 24,621 ms (640); lite 17,739 ms (original), 17,636 ms (960) e 16,933 ms (640).

Leitura:

- A inferência é a maior etapa (cerca de 60% do total no full), seguida da decodificação (cerca de 16 a 20 s/min). A escrita do CSV é desprezível (0,4 s/min).
- Reduzir o frame quase não muda a inferência e corta a conversão de cor (de 8,1 para 2,6 e 0,7 s/min no full). Esse corte é anulado pelo custo do próprio `cv2.resize`, que é maior em 640 (5,4 s/min) do que em 960 (2,1 s/min). No full, o total ficou em 65,30 (960) e 70,60 (640) contra 68,52 s/min no original. São diferenças de poucos segundos, dentro da variação que esta medição consegue resolver.
- Na mesma repetição, o lite reduziu a inferência em cerca de 26% (31,9 contra 42,9 s/min no tamanho original) e o total em cerca de 17% (56,90 contra 68,52 s/min). Como é um único par de execuções, esse ganho é uma indicação, não um valor estável. Na repetição 2, ambos na janela lenta, a ordem chegou a se inverter (lite original 120,20 contra full original 109,26).

### Custo do preview (bloco B)

Modelo full, tamanho original, CSV e preview:

| Repetição | Total (s/min) | Inferência | Escrita do preview | Desenho do preview | Decodificação | Conversão de cor |
|---|---|---|---|---|---|---|
| 1 | 99,39 | 42,0 | 27,8 | 0,2 | 18,9 | 8,8 |
| 2 | 95,25 | 42,0 | 26,7 | 0,2 | 16,6 | 8,3 |
| Mediana | **97,32** | | | | | |

A passada só de decodificação deu 18,4 s/min nas duas repetições do bloco B, valor próximo ao das repetições 1 e 3 do bloco A. Isso indica que o bloco B rodou sem a disputa vista na repetição 2 do bloco A.

O custo do preview, medido diretamente nas etapas, foi de 27,5 s/min na mediana (desenho e escrita). Quase todo esse custo é a codificação do vídeo mp4v em 1080x1920 (27,3 s/min). O desenho dos braços custa 0,2 s/min. Com preview, o extrator também atendeu ao CA-09 (95,25 e 99,39 s/min).

As medições anteriores (380 s/min sem preview e cerca de 1765 s/min com preview) foram feitas com a máquina carregada e não foram repetidas nas mesmas condições. Esta medição não explica a diferença.

## Qualidade da redução e do lite em relação ao full original

Referência: modelo full com a entrada no tamanho original, que é o padrão do extrator. Todas as comparações usam os 851 frames do vídeo e o braço da frente (mão direita). Distância é a distância euclidiana em x,y normalizados (fração da largura e da altura do frame) entre o mesmo landmark nas duas configurações, calculada só nos frames em que as duas detectaram pose.

Fonte: taxa de pose, visibilidade e frames de baixa visibilidade vêm do JSON do bloco A. A comparação do full reduzido com o full original também vem do JSON. O script não compara modelos diferentes entre si, então a comparação do lite com o full original foi calculada a partir dos CSV gerados no bloco A (`saida/desempenho/bloco_A/tmp/`). O mesmo cálculo aplicado aos CSV do full 960 e 640 reproduz exatamente os valores do JSON.

### Detecção e visibilidade

| Modelo | Entrada | Frames com pose | Taxa de pose | Visibilidade média do braço da frente | Frames com braço da frente abaixo de 0,5 |
|---|---|---|---|---|---|
| full | original | 819 | 96,24% | 0,9014 | 146 |
| full | 960 | 830 | 97,53% | 0,8869 | 174 |
| full | 640 | 822 | 96,59% | 0,8997 | 148 |
| lite | original | 840 | 98,71% | 0,8851 | 192 |
| lite | 960 | 832 | 97,77% | 0,8866 | 192 |
| lite | 640 | 840 | 98,71% | 0,8805 | 198 |

A visibilidade é uma estimativa do próprio modelo. Uma taxa de pose maior não significa pose correta: sem landmarks de referência, não dá para dizer qual configuração acerta mais.

### Concordância frame a frame e diferença de coordenadas

| Configuração comparada com full original | Pose nos dois | Pose só no full original | Pose só na outra | Concordância de detecção | Ombro: média / máxima | Cotovelo: média / máxima | Punho: média / máxima |
|---|---|---|---|---|---|---|---|
| full 960 | 818 | 1 | 12 | 98,47% | 0,01193 / 0,57121 | 0,01227 / 0,42050 | 0,01485 / 0,85428 |
| full 640 | 817 | 2 | 5 | 99,18% | 0,00333 / 0,04352 | 0,00691 / 0,20376 | 0,01214 / 0,90829 |
| lite original | 819 | 0 | 21 | 97,53% | 0,01327 / 0,14879 | 0,02142 / 0,21818 | 0,03112 / 0,35931 |
| lite 960 | 819 | 0 | 13 | 98,47% | 0,01260 / 0,09450 | 0,02149 / 0,28376 | 0,03195 / 0,51767 |
| lite 640 | 819 | 0 | 21 | 97,53% | 0,01324 / 0,08668 | 0,02206 / 0,37862 | 0,03424 / 0,88744 |

Frames (entre os comparados) com distância acima de 0,05, contagem descritiva calculada dos CSV:

| Configuração | Ombro | Cotovelo | Punho |
|---|---|---|---|
| full 960 | 17 | 27 | 47 |
| full 640 | 0 | 13 | 36 |
| lite original | 22 | 65 | 127 |
| lite 960 | 19 | 74 | 134 |
| lite 640 | 23 | 79 | 138 |

Para referência, a redução dentro do próprio lite (JSON): lite 960 contra lite original teve concordância de 99,06% e punho com média 0,01370 e máxima 0,27238; lite 640 contra lite original teve concordância de 100% e punho com média 0,01775 e máxima 0,72714.

Leitura:

- **Reduzir o frame no full** muda pouco a média: punho de 0,015 (960) e 0,012 (640). Há, porém, frames isolados com saltos grandes (máximas de 0,85 e 0,91 no punho, e 0,57 no ombro em 960). Em 640 o ombro ficou estável (máxima 0,044), mas o punho teve 36 frames acima de 0,05.
- **Trocar para o lite** muda mais o braço da frente do que reduzir o frame: a média do punho fica entre 0,031 e 0,034, cerca de duas vezes a da redução no full, e 127 a 138 frames têm o punho a mais de 0,05 do full original. O lite também detecta pose em 13 a 21 frames em que o full não detecta.
- Esta comparação mede a diferença em relação ao full original, não o erro em relação à posição real do braço, e não mede precisão de detecção de jab.

## Conclusão

1. Nesta medição, o extrator no padrão atual (full, tamanho original, CSV) atendeu ao CA-09 com folga: 72,79 s/min na mediana e 68,52 a 72,79 s/min nas execuções sem disputa, contra o limite de 180 s/min. Mesmo na janela lenta ficou em 109,26 s/min. Com preview, 97,32 s/min na mediana.
2. O tempo é dominado pela inferência e, em seguida, pela decodificação. No preview, a codificação do vídeo custa cerca de 27 s/min.
3. Reduzir o frame antes do MediaPipe não trouxe ganho consistente no full: a inferência não diminui, e a economia na conversão de cor é consumida pelo redimensionamento.
4. O lite indicou cerca de 17% a menos no tempo total, em um único par de execuções comparáveis. Ele também muda os landmarks do braço da frente mais do que a redução do frame.
5. A variação entre repetições foi grande (a mesma configuração foi de 65,30 a 178,34 s/min) e veio do momento da execução, não da configuração. A margem até o limite depende do que mais estiver rodando na máquina: uma execução (full 640, repetição 2) passou de 180 s/min.

## Recomendação

Recomendação, sem mudança no padrão do extrator nesta tarefa: **manter o modelo full com o frame no tamanho original.**

- Tempo: o padrão atual já atende ao CA-09 com margem nas execuções sem disputa (68,52 a 72,79 s/min). O ganho do lite (cerca de 17% em um par de execuções) não é necessário para cumprir o critério. A redução do frame não teve ganho consistente.
- Qualidade: o lite desloca o punho da frente em média 0,031 a 0,034 em relação ao full original, com 127 a 138 frames acima de 0,05, e o punho é o landmark central para detectar jab. A redução no full desloca menos na média, mas cria saltos isolados grandes, sem ganho de tempo que compense.
- O preview pode continuar opcional: custou cerca de 27,5 s/min e, com ele, o tempo ficou abaixo do limite nesta medição.

Se um dia for preciso reduzir tempo, o lite é o candidato com ganho medido. A troca exigiria antes avaliar a precisão de detecção de jab com rótulos, porque a qualidade medida aqui (detecção de pose, visibilidade e diferença de coordenadas) não mede precisão de jab.

## Limitações

- Um vídeo só (`amostra_externo`, 28,4 s), fora do protocolo de gravação em diagonal. O CA-09 fala em 1 minuto de vídeo; os valores por minuto são extrapolação linear de 28,4 s.
- Uma máquina só, com processos ativos (mysqld, Edge e outras sessões de ferramentas de desenvolvimento), de 2,17 a 2,39 GB de RAM livre segundo o script (2279 a 2486 MB nos snapshots) e carga pontual de 5% a 25%. Não houve registro contínuo da carga, então a causa da janela lenta não foi identificada.
- Poucas repetições: 3 no bloco A e 2 no bloco B. A janela lenta contaminou duas das três repetições do lite. A comparação de tempo entre full e lite se apoia em um único par de execuções (repetição 3).
- O aquecimento foi feito uma vez por bloco, não antes de cada execução.
- O tempo medido não inclui o pós-processamento do extrator (SHA-256 do vídeo e do modelo, gravação dos JSON). Isso não foi medido aqui.
- A qualidade foi comparada com o full original, que também não é verdade de campo. Nenhuma métrica aqui mede precisão de jab.
- O preview foi medido só com o full no tamanho original.
