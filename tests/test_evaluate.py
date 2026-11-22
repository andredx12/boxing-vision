import random

import pytest

from boxing_vision.evaluate import FP_DUPLICADO, FP_SEM_ROTULO, avaliar, corresponder
from boxing_vision.labels import (
    AJUSTE_GUARDA,
    DIRETO,
    DUVIDA,
    EXTENSAO_PARCIAL,
    FINTA_JAB,
    JAB,
    OCLUSAO,
    SEM_RETORNO,
)


def rot(centro, tipo=JAB, meia=50, marcacoes=(), grupo=None):
    return {
        "inicio_ms": centro - meia, "fim_ms": centro + meia, "tipo": tipo,
        "marcacoes": list(marcacoes), "grupo": grupo,
    }


def det(centro, meia=50, status="detectado", tipo=JAB):
    return {"inicio_ms": centro - meia, "fim_ms": centro + meia, "tipo": tipo, "status": status}


def centros_pareados(deteccoes, rotulos):
    def c(e):
        return (e["inicio_ms"] + e["fim_ms"]) / 2
    return sorted((c(deteccoes[d]), c(rotulos[r])) for d, r in corresponder(deteccoes, rotulos))


# Correspondência

def test_guloso_deixaria_jab_sem_par():
    # O par mais próximo (detecção 1180 com rótulo 1350, 170 ms) deixaria a
    # detecção 1550 sem rótulo alcançável e o rótulo 1000 sem par.
    # O ótimo forma 2 pares mesmo com soma maior (180 + 200 > 170).
    rotulos = [rot(1000), rot(1350)]
    deteccoes = [det(1180), det(1550)]
    assert centros_pareados(deteccoes, rotulos) == [(1180, 1000), (1550, 1350)]

    r = avaliar(deteccoes, rotulos)["com_duvida"]
    assert (r["verdadeiros_positivos"], r["falsos_positivos"], r["falsos_negativos"]) == (2, 0, 0)


def test_limite_de_200_ms_inclusivo():
    assert centros_pareados([det(1200)], [rot(1000)]) == [(1200, 1000)]
    # Centro em 1200,5 ms: fora por meio milissegundo
    fora = {"inicio_ms": 1150, "fim_ms": 1251, "tipo": JAB, "status": "detectado"}
    assert corresponder([fora], [rot(1000)]) == []


def test_menor_soma_entre_solucoes_com_mesmo_numero_de_pares():
    rotulos = [rot(1000), rot(1100)]
    deteccoes = [det(1010), det(1120)]
    assert centros_pareados(deteccoes, rotulos) == [(1010, 1000), (1120, 1100)]


def test_empate_favorece_rotulo_mais_cedo():
    assert centros_pareados([det(1000)], [rot(1100), rot(900)]) == [(1000, 900)]


def test_empate_favorece_deteccao_mais_cedo():
    assert centros_pareados([det(1100), det(900)], [rot(1000)]) == [(900, 1000)]


def test_indices_referem_listas_originais():
    rotulos = [rot(3000), rot(1000)]
    deteccoes = [det(1010), det(5000), det(2990)]
    assert sorted(corresponder(deteccoes, rotulos)) == [(0, 1), (2, 0)]


def test_listas_vazias():
    assert corresponder([], [rot(1000)]) == []
    assert corresponder([det(1000)], []) == []


def _forca_bruta(deteccoes, rotulos, limite_ms=200):
    """Percorre todas as correspondências possíveis com as mesmas três prioridades."""
    c2 = lambda e: e["inicio_ms"] + e["fim_ms"]

    def ordem(ev):
        return sorted(range(len(ev)), key=lambda i: (c2(ev[i]), ev[i]["inicio_ms"], ev[i]["fim_ms"], i))

    od, orr = ordem(deteccoes), ordem(rotulos)
    pos_d = {d: p for p, d in enumerate(od)}
    melhor = None

    def busca(j, usadas, pares, custo):
        nonlocal melhor
        if j == len(orr):
            chave = tuple(sorted((jj, pos_d[d]) for d, jj in pares))
            cand = (-len(pares), custo, chave, list(pares))
            if melhor is None or cand[:3] < melhor[:3]:
                melhor = cand
            return
        r = orr[j]
        busca(j + 1, usadas, pares, custo)
        for d in range(len(deteccoes)):
            dist = abs(c2(deteccoes[d]) - c2(rotulos[r]))
            if d not in usadas and dist <= 2 * limite_ms:
                busca(j + 1, usadas | {d}, pares + [(d, j)], custo + dist)

    busca(0, frozenset(), [], 0)
    return sorted((d, orr[j]) for d, j in melhor[3])


