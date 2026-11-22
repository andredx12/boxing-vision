"""Avaliação do detector de jab contra os rótulos manuais.

Regras em docs/criterios-aceitacao.md (regra de correspondência, métricas,
falsos positivos por tipo) e docs/protocolo-rotulagem.md (versão sem dúvida,
grupos e marcações). Funções puras: recebem listas de eventos em dicionários
com os campos do protocolo e devolvem dicionários serializáveis em JSON.
"""

from __future__ import annotations

from collections import defaultdict

from boxing_vision.labels import (
    DUVIDA,
    EXTENSAO_PARCIAL,
    GRUPO_DOUBLE_JAB,
    JAB,
    OCLUSAO,
    SEM_RETORNO,
    TIPOS_NEGATIVOS,
)
# Reexportados: quem importa estes nomes de evaluate continua funcionando
from boxing_vision.vocabulario import STATUS_AMBIGUO, STATUS_DETECTADO  # noqa: F401

LIMITE_MS = 200

# Categorias de falso positivo que não correspondem a um tipo negativo rotulado
FP_DUPLICADO = "duplicado"
FP_SEM_ROTULO = "sem_rotulo"

# Marcações com recall reportado à parte, sem sair da métrica principal
MARCACOES_RECALL = (SEM_RETORNO, EXTENSAO_PARCIAL, OCLUSAO)


def _centro2(evento: dict) -> int:
    """Dobro do centro, em ms. Mantém tudo em inteiros mesmo com centro em meio ms."""
    return evento["inicio_ms"] + evento["fim_ms"]


def _ordem(eventos: list[dict]) -> list[int]:
    return sorted(range(len(eventos)), key=lambda i: (eventos[i]["inicio_ms"], eventos[i]["fim_ms"], i))


def _ordem_temporal(eventos: list[dict]) -> list[int]:
    """Ordem pelo centro, depois inicio_ms. Igual à ordem de inicio_ms quando os eventos não se sobrepõem."""
    return sorted(
        range(len(eventos)),
        key=lambda i: (_centro2(eventos[i]), eventos[i]["inicio_ms"], eventos[i]["fim_ms"], i),
    )


def _tem_duvida(evento: dict) -> bool:
    return DUVIDA in (evento.get("marcacoes") or [])


def _validar(eventos: list[dict], nome: str) -> None:
    for i, e in enumerate(eventos):
        if e["inicio_ms"] > e["fim_ms"]:
            raise ValueError(f"{nome}[{i}]: inicio_ms maior que fim_ms")


def corresponder(
    deteccoes: list[dict], rotulos: list[dict], limite_ms: int = LIMITE_MS
) -> list[tuple[int, int]]:
    """Correspondência um para um global entre detecções e rótulos.

    Prioridades, nesta ordem:
      1. maior número de pares com centros a no máximo limite_ms
      2. menor soma das diferenças entre centros
      3. desempate: parear primeiro os rótulos e depois as detecções mais cedo,
         na ordem do centro e depois de inicio_ms (igual à ordem de inicio_ms
         quando os eventos não se sobrepõem)

    Programação dinâmica na ordem dos centros. Numa solução com dois pares
    cruzados (detecção de centro mais cedo com rótulo de centro mais tarde e
    vice-versa), trocar os pares não aumenta nenhuma das duas distâncias além
    da maior delas, não aumenta a soma e melhora o desempate, então a solução
    ótima não tem cruzamentos e basta percorrer as duas listas ordenadas. A
    ordem tem que ser a dos centros: por inicio_ms o argumento falha quando
    eventos de durações diferentes se sobrepõem. O teste compara com busca exaustiva.

    Devolve pares (índice da detecção, índice do rótulo) nas listas originais,
    na ordem dos rótulos.
    """
    od, orr = _ordem_temporal(deteccoes), _ordem_temporal(rotulos)
    cd = [_centro2(deteccoes[i]) for i in od]
    cr = [_centro2(rotulos[j]) for j in orr]
    n, m = len(cd), len(cr)
    limite2 = 2 * limite_ms

    # melhor[i][j]: melhor solução para as detecções i.. e os rótulos j..
    # Valor: (pares, soma das distâncias x2, pares em posições ordenadas (rótulo, detecção))
    vazio = (0, 0, ())
    melhor = [[vazio] * (m + 1) for _ in range(n + 1)]

    def supera(a, b) -> bool:
        if a[0] != b[0]:
            return a[0] > b[0]
        if a[1] != b[1]:
            return a[1] < b[1]
        return a[2] < b[2]

    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            cand = melhor[i + 1][j]
            if supera(melhor[i][j + 1], cand):
                cand = melhor[i][j + 1]
            dist = abs(cd[i] - cr[j])
            if dist <= limite2:
                resto = melhor[i + 1][j + 1]
                par = (resto[0] + 1, resto[1] + dist, ((j, i),) + resto[2])
                if supera(par, cand):
                    cand = par
            melhor[i][j] = cand

    return [(od[i], orr[j]) for j, i in melhor[0][0][2]] if n and m else []


