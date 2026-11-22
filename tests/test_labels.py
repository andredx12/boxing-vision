"""Testes do validador de rótulos (docs/protocolo-rotulagem.md)."""

import copy
import json

import pytest

from boxing_vision import labels
from boxing_vision.labels import RotulosInvalidos, carregar, main, validar

NOME = "treino_01.json"


def evento(inicio, fim, tipo="jab", mao="direita", marcacoes=None, grupo=None, observacao=""):
    return {
        "inicio_ms": inicio,
        "fim_ms": fim,
        "tipo": tipo,
        "mao": mao,
        "marcacoes": marcacoes or [],
        "grupo": grupo,
        "observacao": observacao,
    }


def base_valida():
    """Arquivo válido no formato do exemplo do protocolo."""
    return {
        "video": "treino_01.mp4",
        "conjunto": "calibracao",
        "base": "southpaw",
        "ferramenta": "mpv 0.39.0",
        "rotulador": "andre",
        "data_rotulagem": "2026-11-28",
        "trecho_analisado": {"inicio_ms": 2100, "fim_ms": 27850},
        "eventos": [
            evento(2100, 4050, "guarda_parada", None),
            evento(4317, 4550, marcacoes=["sem_retorno"]),
            evento(6083, 6250, grupo="g1"),
            evento(6417, 6617, marcacoes=["extensao_parcial"], grupo="g1"),
            evento(8200, 8433, "direto", "esquerda"),
            evento(10050, 10150, "finta_jab", marcacoes=["duvida"], grupo="g2",
                   observacao="punho avançou pouco, mas rápido"),
            evento(10283, 10517, grupo="g2"),
        ],
    }


def com_eventos(*eventos):
    dados = base_valida()
    dados["eventos"] = list(eventos)
    return dados


def erros_de(dados):
    return validar(dados, nome_arquivo=NOME)


def assert_erro(dados, trecho):
    erros = erros_de(dados)
    assert any(trecho in e for e in erros), f"esperava erro com {trecho!r}, veio {erros}"


def escrever(tmp_path, dados, nome=NOME):
    caminho = tmp_path / nome
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return caminho


# Arquivo válido


def test_arquivo_do_exemplo_do_protocolo_e_valido():
    assert erros_de(base_valida()) == []


def test_base_ortodoxa_inverte_as_maos():
    dados = base_valida()
    dados["base"] = "orthodox"
    dados["eventos"] = [
        evento(4317, 4550, mao="esquerda"),
        evento(8200, 8433, "direto", "direita"),
    ]
    assert erros_de(dados) == []


def test_carregar_devolve_eventos_tipados(tmp_path):
    rotulos = carregar(escrever(tmp_path, base_valida()))
    assert rotulos.base == "southpaw"
    assert (rotulos.trecho_inicio_ms, rotulos.trecho_fim_ms) == (2100, 27850)
    assert len(rotulos.eventos) == 7
    assert rotulos.eventos[1].marcacoes == ("sem_retorno",)
    assert rotulos.eventos[1].centro_ms == (4317 + 4550) / 2


def test_varios_erros_sao_reportados_de_uma_vez():
    dados = base_valida()
    dados["conjunto"] = "treino"
    dados["eventos"][1]["tipo"] = "gancho"
    dados["eventos"][4]["mao"] = "direita"
    assert len(erros_de(dados)) == 3


# Regras do arquivo


def test_campo_obrigatorio_ausente():
    dados = base_valida()
    del dados["ferramenta"]
    assert_erro(dados, "campo obrigatório ausente: ferramenta")


def test_campo_desconhecido_no_arquivo():
    dados = base_valida()
    dados["camera"] = "frontal"
    assert_erro(dados, "campo desconhecido: camera")


def test_campo_desconhecido_no_evento():
    dados = base_valida()
    dados["eventos"][1]["marcacao"] = []
    assert_erro(dados, "campo desconhecido: marcacao")


