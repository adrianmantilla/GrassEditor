"""Pruebas del núcleo de Pradera (Python puro, sin Maya).

    python -m unittest discover -s tests -v
"""

import json
import math
import os
import re
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
sys.path.insert(0, RAIZ)

from pradera import camara as cam  # noqa: E402
from pradera import capa as cp  # noqa: E402
from pradera import estadisticas as est  # noqa: E402
from pradera import matas, reparto, tipos  # noqa: E402
from pradera.mascara import Mascara  # noqa: E402

import instalar  # noqa: E402


def plano(lado=1000.0, n=10, y=None):
    """Suelo cuadrado de ``lado`` cm (centrado) con n×n quads. ``y(x, z)`` da la altura."""
    puntos, tri, caras = [], [], []
    for j in range(n + 1):
        for i in range(n + 1):
            x, z = -lado / 2 + lado * i / n, -lado / 2 + lado * j / n
            puntos.append((x, y(x, z) if y else 0.0, z))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            b, c = a + 1, a + n + 1
            tri += [a, c, b, b, c, c + 1]
            caras += [j * n + i] * 2
    return reparto.Suelo(puntos, tri, caras)


class Tipos(unittest.TestCase):
    def test_ocho_tipos_de_serie(self):
        self.assertEqual(tipos.ORDEN, ["cesped", "silvestre", "seca", "trebol", "espigas", "juncos", "flores",
                                       "ornamental"])

    def test_catalogo_guarda_solo_cambios(self):
        cat = tipos.Catalogo()
        self.assertEqual(cat.a_json(), "{}")
        cat.poner(cat["cesped"].copiar(briznas=20))
        otro = tipos.Catalogo.desde_json(cat.a_json())
        self.assertEqual(otro["cesped"].briznas, 20)
        self.assertEqual(otro["trebol"].a_dict(), tipos.SERIE["trebol"].a_dict())

    def test_tipo_propio_y_clave_libre(self):
        cat = tipos.Catalogo()
        clave = tipos.clave_libre("Césped Inglés", set(cat.claves()))
        self.assertEqual(clave, "cesped_ingles")
        cat.poner(cat["cesped"].copiar(clave=clave, propio=True))
        self.assertIn(clave, tipos.Catalogo.desde_json(cat.a_json()).claves())
        self.assertEqual(tipos.clave_libre("cesped", {"cesped"}), "cesped_2")
        self.assertEqual(tipos.clave_libre("", set()), "tipo")

    def test_validar_corrige(self):
        t = tipos.de_serie("cesped").copiar(briznas=0, altura_max=1, curvatura=5, cabeza="nada")
        t.validar()
        self.assertEqual(t.briznas, 1)
        self.assertGreaterEqual(t.altura_max, t.altura_min)
        self.assertEqual(t.curvatura, 1.0)
        self.assertIsNone(t.cabeza)

    def test_json_roto(self):
        self.assertEqual(tipos.Catalogo.desde_json("{roto").claves(), tipos.ORDEN)


class Matas(unittest.TestCase):
    def test_niveles_de_detalle_bajan(self):
        for clave in tipos.ORDEN:
            completa, simple, tarjeta = matas.triangulos_por_nivel(tipos.SERIE[clave])
            self.assertGreater(completa, simple, clave)
            self.assertGreater(simple, tarjeta, clave)
            self.assertEqual(tarjeta, matas.TRIANGULOS_TARJETA)

    def test_malla_valida(self):
        for clave in tipos.ORDEN:
            for nivel in range(3):
                m = matas.mata(tipos.SERIE[clave], 2, nivel)
                n = len(m.vertices)
                self.assertEqual(len(m.colores), n)
                self.assertEqual(len(m.uvs), n)
                self.assertEqual(len(m.indices) % 3, 0)
                self.assertTrue(all(0 <= i < n for i in m.indices))
                self.assertTrue(all(0 <= c <= 1 for col in m.colores for c in col))
                self.assertTrue(all(0 <= u <= 1 and 0 <= v <= 1 for u, v in m.uvs))

    def test_altura_razonable(self):
        for clave in tipos.ORDEN:
            t = tipos.SERIE[clave]
            caja = matas.mata(t).caja()
            self.assertGreaterEqual(caja[1], -1e-6)
            self.assertLess(caja[4], t.altura * 1.6, clave)
            self.assertGreater(caja[4], t.altura * 0.5, clave)

    def test_misma_semilla_misma_mata(self):
        t = tipos.SERIE["silvestre"]
        self.assertEqual(matas.mata(t, 3).vertices, matas.mata(t, 3).vertices)
        self.assertNotEqual(matas.mata(t, 3).vertices, matas.mata(t, 4).vertices)

    def test_flores_tienen_dos_colores(self):
        t = tipos.SERIE["flores"]
        blancas = matas.mata(t, 0).colores
        rojas = matas.mata(t, 5).colores
        self.assertIn((0.95, 0.95, 0.92), blancas)
        self.assertIn((0.85, 0.12, 0.08), rojas)


