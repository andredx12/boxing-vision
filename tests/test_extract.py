import csv
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
import pytest

import boxing_vision.extract as extract_mod
from boxing_vision.extract import build_header, extract
from conftest import (
    FAKE_MODEL_BYTES,
    LEFT_WRIST,
    RIGHT_WRIST,
    FakeLandmarker,
    build_landmarks,
)

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


def test_timestamps_do_video_sintetico(run_extract):
    _, fake, out = run_extract("southpaw")
    assert len(fake.timestamps) == 10
    assert fake.timestamps[0] == 0
    intervalos = [b - a for a, b in zip(fake.timestamps, fake.timestamps[1:])]
    # Vídeo sintético gravado a 30 FPS constante: ~33 ms entre frames
    assert all(30 <= d <= 37 for d in intervalos)
    rows = list(csv.DictReader((out / "clip_landmarks.csv").open(encoding="utf-8")))
    assert [int(r["timestamp_ms"]) for r in rows] == fake.timestamps


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


# Timestamp real do frame (docs/resultados/fps-variavel.md)

# Intervalo inicial de 120 ms e um frame perdido (salto de 66 ms) entre os frames 3 e 4
PTS_COM_FRAME_PERDIDO = [0.0, 120.0, 153.3, 186.6, 253.2, 286.4]


def run_fake_capture(fake_capture, video, out, model, pos_msec, preview=False):
    cap = fake_capture(pos_msec)
    fake = FakeLandmarker()
    extract(video, out, model, stance="southpaw", preview=preview,
            landmarker_factory=lambda _: fake)
    return cap, fake


def test_timestamp_vem_do_pts_do_frame(fake_capture, video, fake_model, tmp_path):
    _, fake = run_fake_capture(fake_capture, video, tmp_path / "out", fake_model,
                               PTS_COM_FRAME_PERDIDO)
    esperado = [0, 120, 153, 187, 253, 286]
    assert fake.timestamps == esperado
    # O cálculo antigo (índice / FPS médio) daria outros valores
    assert esperado != [round(i * 1000 / 30) for i in range(6)]
    rows = list(csv.DictReader((tmp_path / "out" / "clip_landmarks.csv").open(encoding="utf-8")))
    assert [int(r["timestamp_ms"]) for r in rows] == esperado


def test_timestamp_relativo_ao_primeiro_frame(fake_capture, video, fake_model, tmp_path):
    _, fake = run_fake_capture(fake_capture, video, tmp_path / "out", fake_model,
                               [1000.0, 1040.0, 1075.0])
    # Intervalos de 40 e 35 ms: diferentes do cálculo antigo a 30 FPS (0, 33, 67)
    assert fake.timestamps == [0, 40, 75]


@pytest.mark.parametrize(
    "pos_msec, frame_invalido",
    [
        pytest.param([0.0, 33.3, 33.3, 100.0], 2, id="repetido"),
        pytest.param([0.0, 33.3, 66.7, 0.0, 133.3], 3, id="zerado"),
        pytest.param([0.0, 0.0, 0.0], 1, id="backend_sem_tempo"),
        pytest.param([0.0, 33.3, 66.7, 50.0], 3, id="regressivo"),
        pytest.param([0.0, 33.3, math.nan], 2, id="nan"),
        pytest.param([0.0, 33.1, 33.4], 2, id="empate_no_arredondamento"),
    ],
)
def test_timestamp_invalido_gera_erro(fake_capture, video, fake_model, tmp_path,
                                      pos_msec, frame_invalido):
    fake_capture(pos_msec)
    fake = FakeLandmarker()
    with pytest.raises(ValueError, match=f"frame {frame_invalido}\\b") as exc:
        extract(video, tmp_path / "out", fake_model, stance="southpaw",
                landmarker_factory=lambda _: fake)
    mensagem = str(exc.value).lower()
    assert "regrave" in mensagem and "reporte" in mensagem
    # O valor inválido nunca chega ao MediaPipe
    assert len(fake.timestamps) == frame_invalido


def test_meta_registra_origem_e_intervalos(fake_capture, video, fake_model, tmp_path):
    run_fake_capture(fake_capture, video, tmp_path / "out", fake_model, PTS_COM_FRAME_PERDIDO)
    meta = read_meta(tmp_path / "out")
    assert meta["origem_timestamp"] == "CAP_PROP_POS_MSEC"
    # Intervalos: 120, 33, 34, 66, 33
    assert meta["intervalo_frames_ms"] == {"mediana": 34, "maximo": 120, "acima_50ms": 2}


# Falha no meio da extração

PTS_REPETIDO = [0.0, 33.3, 66.7, 66.7, 133.3]


def test_erro_no_meio_libera_o_video(fake_capture, video, fake_model, tmp_path):
    cap = fake_capture(PTS_REPETIDO)
    fake = FakeLandmarker()
    with pytest.raises(ValueError):
        extract(video, tmp_path / "out", fake_model, stance="southpaw", preview=True,
                landmarker_factory=lambda _: fake)
    assert cap.liberado
    # Nenhum arquivo temporário sobra na pasta de saída
    assert not [p.name for p in (tmp_path / "out").iterdir() if "tmp" in p.name]


def test_erro_no_meio_preserva_saida_anterior(fake_capture, video, fake_model, tmp_path):
    out = tmp_path / "out"
    run_fake_capture(fake_capture, video, out, fake_model, PTS_COM_FRAME_PERDIDO, preview=True)
    antes = {p.name: p.read_bytes() for p in out.iterdir()}

    with pytest.raises(ValueError):
        run_fake_capture(fake_capture, video, out, fake_model, PTS_REPETIDO, preview=True)

    depois = {p.name: p.read_bytes() for p in out.iterdir()}
    assert depois == antes


def test_meta_renomeado_por_ultimo(monkeypatch, run_extract):
    destinos = []
    original = extract_mod.os.replace

    def espiao(src, dst):
        destinos.append(Path(dst).name)
        return original(src, dst)

    monkeypatch.setattr(extract_mod.os, "replace", espiao)
    run_extract("southpaw", preview=True)
    assert set(destinos) == {
        "clip_landmarks.csv", "clip_preview.mp4", "clip_execucao.json", "clip_meta.json"
    }
    # Se o _meta.json existe, a execução foi completa
    assert destinos[-1] == "clip_meta.json"


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
