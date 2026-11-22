# FPS variável nos vídeos de celular

Investigação do impacto da taxa de quadros variável sobre o `timestamp_ms` gerado pelo extrator, medida nos três vídeos de amostra em `videos/`. Data da medição: 2026-11-22.

## Pergunta

O extrator calcula o timestamp de cada frame como `índice × 1000 / fps médio` (`boxing_vision/extract.py`). Os rótulos são feitos no mpv, que mostra o tempo de apresentação real do frame (PTS). Se os dois relógios divergem, a diferença entra direto na regra de correspondência, que aceita no máximo 200 ms entre o centro da detecção e o centro do rótulo.

## Método

Scripts em `saida/fps_variavel/` (fora do versionamento):

- `medir.py`: para cada vídeo, percorre os frames com OpenCV e compara três relógios:
  1. timestamp do extrator: `round(i × 1000 / CAP_PROP_FPS)`
  2. `cv2.CAP_PROP_POS_MSEC` lido após cada frame
  3. `pts_time` de cada frame segundo o `ffprobe` (ffmpeg 9.0.2)
- `gaps.py`: lista os intervalos entre frames maiores que 45 ms (frames perdidos pela câmera).
- `cfr_check.py`: converte cópias dos vídeos para 30 FPS constante com `ffmpeg -fps_mode cfr -r 30 -c:v libx264 -crf 18` e mede frames duplicados e o erro do tempo nominal em relação ao PTS do frame de origem.

Todos os vídeos são H.264 1920×1080, `time_base` 1/90000, `start_time` 0. Python do `.venv`, máquina com 4 núcleos lógicos.

## Resultados

### Os relógios reais concordam entre si

`CAP_PROP_POS_MSEC` e `pts_time` do ffprobe coincidem em todos os frames dos três vídeos, com diferença máxima de 0,0004 ms (arredondamento). O número de frames lido pelo OpenCV é igual ao do ffprobe em todos os casos. Ou seja: o timestamp real está disponível dentro do próprio OpenCV, sem depender do ffprobe.

### Intervalo entre frames

| Vídeo | FPS médio (OpenCV) | Frames | Intervalo mais comum | Intervalo máximo | Intervalos > 50 ms |
|---|---|---|---|---|---|
| amostra_externo | 29,941 | 851 | 33,2 ms | 139,1 ms | 2 |
| amostra_frontal | 29,771 | 454 | 33,2 a 33,5 ms | 107,8 ms | 2 |
| amostra_obstruido | 29,381 | 507 | 33,3 ms | 101,6 ms | 10 |

Padrão observado:

- Os três vídeos começam com um intervalo longo entre o frame 0 e o frame 1 (101 a 139 ms), equivalente a 2 a 3 frames perdidos na partida da câmera.
- Fora disso, a câmera perde frames isolados (intervalos de 66,6 ms, um frame perdido cada).
- No `amostra_obstruido` há 9 frames perdidos concentrados entre 12,4 s e 14,9 s, justamente no trecho com mais movimento e oclusão.

A taxa real é quase constante (cerca de 30 FPS). O FPS médio fica abaixo de 30 porque os frames perdidos aumentam a duração sem aumentar a contagem.

### Desvio do timestamp do extrator em relação ao PTS real

Desvio = timestamp do extrator menos PTS real. Negativo significa que o extrator atrasa; positivo, que adianta.

| Vídeo | Duração | Desvio máximo absoluto | Desvio médio absoluto | Faixa |
|---|---|---|---|---|
| amostra_externo | 28,4 s | **135,5 ms** | 75,1 ms | de -135,5 a +0,1 ms |
| amostra_frontal | 15,2 s | **113,9 ms** | 58,5 ms | de -113,9 a +0,3 ms |
| amostra_obstruido | 17,2 s | **209,2 ms** | 85,6 ms | de -67,6 a +209,2 ms |

A comparação contra `CAP_PROP_POS_MSEC` dá os mesmos números (as duas referências são idênticas).

Desvio ao longo do vídeo (amostras a cada 10% dos frames):

