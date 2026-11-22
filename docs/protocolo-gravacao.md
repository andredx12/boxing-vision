# Protocolo de gravação

Regras para gravar os vídeos de calibração e de teste do Marco 0. Um vídeo fora deste protocolo pode servir para teste de fumaça da pipeline, mas não entra nos conjuntos de dados.

## Posição da câmera

- **Diagonal de ~45° pelo lado da mão da frente.** Para atleta canhoto, a câmera fica à frente do atleta e à direita dele.
- O atleta encara um oponente imaginário à frente, **não a câmera**.
- Câmera fixa (tripé ou apoio), sem tocar nela durante a gravação.
- Altura aproximada do peito.
- Distância de ~3 m entre a câmera e o atleta, o suficiente para manter o corpo inteiro no quadro durante a movimentação de pés.

### Por que diagonal e não frontal

Com a câmera de frente, o jab vai na direção da lente e o braço quase não se estende na imagem 2D. No primeiro vídeo frontal, a razão entre a distância ombro/punho e o comprimento do braço, medida na imagem, ficou entre 0,04 e 0,27 na maioria dos picos de golpe, quando um braço reto no plano da imagem daria perto de 1,0.

Na diagonal de 45°, cerca de 70% da extensão (sen 45°) fica no plano da imagem, e o braço da frente fica mais perto da lente, sem o tronco na frente. **Isso é uma hipótese:** deve ser confirmada com a mesma medida no primeiro clipe diagonal e o resultado registrado em `docs/resultados/`.

## Enquadramento

- **Corpo inteiro visível**, com margem acima da cabeça e abaixo dos pés durante todo o clipe, inclusive na movimentação de pés.
- Uma pessoa só no quadro.

## Iluminação

- Luz na frente ou ao lado do atleta, **nunca atrás**. Janela ou lâmpada atrás do atleta deixa o corpo escuro e reduz a qualidade dos landmarks.

## Início e fim do clipe

1. Iniciar a gravação.
2. Entrar em guarda e esperar 2 segundos parado.
3. Executar a sequência.
4. Voltar à guarda, esperar 2 segundos e só então encerrar a gravação.

Os frames de manuseio da câmera no início e no fim não têm pose útil. O trecho analisado é definido pelos rótulos, não pelas bordas do arquivo.

## Taxa de quadros

- Gravar em 30 ou 60 FPS, com taxa fixa se o celular permitir.
- Registrar a configuração usada.

> **Pendente:** os vídeos de celular gravados até agora têm FPS médio não inteiro (29,38 a 29,94), o que indica taxa de quadros variável. O extrator calcula o timestamp como índice do frame dividido pelo FPS médio, o que pode se afastar do tempo real ao longo do vídeo e afetar a tolerância de 200 ms da regra de correspondência. A decisão sobre como tratar isso no código ainda não foi tomada.

## Registro por clipe

Para cada vídeo, registrar:

| Campo | Exemplo |
|-------|---------|
| Arquivo | `treino_2026-11-27_01.mp4` |
| Data | 2026-11-27 |
| Base | `southpaw` |
| Ângulo | diagonal 45°, lado direito |
| Distância | ~3 m |
| FPS configurado | 30 |
| Conjunto | calibração ou teste |

Os vídeos ficam em `videos/` e nunca são versionados.