def _divide(a: int, b: int) -> float | None:
    return a / b if b else None


def _estatisticas(erros: list[float]) -> dict | None:
    if not erros:
        return None
    abs_ = [abs(e) for e in erros]
    return {
        "medio_abs_ms": sum(abs_) / len(abs_),
        "max_abs_ms": max(abs_),
        "medio_com_sinal_ms": sum(erros) / len(erros),
    }


def _classificar_fps(
    sem_par: list[int], deteccoes: list[dict], jabs: list[dict], negativos: list[dict], limite_ms: int
) -> dict[int, tuple[str, int | None]]:
    """Categoria de cada detecção sem par: (tipo negativo | duplicado | sem_rotulo, índice do evento)."""
    limite2 = 2 * limite_ms
    ord_neg, ord_jab = _ordem(negativos), _ordem(jabs)
    saida = {}
    for d in sem_par:
        c = _centro2(deteccoes[d])
        # Negativo que contém o centro; com mais de um, o de centro mais próximo
        dentro = [k for k in ord_neg if 2 * negativos[k]["inicio_ms"] <= c <= 2 * negativos[k]["fim_ms"]]
        if dentro:
            k = min(dentro, key=lambda k: abs(c - _centro2(negativos[k])))
            saida[d] = (negativos[k]["tipo"], k)
            continue
        perto = [k for k in ord_jab if abs(c - _centro2(jabs[k])) <= limite2]
        if perto:
            saida[d] = (FP_DUPLICADO, min(perto, key=lambda k: abs(c - _centro2(jabs[k]))))
        else:
            saida[d] = (FP_SEM_ROTULO, None)
    return saida


def _metricas(
    deteccoes: list[dict],
    jabs: list[dict],
    negativos: list[dict],
    pares: list[tuple[int, int]],
    fps: dict[int, tuple[str, int | None]],
    sem_duvida: bool,
) -> dict:
    jab_ok = [not (sem_duvida and _tem_duvida(j)) for j in jabs]
    neg_ok = [not (sem_duvida and _tem_duvida(n)) for n in negativos]

    pares_v = [(d, r) for d, r in pares if jab_ok[r]]
    # Na versão sem dúvida saem os falsos positivos dentro de negativo com dúvida
    # e os duplicados de jab com dúvida
    fps_v = {
        d: (cat, k) for d, (cat, k) in fps.items()
        if not (cat in TIPOS_NEGATIVOS and not neg_ok[k])
        and not (cat == FP_DUPLICADO and not jab_ok[k])
    }

    tp = len(pares_v)
    fp = len(fps_v)
    fn = sum(jab_ok) - tp
    precisao = _divide(tp, tp + fp)
    recall = _divide(tp, tp + fn)
    if precisao is None or recall is None:
        f1 = None
    elif precisao + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precisao * recall / (precisao + recall)

    loc = None
    if pares_v:
        loc = {
            "inicio": _estatisticas([deteccoes[d]["inicio_ms"] - jabs[r]["inicio_ms"] for d, r in pares_v]),
            "fim": _estatisticas([deteccoes[d]["fim_ms"] - jabs[r]["fim_ms"] for d, r in pares_v]),
            "centro": _estatisticas([(_centro2(deteccoes[d]) - _centro2(jabs[r])) / 2 for d, r in pares_v]),
        }

    # Taxa por tipo: negativos com pelo menos uma detecção / negativos rotulados (CA-04)
    por_neg = defaultdict(int)
    for cat, k in fps_v.values():
        if cat in TIPOS_NEGATIVOS:
            por_neg[k] += 1
    fp_por_tipo = {}
    for tipo in TIPOS_NEGATIVOS:
        idx = [k for k, n in enumerate(negativos) if n["tipo"] == tipo and neg_ok[k]]
        com = sum(1 for k in idx if por_neg[k])
        fp_por_tipo[tipo] = {
            "rotulados": len(idx),
            "com_deteccao": com,
            "deteccoes": sum(por_neg[k] for k in idx),
            "taxa": _divide(com, len(idx)),
        }
    categorias = [cat for cat, _ in fps_v.values()]

    pareados = {r for _, r in pares_v}
    recall_por_marcacao = {}
    for marca in MARCACOES_RECALL:
        idx = [k for k, j in enumerate(jabs) if jab_ok[k] and marca in (j.get("marcacoes") or [])]
        acertos = sum(1 for k in idx if k in pareados)
        recall_por_marcacao[marca] = {"rotulados": len(idx), "detectados": acertos, "recall": _divide(acertos, len(idx))}

    duplicados_por_jab = defaultdict(int)
    for cat, k in fps_v.values():
        if cat == FP_DUPLICADO:
            duplicados_por_jab[k] += 1
    grupos = defaultdict(list)
    for k, j in enumerate(jabs):
        if j.get("grupo") is not None:
            grupos[j["grupo"]].append(k)
    double_jabs = []
    for g in sorted(grupos):
        membros = sorted(grupos[g], key=lambda k: (jabs[k]["inicio_ms"], k))
        if tuple(jabs[k]["tipo"] for k in membros) != GRUPO_DOUBLE_JAB:
            continue
        if not all(jab_ok[k] for k in membros):
            continue
        com_par = sum(1 for k in membros if k in pareados)
        extras = sum(duplicados_por_jab[k] for k in membros)
        double_jabs.append({
            "grupo": g,
            "inicio_ms": jabs[membros[0]]["inicio_ms"],
            "jabs_com_par": com_par,
            "deteccoes": com_par + extras,
            "ok": com_par == len(membros) and extras == 0,
        })

    erros = [
        {"erro": "falso_negativo", "inicio_ms": jabs[k]["inicio_ms"], "fim_ms": jabs[k]["fim_ms"], "categoria": None}
        for k in range(len(jabs)) if jab_ok[k] and k not in pareados
    ] + [
        {"erro": "falso_positivo", "inicio_ms": deteccoes[d]["inicio_ms"], "fim_ms": deteccoes[d]["fim_ms"], "categoria": cat}
        for d, (cat, _) in fps_v.items()
    ]
    erros.sort(key=lambda e: (e["inicio_ms"], e["fim_ms"], e["erro"]))

    return {
        "jabs_rotulados": sum(jab_ok),
        "verdadeiros_positivos": tp,
        "falsos_positivos": fp,
        "falsos_negativos": fn,
        "precisao": precisao,
        "recall": recall,
        "f1": f1,
        "localizacao": loc,
        "fp_por_tipo": fp_por_tipo,
        "fp_duplicados": categorias.count(FP_DUPLICADO),
        "fp_sem_rotulo": categorias.count(FP_SEM_ROTULO),
        "recall_por_marcacao": recall_por_marcacao,
        "double_jabs": double_jabs,
        "erros": erros,
    }