| amostra_externo | | amostra_frontal | | amostra_obstruido | |
|---|---|---|---|---|---|
| tempo real | desvio | tempo real | desvio | tempo real | desvio |
| 0,0 s | 0 ms | 0,0 s | 0 ms | 0,0 s | 0 ms |
| 3,0 s | -133 ms | 1,6 s | -69 ms | 1,7 s | -32 ms |
| 5,8 s | -119 ms | 3,1 s | -107 ms | 3,4 s | +5 ms |
| 8,6 s | -105 ms | 4,6 s | -82 ms | 5,1 s | +40 ms |
| 11,5 s | -91 ms | 6,1 s | -77 ms | 6,7 s | +77 ms |
| 14,3 s | -78 ms | 7,6 s | -77 ms | 8,4 s | +113 ms |
| 17,1 s | -64 ms | 9,1 s | -61 ms | 10,1 s | +158 ms |
| 19,9 s | -50 ms | 10,6 s | -45 ms | 11,7 s | +194 ms |
| 22,8 s | -36 ms | 12,1 s | -30 ms | 13,5 s | +164 ms |
| 25,6 s | -14 ms | 13,6 s | -5 ms | 15,4 s | -41 ms |
| 28,4 s | 0 ms | 15,1 s | -1 ms | 17,2 s | -1 ms |

Maior variação do desvio dentro de uma janela de 1 s: 134 ms (externo), 71 ms (frontal), 220 ms (obstruido).

### Por que o desvio tem essa forma

O FPS médio é calculado sobre o vídeo inteiro, então o erro é forçado a zero no último frame. No meio do vídeo ele depende de onde caem os frames perdidos:

- Em `amostra_externo`, o intervalo de 139 ms logo no início deixa o extrator cerca de 105 ms atrasado em menos de 1 s. Depois, como o extrator avança 33,40 ms por frame e a câmera avança 33,23 ms, o atraso diminui aos poucos até zerar no fim.
- Em `amostra_obstruido`, o intervalo típico é 33,3 ms, mas o extrator avança 34,04 ms por frame. O erro cresce cerca de 0,7 ms por frame até chegar a +209 ms perto de 12,4 s, e só é compensado quando os 9 frames perdidos acontecem.

Consequência: o erro não é um atraso constante que daria para descontar. Ele muda de sinal e de tamanho conforme o vídeo, e cresce com a duração do trecho sem frames perdidos. Os vídeos de treino do Marco 0 serão mais longos que estas amostras de 15 a 28 s, então não há nada que limite o erro a estes valores (isto é uma inferência, não foi medido em vídeos longos).

## Conclusão: o desvio ameaça a tolerância de 200 ms?

Sim.

- Em `amostra_obstruido` o desvio passa de 200 ms (209 ms). Um jab detectado exatamente no frame certo seria contado como falso positivo e o rótulo como falso negativo nesse trecho.
- Nos outros dois vídeos o desvio chega a 114 e 135 ms. Isso consome mais da metade da tolerância antes de considerar o erro do próprio detector, que também precisa caber nos 200 ms.
- O erro é sistemático e varia com o vídeo, então distorce a avaliação de localização temporal de forma diferente em cada clipe.

Efeito secundário: qualquer cálculo de velocidade do punho que use a diferença entre timestamps do extrator vai tratar um intervalo real de 66 ms (frame perdido) como se fosse 33 ms, dobrando a velocidade aparente naquele frame. No `amostra_obstruido` isso acontece 9 vezes em 2,5 s.

## Comparação das soluções

### A. Usar o timestamp real do frame

Ler `cap.get(cv2.CAP_PROP_POS_MSEC)` depois de cada `cap.read()` e usar esse valor como `timestamp_ms`.

Prós:

- Erro medido em relação ao PTS: 0,0004 ms. Fica no mesmo relógio que o mpv usa na rotulagem.
- Não altera o vídeo, não recodifica, não gera arquivo intermediário e o `video_sha256` do metadado continua apontando para o arquivo original.
- Custo de processamento praticamente nulo.
- Continua reprodutível: o PTS é gravado no arquivo, então duas execuções no mesmo vídeo dão os mesmos timestamps. A preocupação do comentário atual do extrator ("não do relógio do decoder") não se aplica, porque o valor não vem de um relógio de execução e sim do contêiner.
- Os timestamps são estritamente crescentes (menor intervalo medido: 24,9 ms), o que atende à exigência do `detect_for_video` do MediaPipe.
- Velocidades calculadas com a diferença real de tempo ficam corretas também nos frames perdidos.