def test_programacao_dinamica_igual_a_busca_exaustiva():
    rng = random.Random(20261122)
    for _ in range(2000):
        rotulos = [rot(rng.randrange(0, 1500, 10), meia=rng.randrange(10, 120, 10)) for _ in range(rng.randint(0, 6))]
        deteccoes = [det(rng.randrange(0, 1500, 10), meia=rng.randrange(10, 120, 10)) for _ in range(rng.randint(0, 6))]
        assert sorted(corresponder(deteccoes, rotulos)) == _forca_bruta(deteccoes, rotulos)


def test_eventos_sobrepostos_de_duracoes_diferentes():
    # Caso achado pela busca exaustiva: a ordem por inicio_ms difere da ordem
    # dos centros (rótulo 510-710 começa antes de 570-630, mas o centro é depois).
    # Percorrer por inicio_ms dava soma 200 ms; o ótimo é 180 ms.
    deteccoes = [{"inicio_ms": a, "fim_ms": b, "tipo": JAB, "status": "detectado"}
                 for a, b in [(390, 610), (660, 720), (1120, 1220)]]
    rotulos = [{"inicio_ms": a, "fim_ms": b, "tipo": JAB, "marcacoes": [], "grupo": None}
               for a, b in [(510, 710), (170, 290), (1110, 1230), (570, 630)]]
    pares = corresponder(deteccoes, rotulos)
    assert len(pares) == 3
    assert sum(abs(deteccoes[d]["inicio_ms"] + deteccoes[d]["fim_ms"] - rotulos[r]["inicio_ms"] - rotulos[r]["fim_ms"])
               for d, r in pares) == 360
    assert sorted(pares) == _forca_bruta(deteccoes, rotulos)


def test_ordem_da_entrada_nao_muda_resultado():
    rng = random.Random(7)
    rotulos = [rot(c) for c in (1000, 1350, 2000, 2300, 3000)] + [rot(4000, tipo=DIRETO)]
    deteccoes = [det(c) for c in (1180, 1550, 2150, 2160, 3500, 4010)]
    base = avaliar(deteccoes, rotulos)
    for _ in range(20):
        rng.shuffle(rotulos)
        rng.shuffle(deteccoes)
        assert avaliar(deteccoes, rotulos) == base


# Métricas

def test_precisao_recall_f1():
    rotulos = [rot(1000), rot(2000), rot(3000)]
    deteccoes = [det(1000), det(2000), det(5000)]
    r = avaliar(deteccoes, rotulos)["com_duvida"]
    assert (r["verdadeiros_positivos"], r["falsos_positivos"], r["falsos_negativos"]) == (2, 1, 1)
    assert r["precisao"] == pytest.approx(2 / 3)
    assert r["recall"] == pytest.approx(2 / 3)
    assert r["f1"] == pytest.approx(2 / 3)
    assert r["fp_sem_rotulo"] == 1
    assert [e["erro"] for e in r["erros"]] == ["falso_negativo", "falso_positivo"]
    assert r["erros"][1]["categoria"] == FP_SEM_ROTULO


def test_divisao_por_zero():
    r = avaliar([], [rot(1000)])["com_duvida"]
    assert r["precisao"] is None and r["recall"] == 0 and r["f1"] is None
    r = avaliar([], [])["com_duvida"]
    assert r["precisao"] is None and r["recall"] is None and r["f1"] is None
    r = avaliar([det(1000)], [rot(5000)])["com_duvida"]
    assert r["precisao"] == 0 and r["recall"] == 0 and r["f1"] == 0


def test_erro_de_localizacao():
    rotulos = [{"inicio_ms": 1000, "fim_ms": 1200, "tipo": JAB, "marcacoes": [], "grupo": None},
               {"inicio_ms": 3000, "fim_ms": 3200, "tipo": JAB, "marcacoes": [], "grupo": None}]
    deteccoes = [{"inicio_ms": 1030, "fim_ms": 1190, "tipo": JAB, "status": "detectado"},
                 {"inicio_ms": 2950, "fim_ms": 3220, "tipo": JAB, "status": "detectado"}]
    loc = avaliar(deteccoes, rotulos)["com_duvida"]["localizacao"]
    assert loc["inicio"] == {"medio_abs_ms": 40, "max_abs_ms": 50, "medio_com_sinal_ms": -10}
    assert loc["fim"] == {"medio_abs_ms": 15, "max_abs_ms": 20, "medio_com_sinal_ms": 5}
    assert loc["centro"] == {"medio_abs_ms": 12.5, "max_abs_ms": 15, "medio_com_sinal_ms": -2.5}
    assert avaliar([], rotulos)["com_duvida"]["localizacao"] is None


