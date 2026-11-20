"""Extração de landmarks de pose de um vídeo MP4 com MediaPipe Pose Landmarker.

Uso:
    python -m boxing_vision.extract videos/treino.mp4
    python -m boxing_vision.extract videos/treino.mp4 --preview
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision

LANDMARK_NAMES = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer",
    "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear", "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_pinky", "right_pinky",
    "left_index", "right_index", "left_thumb", "right_thumb",
    "left_hip", "right_hip", "left_knee", "right_knee",
    "left_ankle", "right_ankle", "left_heel", "right_heel",
    "left_foot_index", "right_foot_index",
]

# Braço da frente de um atleta ortodoxo: o foco do Marco 0
LEFT_ARM = {"left_shoulder": 11, "left_elbow": 13, "left_wrist": 15}

DEFAULT_MODEL = Path("models/pose_landmarker_full.task")
FIELDS = ("x", "y", "z", "vis", "pres")


@dataclass
class ExtractionSummary:
    total_frames: int
    frames_with_pose: int
    left_arm_visibility_mean: float
    left_arm_low_visibility_frames: int
    seconds: float

    @property
    def pose_rate(self) -> float:
        return self.frames_with_pose / self.total_frames if self.total_frames else 0.0


def build_header() -> list[str]:
    header = ["frame", "timestamp_ms", "pose_detectada"]
    for name in LANDMARK_NAMES:
        header += [f"{name}_{f}" for f in FIELDS]
    return header


def landmarks_to_row(frame_idx: int, ts_ms: int, landmarks) -> list:
    row: list = [frame_idx, ts_ms, 1 if landmarks else 0]
    if not landmarks:
        row += [""] * (len(LANDMARK_NAMES) * len(FIELDS))
        return row
    for lm in landmarks:
        row += [
            round(lm.x, 6),
            round(lm.y, 6),
            round(lm.z, 6),
            round(lm.visibility or 0.0, 4),
            round(lm.presence or 0.0, 4),
        ]
    return row


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def create_landmarker(model_path: Path):
    options = vision.PoseLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
    )
    return vision.PoseLandmarker.create_from_options(options)


def draw_left_arm(frame, landmarks, low_vis: float) -> None:
    h, w = frame.shape[:2]
    pts = []
    for idx in LEFT_ARM.values():
        lm = landmarks[idx]
        color = (0, 200, 0) if (lm.visibility or 0) >= low_vis else (0, 0, 255)
        p = (int(lm.x * w), int(lm.y * h))
        pts.append(p)
        cv2.circle(frame, p, 6, color, -1)
    cv2.line(frame, pts[0], pts[1], (255, 255, 255), 2)
    cv2.line(frame, pts[1], pts[2], (255, 255, 255), 2)


def extract(
    video_path: Path,
    out_dir: Path,
    model_path: Path,
    preview: bool = False,
    low_vis: float = 0.5,
    landmarker_factory=create_landmarker,
) -> ExtractionSummary:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Não consegui abrir o vídeo: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = video_path.stem
    csv_path = out_dir / f"{stem}_landmarks.csv"
    meta_path = out_dir / f"{stem}_meta.json"

    writer_video = None
    if preview:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer_video = cv2.VideoWriter(
            str(out_dir / f"{stem}_preview.mp4"), fourcc, fps, (width, height)
        )

    total = with_pose = low_vis_frames = 0
    vis_sum = 0.0
    vis_count = 0
    start = time.perf_counter()

    with landmarker_factory(model_path) as landmarker, csv_path.open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f)
        writer.writerow(build_header())

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            # Timestamp derivado do índice do frame, não do relógio do decoder,
            # pra garantir reprodutibilidade
            ts_ms = int(round(total * 1000.0 / fps))
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect_for_video(mp_image, ts_ms)

            landmarks = result.pose_landmarks[0] if result.pose_landmarks else None
            writer.writerow(landmarks_to_row(total, ts_ms, landmarks))

            if landmarks:
                with_pose += 1
                arm_vis = [landmarks[i].visibility or 0.0 for i in LEFT_ARM.values()]
                vis_sum += sum(arm_vis)
                vis_count += len(arm_vis)
                if min(arm_vis) < low_vis:
                    low_vis_frames += 1
                if writer_video is not None:
                    draw_left_arm(frame, landmarks, low_vis)
            else:
                low_vis_frames += 1

            if writer_video is not None:
                writer_video.write(frame)
            total += 1

    cap.release()
    if writer_video is not None:
        writer_video.release()

    summary = ExtractionSummary(
        total_frames=total,
        frames_with_pose=with_pose,
        left_arm_visibility_mean=(vis_sum / vis_count) if vis_count else math.nan,
        left_arm_low_visibility_frames=low_vis_frames,
        seconds=time.perf_counter() - start,
    )

    meta = {
        "video": video_path.name,
        "video_sha256": file_sha256(video_path),
        "fps": fps,
        "largura": width,
        "altura": height,
        "frames": total,
        "duracao_s": round(total / fps, 3) if fps else None,
        "modelo": model_path.name,
        "mediapipe_versao": mp.__version__,
        "limite_visibilidade": low_vis,
        "frames_com_pose": with_pose,
        "taxa_pose": round(summary.pose_rate, 4),
        "visibilidade_media_braco_esquerdo": round(summary.left_arm_visibility_mean, 4)
        if vis_count
        else None,
        "frames_braco_esquerdo_baixa_visibilidade": low_vis_frames,
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # Dados que mudam a cada execução ficam separados do resultado reprodutível
    execucao = {
        "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tempo_processamento_s": round(summary.seconds, 2),
        "segundos_por_minuto_de_video": round(summary.seconds / (total / fps / 60), 2)
        if total and fps
        else None,
        "python": platform.python_version(),
        "sistema": platform.platform(),
        "processador": platform.processor(),
    }
    (out_dir / f"{stem}_execucao.json").write_text(
        json.dumps(execucao, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extração de landmarks de pose de um vídeo.")
    parser.add_argument("video", type=Path)
    parser.add_argument("--out", type=Path, default=Path("saida/landmarks"))
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--preview", action="store_true", help="gera MP4 com o braço esquerdo desenhado")
    parser.add_argument("--low-vis", type=float, default=0.5)
    args = parser.parse_args(argv)

    if not args.model.exists():
        print(f"Modelo não encontrado em {args.model}. Veja o README (seção Setup).", file=sys.stderr)
        return 1

    s = extract(args.video, args.out, args.model, args.preview, args.low_vis)
    print(f"Frames: {s.total_frames}")
    print(f"Pose detectada: {s.frames_with_pose} ({s.pose_rate:.1%})")
    print(f"Visibilidade média do braço esquerdo: {s.left_arm_visibility_mean:.3f}")
    print(f"Frames com braço esquerdo pouco visível: {s.left_arm_low_visibility_frames}")
    print(f"Tempo de processamento: {s.seconds:.1f}s")
    return 0 if s.total_frames else 1


if __name__ == "__main__":
    raise SystemExit(main())
