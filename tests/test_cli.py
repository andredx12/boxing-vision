import pytest

import boxing_vision.extract as extract_mod


class ChamadaCapturada(Exception):
    pass


def test_cli_sem_stance_sai_com_erro(video, fake_model, capsys):
    with pytest.raises(SystemExit) as exc:
        extract_mod.main([str(video), "--model", str(fake_model)])
    assert exc.value.code == 2
    assert "--stance" in capsys.readouterr().err


def test_cli_rejeita_stance_invalida(video, fake_model, capsys):
    with pytest.raises(SystemExit) as exc:
        extract_mod.main([str(video), "--model", str(fake_model), "--stance", "canhoto"])
    assert exc.value.code == 2
    # Erro de valor inválido, não de argumento desconhecido
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize("stance, mao", [("orthodox", "esquerda"), ("southpaw", "direita")])
def test_cli_imprime_mao_da_frente(monkeypatch, video, fake_model, capsys, stance, mao):
    resumo = extract_mod.ExtractionSummary(
        total_frames=10, frames_with_pose=5, front_arm=mao,
        front_arm_visibility_mean=0.9, front_arm_low_visibility_frames=1, seconds=1.0,
    )
    monkeypatch.setattr(extract_mod, "extract", lambda *a, **k: resumo)
    assert extract_mod.main([str(video), "--model", str(fake_model), "--stance", stance]) == 0
    assert f"braço da frente: {mao}" in capsys.readouterr().out


@pytest.mark.parametrize("stance", ["orthodox", "southpaw"])
def test_cli_repassa_stance_para_extract(monkeypatch, video, fake_model, stance):
    capturado = {}

    def espiao(*args, **kwargs):
        capturado.update(kwargs)
        raise ChamadaCapturada

    monkeypatch.setattr(extract_mod, "extract", espiao)
    with pytest.raises(ChamadaCapturada):
        extract_mod.main([str(video), "--model", str(fake_model), "--stance", stance])
    assert capturado["stance"] == stance