def test_deteccao_duplicada_conta_como_falso_positivo():
    r = avaliar([det(1000), det(1100)], [rot(1000)])["com_duvida"]
    assert (r["verdadeiros_positivos"], r["falsos_positivos"]) == (1, 1)
    assert r["fp_duplicados"] == 1
    assert r["erros"][0]["categoria"] == FP_DUPLICADO


def test_falsos_positivos_por_tipo_de_negativo():
    rotulos = [
        rot(1000, tipo=DIRETO, meia=120), rot(3000, tipo=DIRETO, meia=120),
        rot(5000, tipo=FINTA_JAB, meia=80), rot(7000),
    ]
    deteccoes = [det(1000), det(1060), det(7000)]
    r = avaliar(deteccoes, rotulos)["com_duvida"]
    assert r["fp_por_tipo"][DIRETO] == {"rotulados": 2, "com_deteccao": 1, "deteccoes": 2, "taxa": 0.5}
    assert r["fp_por_tipo"][FINTA_JAB] == {"rotulados": 1, "com_deteccao": 0, "deteccoes": 0, "taxa": 0}
    assert r["fp_por_tipo"][AJUSTE_GUARDA]["taxa"] is None
    assert r["falsos_positivos"] == 2 and r["fp_duplicados"] == 0


def test_negativo_tem_prioridade_sobre_duplicado():
    # Finta seguida de jab: detecção extra no centro da finta, a 150 ms do jab
    rotulos = [rot(1000, tipo=FINTA_JAB, grupo="g1"), rot(1150, grupo="g1")]
    r = avaliar([det(1000), det(1150)], rotulos)["com_duvida"]
    assert r["fp_por_tipo"][FINTA_JAB]["com_deteccao"] == 1
    assert r["fp_duplicados"] == 0


def test_status_e_tipo_das_deteccoes():
    deteccoes = [
        det(1000), det(2000, status="ambiguo"), det(3000, status="rejeitado"),
        det(4000, status="nao_analisavel"), det(5000, tipo=DIRETO),
    ]
    rotulos = [rot(1000), rot(2000)]
    r = avaliar(deteccoes, rotulos)
    assert r["deteccoes_consideradas"] == 1
    assert r["deteccoes_ambiguas"] == 1
    c = r["com_duvida"]
    # O ambíguo não conta como detecção: o jab de 2000 fica sem par
    assert (c["verdadeiros_positivos"], c["falsos_positivos"], c["falsos_negativos"]) == (1, 0, 1)


def test_deteccoes_fora_do_trecho_analisado_sao_ignoradas():
    trecho = {"inicio_ms": 500, "fim_ms": 3000}
    r = avaliar([det(1000), det(200), det(3500)], [rot(1000)], trecho=trecho)
    assert r["deteccoes_consideradas"] == 1
    assert r["deteccoes_fora_do_trecho"] == 2
    assert r["com_duvida"]["falsos_positivos"] == 0


def test_inicio_maior_que_fim_e_rejeitado():
    with pytest.raises(ValueError):
        avaliar([{"inicio_ms": 10, "fim_ms": 5, "tipo": JAB, "status": "detectado"}], [])


# Double jab (CA-04)

DOUBLE = [rot(1100, meia=100, grupo="g1"), rot(1450, meia=100, grupo="g1")]


def test_double_jab_com_duas_deteccoes():
    r = avaliar([det(1100), det(1450)], DOUBLE)["com_duvida"]
    assert r["double_jabs"] == [{"grupo": "g1", "inicio_ms": 1000, "jabs_com_par": 2, "deteccoes": 2, "ok": True}]


def test_double_jab_com_uma_deteccao():
    # Uma detecção cobrindo os dois golpes: centro equidistante, fica com o primeiro
    r = avaliar([{"inicio_ms": 1000, "fim_ms": 1550, "tipo": JAB, "status": "detectado"}], DOUBLE)["com_duvida"]
    assert r["double_jabs"][0]["jabs_com_par"] == 1
    assert r["double_jabs"][0]["ok"] is False
    assert r["falsos_negativos"] == 1


