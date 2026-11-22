# Critérios de aceitação

Este documento define, de forma verificável, quando cada funcionalidade do Boxing Vision é considerada pronta. Nenhuma funcionalidade avança sem cumprir seus critérios.

Começamos por um único objetivo: **identificar corretamente o jab**.

---

## Marco 0: detecção de jab

### Escopo

- Atleta canhoto (base southpaw): jab = mão direita, que é a mão da frente
- Shadowboxing, uma pessoa, câmera fixa
- Diagonal de ~45° pelo lado da mão da frente, corpo inteiro visível, conforme o [protocolo de gravação](protocolo-gravacao.md)
- Vídeos de 10 a 30 segundos, 30 ou 60 FPS

Fora do escopo: base ortodoxa, ângulo frontal, direto, gancho, uppercut, saco de pancadas, sparring e avaliação do retorno à guarda.

O código aceita as duas bases (`--stance`), mas só a base canhota é avaliada no Marco 0. Nenhum resultado para atleta ortodoxo pode ser reivindicado sem um conjunto de teste próprio. A decisão está registrada no [ADR 003](adr/003-base-canhota-no-marco-0.md).

Neste documento, "braço da frente" e "mão da frente" se referem ao lado definido pela base: direito no Marco 0.

### Eventos

O jab e o retorno à guarda são eventos **separados**. Um jab tecnicamente ruim, sem retorno correto, continua sendo reconhecido como jab.

| Evento | O que identifica | Marco |
|--------|------------------|-------|
| `jab` | Extensão do braço da frente correspondente ao golpe | Marco 0 |
| `retorno_guarda` | Se a mão voltou adequadamente após o golpe | Marco 1 |

### Definição operacional de jab

Um jab é um evento em que, na mão da frente:

1. O cotovelo parte de uma posição flexionada
2. O braço se estende na direção à frente do atleta
3. O punho se afasta do ombro além de uma fração do comprimento do braço
4. O braço atinge um pico de extensão e começa a recolher

O evento termina no início do recolhimento. **O retorno completo à guarda não é condição para existir o jab.**

Tratamento de casos limite:

| Situação | Status |
|----------|--------|
| Extensão seguida de recolhimento | `detectado` (jab confirmado) |
| Extensão seguida de braço parado | Evento pendente; encerrado após timeout configurável como `ambiguo` |
| Extensão interrompida antes do limiar | `rejeitado` (possível finta), nunca classificado automaticamente como jab |

Eventos `ambiguo` não contam como detecção nas métricas principais e são reportados à parte.

Os limiares (ângulo do cotovelo, fração de extensão, velocidade mínima, duração máxima) ficam em arquivo de configuração e são calibrados apenas com o conjunto de calibração.

> Limitação: esta definição ainda não foi validada por um treinador de boxe. Ela se baseia em referências técnicas públicas e deve ser revisada quando houver validação profissional.

### Dados

| Conjunto | Uso | Mínimo operacional | Meta |
|----------|-----|--------------------|------|
| Calibração | Ajustar limiares | 6 clipes | |
| Teste | Medir resultado final | 4 clipes, gravados em outro dia | 50 jabs reais e 50 movimentos negativos |

- O conjunto de teste nunca é usado para ajustar limiares
- Rótulos manuais em `labels/*.json`, com início e fim de cada evento em milissegundos
- Enquanto todos os vídeos forem da mesma pessoa, a avaliação é **preliminar** e isso deve constar em todo resultado publicado

### Movimentos negativos obrigatórios

O conjunto de teste deve conter, além de jabs, movimentos que podem confundir o algoritmo:

| Movimento | Por que incluir |
|-----------|-----------------|
| Direto (mão de trás) | Golpe parecido com a outra mão |
| Guarda parada | Linha de base sem movimento |
| Movimentação de pés | Deslocamento do corpo sem golpe |
| Estender a mão da frente sem golpear | Extensão lenta, sem intenção de golpe |
| Ajuste de guarda | Movimento curto da mão da frente |
| Finta de jab | Início de jab interrompido |
| Jab com extensão parcial | Caso limite entre jab e finta (rotular como jab ou negativo e documentar o critério) |
| Dois jabs rápidos (double jab) | Testa se gera exatamente dois eventos |

### Campos de confiança

A confiança do MediaPipe se refere à qualidade/visibilidade de cada ponto do corpo. Ela **não** é a probabilidade de o movimento ser um jab. Por isso, os campos são separados:

| Campo | Significado |
|-------|-------------|
| `confianca_pose` | Qualidade média dos landmarks usados (ombro, cotovelo, punho) durante o evento |
| `confianca_evento` | Score heurístico de 0 a 1 que indica o quanto o movimento atendeu às regras |
| `status` | `detectado`, `ambiguo`, `rejeitado` ou `nao_analisavel` |

`confianca_evento` não é uma probabilidade calibrada e não deve ser apresentado como tal sem validação específica.

### Regra de correspondência

A avaliação compara detecções e rótulos com **correspondência um para um**:

