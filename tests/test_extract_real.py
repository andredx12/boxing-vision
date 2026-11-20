"""Teste de integração com o MediaPipe real.

Roda só quando existem o modelo e um vídeo de amostra local:
    models/pose_landmarker_full.task
    videos/amostra.mp4
Sem eles, o teste é pulado.
"""

import json
from pathlib import Path

import pytest

from boxing_vision.extract import extract

MODEL = Path("models/pose_landmarker_full.task")
SAMPLE = Path("videos/amostra.mp4")

pytestmark = pytest.mark.skipif(
    not (MODEL.exists() and SAMPLE.exists()),
    reason="modelo ou vídeo de amostra ausente",
)


def test_mediapipe_real_detecta_pose(tmp_path):
    summary = extract(SAMPLE, tmp_path, MODEL)
    assert summary.total_frames > 0
    # Pessoa de corpo inteiro com câmera fixa: a pose deve aparecer na maior parte do vídeo
    assert summary.pose_rate >= 0.9


def test_mediapipe_real_reprodutivel(tmp_path):
    extract(SAMPLE, tmp_path / "a", MODEL)
    extract(SAMPLE, tmp_path / "b", MODEL)
    stem = SAMPLE.stem
    for name in (f"{stem}_landmarks.csv", f"{stem}_meta.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_mediapipe_real_braco_esquerdo_visivel(tmp_path):
    extract(SAMPLE, tmp_path, MODEL)
    meta = json.loads((tmp_path / f"{SAMPLE.stem}_meta.json").read_text())
    assert meta["visibilidade_media_braco_esquerdo"] >= 0.5
