"""Carregamento e validação dos rótulos manuais (labels/<video>.json).

As regras seguem docs/protocolo-rotulagem.md. O vocabulário (mão, base, tipos,
marcações) fica definido aqui para ser importado pelo avaliador.

Uso:
    python -m boxing_vision.labels labels/treino_2026-11-27_01.json
    python -m boxing_vision.labels labels/*.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# Mão anatômica do atleta, não o lado da imagem
MAO_DIREITA = "direita"
MAO_ESQUERDA = "esquerda"
MAOS = (MAO_DIREITA, MAO_ESQUERDA)

# Bases aceitas (mesmos valores do --stance da extração)
BASE_ORTODOXA = "orthodox"
BASE_CANHOTA = "southpaw"
BASES = (BASE_ORTODOXA, BASE_CANHOTA)

MAO_DA_FRENTE = {BASE_ORTODOXA: MAO_ESQUERDA, BASE_CANHOTA: MAO_DIREITA}
MAO_DE_TRAS = {BASE_ORTODOXA: MAO_DIREITA, BASE_CANHOTA: MAO_ESQUERDA}

CONJUNTOS = ("calibracao", "teste")

# Tipos de evento
JAB = "jab"
DIRETO = "direto"
GUARDA_PARADA = "guarda_parada"
MOVIMENTACAO_PES = "movimentacao_pes"
EXTENSAO_SEM_GOLPE = "extensao_sem_golpe"
AJUSTE_GUARDA = "ajuste_guarda"
FINTA_JAB = "finta_jab"
TIPOS = (JAB, DIRETO, GUARDA_PARADA, MOVIMENTACAO_PES, EXTENSAO_SEM_GOLPE, AJUSTE_GUARDA, FINTA_JAB)
TIPOS_POSITIVOS = (JAB,)
TIPOS_NEGATIVOS = tuple(t for t in TIPOS if t not in TIPOS_POSITIVOS)

# Mão permitida por tipo: "frente", "tras", "qualquer" ou None (sem mão)
_MAO_POR_TIPO = {
    JAB: "frente",
    DIRETO: "tras",
    GUARDA_PARADA: None,
    MOVIMENTACAO_PES: None,
    EXTENSAO_SEM_GOLPE: "frente",
    AJUSTE_GUARDA: "qualquer",
    FINTA_JAB: "frente",
}

# Marcações e os tipos em que cada uma pode aparecer
SEM_RETORNO = "sem_retorno"
EXTENSAO_PARCIAL = "extensao_parcial"
DUVIDA = "duvida"
OCLUSAO = "oclusao"
MARCACOES = {
    SEM_RETORNO: (JAB, DIRETO),
    EXTENSAO_PARCIAL: (JAB,),
    DUVIDA: TIPOS,
    OCLUSAO: TIPOS,
}

# Combinações de tipos aceitas num grupo, na ordem de inicio_ms
GRUPO_DOUBLE_JAB = (JAB, JAB)
GRUPO_FINTA_JAB = (FINTA_JAB, JAB)
GRUPOS_VALIDOS = (GRUPO_DOUBLE_JAB, GRUPO_FINTA_JAB)

CAMPOS_ARQUIVO = (
    "video", "conjunto", "base", "ferramenta", "rotulador",
    "data_rotulagem", "trecho_analisado", "eventos",
)
CAMPOS_TRECHO = ("inicio_ms", "fim_ms")
CAMPOS_EVENTO = ("inicio_ms", "fim_ms", "tipo", "mao", "marcacoes", "grupo", "observacao")


@dataclass(frozen=True)
class Evento:
    inicio_ms: int
    fim_ms: int
    tipo: str
    mao: str | None
    marcacoes: tuple[str, ...]
    grupo: str | None
    observacao: str

    @property
    def centro_ms(self) -> float:
        return (self.inicio_ms + self.fim_ms) / 2


@dataclass(frozen=True)
class Rotulos:
    video: str
    conjunto: str
    base: str
    ferramenta: str
    rotulador: str
    data_rotulagem: str
    trecho_inicio_ms: int
    trecho_fim_ms: int
    eventos: tuple[Evento, ...]


class RotulosInvalidos(Exception):
    def __init__(self, caminho: Path, erros: list[str]):
        self.caminho = caminho
        self.erros = erros
        super().__init__(f"{caminho}: {len(erros)} erro(s) de validação")


def _eh_inteiro(valor) -> bool:
    # bool é subclasse de int em Python e não deve passar como tempo
    return isinstance(valor, int) and not isinstance(valor, bool)


def _texto_nao_vazio(valor) -> bool:
    return isinstance(valor, str) and valor.strip() != ""


def _campos(obj: dict, esperados: tuple[str, ...], onde: str) -> list[str]:
    erros = [f"{onde}: campo obrigatório ausente: {c}" for c in esperados if c not in obj]
    erros += [f"{onde}: campo desconhecido: {c}" for c in obj if c not in esperados]
    return erros


def _maos_permitidas(tipo: str, base: str) -> tuple[str | None, ...]:
    regra = _MAO_POR_TIPO[tipo]
    if regra is None:
        return (None,)
    if regra == "qualquer":
        return MAOS
    if regra == "frente":
        return (MAO_DA_FRENTE[base],)
    return (MAO_DE_TRAS[base],)


def _validar_evento(ev: dict, onde: str, base: str | None, trecho: tuple[int, int] | None) -> list[str]:
    erros = _campos(ev, CAMPOS_EVENTO, onde)

    inicio, fim = ev.get("inicio_ms"), ev.get("fim_ms")
    tempos_ok = True
    for nome, valor in (("inicio_ms", inicio), ("fim_ms", fim)):
        if nome in ev and (not _eh_inteiro(valor) or valor < 0):
            erros.append(f"{onde}: {nome} deve ser inteiro não negativo, recebido {valor!r}")
            tempos_ok = False
    tempos_ok = tempos_ok and "inicio_ms" in ev and "fim_ms" in ev
    if tempos_ok:
        if inicio >= fim:
            erros.append(f"{onde}: inicio_ms ({inicio}) deve ser menor que fim_ms ({fim})")
        if trecho is not None and (inicio < trecho[0] or fim > trecho[1]):
            erros.append(
                f"{onde}: evento {inicio}-{fim} ms fora de trecho_analisado {trecho[0]}-{trecho[1]} ms"
            )

    tipo = ev.get("tipo")
    tipo_ok = tipo in TIPOS
    if "tipo" in ev and not tipo_ok:
        erros.append(f"{onde}: tipo desconhecido: {tipo!r}")

    if "mao" in ev:
        mao = ev["mao"]
        if mao is not None and mao not in MAOS:
            erros.append(f"{onde}: mao deve ser {MAOS} ou null, recebido {mao!r}")
        elif tipo_ok and base in BASES:
            permitidas = _maos_permitidas(tipo, base)
            if mao not in permitidas:
                legivel = ", ".join("null" if m is None else m for m in permitidas)
                erros.append(f"{onde}: mao {mao!r} incompatível com tipo {tipo!r} (esperado: {legivel})")

    marcacoes = ev.get("marcacoes")
    if "marcacoes" in ev:
        if not isinstance(marcacoes, list):
            erros.append(f"{onde}: marcacoes deve ser uma lista, recebido {marcacoes!r}")
            marcacoes = []
        for m in marcacoes:
            if m not in MARCACOES:
                erros.append(f"{onde}: marcação desconhecida: {m!r}")
            elif tipo_ok and tipo not in MARCACOES[m]:
                erros.append(f"{onde}: marcação {m!r} não é permitida para o tipo {tipo!r}")
        repetidas = sorted({m for m in marcacoes if isinstance(m, str) and marcacoes.count(m) > 1})
        for m in repetidas:
            erros.append(f"{onde}: marcação repetida: {m!r}")
    else:
        marcacoes = []

    observacao = ev.get("observacao")
    if "observacao" in ev and not isinstance(observacao, str):
        erros.append(f"{onde}: observacao deve ser texto, recebido {observacao!r}")
    elif DUVIDA in marcacoes and not _texto_nao_vazio(observacao):
        erros.append(f"{onde}: marcação 'duvida' exige o motivo em observacao")

    if "grupo" in ev and ev["grupo"] is not None and not _texto_nao_vazio(ev["grupo"]):
        erros.append(f"{onde}: grupo deve ser texto não vazio ou null, recebido {ev['grupo']!r}")

    return erros


def _tempos_validos(ev: dict) -> bool:
    i, f = ev.get("inicio_ms"), ev.get("fim_ms")
    return _eh_inteiro(i) and _eh_inteiro(f) and i < f


def _validar_conjunto_de_eventos(eventos: list[dict]) -> list[str]:
    erros = []
    validos = [(n, ev) for n, ev in enumerate(eventos) if isinstance(ev, dict) and _tempos_validos(ev)]

    # Ordem por inicio_ms
    for (n_ant, ant), (n, ev) in zip(validos, validos[1:]):
        if ev["inicio_ms"] < ant["inicio_ms"]:
            erros.append(
                f"eventos[{n}]: fora de ordem (inicio_ms {ev['inicio_ms']} menor que "
                f"o de eventos[{n_ant}], {ant['inicio_ms']})"
            )

    # Jab não pode se sobrepor a nenhum outro evento; encostar (fim == início) é permitido
    for n, jab in validos:
        if jab.get("tipo") != JAB:
            continue
        for m, outro in validos:
            if m == n or (outro.get("tipo") == JAB and m < n):
                continue  # par jab/jab é reportado uma vez só
            if jab["inicio_ms"] < outro["fim_ms"] and outro["inicio_ms"] < jab["fim_ms"]:
                erros.append(
                    f"eventos[{n}]: jab {jab['inicio_ms']}-{jab['fim_ms']} ms se sobrepõe a "
                    f"eventos[{m}] ({outro.get('tipo')}, {outro['inicio_ms']}-{outro['fim_ms']} ms)"
                )

    # Grupos: exatamente dois eventos, numa combinação válida
    grupos: dict[str, list[tuple[int, dict]]] = {}
    for n, ev in enumerate(eventos):
        if isinstance(ev, dict) and _texto_nao_vazio(ev.get("grupo")):
            grupos.setdefault(ev["grupo"], []).append((n, ev))
    for nome, membros in grupos.items():
        if len(membros) != 2:
            erros.append(f"grupo {nome!r}: deve ter exatamente 2 eventos, tem {len(membros)}")
            continue
        if not all(_tempos_validos(ev) for _, ev in membros):
            continue  # a ordem do grupo não é confiável sem tempos válidos
        ordenados = sorted(membros, key=lambda par: par[1]["inicio_ms"])
        tipos = tuple(ev.get("tipo") for _, ev in ordenados)
        if tipos not in GRUPOS_VALIDOS:
            validas = " ou ".join(" + ".join(g) for g in GRUPOS_VALIDOS)
            erros.append(
                f"grupo {nome!r}: combinação {' + '.join(map(str, tipos))} inválida (esperado: {validas})"
            )

    return erros


def validar(dados, nome_arquivo: str | None = None) -> list[str]:
    """Devolve a lista de todos os erros encontrados. Lista vazia = rótulos válidos."""
    if not isinstance(dados, dict):
        return ["o arquivo deve conter um objeto JSON"]

    erros = _campos(dados, CAMPOS_ARQUIVO, "arquivo")

    video = dados.get("video")
    if "video" in dados:
        if not _texto_nao_vazio(video):
            erros.append(f"arquivo: video deve ser texto não vazio, recebido {video!r}")
        elif nome_arquivo is not None and Path(video).stem != Path(nome_arquivo).stem:
            erros.append(
                f"arquivo: video {video!r} não corresponde ao nome do arquivo de rótulos {nome_arquivo!r}"
            )

    if "conjunto" in dados and dados["conjunto"] not in CONJUNTOS:
        erros.append(f"arquivo: conjunto deve ser {CONJUNTOS}, recebido {dados['conjunto']!r}")

    base = dados.get("base")
    if "base" in dados and base not in BASES:
        erros.append(f"arquivo: base deve ser {BASES}, recebido {base!r}")

    for campo in ("ferramenta", "rotulador"):
        if campo in dados and not _texto_nao_vazio(dados[campo]):
            erros.append(f"arquivo: {campo} deve ser texto não vazio, recebido {dados[campo]!r}")

    if "data_rotulagem" in dados:
        valor = dados["data_rotulagem"]
        try:
            if not isinstance(valor, str) or len(valor) != 10:
                raise ValueError
            date.fromisoformat(valor)
        except ValueError:
            erros.append(f"arquivo: data_rotulagem deve ser uma data AAAA-MM-DD, recebido {valor!r}")

    trecho = None
    if "trecho_analisado" in dados:
        t = dados["trecho_analisado"]
        if not isinstance(t, dict):
            erros.append(f"trecho_analisado: deve ser um objeto, recebido {t!r}")
        else:
            erros_trecho = _campos(t, CAMPOS_TRECHO, "trecho_analisado")
            for nome in CAMPOS_TRECHO:
                if nome in t and (not _eh_inteiro(t[nome]) or t[nome] < 0):
                    erros_trecho.append(
                        f"trecho_analisado: {nome} deve ser inteiro não negativo, recebido {t[nome]!r}"
                    )
            if not erros_trecho:
                if t["inicio_ms"] >= t["fim_ms"]:
                    erros_trecho.append(
                        f"trecho_analisado: inicio_ms ({t['inicio_ms']}) deve ser menor que "
                        f"fim_ms ({t['fim_ms']})"
                    )
                else:
                    trecho = (t["inicio_ms"], t["fim_ms"])
            erros += erros_trecho

    if "eventos" in dados:
        eventos = dados["eventos"]
        if not isinstance(eventos, list):
            erros.append(f"arquivo: eventos deve ser uma lista, recebido {type(eventos).__name__}")
        else:
            for n, ev in enumerate(eventos):
                onde = f"eventos[{n}]"
                if not isinstance(ev, dict):
                    erros.append(f"{onde}: deve ser um objeto")
                    continue
                if _eh_inteiro(ev.get("inicio_ms")):
                    onde += f" ({ev['inicio_ms']} ms)"
                erros += _validar_evento(ev, onde, base, trecho)
            erros += _validar_conjunto_de_eventos(eventos)

    return erros


def carregar(caminho: Path | str) -> Rotulos:
    """Lê e valida um arquivo de rótulos. Levanta RotulosInvalidos com todos os erros."""
    caminho = Path(caminho)
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RotulosInvalidos(caminho, ["arquivo não encontrado"]) from None
    except json.JSONDecodeError as e:
        raise RotulosInvalidos(caminho, [f"JSON inválido: {e}"]) from None

    erros = validar(dados, nome_arquivo=caminho.name)
    if erros:
        raise RotulosInvalidos(caminho, erros)

    eventos = tuple(
        Evento(
            inicio_ms=ev["inicio_ms"],
            fim_ms=ev["fim_ms"],
            tipo=ev["tipo"],
            mao=ev["mao"],
            marcacoes=tuple(ev["marcacoes"]),
            grupo=ev["grupo"],
            observacao=ev["observacao"],
        )
        for ev in dados["eventos"]
    )
    return Rotulos(
        video=dados["video"],
        conjunto=dados["conjunto"],
        base=dados["base"],
        ferramenta=dados["ferramenta"],
        rotulador=dados["rotulador"],
        data_rotulagem=dados["data_rotulagem"],
        trecho_inicio_ms=dados["trecho_analisado"]["inicio_ms"],
        trecho_fim_ms=dados["trecho_analisado"]["fim_ms"],
        eventos=eventos,
    )


def main(argv: list[str] | None = None) -> int:
    # Acentos corretos em qualquer terminal, inclusive com a saída redirecionada no Windows
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Valida arquivos de rótulos (labels/<video>.json).")
    parser.add_argument("arquivos", type=Path, nargs="+")
    args = parser.parse_args(argv)

    invalidos = 0
    for caminho in args.arquivos:
        try:
            rotulos = carregar(caminho)
        except RotulosInvalidos as e:
            invalidos += 1
            print(f"{caminho}: {len(e.erros)} erro(s)")
            for erro in e.erros:
                print(f"  - {erro}")
        else:
            print(f"{caminho}: ok ({len(rotulos.eventos)} eventos)")
    return 1 if invalidos else 0


if __name__ == "__main__":
    raise SystemExit(main())