Contras:

- `CAP_PROP_POS_MSEC` depende do backend do OpenCV. Foi validado aqui com o backend padrão do `.venv` nestes três vídeos; outro backend ou outro contêiner pode se comportar diferente. Precisa de um teste ou checagem que detecte valores não crescentes ou zerados.
- Vídeos com `start_time` diferente de zero exigiriam subtrair o PTS do primeiro frame (todos os medidos começam em 0).
- O código seguinte não pode assumir intervalo fixo entre frames: tudo que hoje usaria `1 / fps` precisa usar a diferença de timestamps.
- O vídeo de preview continua gravado com FPS fixo, então o tempo dele pode divergir levemente do original. Só afeta a visualização.

### B. Converter para FPS constante com ffmpeg antes de processar

Prós:

- O código continua simples: intervalo fixo de 33,33 ms (medido: 33,333 a 33,334 ms em todos os frames convertidos).
- O erro do tempo nominal em relação ao PTS do frame de origem fica pequeno na maior parte dos frames (médio de 7,7 a 9,4 ms).

Contras:

- Os frames perdidos não voltam: o ffmpeg duplica o frame anterior. Medido: 4 duplicados no externo, 4 no frontal e 11 no obstruido. Um frame duplicado mostra movimento zero seguido de um salto dobrado, o mesmo problema de velocidade da situação atual, só que escondido. No obstruido os duplicados caem no trecho de 12,4 a 14,9 s, onde o movimento importa.
- Nos frames duplicados o conteúdo é mais velho que o timestamp: erro máximo medido de 67 ms (externo), 41 ms (frontal) e 35 ms (obstruido).
- O ffmpeg também descarta frames quando dois caem muito próximos (o externo tem 851 frames de origem, 854 convertidos e 4 duplicados, então 1 frame original foi descartado).
- Recodificação com perda (CRF 18), que pode alterar levemente os landmarks.
- Custo alto em vídeo 1080p: 166 s para converter 15,2 s de vídeo com preset `medium` (cerca de 11 vezes o tempo real) e 60 s com `veryfast` (cerca de 4 vezes), sem outra carga na máquina.
- Cria um segundo arquivo por vídeo. O hash, a rotulagem e a extração precisam apontar todos para o convertido, senão a divergência volta. Rotular no original e extrair do convertido mantém um erro de até um frame e meio nos duplicados.
- Adiciona o ffmpeg como dependência externa do pipeline, fora do `.venv`.

## Recomendação

Adotar a solução A (timestamp real via `CAP_PROP_POS_MSEC`).

Ela resolve o problema na origem com erro medido praticamente nulo, mantém o rótulo e a extração no mesmo relógio que o mpv usa, não mexe no vídeo e não custa tempo de processamento. A solução B troca o erro de timestamp por frames duplicados e recodificação, e ainda custa de 4 a 11 vezes o tempo real do vídeo.

Cuidados para a implementação (não implementados nesta investigação):

1. Subtrair o PTS do primeiro frame, para o primeiro `timestamp_ms` ser 0 mesmo em vídeos com `start_time` diferente de zero.
2. Verificar que os timestamps são estritamente crescentes e falhar com mensagem clara se não forem.
3. Registrar no metadado a origem do timestamp e um resumo dos intervalos (mediana, máximo, quantidade de intervalos acima de 50 ms), para sinalizar vídeos com muitos frames perdidos.
4. Nas etapas seguintes, calcular velocidades com a diferença real de tempo entre frames, nunca com `1 / fps`.
5. Atualizar o comentário sobre reprodutibilidade no extrator e a pendência registrada em `docs/protocolo-gravacao.md`.

## Limitações

- Três vídeos curtos (15 a 28 s) do mesmo celular. Vídeos longos e outros aparelhos podem ter outro padrão de frames perdidos.
- A concordância entre `CAP_PROP_POS_MSEC` e ffprobe foi verificada só com o OpenCV instalado no `.venv` e no Windows.
- O tempo de conversão foi medido em uma única execução por preset, em uma máquina de 4 núcleos lógicos.