def test_campo_ausente_no_evento():
    dados = base_valida()
    del dados["eventos"][1]["grupo"]
    assert_erro(dados, "campo obrigatório ausente: grupo")


def test_video_deve_corresponder_ao_nome_do_arquivo():
    dados = base_valida()
    dados["video"] = "treino_02.mp4"
    assert_erro(dados, "não corresponde ao nome do arquivo")


def test_conjunto_invalido():
    dados = base_valida()
    dados["conjunto"] = "treino"
    assert_erro(dados, "conjunto deve ser")


def test_base_invalida():
    dados = base_valida()
    dados["base"] = "canhoto"
    assert_erro(dados, "base deve ser")


@pytest.mark.parametrize("campo", ["ferramenta", "rotulador"])
@pytest.mark.parametrize("valor", ["", "   ", None])
def test_texto_obrigatorio_nao_vazio(campo, valor):
    dados = base_valida()
    dados[campo] = valor
    assert_erro(dados, f"{campo} deve ser texto não vazio")


@pytest.mark.parametrize("valor", ["28/11/2026", "2026-13-01", "2026-11-28T10:00", 20261128])
def test_data_rotulagem_invalida(valor):
    dados = base_valida()
    dados["data_rotulagem"] = valor
    assert_erro(dados, "data_rotulagem deve ser uma data AAAA-MM-DD")


def test_trecho_com_inicio_maior_que_fim():
    dados = com_eventos()
    dados["trecho_analisado"] = {"inicio_ms": 5000, "fim_ms": 5000}
    assert_erro(dados, "trecho_analisado: inicio_ms (5000) deve ser menor que fim_ms (5000)")


def test_trecho_com_tempo_nao_inteiro():
    dados = com_eventos()
    dados["trecho_analisado"] = {"inicio_ms": 2100.5, "fim_ms": 27850}
    assert_erro(dados, "trecho_analisado: inicio_ms deve ser inteiro")


def test_eventos_deve_ser_lista():
    dados = base_valida()
    dados["eventos"] = {}
    assert_erro(dados, "eventos deve ser uma lista")


def test_eventos_fora_de_ordem():
    dados = com_eventos(evento(8200, 8433, "direto", "esquerda"), evento(4317, 4550))
    assert_erro(dados, "eventos[1]: fora de ordem")


# Regras de cada evento


@pytest.mark.parametrize("valor", [4317.0, "4317", True, -10])
def test_tempo_do_evento_deve_ser_inteiro_nao_negativo(valor):
    dados = com_eventos(evento(valor, 4550))
    assert_erro(dados, "inicio_ms deve ser inteiro não negativo")


@pytest.mark.parametrize("inicio, fim", [(4550, 4317), (4317, 4317)])
def test_inicio_deve_ser_menor_que_fim(inicio, fim):
    dados = com_eventos(evento(inicio, fim))
    assert_erro(dados, f"inicio_ms ({inicio}) deve ser menor que fim_ms ({fim})")


@pytest.mark.parametrize("inicio, fim", [(2000, 2500), (27800, 27900)])
def test_evento_fora_do_trecho_analisado(inicio, fim):
    dados = com_eventos(evento(inicio, fim))
    assert_erro(dados, "fora de trecho_analisado")


def test_evento_nas_bordas_do_trecho_e_valido():
    dados = com_eventos(evento(2100, 2400, "guarda_parada", None), evento(27500, 27850))
    assert erros_de(dados) == []


def test_tipo_desconhecido():
    dados = com_eventos(evento(4317, 4550, "jab_parcial"))
    assert_erro(dados, "tipo desconhecido: 'jab_parcial'")


def test_mao_fora_do_vocabulario():
    dados = com_eventos(evento(4317, 4550, mao="right"))
    assert_erro(dados, "mao deve ser")


