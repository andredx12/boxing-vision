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
import os
import platform
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision

from boxing_vision.vocabulario import BASES, MAO_DA_FRENTE, MAO_DIREITA, MAO_ESQUERDA

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

# Mão anatômica (vocabulário do projeto) -> prefixo dos landmarks do MediaPipe
LADO_MEDIAPIPE = {MAO_ESQUERDA: "left", MAO_DIREITA: "right"}

# Ombro, cotovelo e punho de cada mão
ARMS = {
    mao: tuple(LANDMARK_NAMES.index(f"{lado}_{joint}") for joint in ("shoulder", "elbow", "wrist"))
    for mao, lado in LADO_MEDIAPIPE.items()
}

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
    """Mão da frente ("direita" ou "esquerda") para a base informada."""
    if stance not in BASES:
        raise ValueError(f"stance inválida: {stance!r}. Use uma de: {', '.join(BASES)}")
    return MAO_DA_FRENTE[stance]


def validar_low_vis(low_vis: float) -> float:
    """Limite de visibilidade, entre 0 e 1 (a escala da visibilidade do MediaPipe)."""
    # A comparação encadeada também rejeita nan
    if not 0.0 <= low_vis <= 1.0:
        raise ValueError(f"low_vis deve estar entre 0 e 1, recebido: {low_vis}")
    return low_vis


def _arg_low_vis(texto: str) -> float:
    try:
        return validar_low_vis(float(texto))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{texto!r} inválido: {exc}") from None