def avaliar(
    deteccoes: list[dict],
    rotulos: list[dict],
    trecho: dict | None = None,
    limite_ms: int = LIMITE_MS,
) -> dict:
    """Avalia as detecções de um clipe contra os rótulos dele.

    deteccoes: eventos do detector (inicio_ms, fim_ms, tipo, status).
    rotulos: eventos do arquivo de rótulos (inicio_ms, fim_ms, tipo, marcacoes, grupo).
    trecho: trecho_analisado do arquivo de rótulos; detecções com centro fora dele são ignoradas.

    Devolve a versão com dúvida (métrica principal) e a versão sem dúvida lado a lado.
    """
    _validar(deteccoes, "deteccoes")
    _validar(rotulos, "rotulos")

    def no_trecho(e: dict) -> bool:
        if trecho is None:
            return True
        return 2 * trecho["inicio_ms"] <= _centro2(e) <= 2 * trecho["fim_ms"]

    jab_det = [d for d in deteccoes if d["tipo"] == JAB]
    validas = [d for d in jab_det if d["status"] == STATUS_DETECTADO and no_trecho(d)]
    ambiguas = sum(1 for d in jab_det if d["status"] == STATUS_AMBIGUO and no_trecho(d))
    fora = sum(1 for d in jab_det if d["status"] in (STATUS_DETECTADO, STATUS_AMBIGUO) and not no_trecho(d))

    jabs = [r for r in rotulos if r["tipo"] == JAB]
    negativos = [r for r in rotulos if r["tipo"] in TIPOS_NEGATIVOS]

    # A correspondência usa todos os eventos; a versão sem dúvida só filtra depois
    pares = corresponder(validas, jabs, limite_ms)
    com_par = {d for d, _ in pares}
    sem_par = [d for d in _ordem(validas) if d not in com_par]
    fps = _classificar_fps(sem_par, validas, jabs, negativos, limite_ms)

    return {
        "limite_ms": limite_ms,
        "deteccoes_consideradas": len(validas),
        "deteccoes_ambiguas": ambiguas,
        "deteccoes_fora_do_trecho": fora,
        "eventos_com_duvida": sum(1 for r in rotulos if _tem_duvida(r)),
        "pares": [
            {
                "deteccao": {"inicio_ms": validas[d]["inicio_ms"], "fim_ms": validas[d]["fim_ms"]},
                "rotulo": {"inicio_ms": jabs[r]["inicio_ms"], "fim_ms": jabs[r]["fim_ms"]},
                "erro_centro_ms": (_centro2(validas[d]) - _centro2(jabs[r])) / 2,
            }
            for d, r in pares
        ],
        "com_duvida": _metricas(validas, jabs, negativos, pares, fps, sem_duvida=False),
        "sem_duvida": _metricas(validas, jabs, negativos, pares, fps, sem_duvida=True),
    }
