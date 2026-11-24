"""Preferencias globales de GrassEditor (las que cambia MantiTools)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from grasseditor import preferencias as pf  # noqa: E402


def test_de_serie_sin_archivo(tmp_path):
    assert pf.leer("render_automatico", str(tmp_path)) is True
    assert pf.leer("tipo_inicial", str(tmp_path)) == "silvestre"
    assert pf.leer("densidad_inicial", str(tmp_path)) == 100


def test_escribe_y_lee(tmp_path):
    pf.escribir("render_automatico", False, str(tmp_path))
    pf.escribir("tipo_inicial", "cesped", str(tmp_path))
    pf.escribir("densidad_inicial", 150, str(tmp_path))
    assert pf.leer("render_automatico", str(tmp_path)) is False
    assert pf.leer("tipo_inicial", str(tmp_path)) == "cesped"
    assert pf.leer("densidad_inicial", str(tmp_path)) == 150


def test_valores_raros_vuelven_a_los_de_serie(tmp_path):
    pf.escribir("tipo_inicial", "no_existe", str(tmp_path))
    pf.escribir("densidad_inicial", 9999, str(tmp_path))
    pf.escribir("render_automatico", "si", str(tmp_path))
    assert pf.leer("tipo_inicial", str(tmp_path)) == "silvestre"
    assert pf.leer("densidad_inicial", str(tmp_path)) == 300
    assert pf.leer("render_automatico", str(tmp_path)) is True


def test_clave_desconocida(tmp_path):
    import pytest
    with pytest.raises(KeyError):
        pf.escribir("otra", 1, str(tmp_path))
