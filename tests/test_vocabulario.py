import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACOTE = ROOT / "boxing_vision"


def imports_do_modulo(caminho: Path) -> set[str]:
    """Nomes de módulo importados no arquivo (relativos marcados com '.')."""
    nomes = set()
    for no in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
        if isinstance(no, ast.Import):
            nomes.update(a.name for a in no.names)
        elif isinstance(no, ast.ImportFrom):
            nomes.add("." * no.level + (no.module or ""))
    return nomes


def test_valores_do_vocabulario():
    from boxing_vision import vocabulario as v

    assert v.MAOS == ("direita", "esquerda")
    assert v.BASES == ("orthodox", "southpaw")
    assert v.MAO_DA_FRENTE == {"orthodox": "esquerda", "southpaw": "direita"}
    assert v.MAO_DE_TRAS == {"orthodox": "direita", "southpaw": "esquerda"}
    assert v.STATUS_DETECTADO == "detectado"
    assert v.STATUS_AMBIGUO == "ambiguo"


def test_vocabulario_nao_importa_nada_do_projeto():
    proibidos = [
        m for m in imports_do_modulo(PACOTE / "vocabulario.py")
        if m.startswith(".") or m.split(".")[0] == "boxing_vision"
    ]
    assert proibidos == []


def test_vocabulario_carrega_sozinho():
    # Processo novo: nenhum outro módulo do projeto entra junto com o vocabulário
    codigo = (
        "import sys, boxing_vision.vocabulario; "
        "print(sorted(m for m in sys.modules if m.startswith('boxing_vision.')))"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert saida == "['boxing_vision.vocabulario']"


@pytest.mark.parametrize("nome", ["MAOS", "BASES", "MAO_DA_FRENTE", "MAO_DE_TRAS"])
def test_labels_expoe_o_mesmo_objeto_do_vocabulario(nome):
    from boxing_vision import labels, vocabulario

    assert getattr(labels, nome) is getattr(vocabulario, nome)


@pytest.mark.parametrize("nome", ["STATUS_DETECTADO", "STATUS_AMBIGUO"])
def test_evaluate_expoe_o_status_do_vocabulario(nome):
    from boxing_vision import evaluate, vocabulario

    assert getattr(evaluate, nome) == getattr(vocabulario, nome)
    assert not any(
        isinstance(no, ast.Assign) and any(getattr(t, "id", None) == nome for t in no.targets)
        for no in ast.walk(ast.parse((PACOTE / "evaluate.py").read_text(encoding="utf-8")))
    ), f"{nome} ainda é definido no evaluate.py"


def test_extract_importa_do_vocabulario_e_nao_dos_rotulos():
    imports = imports_do_modulo(PACOTE / "extract.py")
    assert "boxing_vision.vocabulario" in imports
    assert "boxing_vision.labels" not in imports
