from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from boxing_vision.extract import LANDMARK_NAMES, extract

LEFT_ARM_IDX = (11, 13, 15)
RIGHT_ARM_IDX = (12, 14, 16)
LEFT_WRIST, RIGHT_WRIST = 15, 16

FAKE_MODEL_BYTES = b"modelo-falso-para-teste"


def build_landmarks(vis: dict[int, float] | None = None, default_vis: float = 0.9):
    """33 landmarks com o braço esquerdo em x=0,25 e o direito em x=0,75."""
    vis = vis or {}
    lms = []
    for i in range(len(LANDMARK_NAMES)):
        if i in LEFT_ARM_IDX:
            x = 0.25
        elif i in RIGHT_ARM_IDX:
            x = 0.75
        else:
            x = 0.5
        # Ombro, cotovelo e punho em alturas diferentes para o desenho ter segmentos
        y = {11: 0.3, 12: 0.3, 13: 0.5, 14: 0.5, 15: 0.7, 16: 0.7}.get(i, 0.5)
        lms.append(SimpleNamespace(x=x, y=y, z=0.0, visibility=vis.get(i, default_vis), presence=0.95))
    return lms


class FakeLandmarker:
    """Roteiro de 10 frames, assimétrico entre os braços.

    - Frames ímpares: sem pose (5 frames)
    - Frames 4 e 8: braço esquerdo inteiro com visibilidade 0,2
    - Frame 6: só o punho direito com visibilidade 0,2
    - Demais pontos: visibilidade 0,9

    Assim, orthodox (braço esquerdo) tem 2 frames de baixa visibilidade e
    southpaw (braço direito) tem 1. Uma escolha de braço errada muda o resultado.
    """

    def __init__(self):
        self.timestamps = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def detect_for_video(self, image, ts_ms):
        idx = len(self.timestamps)
        self.timestamps.append(ts_ms)
        if idx % 2:
            return SimpleNamespace(pose_landmarks=[])
        if idx in (4, 8):
            vis = {i: 0.2 for i in LEFT_ARM_IDX}
        elif idx == 6:
            vis = {RIGHT_WRIST: 0.2}
        else:
            vis = {}
        return SimpleNamespace(pose_landmarks=[build_landmarks(vis)])


def make_video(path: Path, frames: int = 10, fps: float = 30.0) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 48))
    for _ in range(frames):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()


@pytest.fixture
def video(tmp_path) -> Path:
    path = tmp_path / "clip.mp4"
    make_video(path)
    return path


@pytest.fixture
def fake_model(tmp_path) -> Path:
    path = tmp_path / "fake.task"
    path.write_bytes(FAKE_MODEL_BYTES)
    return path


@pytest.fixture
def run_extract(tmp_path, video, fake_model):
    """Roda extract() com o FakeLandmarker e devolve (resumo, fake, pasta de saída)."""

    def _run(stance: str, preview: bool = False, out_name: str = "out"):
        fake = FakeLandmarker()
        out = tmp_path / out_name
        summary = extract(
            video, out, fake_model, stance=stance, preview=preview,
            landmarker_factory=lambda _: fake,
        )
        return summary, fake, out

    return _run
