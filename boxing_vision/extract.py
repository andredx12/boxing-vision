"""Extração de landmarks de pose de um vídeo MP4 com MediaPipe Pose Landmarker.

Uso:
    python -m boxing_vision.extract videos/treino.mp4 --stance southpaw
    python -m boxing_vision.extract videos/treino.mp4 --stance southpaw --preview
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

# Ombro, cotovelo e punho de cada lado, com os nomes anatômicos do MediaPipe
ARMS = {
    side: tuple(LANDMARK_NAMES.index(f"{side}_{joint}") for joint in ("shoulder", "elbow", "wrist"))
    for side in ("left", "right")
}

# A base define qual braço fica na frente: ortodoxo = esquerdo, canhoto = direito
STANCES = {"orthodox": "left", "southpaw": "right"}

# Opções explícitas (iguais aos padrões do MediaPipe 0.10.32) para ficarem registradas no meta
LANDMARKER_OPTIONS = {
    "running_mode": "VIDEO",
    "num_poses": 1,
    "min_pose_detection_confidence": 0.5,
    "min_pose_presence_confidence": 0.5,
    "min_tracking_confidence": 0.5,
}

DEFAULT_MODEL = Path("models/pose_landmarker_full.task")
FIELDS = ("x", "y", "z", "vis", "pres")

FRONT_COLOR = (0, 215, 255)
REAR_COLOR = (160, 160, 160)
OK_COLOR = (0, 200, 0)
LOW_VIS_COLOR = (0, 0, 255)


@dataclass
class ExtractionSummary:
    total_frames: int
    frames_with_pose: int
    front_arm: str
    front_arm_visibility_mean: float
    front_arm_low_visibility_frames: int
    seconds: float

    @property
    def frames_without_pose(self) -> int:
        return self.total_frames - self.frames_with_pose

    @property
    def pose_rate(self) -> float:
        return self.frames_with_pose / self.total_frames if self.total_frames else 0.0


def front_arm(stance: str) -> str:
    """Lado do braço da frente ("left" ou "right") para a base informada."""
    try:
        return STANCES[stance]
    except KeyError:
        raise ValueError(
            f"stance inválida: {stance!r}. Use uma de: {', '.join(STANCES)}"
        ) from None


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
    opts = {k: v for k, v in LANDMARKER_OPTIONS.items() if k != "running_mode"}
    options = vision.PoseLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode[LANDMARKER_OPTIONS["running_mode"]],
        **opts,
    )
    return vision.PoseLandmarker.create_from_options(options)


def draw_arms(frame, landmarks, stance: str, low_vis: float) -> None:
    """Desenha os dois braços e marca o da frente com o rótulo FRENTE.

    Segmentos: amarelo no braço da frente, cinza no de trás.
    Articulações: verde com visibilidade suficiente, vermelho abaixo do limite.
    """
    front = front_arm(stance)
    h, w = frame.shape[:2]
    for side, idxs in ARMS.items():
        pts = [(int(landmarks[i].x * w), int(landmarks[i].y * h)) for i in idxs]
        color = FRONT_COLOR if side == front else REAR_COLOR
        cv2.line(frame, pts[0], pts[1], color, 2)
        cv2.line(frame, pts[1], pts[2], color, 2)
        for i, p in zip(idxs, pts):
            ok = (landmarks[i].visibility or 0.0) >= low_vis
            cv2.circle(frame, p, 6, OK_COLOR if ok else LOW_VIS_COLOR, -1)
        if side == front:
            wx, wy = pts[2]
            (tw, th), _ = cv2.getTextSize("FRENTE", cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            # Mantém o rótulo dentro do quadro quando o punho está perto da borda
            x = min(max(wx + 8, 0), max(w - tw, 0))
            y = min(max(wy - 8, th), h - 1)
            cv2.putText(frame, "FRENTE", (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, FRONT_COLOR, 2)


def extract(
    video_path: Path,
    out_dir: Path,
    model_path: Path,
    *,
    stance: str,
    preview: bool = False,
    low_vis: float = 0.5,
    landmarker_factory=create_landmarker,
) -> ExtractionSummary:
    side = front_arm(stance)
    arm_idxs = ARMS[side]

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Não consegui abrir o vídeo: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or not math.isfinite(fps) or fps <= 0:
        cap.release()
        # Sem FPS confiável os timestamps seriam inventados
        raise ValueError(f"FPS inválido ({fps}) no vídeo: {video_path}")
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

            # Baixa visibilidade só é contada em frames com pose; frames sem pose
            # são outra categoria de falha e ficam em frames_sem_pose
            if landmarks:
                with_pose += 1
                arm_vis = [landmarks[i].visibility or 0.0 for i in arm_idxs]
                vis_sum += sum(arm_vis)
                vis_count += len(arm_vis)
                if min(arm_vis) < low_vis:
                    low_vis_frames += 1
                if writer_video is not None:
                    draw_arms(frame, landmarks, stance, low_vis)

            if writer_video is not None:
                writer_video.write(frame)
            total += 1

    cap.release()
    if writer_video is not None:
        writer_video.release()

    summary = ExtractionSummary(
        total_frames=total,
        frames_with_pose=with_pose,
        front_arm=side,
        front_arm_visibility_mean=(vis_sum / vis_count) if vis_count else math.nan,
        front_arm_low_visibility_frames=low_vis_frames,
        seconds=time.perf_counter() - start,
    )

    meta = {
        "video": video_path.name,
        "video_sha256": file_sha256(video_path),
        "fps": fps,
        "largura": width,
        "altura": height,
        "frames": total,
        "duracao_s": round(total / fps, 3),
        "modelo": model_path.name,
        "modelo_sha256": file_sha256(model_path),
        "mediapipe_versao": mp.__version__,
        "opencv_versao": cv2.__version__,
        "opcoes_landmarker": LANDMARKER_OPTIONS,
        "base": stance,
        "braco_frente": side,
        "limite_visibilidade": low_vis,
        "frames_com_pose": with_pose,
        "frames_sem_pose": summary.frames_without_pose,
        "taxa_pose": round(summary.pose_rate, 4),
        # Média calculada apenas sobre os frames com pose
        "visibilidade_media_braco_frente": round(summary.front_arm_visibility_mean, 4)
        if vis_count
        else None,
        "frames_braco_frente_baixa_visibilidade": low_vis_frames,
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # Dados que mudam a cada execução ficam separados do resultado reprodutível
    execucao = {
        "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tempo_processamento_s": round(summary.seconds, 2),
        "segundos_por_minuto_de_video": round(summary.seconds / (total / fps / 60), 2)
        if total
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
    parser.add_argument(
        "--stance",
        required=True,
        choices=list(STANCES),
        help="base do atleta; define o braço da frente (orthodox = esquerdo, southpaw = direito)",
    )
    parser.add_argument("--out", type=Path, default=Path("saida/landmarks"))
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--preview", action="store_true", help="gera MP4 com os dois braços desenhados")
    parser.add_argument("--low-vis", type=float, default=0.5)
    args = parser.parse_args(argv)

    if not args.model.exists():
        print(f"Modelo não encontrado em {args.model}. Veja o README (seção Setup).", file=sys.stderr)
        return 1

    s = extract(
        args.video, args.out, args.model,
        stance=args.stance, preview=args.preview, low_vis=args.low_vis,
    )
    lado = "esquerdo" if s.front_arm == "left" else "direito"
    print(f"Base: {args.stance} (braço da frente: {lado})")
    print(f"Frames: {s.total_frames}")
    print(f"Pose detectada: {s.frames_with_pose} ({s.pose_rate:.1%})")
    print(f"Frames sem pose: {s.frames_without_pose}")
    print(f"Visibilidade média do braço da frente: {s.front_arm_visibility_mean:.3f}")
    print(f"Frames com braço da frente pouco visível: {s.front_arm_low_visibility_frames}")
    print(f"Tempo de processamento: {s.seconds:.1f}s")
    return 0 if s.total_frames else 1


if __name__ == "__main__":
    raise SystemExit(main())
