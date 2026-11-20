import csv
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from boxing_vision.extract import LANDMARK_NAMES, build_header, extract


def make_video(path: Path, frames: int = 10, fps: float = 30.0) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 48))
    for _ in range(frames):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()


class FakeLandmarker:
    """Pose só nos frames pares, braço esquerdo pouco visível no frame 4."""

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
        vis = 0.2 if idx == 4 else 0.9
        lms = [SimpleNamespace(x=0.5, y=0.5, z=0.0, visibility=vis, presence=0.95) for _ in LANDMARK_NAMES]
        return SimpleNamespace(pose_landmarks=[lms])


def run(tmp_path, preview=False):
    video = tmp_path / "clip.mp4"
    make_video(video)
    fake = FakeLandmarker()
    summary = extract(video, tmp_path / "out", Path("fake.task"), preview=preview,
                      landmarker_factory=lambda _: fake)
    return summary, fake, tmp_path / "out"


def test_csv_tem_uma_linha_por_frame(tmp_path):
    summary, _, out = run(tmp_path)
    rows = list(csv.reader((out / "clip_landmarks.csv").open()))
    assert rows[0] == build_header()
    assert len(rows) - 1 == summary.total_frames == 10
    assert all(len(r) == len(rows[0]) for r in rows)


def test_frames_sem_pose_ficam_vazios(tmp_path):
    _, _, out = run(tmp_path)
    rows = list(csv.DictReader((out / "clip_landmarks.csv").open()))
    assert rows[1]["pose_detectada"] == "0"
    assert rows[1]["left_wrist_x"] == ""
    assert rows[0]["pose_detectada"] == "1"


def test_timestamps_crescentes_e_derivados_do_fps(tmp_path):
    _, fake, _ = run(tmp_path)
    assert fake.timestamps == [round(i * 1000 / 30) for i in range(10)]


def test_resumo_e_meta(tmp_path):
    summary, _, out = run(tmp_path)
    assert summary.frames_with_pose == 5
    # 5 frames sem pose + 1 frame com braço pouco visível
    assert summary.left_arm_low_visibility_frames == 6
    meta = json.loads((out / "clip_meta.json").read_text())
    assert meta["frames"] == 10
    assert meta["taxa_pose"] == 0.5
    assert len(meta["video_sha256"]) == 64


def test_saida_reprodutivel(tmp_path):
    _, _, out = run(tmp_path)
    first = (out / "clip_landmarks.csv").read_bytes()
    _, _, out2 = run(tmp_path)
    assert (out2 / "clip_landmarks.csv").read_bytes() == first


def test_preview_gerado(tmp_path):
    _, _, out = run(tmp_path, preview=True)
    assert (out / "clip_preview.mp4").stat().st_size > 0


def test_meta_reprodutivel_e_execucao_separada(tmp_path):
    _, _, out = run(tmp_path)
    meta1 = (out / "clip_meta.json").read_bytes()
    _, _, out2 = run(tmp_path)
    assert (out2 / "clip_meta.json").read_bytes() == meta1
    assert "tempo_processamento_s" not in json.loads(meta1)
    assert "tempo_processamento_s" in json.loads((out / "clip_execucao.json").read_text())