class Mascaras(unittest.TestCase):
    def test_pintar_y_guardar(self):
        m = Mascara((-500, -500, 500, 500), 0)
        self.assertEqual((m.ancho, m.alto), (100, 100))
        self.assertTrue(m.vacia())
        m.pintar(0, 0, 100, 1.0, "poner")
        self.assertGreater(m.valor(0, 0), 0.99)
        self.assertEqual(m.valor(300, 300), 0.0)
        otra = Mascara.desde_texto(m.a_texto())
        self.assertEqual(otra.datos, m.datos)
        self.assertEqual(otra.caja, m.caja)
        m.pintar(0, 0, 100, 1.0, "quitar")
        self.assertEqual(m.valor(0, 0), 0.0)
        m.llenar(0)
        self.assertTrue(m.vacia())

    def test_suavizar_difumina(self):
        m = Mascara((0, 0, 400, 400), 0)
        m.pintar(100, 200, 100, 1.0, "poner", dureza=0.95)
        borde = m.valor(196, 200)
        for _ in range(4):
            m.pintar(200, 200, 150, 1.0, "suavizar")
        self.assertNotAlmostEqual(m.valor(196, 200), borde, places=2)

    def test_fuera_de_la_caja(self):
        m = Mascara((0, 0, 100, 100), 255)
        self.assertEqual(m.valor(-50, 50), 0.0)
        self.assertEqual(m.muestreador()(150, 50), 0.0)
        self.assertEqual(m.muestreador()(50, 50), 1.0)

    def test_texto_roto(self):
        self.assertIsNone(Mascara.desde_texto("1|2|roto"))
        self.assertIsNone(Mascara.desde_texto(""))

    def test_ajustar_a_otra_caja(self):
        m = Mascara((0, 0, 100, 100), 0)
        m.pintar(25, 25, 20, 1.0)
        n = m.ajustada_a((0, 0, 200, 200))
        self.assertGreater(n.valor(25, 25), 0.9)
        self.assertEqual(n.valor(150, 150), 0.0)

    def test_limites_de_tamano(self):
        self.assertEqual(Mascara((0, 0, 100000, 10), 0).ancho, 512)
        self.assertEqual(Mascara((0, 0, 10, 10), 0).ancho, 8)


