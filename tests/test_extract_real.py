"""Teste de integração com o MediaPipe real.

Roda só quando existem o modelo e um vídeo gravado conforme docs/protocolo-gravacao.md
(atleta canhoto, diagonal de ~45°, corpo inteiro):
    models/pose_landmarker_full.task
    videos/amostra_diagonal.mp4
Sem eles, o teste é pulado.
"""

import json
from pathlib import Path

import pytest

from boxing_vision.extract import extract

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models" / "pose_landmarker_full.task"
SAMPLE = ROOT / "videos" / "amostra_diagonal.mp4"
STANCE = "southpaw"

faltando = [str(p.relative_to(ROOT)) for p in (MODEL, SAMPLE) if not p.exists()]
pytestmark = pytest.mark.skipif(bool(faltando), reason=f"arquivo ausente: {', '.join(faltando)}")


def test_mediapipe_real_detecta_pose(tmp_path):
    summary = extract(SAMPLE, tmp_path, MODEL, stance=STANCE)
    assert summary.total_frames > 0
    # Corpo inteiro com câmera fixa: a pose deve aparecer na maior parte do vídeo
    assert summary.pose_rate >= 0.9


def test_mediapipe_real_reprodutivel(tmp_path):
    extract(SAMPLE, tmp_path / "a", MODEL, stance=STANCE)
    extract(SAMPLE, tmp_path / "b", MODEL, stance=STANCE)
    stem = SAMPLE.stem
    for name in (f"{stem}_landmarks.csv", f"{stem}_meta.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_mediapipe_real_braco_frente_visivel(tmp_path):
    extract(SAMPLE, tmp_path, MODEL, stance=STANCE)
    meta = json.loads((tmp_path / f"{SAMPLE.stem}_meta.json").read_text(encoding="utf-8"))
    assert meta["braco_frente"] == "right"
    assert meta["visibilidade_media_braco_frente"] >= 0.5