- Uma detecção pode corresponder a um jab rotulado se o centro dela estiver a no máximo 200 ms do centro do rótulo
- A correspondência é **global** e tem duas prioridades, nesta ordem:
  1. Maximizar o número de pares válidos (dentro de 200 ms)
  2. Entre as soluções com esse número máximo, minimizar a soma das diferenças temporais
- Implementação: programação dinâmica na ordem do tempo, sem dependência nova (ver [ADR 004](adr/004-correspondencia-por-programacao-dinamica.md)). Um teste unitário cobre o caso em que a escolha gulosa deixaria um jab sem par, e outro compara o resultado com uma busca exaustiva
- Empates são resolvidos de forma determinística pela ordem do centro do evento e depois de `inicio_ms` (para eventos que não se sobrepõem, é a mesma ordem de `inicio_ms`)
- Detecções duplicadas ou sem rótulo correspondente contam como **falso positivo**
- Jabs rotulados sem detecção correspondente contam como **falso negativo**

Localização temporal e classificação são avaliadas separadamente:

- **Classificação:** precisão, recall e F1 com a regra acima
- **Localização:** erro médio e máximo, em ms, entre início/fim detectados e rotulados nas correspondências corretas

### Categorias de falha

Cada erro no relatório é classificado em uma categoria:

| Categoria | Definição |
|-----------|-----------|
| Falha de pose | Landmarks do braço ausentes ou com `confianca_pose` abaixo do limite durante o jab rotulado |
| Falha de classificação | Pose adequada, mas o detector errou |
| Falha de localização | Jab correspondido, mas com erro de tempo acima do aceitável |

Jabs perdidos por falha de pose **continuam contando como falso negativo** na métrica principal. Uma métrica secundária sem esses casos pode ser reportada, desde que identificada como tal. Isso evita inflar o recall descartando exemplos difíceis.

### Disciplina experimental

- Conjuntos de dados versionados (`dados/v1/calibracao`, `dados/v1/teste`)
- Configuração congelada e registrada (hash do arquivo) antes de rodar no conjunto de teste
- Se limiares ou arquitetura forem alterados com base nos erros do teste, esse conjunto passa a ser de calibração e um **novo conjunto de teste independente** é gravado
- Cada avaliação registra: versão do código, versão dos dados e hash da configuração

### Critérios

> **Atenção:** as metas de precisão e recall abaixo são hipóteses de desempenho, não resultados obtidos. Elas podem ser revistas depois da primeira avaliação real, com a justificativa registrada em `docs/resultados/`.

**CA-01: Correspondência**
- A avaliação aplica a regra de correspondência um para um descrita acima

**CA-02: Precisão**
- Precisão ≥ 0,85 no conjunto de teste

**CA-03: Recall**
- Recall ≥ 0,80 no conjunto de teste

**CA-04: Negativos**
- No máximo 10% dos diretos rotulados são detectados como jab
- A taxa de falso positivo de cada tipo de movimento negativo é reportada separadamente
- Um double jab gera exatamente dois eventos

**CA-05: Jab sem retorno continua sendo jab**
- Clipes de teste com jab sem retorno correto à guarda devem ter o jab detectado normalmente

**CA-06: Reprodutibilidade**
- Mesmo vídeo + mesma versão do código + mesma configuração + mesmo ambiente (versão do MediaPipe, sistema, CPU) = landmarks, eventos e metadados idênticos
- Dados que variam entre execuções (tempo de processamento, data) ficam em arquivo separado (`*_execucao.json`) e não entram na comparação
- Verificado por teste automatizado

**CA-07: Trechos não analisáveis**
- Frames em que `confianca_pose` do braço da frente fica abaixo do limite configurado são marcados como `nao_analisavel`
- Nenhum jab é detectado dentro desses trechos

**CA-08: Saída**
- O JSON contém, para cada evento: `tipo`, `inicio_ms`, `fim_ms`, `mao`, `confianca_pose`, `confianca_evento`, `status`
- O vídeo anotado mostra o esqueleto e um rótulo "JAB" durante cada evento detectado

**CA-09: Desempenho**
- Processar 1 minuto de vídeo leva no máximo 3 minutos no PC de desenvolvimento (8 GB de RAM, sem GPU dedicada)

**CA-10: Avaliação automatizada**
- Um único comando roda a avaliação e imprime precisão, recall, F1, erro de localização, falsos positivos por tipo de movimento e a lista de erros com timestamp

```bash
python -m boxing_vision.evaluate --split teste
```

### Definição de pronto

O Marco 0 está concluído quando:

- [ ] CA-01 a CA-10 passam
- [ ] O relatório de avaliação está salvo em `docs/resultados/marco-0.md`
- [ ] O relatório informa quantos jabs e negativos foram usados e que a avaliação é preliminar
- [ ] Os erros encontrados foram analisados e documentados
- [ ] As limitações observadas foram registradas no README

---

## Próximos marcos

Critérios de `retorno_guarda`, direto e demais funcionalidades serão escritos somente depois que o Marco 0 estiver concluído.
