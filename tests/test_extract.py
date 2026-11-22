import csv
import hashlib
import json

import cv2
import numpy as np
import pytest

import boxing_vision.extract as extract_mod
from boxing_vision.extract import build_header, extract
from conftest import FAKE_MODEL_BYTES, LEFT_WRIST, RIGHT_WRIST, build_landmarks

BASES = ("orthodox", "southpaw")


def read_meta(out):
    return json.loads((out / "clip_meta.json").read_text(encoding="utf-8"))


# Base obrigatória

def test_extract_exige_base(video, fake_model, tmp_path):
    with pytest.raises(TypeError):
        extract(video, tmp_path / "out", fake_model)


def test_extract_rejeita_base_invalida(run_extract):
    with pytest.raises(ValueError, match="stance"):
        run_extract("canhoto")


# CSV

def test_csv_tem_uma_linha_por_frame(run_extract):
    summary, _, out = run_extract("southpaw")
    rows = list(csv.reader((out / "clip_landmarks.csv").open(encoding="utf-8")))
    assert rows[0] == build_header()
    assert len(rows) - 1 == summary.total_frames == 10
    assert all(len(r) == len(rows[0]) for r in rows)


def test_frames_sem_pose_ficam_vazios(run_extract):
    _, _, out = run_extract("southpaw")
    rows = list(csv.DictReader((out / "clip_landmarks.csv").open(encoding="utf-8")))
    assert rows[1]["pose_detectada"] == "0"
    assert rows[1]["right_wrist_x"] == ""
    assert rows[0]["pose_detectada"] == "1"


def test_csv_identico_para_as_duas_bases(run_extract):
    _, _, out_o = run_extract("orthodox", out_name="orthodox")
    _, _, out_s = run_extract("southpaw", out_name="southpaw")
    assert (out_o / "clip_landmarks.csv").read_bytes() == (out_s / "clip_landmarks.csv").read_bytes()


def test_timestamps_crescentes_e_derivados_do_fps(run_extract):
    _, fake, _ = run_extract("southpaw")
    assert fake.timestamps == [round(i * 1000 / 30) for i in range(10)]


# Metadados

@pytest.mark.parametrize("stance, braco", [("orthodox", "left"), ("southpaw", "right")])
def test_meta_registra_base_e_braco_frente(run_extract, stance, braco):
    _, _, out = run_extract(stance)
    meta = read_meta(out)
    assert meta["base"] == stance
    assert meta["braco_frente"] == braco


@pytest.mark.parametrize("stance", BASES)
def test_frames_sem_pose_separados_de_baixa_visibilidade(run_extract, stance):
    _, _, out = run_extract(stance)
    meta = read_meta(out)
    assert meta["frames"] == 10
    assert meta["frames_com_pose"] == 5
    assert meta["frames_sem_pose"] == 5
    assert meta["frames_com_pose"] + meta["frames_sem_pose"] == meta["frames"]
    assert meta["taxa_pose"] == 0.5


@pytest.mark.parametrize(
    "stance, baixa_vis, vis_media",
    # orthodox: 9 pontos a 0,9 e 6 a 0,2 no braço esquerdo
    # southpaw: 14 pontos a 0,9 e 1 a 0,2 no braço direito
    [("orthodox", 2, (9 * 0.9 + 6 * 0.2) / 15), ("southpaw", 1, (14 * 0.9 + 0.2) / 15)],
)
def test_metricas_seguem_braco_da_frente(run_extract, stance, baixa_vis, vis_media):
    _, _, out = run_extract(stance)
    meta = read_meta(out)
    assert meta["frames_braco_frente_baixa_visibilidade"] == baixa_vis
    assert meta["visibilidade_media_braco_frente"] == pytest.approx(vis_media, abs=1e-4)


def test_meta_sem_chaves_do_braco_esquerdo_fixo(run_extract):
    _, _, out = run_extract("southpaw")
    meta = read_meta(out)
    assert not [k for k in meta if "esquerdo" in k]


def test_meta_registra_sha256_do_modelo(run_extract):
    _, _, out = run_extract("southpaw")
    meta = read_meta(out)
    assert meta["modelo_sha256"] == hashlib.sha256(FAKE_MODEL_BYTES).hexdigest()
    assert len(meta["video_sha256"]) == 64


def test_meta_registra_opencv_e_opcoes_do_landmarker(run_extract):
    _, _, out = run_extract("southpaw")
    meta = read_meta(out)
    assert meta["opencv_versao"] == cv2.__version__
    assert meta["opcoes_landmarker"] == extract_mod.LANDMARKER_OPTIONS


def test_fps_zero_gera_erro_explicito(monkeypatch, fake_model, tmp_path):
    class CaptureSemFps:
        def __init__(self, *_):
            pass

        def isOpened(self):
            return True

        def get(self, prop):
            return 0.0

        def read(self):
            return False, None

        def release(self):
            pass

    monkeypatch.setattr(extract_mod.cv2, "VideoCapture", CaptureSemFps)
    with pytest.raises(ValueError, match="FPS"):
        extract(tmp_path / "clip.mp4", tmp_path / "out", fake_model, stance="southpaw",
                landmarker_factory=lambda _: pytest.fail("não deveria abrir o modelo"))


# Reprodutibilidade (CA-06)

def test_saida_reprodutivel(run_extract):
    _, _, out1 = run_extract("southpaw", out_name="a")
    _, _, out2 = run_extract("southpaw", out_name="b")
    for name in ("clip_landmarks.csv", "clip_meta.json"):
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes()


def test_execucao_separada_do_meta(run_extract):
    _, _, out = run_extract("southpaw")
    assert "tempo_processamento_s" not in read_meta(out)
    execucao = json.loads((out / "clip_execucao.json").read_text(encoding="utf-8"))
    assert "tempo_processamento_s" in execucao


# Preview

def test_preview_gerado(run_extract):
    _, _, out = run_extract("southpaw", preview=True)
    assert (out / "clip_preview.mp4").stat().st_size > 0


@pytest.mark.parametrize("stance", BASES)
def test_preview_desenha_os_dois_bracos(stance):
    h, w = 100, 200
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    lms = build_landmarks()
    extract_mod.draw_arms(frame, lms, stance, 0.5)
    for idx in (LEFT_WRIST, RIGHT_WRIST):
        x, y = int(lms[idx].x * w), int(lms[idx].y * h)
        assert frame[y, x].any(), f"punho {idx} não foi desenhado"


@pytest.mark.parametrize("stance, punho_frente", [("orthodox", LEFT_WRIST), ("southpaw", RIGHT_WRIST)])
def test_preview_rotula_frente_no_braco_certo(monkeypatch, stance, punho_frente):
    textos = []
    original = cv2.putText

    def espiao(img, text, org, *args, **kwargs):
        textos.append((text, org))
        return original(img, text, org, *args, **kwargs)

    monkeypatch.setattr(extract_mod.cv2, "putText", espiao)
    h, w = 100, 200
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    lms = build_landmarks()
    extract_mod.draw_arms(frame, lms, stance, 0.5)

    rotulos = [org for text, org in textos if text == "FRENTE"]
    assert len(rotulos) == 1
    x_rotulo = rotulos[0][0]
    x_frente = lms[punho_frente].x * w
    x_tras = lms[RIGHT_WRIST if punho_frente == LEFT_WRIST else LEFT_WRIST].x * w
    assert abs(x_rotulo - x_frente) < abs(x_rotulo - x_tras)