def test_double_jab_com_tres_deteccoes():
    r = avaliar([det(1100), det(1300), det(1450)], DOUBLE)["com_duvida"]
    assert r["double_jabs"][0]["deteccoes"] == 3
    assert r["double_jabs"][0]["ok"] is False
    assert r["fp_duplicados"] == 1


def test_grupo_finta_jab_nao_entra_como_double_jab():
    rotulos = [rot(1000, tipo=FINTA_JAB, grupo="g2"), rot(1300, grupo="g2")]
    assert avaliar([det(1300)], rotulos)["com_duvida"]["double_jabs"] == []


# Recall por marcação (CA-05)

def test_recall_por_marcacao():
    rotulos = [
        rot(1000, marcacoes=[SEM_RETORNO]), rot(2000, marcacoes=[SEM_RETORNO]),
        rot(3000, marcacoes=[EXTENSAO_PARCIAL]), rot(4000),
    ]
    r = avaliar([det(1000), det(3000), det(4000)], rotulos)["com_duvida"]["recall_por_marcacao"]
    assert r[SEM_RETORNO] == {"rotulados": 2, "detectados": 1, "recall": 0.5}
    assert r[EXTENSAO_PARCIAL] == {"rotulados": 1, "detectados": 1, "recall": 1.0}
    assert r[OCLUSAO] == {"rotulados": 0, "detectados": 0, "recall": None}


# Versão sem dúvida

def test_jab_com_duvida_sai_junto_com_a_deteccao_pareada():
    rotulos = [rot(1000), rot(3000, marcacoes=[DUVIDA])]
    r = avaliar([det(1000), det(3000)], rotulos)
    assert r["eventos_com_duvida"] == 1
    c, s = r["com_duvida"], r["sem_duvida"]
    assert (c["jabs_rotulados"], c["verdadeiros_positivos"], c["falsos_positivos"]) == (2, 2, 0)
    assert (s["jabs_rotulados"], s["verdadeiros_positivos"], s["falsos_positivos"]) == (1, 1, 0)


def test_jab_com_duvida_sem_par_nao_conta_como_falso_negativo():
    rotulos = [rot(1000), rot(3000, marcacoes=[DUVIDA])]
    r = avaliar([det(1000)], rotulos)
    assert r["com_duvida"]["falsos_negativos"] == 1
    assert r["sem_duvida"]["falsos_negativos"] == 0
    assert r["sem_duvida"]["recall"] == 1


def test_falso_positivo_em_negativo_com_duvida_sai_da_conta():
    rotulos = [rot(1000, tipo=FINTA_JAB, meia=80, marcacoes=[DUVIDA]), rot(3000, tipo=FINTA_JAB, meia=80)]
    r = avaliar([det(1000), det(3000)], rotulos)
    assert r["com_duvida"]["falsos_positivos"] == 2
    assert r["com_duvida"]["fp_por_tipo"][FINTA_JAB]["rotulados"] == 2
    assert r["sem_duvida"]["falsos_positivos"] == 1
    assert r["sem_duvida"]["fp_por_tipo"][FINTA_JAB] == {"rotulados": 1, "com_deteccao": 1, "deteccoes": 1, "taxa": 1.0}


def test_duplicado_de_jab_com_duvida_sai_da_conta():
    rotulos = [rot(1000, marcacoes=[DUVIDA]), rot(3000)]
    deteccoes = [det(1000), det(1100), det(3000), det(3100)]
    r = avaliar(deteccoes, rotulos)
    assert (r["com_duvida"]["falsos_positivos"], r["com_duvida"]["fp_duplicados"]) == (2, 2)
    # Sai o duplicado do jab duvidoso; o duplicado do jab sem dúvida continua
    s = r["sem_duvida"]
    assert (s["verdadeiros_positivos"], s["falsos_positivos"], s["fp_duplicados"]) == (1, 1, 1)
    assert [e["inicio_ms"] for e in s["erros"]] == [3050]


def test_correspondencia_usa_todos_os_eventos_antes_de_tirar_a_duvida():
    # Com todos os eventos, a única detecção pareia com o jab duvidoso (distância 0).
    # Se o duvidoso saísse antes, ela pareia com o jab de 1150 e viraria acerto.
    rotulos = [rot(1000, marcacoes=[DUVIDA]), rot(1150)]
    s = avaliar([det(1000)], rotulos)["sem_duvida"]
    assert (s["verdadeiros_positivos"], s["falsos_positivos"], s["falsos_negativos"]) == (0, 0, 1)
