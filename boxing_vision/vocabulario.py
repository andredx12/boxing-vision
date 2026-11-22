"""Vocabulário compartilhado do Boxing Vision.

Valores usados ao mesmo tempo pela extração, pelos rótulos manuais e pela
avaliação. Este módulo não importa nada do projeto, para que qualquer outro
possa importá-lo sem risco de importação circular.
"""

# Mão anatômica do atleta, não o lado da imagem
MAO_DIREITA = "direita"
MAO_ESQUERDA = "esquerda"
MAOS = (MAO_DIREITA, MAO_ESQUERDA)

# Bases aceitas (os mesmos valores do --stance da extração)
BASE_ORTODOXA = "orthodox"
BASE_CANHOTA = "southpaw"
BASES = (BASE_ORTODOXA, BASE_CANHOTA)

MAO_DA_FRENTE = {BASE_ORTODOXA: MAO_ESQUERDA, BASE_CANHOTA: MAO_DIREITA}
MAO_DE_TRAS = {BASE_ORTODOXA: MAO_DIREITA, BASE_CANHOTA: MAO_ESQUERDA}

# Status de saída do detector (CA-08)
STATUS_DETECTADO = "detectado"
STATUS_AMBIGUO = "ambiguo"