def frames_declarados(valor: float) -> int | None:
    """Total de frames declarado pelo contêiner, ou None quando o valor não é utilizável.

    Alguns backends devolvem 0, negativo ou estimativa fracionária quando o contêiner
    não informa o total; nesses casos nenhum número é registrado.
    """
    if not math.isfinite(valor) or valor <= 0 or not float(valor).is_integer():
        return None
    return int(valor)


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
    for mao, idxs in ARMS.items():
        pts = [(int(landmarks[i].x * w), int(landmarks[i].y * h)) for i in idxs]
        color = FRONT_COLOR if mao == front else REAR_COLOR
        cv2.line(frame, pts[0], pts[1], color, 2)
        cv2.line(frame, pts[1], pts[2], color, 2)
        for i, p in zip(idxs, pts):
            ok = (landmarks[i].visibility or 0.0) >= low_vis
            cv2.circle(frame, p, 6, OK_COLOR if ok else LOW_VIS_COLOR, -1)
        if mao == front:
            wx, wy = pts[2]
            (tw, th), _ = cv2.getTextSize("FRENTE", cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            # Mantém o rótulo dentro do quadro quando o punho está perto da borda
            x = min(max(wx + 8, 0), max(w - tw, 0))
            y = min(max(wy - 8, th), h - 1)
            cv2.putText(frame, "FRENTE", (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, FRONT_COLOR, 2)


def frame_timestamp_ms(pos_msec: float, first_pos_msec: float, prev_ts_ms: int | None,
                       frame_idx: int) -> int:
    """Timestamp do frame em ms, relativo ao primeiro frame, validado para o MediaPipe.

    O valor vem do tempo de apresentação gravado no contêiner (CAP_PROP_POS_MSEC),
    não do relógio da execução, então é reprodutível.
    """
    if not math.isfinite(pos_msec):
        problema = f"CAP_PROP_POS_MSEC devolveu {pos_msec}"
    else:
        ts_ms = int(round(pos_msec - first_pos_msec))
        if prev_ts_ms is None or ts_ms > prev_ts_ms:
            return ts_ms
        problema = f"{ts_ms} ms depois de {prev_ts_ms} ms"
    raise ValueError(
        f"Timestamp inválido no frame {frame_idx}: {problema}. O MediaPipe exige tempo "
        "estritamente crescente entre frames. Regrave o vídeo seguindo "
        "docs/protocolo-gravacao.md; se o problema continuar, reporte o caso com o "
        "arquivo de vídeo e esta mensagem."
    )


def interval_summary(timestamps: list[int]) -> dict:
    """Resumo dos intervalos entre frames, para sinalizar vídeos com frames perdidos."""
    intervals = [b - a for a, b in zip(timestamps, timestamps[1:])]
    if not intervals:
        return {"mediana": None, "maximo": None, "acima_50ms": 0}
    return {
        # Sempre float: com quantidade par de intervalos a mediana pode ser fracionária
        "mediana": float(statistics.median(intervals)),
        "maximo": max(intervals),
        "acima_50ms": sum(1 for d in intervals if d > 50),
    }


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
    mao_frente = front_arm(stance)
    validar_low_vis(low_vis)
    arm_idxs = ARMS[mao_frente]

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Não consegui abrir o vídeo: {video_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = video_path.stem
    final = {
        "csv": out_dir / f"{stem}_landmarks.csv",
        "preview": out_dir / f"{stem}_preview.mp4",
        "execucao": out_dir / f"{stem}_execucao.json",
        "meta": out_dir / f"{stem}_meta.json",
    }
    # Tudo é gravado em temporários e só renomeado no fim: uma execução que falha
    # não apaga nem mistura a saída da execução anterior
    tmp = {k: p.with_name(p.stem + ".tmp" + p.suffix) for k, p in final.items()}

    writer_video = None
    timestamps: list[int] = []
    total = with_pose = low_vis_frames = 0
    vis_sum = 0.0
    vis_count = 0
    start = time.perf_counter()

    try:
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            if not fps or not math.isfinite(fps) or fps <= 0:
                raise ValueError(f"FPS inválido ({fps}) no vídeo: {video_path}")
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            # Lido antes do laço: depois do release() o OpenCV devolve 0
            declarados = frames_declarados(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if preview:
                # O preview é gravado em FPS constante e serve só para conferência
                # visual; o tempo de referência é o timestamp_ms do CSV
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer_video = cv2.VideoWriter(str(tmp["preview"]), fourcc, fps, (width, height))
                # Checado antes de abrir o modelo: falha cedo, e o except abaixo
                # remove o arquivo vazio que o OpenCV pode ter deixado
                if not writer_video.isOpened():
                    raise RuntimeError(
                        f"Não consegui criar o vídeo de preview em {tmp['preview']} "
                        f"(codec mp4v, {width}x{height}, {fps} FPS). Rode sem --preview "
                        "ou verifique a instalação do OpenCV."
                    )

            with landmarker_factory(model_path) as landmarker, tmp["csv"].open(
                "w", newline="", encoding="utf-8"
            ) as f:
                writer = csv.writer(f)
                writer.writerow(build_header())
                first_pos = None

                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break

                    pos = cap.get(cv2.CAP_PROP_POS_MSEC)
                    if first_pos is None:
                        first_pos = pos
                    ts_ms = frame_timestamp_ms(
                        pos, first_pos, timestamps[-1] if timestamps else None, total
                    )
                    timestamps.append(ts_ms)

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
        finally:
            cap.release()
            if writer_video is not None:
                writer_video.release()

        summary = ExtractionSummary(
            total_frames=total,
            frames_with_pose=with_pose,
            front_arm=mao_frente,
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
            # Total declarado pelo contêiner; diferente de "frames" quando o decoder
            # não entregou todos. None quando o contêiner não informa um total válido
            "frames_declarados": declarados,
            "duracao_s": round(total / fps, 3),
            "origem_timestamp": "CAP_PROP_POS_MSEC",
            "intervalo_frames_ms": interval_summary(timestamps),
            "modelo": model_path.name,
            "modelo_sha256": file_sha256(model_path),
            "mediapipe_versao": mp.__version__,
            "opencv_versao": cv2.__version__,
            "opcoes_landmarker": LANDMARKER_OPTIONS,
            "base": stance,
            "braco_frente": mao_frente,
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
        tmp["meta"].write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

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
        tmp["execucao"].write_text(
            json.dumps(execucao, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except BaseException:
        for p in tmp.values():
            p.unlink(missing_ok=True)
        raise

    # O meta antigo sai primeiro e o novo entra por último: se o _meta.json
    # existe, a execução que gerou os outros arquivos foi completa.
    # os.replace sobrescreve o destino também no Windows, ao contrário de os.rename
    final["meta"].unlink(missing_ok=True)
    for key in ("csv", "preview", "execucao", "meta"):
        if tmp[key].exists():
            os.replace(tmp[key], final[key])
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extração de landmarks de pose de um vídeo.")
    parser.add_argument("video", type=Path)
    parser.add_argument(
        "--stance",
        required=True,
        choices=list(BASES),
        help="base do atleta; define o braço da frente (orthodox = esquerdo, southpaw = direito)",
    )
    parser.add_argument("--out", type=Path, default=Path("saida/landmarks"))
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument(
        "--preview",
        action="store_true",
        help="gera MP4 com os dois braços desenhados, em FPS constante, só para conferência visual",
    )
    parser.add_argument(
        "--low-vis",
        type=_arg_low_vis,
        default=0.5,
        help="limite de visibilidade do braço da frente, entre 0 e 1",
    )
    args = parser.parse_args(argv)

    if not args.model.exists():
        print(f"Modelo não encontrado em {args.model}. Veja o README (seção Setup).", file=sys.stderr)
        return 1

    s = extract(
        args.video, args.out, args.model,
        stance=args.stance, preview=args.preview, low_vis=args.low_vis,
    )
    print(f"Base: {args.stance} (braço da frente: {s.front_arm})")
    print(f"Frames: {s.total_frames}")
    print(f"Pose detectada: {s.frames_with_pose} ({s.pose_rate:.1%})")
    print(f"Frames sem pose: {s.frames_without_pose}")
    print(f"Visibilidade média do braço da frente: {s.front_arm_visibility_mean:.3f}")
    print(f"Frames com braço da frente pouco visível: {s.front_arm_low_visibility_frames}")
    print(f"Tempo de processamento: {s.seconds:.1f}s")
    return 0 if s.total_frames else 1


if __name__ == "__main__":
    raise SystemExit(main())