@pytest.mark.parametrize(
    "tipo, mao",
    [
        ("jab", "esquerda"),
        ("jab", None),
        ("direto", "direita"),
        ("guarda_parada", "direita"),
        ("movimentacao_pes", "esquerda"),
        ("extensao_sem_golpe", "esquerda"),
        ("finta_jab", "esquerda"),
        ("ajuste_guarda", None),
    ],
)
def test_mao_incompativel_com_o_tipo(tipo, mao):
    dados = com_eventos(evento(4317, 4550, tipo, mao))
    assert_erro(dados, "incompatível com tipo")


@pytest.mark.parametrize("mao", ["direita", "esquerda"])
def test_ajuste_de_guarda_aceita_qualquer_mao(mao):
    assert erros_de(com_eventos(evento(4317, 4550, "ajuste_guarda", mao))) == []


def test_marcacoes_deve_ser_lista():
    ev = evento(4317, 4550)
    ev["marcacoes"] = "sem_retorno"
    assert_erro(com_eventos(ev), "marcacoes deve ser uma lista")


def test_marcacao_desconhecida():
    dados = com_eventos(evento(4317, 4550, marcacoes=["parcial"]))
    assert_erro(dados, "marcação desconhecida: 'parcial'")


@pytest.mark.parametrize(
    "tipo, mao, marcacao",
    [
        ("finta_jab", "direita", "extensao_parcial"),
        ("direto", "esquerda", "extensao_parcial"),
        ("guarda_parada", None, "sem_retorno"),
        ("finta_jab", "direita", "sem_retorno"),
    ],
)
def test_marcacao_nao_permitida_para_o_tipo(tipo, mao, marcacao):
    dados = com_eventos(evento(4317, 4550, tipo, mao, marcacoes=[marcacao]))
    assert_erro(dados, f"marcação '{marcacao}' não é permitida para o tipo '{tipo}'")


def test_oclusao_permitida_em_qualquer_tipo():
    dados = com_eventos(evento(4317, 4550, "movimentacao_pes", None, marcacoes=["oclusao"]))
    assert erros_de(dados) == []


def test_marcacao_repetida():
    dados = com_eventos(evento(4317, 4550, marcacoes=["oclusao", "oclusao"]))
    assert_erro(dados, "marcação repetida: 'oclusao'")


@pytest.mark.parametrize("observacao", ["", "   "])
def test_duvida_exige_observacao(observacao):
    dados = com_eventos(evento(4317, 4550, marcacoes=["duvida"], observacao=observacao))
    assert_erro(dados, "marcação 'duvida' exige o motivo em observacao")


def test_observacao_deve_ser_texto():
    dados = com_eventos(evento(4317, 4550, observacao=None))
    assert_erro(dados, "observacao deve ser texto")


# Sobreposição


def test_jab_sobreposto_a_jab():
    dados = com_eventos(evento(4317, 4550), evento(4500, 4700))
    erros = [e for e in erros_de(dados) if "se sobrepõe" in e]
    assert len(erros) == 1  # o par é reportado uma vez só


@pytest.mark.parametrize(
    "outro",
    [
        evento(4000, 5000, "guarda_parada", None),
        evento(4400, 4600, "movimentacao_pes", None),
        evento(4500, 4700, "direto", "esquerda"),
        evento(4200, 4400, "finta_jab"),
    ],
)
def test_jab_nao_pode_se_sobrepor_a_nenhum_outro_evento(outro):
    eventos = sorted([evento(4317, 4550), outro], key=lambda e: e["inicio_ms"])
    assert_erro(com_eventos(*eventos), "se sobrepõe")


def test_jab_encostado_em_outro_evento_e_valido():
    dados = com_eventos(evento(4000, 4317, "guarda_parada", None), evento(4317, 4550), evento(4550, 4700))
    assert erros_de(dados) == []


def test_negativos_podem_se_sobrepor_entre_si():
    dados = com_eventos(
        evento(4000, 6000, "movimentacao_pes", None),
        evento(4500, 4800, "ajuste_guarda", "direita"),
    )
    assert erros_de(dados) == []


# Grupos