class Reparto(unittest.TestCase):
    def setUp(self):
        self.cat = tipos.Catalogo()
        self.suelo = plano(1000.0, 10)   # 10 × 10 m = 100 m²

    def test_densidad(self):
        cand = reparto.candidatos(self.suelo, [["cesped", 100]], self.cat, 100.0, 1)
        self.assertAlmostEqual(len(cand) / 10000.0, 1.0, delta=0.02)   # 100 m² × 100 matas/m²
        cand = reparto.candidatos(self.suelo, [["cesped", 100]], self.cat, 50.0, 1)
        self.assertAlmostEqual(len(cand) / 5000.0, 1.0, delta=0.03)

    def test_mezcla(self):
        cand = reparto.candidatos(self.suelo, [["silvestre", 50], ["flores", 50]], self.cat, 100.0, 1)
        n_flores = sum(1 for k in cand.tipo if cand.claves[k] == "flores")
        # 50 m² × 60 + 50 m² × 20 = 3000 + 1000
        self.assertAlmostEqual(len(cand), 4000, delta=120)
        self.assertAlmostEqual(n_flores, 1000, delta=80)
        self.assertEqual(reparto.normalizar_mezcla([["a", 0], ["b", 2], ["b", 2]]), [("b", 1.0)])

    def test_esperadas_sin_generar(self):
        self.assertAlmostEqual(reparto.esperadas(self.suelo, [["silvestre", 1]], self.cat), 6000, delta=1)

    def test_semilla(self):
        a = reparto.candidatos(self.suelo, [["silvestre", 100]], self.cat, 100.0, 1)
        b = reparto.candidatos(self.suelo, [["silvestre", 100]], self.cat, 100.0, 1)
        c = reparto.candidatos(self.suelo, [["silvestre", 100]], self.cat, 100.0, 2)
        self.assertEqual(list(a.x), list(b.x))
        self.assertNotEqual(list(a.x[:50]), list(c.x[:50]))

    def test_sin_grumos(self):
        """Reparto uniforme: cada metro cuadrado tiene casi las mismas matas."""
        cand = reparto.candidatos(self.suelo, [["cesped", 100]], self.cat, 100.0, 3)
        cuenta = {}
        for x, z in zip(cand.x, cand.z):
            k = (int((x + 500) // 100), int((z + 500) // 100))
            cuenta[k] = cuenta.get(k, 0) + 1
        valores = list(cuenta.values())
        self.assertEqual(len(valores), 100)
        self.assertLess(max(valores) - min(valores), 40)

    def test_dentro_del_suelo_y_escala(self):
        cand = reparto.candidatos(self.suelo, [["juncos", 100]], self.cat, 100.0, 1)
        t = self.cat["juncos"]
        self.assertTrue(all(-500 <= x <= 500 for x in cand.x))
        lo, hi = t.altura_min / t.altura * 0.75, t.altura_max / t.altura * 1.25
        self.assertTrue(all(lo - 1e-6 <= e <= hi + 1e-6 for e in cand.escala))

    def test_caras(self):
        cand = reparto.candidatos(self.suelo, [["cesped", 100]], self.cat, 100.0, 1, caras=[0, 1])
        self.assertAlmostEqual(len(cand), 200, delta=25)    # dos caras de 1 m²
        self.assertAlmostEqual(self.suelo.area([0, 1]), 20000.0)

    def test_matriz_mueve_y_escala(self):
        s = plano(100.0, 1)
        s.matriz = [2, 0, 0, 0, 0, 1, 0, 0, 0, 0, 2, 0, 1000, 50, 0, 1]
        cand = reparto.candidatos(s, [["cesped", 100]], self.cat, 100.0, 1)
        self.assertAlmostEqual(len(cand), 400, delta=30)    # 2 × 2 m
        self.assertTrue(all(900 <= x <= 1100 for x in cand.x))
        self.assertTrue(all(-50 <= lx <= 50 for lx in cand.lx))
        self.assertLess(abs(s.escala() - 2.0), 1e-9)

    def test_maximo(self):
        cand = reparto.candidatos(self.suelo, [["cesped", 100]], self.cat, 100.0, 1, maximo=500)
        self.assertEqual(len(cand), 500)
        self.assertTrue(cand.recortadas)

    def test_pendiente(self):
        # media loma: la mitad izquierda plana, la derecha a 45°
        s = plano(1000.0, 20, y=lambda x, z: max(0.0, x))
        cand = reparto.candidatos(s, [["cesped", 100]], self.cat, 100.0, 1)
        acept = reparto.aceptados(cand, None, reparto.Reglas(pendiente_max=30))
        self.assertTrue(all(cand.x[i] <= 25 for i in acept))
        self.assertGreater(len(acept), 0.4 * 10000)

    def test_altura(self):
        s = plano(1000.0, 20, y=lambda x, z: x)
        cand = reparto.candidatos(s, [["silvestre", 100]], self.cat, 100.0, 1)
        acept = reparto.aceptados(cand, None, reparto.Reglas(altura_max=0))
        self.assertTrue(all(cand.y[i] < 10 for i in acept))

    def test_mascara_vacia_y_llena(self):
        cand = reparto.candidatos(self.suelo, [["silvestre", 100]], self.cat, 100.0, 1)
        caja = self.suelo.caja_local()
        self.assertEqual(len(reparto.aceptados(cand, Mascara(caja, 0))), 0)
        self.assertEqual(len(reparto.aceptados(cand, Mascara(caja, 255))), len(cand))
        self.assertEqual(len(reparto.aceptados(cand, None)), len(cand))
        media = Mascara(caja, 0)
        media.pintar(-250, 0, 2000, 1.0)   # todo
        media.pintar(250, 0, 0.01, 1.0)
        mitad = Mascara(caja, 0)
        for z in range(-500, 501, 50):
            mitad.pintar(-300, z, 260, 1.0, dureza=0.9)
        n = len(reparto.aceptados(cand, mitad))
        self.assertGreater(n, 0.3 * len(cand))
        self.assertLess(n, 0.7 * len(cand))

    def test_camino_parterre_objetos_copas(self):
        cand = reparto.candidatos(self.suelo, [["cesped", 100]], self.cat, 100.0, 1)
        total = len(cand)
        camino = {"puntos": [(-600, 0), (600, 0)], "cerrada": False, "modo": "fuera", "ancho": 100}
        acept = reparto.aceptados(cand, None, reparto.Reglas(curvas=[camino], borde=10))
        self.assertTrue(all(abs(cand.z[i]) >= 45 for i in acept))
        self.assertAlmostEqual(len(acept) / total, 0.89, delta=0.03)
        cuadrado = [(-200, -200), (200, -200), (200, 200), (-200, 200)]
        dentro = {"puntos": cuadrado, "cerrada": True, "modo": "dentro"}
        acept = reparto.aceptados(cand, None, reparto.Reglas(curvas=[dentro], borde=1))
        self.assertTrue(all(abs(cand.x[i]) <= 210 and abs(cand.z[i]) <= 210 for i in acept))
        self.assertAlmostEqual(len(acept) / total, 0.16, delta=0.02)
        # Con un borde ancho el parterre conserva su área: la transición va mitad dentro, mitad fuera
        circulo = {"puntos": [(200 * math.cos(a * math.pi / 25), 200 * math.sin(a * math.pi / 25))
                              for a in range(50)], "cerrada": True, "modo": "dentro"}
        acept = reparto.aceptados(cand, None, reparto.Reglas(curvas=[circulo], borde=40))
        self.assertAlmostEqual(len(acept) / (total * math.pi * 200 ** 2 / 1e6), 1.0, delta=0.06)
        fuera = dict(dentro, modo="fuera")
        acept = reparto.aceptados(cand, None, reparto.Reglas(curvas=[fuera], borde=1))
        self.assertAlmostEqual(len(acept) / total, 0.84, delta=0.02)
        acept = reparto.aceptados(cand, None, reparto.Reglas(objetos=[(0, 0, 100)], borde=1))
        self.assertTrue(all(math.hypot(cand.x[i], cand.z[i]) > 95 for i in acept))
        acept = reparto.aceptados(cand, None, reparto.Reglas(copas=[(0, 0, 300)], borde=1, factor_copa=0.5))
        dentro_copa = sum(1 for i in acept if math.hypot(cand.x[i], cand.z[i]) < 290)
        esperado = math.pi * 290 ** 2 / 1e6 * total * 0.5
        self.assertAlmostEqual(dentro_copa / esperado, 1.0, delta=0.1)

    def test_visor_subconjunto(self):
        cand = reparto.candidatos(self.suelo, [["cesped", 100]], self.cat, 100.0, 1)
        todas = reparto.aceptados(cand, None)
        visor = reparto.aceptados(cand, None, visor=0.1)
        self.assertTrue(set(visor) <= set(todas))
        self.assertAlmostEqual(len(visor) / len(todas), 0.1, delta=0.01)


def camara_mirando(pos, objetivo, focal=35.0):
    """Matriz de mundo (Maya) de una cámara en ``pos`` que mira a ``objetivo``."""
    zx, zy, zz = (pos[0] - objetivo[0], pos[1] - objetivo[1], pos[2] - objetivo[2])
    l = math.sqrt(zx * zx + zy * zy + zz * zz)
    z = (zx / l, zy / l, zz / l)
    x = (z[2], 0.0, -z[0])
    lx = math.sqrt(x[0] ** 2 + x[2] ** 2) or 1.0
    x = (x[0] / lx, 0.0, x[2] / lx)
    y = (z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0])
    return cam.Camara(list(x) + [0] + list(y) + [0] + list(z) + [0] + list(pos) + [1], focal, 1.417, 16 / 9.0)


class Camaras(unittest.TestCase):
    def setUp(self):
        self.cat = tipos.Catalogo()
        self.suelo = plano(4000.0, 20)
        self.cand = reparto.candidatos(self.suelo, [["silvestre", 100], ["flores", 20]], self.cat, 100.0, 1)
        self.todas = reparto.aceptados(self.cand)
        self.camara = camara_mirando((0, 170, 2000), (0, 0, 0))

    def test_camara_ve(self):
        c = self.camara
        self.assertTrue(c.ve(0, 0, 0))
        self.assertFalse(c.ve(0, 0, 2500))         # detrás
        self.assertFalse(c.ve(3000, 0, 1000, 0))   # muy a un lado
        self.assertAlmostEqual(c.fov_h, 54.43, delta=0.1)

    def test_recorte(self):
        sin = cam.Opciones(recorte=False, lod=False, aclarar=False)
        con = cam.Opciones(recorte=True, lod=False, aclarar=False, margen=0)
        n_sin = len(cam.salida(self.cand, self.todas, sin, self.camara))
        n_con = len(cam.salida(self.cand, self.todas, con, self.camara))
        self.assertEqual(n_sin, len(self.todas))
        self.assertLess(n_con, 0.6 * n_sin)
        self.assertGreater(n_con, 0.15 * n_sin)

    def test_niveles_por_distancia(self):
        op = cam.Opciones(recorte=False, lod=True, aclarar=False, cerca=800, medio=2000)
        s = cam.salida(self.cand, self.todas, op, self.camara)
        niveles = [i % 3 for i in s.indices]
        self.assertEqual(set(niveles), {0, 1, 2})
        for k in range(len(s)):
            x, y, z = s.posiciones[k]
            d = math.sqrt(x * x + (y - 170) ** 2 + (z - 2000) ** 2)
            if d < 700:
                self.assertEqual(niveles[k], 0)
            if d > 2300:
                self.assertEqual(niveles[k], 2)

    def test_indices_y_huecos(self):
        op = cam.Opciones(recorte=False, lod=False, aclarar=False)
        s = cam.salida(self.cand, self.todas, op, None)
        for k in range(0, len(s), 97):
            i = s.ids[k]
            self.assertEqual(s.indices[k], self.cand.tipo[i] * 18 + self.cand.variante[i] * 3)

    def test_aclarar(self):
        sin = cam.Opciones(recorte=False, lod=True, aclarar=False)
        con = cam.Opciones(recorte=False, lod=True, aclarar=True, aclarar_cantidad=0.5)
        a = cam.salida(self.cand, self.todas, sin, self.camara)
        b = cam.salida(self.cand, self.todas, con, self.camara)
        self.assertLess(len(b), len(a))
        self.assertGreater(max(e[0] for e in b.escalas), max(e[0] for e in a.escalas))

    def test_visor(self):
        op = cam.Opciones(visor_porcentaje=10, visor_como="tarjetas")
        s = cam.salida(self.cand, self.todas, op, self.camara, render=False)
        self.assertAlmostEqual(len(s) / float(len(self.todas)), 0.1, delta=0.015)
        self.assertTrue(all(i % 3 == 2 for i in s.indices))
        op = cam.Opciones(visor_porcentaje=100, visor_como="matas")
        s = cam.salida(self.cand, self.todas, op, self.camara, render=False)
        self.assertEqual(len(s), len(self.todas))
        self.assertTrue(all(i % 3 == 0 for i in s.indices))

    def test_opciones_json(self):
        op = cam.Opciones.desde_dict({"visor_como": "raro", "medio": 1, "cerca": 500})
        self.assertEqual(op.visor_como, "tarjetas")
        self.assertEqual(op.medio, 500)


class Estadisticas(unittest.TestCase):
    def test_semaforo(self):
        self.assertEqual(est.semaforo(1000), "verde")
        self.assertEqual(est.semaforo(5e6), "ambar")
        self.assertEqual(est.semaforo(2e7), "rojo")

    def test_formatos(self):
        self.assertEqual(est.miles(1234567), "1.234.567")
        self.assertEqual(est.corto(1234567), "1,2 M")
        self.assertEqual(est.corto(45300), "45 mil")
        self.assertEqual(est.bytes_legibles(3 * 1024 ** 2), "3 MB")

    def test_consejos(self):
        inf = est.Informe()
        inf.triangulos = 12e6
        inf.por_capa = {"a": 10e6, "b": 2e6}
        inf.por_tipo = {"cesped": 9e6, "flores": 3e6}
        lista = est.consejos(inf, {"a": {"recorte": False, "lod": True, "aclarar": True}})
        self.assertEqual(lista[0], ("consejo_recorte", {"capa": "a"}))
        self.assertIn(("consejo_tipo", {"tipo": "cesped", "parte": 75}), lista)
        inf.triangulos = 100
        self.assertEqual(est.consejos(inf), [])


class Capas(unittest.TestCase):
    def setUp(self):
        self.cat = tipos.Catalogo()
        self.suelo = plano(2000.0, 10)

    def test_motor_guarda_pasos(self):
        m = cp.Motor()
        aj = cp.AjustesCapa(mezcla=[["silvestre", 100]])
        self.assertTrue(m.preparar(self.suelo, aj, self.cat))
        self.assertFalse(m.preparar(self.suelo, aj, self.cat))
        cand = m.candidatas
        mascara = Mascara(self.suelo.caja_local(), 0)
        mascara.pintar(0, 0, 300, 1.0)
        self.assertTrue(m.preparar(self.suelo, aj, self.cat, mascara.a_texto()))
        self.assertIs(m.candidatas, cand)    # pintar no vuelve a sembrar
        self.assertLess(len(m.aceptadas()), len(cand))
        aj2 = cp.AjustesCapa.desde_json(aj.a_json())
        aj2.densidad = 50
        m.preparar(self.suelo, aj2, self.cat, mascara.a_texto())
        self.assertIsNot(m.candidatas, cand)

    def test_informe(self):
        m = cp.Motor()
        aj = cp.AjustesCapa(mezcla=[["cesped", 100]], opciones={"recorte": False, "lod": False})
        m.preparar(self.suelo, aj, self.cat)
        inf = m.informe(None)
        tris = cp.triangulos_tipo(self.cat["cesped"])[0]
        self.assertEqual(inf.matas, len(m.candidatas))
        self.assertEqual(inf.triangulos, inf.matas * tris)
        self.assertEqual(inf.unicos, tris * tipos.VARIANTES)
        self.assertLess(inf.memoria, inf.memoria_sin_instancias)
        self.assertAlmostEqual(inf.visor / float(inf.matas), 0.1, delta=0.02)

    def test_capa_apagada(self):
        m = cp.Motor()
        aj = cp.AjustesCapa(activa=False)
        m.preparar(self.suelo, aj, self.cat)
        self.assertEqual(len(m.salida()), 0)
        self.assertEqual(m.informe().matas, 0)

    def test_hornear(self):
        m = cp.Motor()
        aj = cp.AjustesCapa(mezcla=[["silvestre", 80], ["flores", 20]], reglas={"objetos": [(0, 0, 300)]})
        m.preparar(self.suelo, aj, self.cat)
        texto = m.horneado()
        antes = m.salida(None, True)
        otro = cp.Motor()
        otro.preparar(None, aj, self.cat, "", texto)
        self.assertTrue(otro.horneada)
        despues = otro.salida(None, True)
        self.assertEqual(len(antes), len(despues))
        self.assertEqual(list(antes.indices), list(despues.indices))
        self.assertAlmostEqual(antes.posiciones[10][0], despues.posiciones[10][0], places=3)
        self.assertIsNone(cp.deshornear("roto"))
        # Deshornear: vuelve a calcular
        otro.preparar(self.suelo, aj, self.cat, "", "")
        self.assertFalse(otro.horneada)
        self.assertEqual(len(otro.salida(None, True)), len(antes))

    def test_ajustes_json(self):
        aj = cp.AjustesCapa.desde_json('{"densidad": 50, "raro": 1}')
        self.assertEqual(aj.densidad, 50)
        self.assertEqual(aj.opciones["visor_como"], "tarjetas")
        self.assertEqual(cp.AjustesCapa.desde_json("roto").mezcla, [["silvestre", 100.0]])


class Textos(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(RAIZ, "scripts", "pradera", "i18n", "es.json"), encoding="utf-8") as f:
            self.es = json.load(f)

    def _codigo(self):
        carpeta = os.path.join(RAIZ, "scripts", "pradera")
        texto = ""
        for nombre in os.listdir(carpeta):
            if nombre.endswith(".py"):
                with open(os.path.join(carpeta, nombre), encoding="utf-8") as f:
                    texto += f.read()
        with open(os.path.join(RAIZ, "instalar.py"), encoding="utf-8") as f:
            texto += f.read()
        return texto

    def test_claves_usadas_existen(self):
        codigo = self._codigo()
        usadas = set(re.findall(r'\bt\("([a-z_0-9]+)"', codigo))
        usadas = {u for u in usadas if not u.endswith("_")}
        botones = set(re.findall(r'_boton\("([a-z_0-9]+)"', codigo))
        usadas |= botones | {"ayuda_" + b for b in botones}
        usadas |= set(re.findall(r'_grupo\("([a-z_0-9]+)"', codigo))
        usadas |= set(re.findall(r'"(consejo_[a-z]+)"', codigo))
        for clave in tipos.ORDEN:
            usadas |= {"tipo_" + clave, tipos.USOS[clave]}
        for modo in ("poner", "quitar", "suavizar"):
            usadas |= {"pincel_" + modo, "ayuda_pincel_" + modo}
        usadas |= {"como_" + c for c in cam.COMO}
        usadas |= {"curva_dentro", "curva_fuera", "curva_camino", "vista_render_no", "aviso_sueltas",
                   "aviso_unir", "instalado_titulo", "instalado_texto"}
        usadas |= {"semaforo_" + c for c in ("verde", "ambar", "rojo")}
        for campo in ("altura_min", "altura_max", "densidad", "briznas", "segmentos", "anchura", "curvatura",
                      "abertura", "radio"):
            usadas |= {"campo_" + campo, "ayuda_campo_" + campo}
        faltan = sorted(usadas - set(self.es))
        self.assertEqual(faltan, [])

    def test_sin_vacios_y_formato(self):
        from pradera.i18n import t
        self.assertTrue(all(isinstance(v, str) and v.strip() for v in self.es.values()))
        self.assertEqual(t("capa_creada", capa="a", suelo="b"), "Capa a creada sobre b.")
        self.assertEqual(t("clave_que_no_existe"), "clave_que_no_existe")


class Instalacion(unittest.TestCase):
    def test_mod(self):
        texto = instalar.contenido_mod("C:\\Users\\Ana\\Pradera", "1.0.0")
        self.assertIn("+ Pradera 1.0.0 C:/Users/Ana/Pradera", texto)
        self.assertIn("plug-ins: plug-ins", texto)

    def test_version(self):
        import pradera
        self.assertEqual(instalar._version(RAIZ), pradera.__version__)

    def test_ruta_mod_sin_tildes(self):
        modulos = "/Users/jose/Library/Preferences/Autodesk/maya/modules"
        raiz = "/Users/jose/Descargas/Pradera año"
        self.assertEqual(instalar.ruta_para_mod(raiz, modulos), raiz)
        self.assertEqual(instalar.ruta_para_mod("/Users/ana/Pradera", modulos), "/Users/ana/Pradera")

    def test_compila_todo(self):
        """Todos los archivos de Python se pueden compilar (también los que necesitan Maya)."""
        import py_compile
        for carpeta, _, archivos in os.walk(RAIZ):
            if ".git" in carpeta:
                continue
            for nombre in archivos:
                if nombre.endswith(".py"):
                    py_compile.compile(os.path.join(carpeta, nombre), doraise=True)


if __name__ == "__main__":
    unittest.main()