@pytest.mark.parametrize("grupo", ["", "  ", 1])
def test_grupo_deve_ser_texto_ou_null(grupo):
    dados = com_eventos(evento(4317, 4550, grupo=grupo))
    assert_erro(dados, "grupo deve ser texto não vazio ou null")


def test_grupo_com_um_evento():
    dados = com_eventos(evento(4317, 4550, grupo="g1"))
    assert_erro(dados, "grupo 'g1': deve ter exatamente 2 eventos, tem 1")


def test_grupo_com_tres_eventos():
    dados = com_eventos(
        evento(4317, 4550, grupo="g1"), evento(4600, 4800, grupo="g1"), evento(4900, 5100, grupo="g1")
    )
    assert_erro(dados, "grupo 'g1': deve ter exatamente 2 eventos, tem 3")


@pytest.mark.parametrize(
    "primeiro, segundo",
    [
        (evento(4317, 4550, grupo="g1"), evento(4600, 4800, "finta_jab", grupo="g1")),  # ordem invertida
        (evento(4317, 4550, grupo="g1"), evento(4600, 4800, "direto", "esquerda", grupo="g1")),  # um-dois
        (evento(4317, 4550, "finta_jab", grupo="g1"), evento(4600, 4800, "finta_jab", grupo="g1")),
    ],
)
def test_combinacao_de_grupo_invalida(primeiro, segundo):
    assert_erro(com_eventos(primeiro, segundo), "grupo 'g1': combinação")


# Carregamento e CLI


def test_carregar_levanta_erro_com_todos_os_erros(tmp_path):
    dados = base_valida()
    dados["conjunto"] = "treino"
    dados["base"] = "canhoto"
    with pytest.raises(RotulosInvalidos) as exc:
        carregar(escrever(tmp_path, dados))
    assert len(exc.value.erros) == 2


def test_carregar_usa_o_nome_do_arquivo(tmp_path):
    with pytest.raises(RotulosInvalidos) as exc:
        carregar(escrever(tmp_path, base_valida(), nome="outro_video.json"))
    assert any("não corresponde ao nome do arquivo" in e for e in exc.value.erros)


def test_carregar_json_malformado(tmp_path):
    caminho = tmp_path / NOME
    caminho.write_text("{ isto não é json", encoding="utf-8")
    with pytest.raises(RotulosInvalidos) as exc:
        carregar(caminho)
    assert "JSON inválido" in exc.value.erros[0]


def test_cli_arquivo_valido(tmp_path, capsys):
    caminho = escrever(tmp_path, base_valida())
    assert main([str(caminho)]) == 0
    assert "ok (7 eventos)" in capsys.readouterr().out


def test_cli_arquivo_invalido_mostra_os_erros(tmp_path, capsys):
    dados = base_valida()
    dados["eventos"][1]["tipo"] = "gancho"
    assert main([str(escrever(tmp_path, dados))]) == 1
    saida = capsys.readouterr().out
    assert "1 erro(s)" in saida
    assert "tipo desconhecido: 'gancho'" in saida


def test_cli_arquivo_inexistente(tmp_path, capsys):
    assert main([str(tmp_path / "nao_existe.json")]) == 1
    assert "arquivo não encontrado" in capsys.readouterr().out


def test_cli_varios_arquivos_falha_se_algum_for_invalido(tmp_path):
    valido = escrever(tmp_path, base_valida())
    invalido = copy.deepcopy(base_valida())
    invalido["video"] = "treino_02.mp4"
    invalido["base"] = "canhoto"
    assert main([str(valido), str(escrever(tmp_path, invalido, nome="treino_02.json"))]) == 1


def test_vocabulario_exportado():
    assert labels.MAOS == ("direita", "esquerda")
    assert labels.BASES == ("orthodox", "southpaw")
    assert labels.MAO_DA_FRENTE["southpaw"] == "direita"
    assert labels.MAO_DE_TRAS["southpaw"] == "esquerda"
