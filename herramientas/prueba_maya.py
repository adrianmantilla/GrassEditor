"""Prueba de Pradera dentro de Maya, sin interfaz (herramienta de desarrollo).

Desde la terminal, con el mayapy de cada versión:

    /Applications/Autodesk/maya2027/Maya.app/Contents/bin/mayapy herramientas/prueba_maya.py
    "C:\\Program Files\\Autodesk\\Maya2027\\bin\\mayapy.exe" herramientas\\prueba_maya.py

Termina con «RESULTADO: OK» o con la lista de fallos. Al final mide la prueba
de carga (unas 300.000 matas) y lo escribe en la salida.
"""

import math
import os
import sys
import tempfile
import time
import traceback

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    sys.stdout.flush()
    if not condicion:
        fallos.append(texto)


def _instancer(instanciador):
    # API clásica: la API 2.0 de Maya 2026-2027 no trae OpenMayaFX
    import maya.OpenMaya as om1
    import maya.OpenMayaFX as omfx1
    sel = om1.MSelectionList()
    sel.add(instanciador)
    camino = om1.MDagPath()
    sel.getDagPath(0, camino)
    return omfx1.MFnInstancer(camino)


def contar(instanciador):
    """Matas que pone el instanciador (lo que ve Maya, no lo que dice Pradera)."""
    return _instancer(instanciador).particleCount()


def matriz_instancia(instanciador, i):
    """Matriz de la mata ``i`` según el instanciador, como lista de 16 números."""
    import maya.OpenMaya as om1
    caminos, matriz = om1.MDagPathArray(), om1.MMatrix()
    _instancer(instanciador).instancesForParticle(i, caminos, matriz)
    return [matriz(f, c) for f in range(4) for c in range(4)]


def main():
    import maya.standalone
    maya.standalone.initialize(name="python")
    from maya import cmds, mel

    print("Maya", cmds.about(version=True), "-", cmds.about(operatingSystem=True))
    tmp = tempfile.mkdtemp(prefix="pradera_prueba_")

    # --- plugin -------------------------------------------------------------------------
    cmds.loadPlugin(os.path.join(RAIZ, "plug-ins", "pradera_plugin.py"))
    comprobar(cmds.pluginInfo("pradera_plugin", query=True, loaded=True), "el plugin se carga")
    comprobar("praderaCapa" in cmds.allNodeTypes(), "nodo praderaCapa registrado")
    comprobar(hasattr(cmds, "praderaAccion") and hasattr(cmds, "praderaRender"), "comandos registrados")
    try:
        cmds.loadPlugin("mtoa", quiet=True)
    except RuntimeError:
        pass
    arnold = cmds.pluginInfo("mtoa", query=True, loaded=True)
    print("  (Arnold cargado: {})".format(arnold))

    from pradera import capa as cp
    from pradera import convertir, ejemplos, escena, interfaz_maya, matas, pincel, tipos

    # --- fase 0: prototipos -------------------------------------------------------------
    rutas = escena.prototipos("silvestre")
    comprobar(len(rutas) == 18, "18 prototipos de hierba silvestre")
    tris = cp.triangulos_tipo(tipos.SERIE["silvestre"])
    reales = [cmds.polyEvaluate(rutas[n], triangle=True) for n in range(3)]
    comprobar(reales[2] == matas.TRIANGULOS_TARJETA, "la tarjeta tiene {} triángulos ({})".format(
        matas.TRIANGULOS_TARJETA, reales[2]))
    comprobar(abs(reales[0] - tris[0]) <= tris[0] * 0.3, "mata completa con los triángulos previstos ({} ~ {})"
              .format(reales[0], tris[0]))
    forma = cmds.listRelatives(rutas[0], shapes=True, fullPath=True)[0]
    comprobar(cmds.polyColorSet(forma, query=True, allColorSets=True) == ["colorSet1"], "colores de vértice")
    comprobar(cmds.polyEvaluate(forma, uvcoord=True) > 0, "la mata tiene UVs")
    comprobar(escena.SG in (cmds.listConnections(forma, type="shadingEngine") or []), "material asignado")
    if arnold:
        comprobar(bool(cmds.listConnections(escena.SG + ".aiSurfaceShader")), "material de Arnold conectado")
    comprobar(escena.prototipos("silvestre") == rutas, "pedir los prototipos otra vez no los rehace")

    # --- fase 1: capa sobre un plano -----------------------------------------------------
    plano = cmds.polyPlane(width=1000, height=1000, subdivisionsX=10, subdivisionsY=10, name="suelo_prueba")[0]
    sin_optimizar = {"recorte": False, "lod": False, "aclarar": False}
    capa = escena.crear_capa(plano, nombre="prueba", mezcla=[["cesped", 100]], opciones=sin_optimizar)
    instancias = escena.instanciador(capa)
    comprobar(bool(instancias), "la capa tiene instanciador")
    conectados = cmds.listConnections(instancias + ".inputHierarchy", source=True) or []
    comprobar(len(conectados) == 18, "18 prototipos conectados al instanciador ({})".format(len(conectados)))
    inicio = time.time()
    n = contar(instancias)
    print("  ({} matas en {:.2f} s)".format(n, time.time() - inicio))
    comprobar(abs(n - 10000) < 300, "100 m² de césped dan unas 10.000 matas ({})".format(n))
    atributos = [a for a in ("rotationAngleUnits", "rotationOrder", "levelOfDetail")
                 if cmds.attributeQuery(a, node=instancias, exists=True)]
    print("  (atributos del instanciador: {})".format(", ".join(atributos)))

    # La matriz de la primera mata debe coincidir con lo que calcula Pradera
    motor = cp.Motor()
    s = escena.leer_suelo(escena.forma_suelo(capa), cmds.getAttr(plano + ".worldMatrix[0]"))
    motor.preparar(s, escena.ajustes(capa), escena.catalogo())
    salida = motor.salida(None, True)
    m = matriz_instancia(instancias, 0)
    pos = tuple(m[12:15])
    esperado = salida.posiciones[0]
    comprobar(all(abs(a - b) < 0.01 for a, b in zip(pos, esperado)), "posición de la primera mata {} = {}"
              .format(tuple(round(v, 2) for v in pos), tuple(round(v, 2) for v in esperado)))
    import maya.api.OpenMaya as om
    giro = om.MTransformationMatrix(om.MMatrix(m)).rotation()
    esperado_y = salida.giros[0][1]
    giro_y = math.degrees(giro.y) % 360
    comprobar(abs(((giro_y - esperado_y + 180) % 360) - 180) < 5 or abs(salida.giros[0][0]) > 8,
              "el giro va en grados ({:.1f} = {:.1f})".format(giro_y, esperado_y))

    # Visor ligero
    cmds.setAttr(capa + ".modo", 1)
    n_visor = contar(instancias)
    comprobar(0.07 * n < n_visor < 0.13 * n, "el visor enseña un 10 % ({})".format(n_visor))
    cmds.setAttr(capa + ".modo", 0)
    comprobar(contar(instancias) == n, "sin interfaz se ve la hierba de render")

    # Ganchos de render
    pre = cmds.getAttr("defaultRenderGlobals.preMel") or ""
    comprobar("praderaRender -antes" in pre, "MEL de antes del render instalado")
    cmds.setAttr(capa + ".modo", 1)
    mel.eval(pre)
    comprobar(escena.en_render(), "praderaRender -antes pone la hierba en calidad de render")
    comprobar(contar(instancias) == n, "durante el render salen todas las matas")
    mel.eval(cmds.getAttr("defaultRenderGlobals.postMel"))
    comprobar(not escena.en_render(), "praderaRender -despues vuelve al visor")
    cmds.setAttr(capa + ".modo", 0)

    # Deshacer de los ajustes
    aj = escena.ajustes(capa)
    aj.densidad = 50.0
    cmds.undoInfo(state=True, infinity=True)
    escena.guardar_ajustes(capa, aj)
    n50 = contar(instancias)
    comprobar(abs(n50 - n / 2.0) < 300, "densidad al 50 % ({})".format(n50))
    cmds.undo()
    comprobar(contar(instancias) == n, "Ctrl+Z devuelve la densidad")

    # --- fase 2: zonas ------------------------------------------------------------------
    pincel.pintar_en(capa, [(x, 0, z) for x in range(-500, 1, 100) for z in range(-500, 501, 100)], 120, "quitar")
    n_pintado = contar(instancias)
    comprobar(0.3 * n < n_pintado < 0.7 * n, "el pincel quita la mitad ({})".format(n_pintado))
    pincel.llenar(capa, 255)
    comprobar(contar(instancias) == n, "Todo el suelo devuelve toda la hierba")
    pincel.llenar(capa, 0)
    comprobar(contar(instancias) == 0, "Vaciar deja la capa sin hierba")
    pincel.llenar(capa, 255)
    curva = cmds.circle(normal=(0, 1, 0), radius=200, name="parterre_prueba")[0]
    datos = escena.puntos_de_curva(curva)
    comprobar(datos and datos["cerrada"] and len(datos["puntos"]) > 8, "una circunferencia es una curva cerrada")
    aj = escena.ajustes(capa)
    aj.reglas["curvas"] = [dict(datos, modo="dentro")]
    escena.guardar_ajustes(capa, aj)
    n_dentro = contar(instancias)
    previsto = math.pi * 2.0 ** 2 * 100
    comprobar(abs(n_dentro - previsto) < previsto * 0.15, "parterre de 2 m de radio ({} ~ {:.0f})"
              .format(n_dentro, previsto))
    aj.reglas["curvas"] = []
    escena.guardar_ajustes(capa, aj)

    # Caras seleccionadas
    cmds.select(plano + ".f[0:9]")
    suelo_sel, caras = escena.suelo_de_seleccion()
    comprobar(caras == list(range(10)), "caras de la selección")
    capa_caras = escena.crear_capa(suelo_sel, caras, nombre="caras", mezcla=[["cesped", 100]],
                                   opciones=sin_optimizar)
    n_caras = contar(escena.instanciador(capa_caras))
    comprobar(abs(n_caras - 1000) < 120, "10 caras de 1 m² dan unas 1.000 matas ({})".format(n_caras))
    escena.borrar_capa(capa_caras)
    comprobar(not cmds.objExists(capa_caras), "borrar capa")

    # Tipo editado: cambian los prototipos de todas las capas
    cesped = escena.catalogo()["cesped"].copiar(briznas=4)
    escena.guardar_tipo(cesped)
    t_nuevo = cmds.polyEvaluate(escena.prototipos("cesped")[0], triangle=True)
    comprobar(t_nuevo < 40, "editar el tipo rehace sus matas ({} triángulos)".format(t_nuevo))
    escena.restaurar_tipo("cesped")

    # --- fase 3: rendimiento --------------------------------------------------------------
    camara = cmds.camera(name="cam_prueba", focalLength=35)[0]
    cmds.xform(camara, translation=(0, 170, 700), rotation=(-10, 0, 0))
    escena.conectar_camara(capa, camara)
    aj = escena.ajustes(capa)
    aj.opciones.update(recorte=True, margen=0.0, lod=True, cerca=300.0, medio=600.0, aclarar=True)
    escena.guardar_ajustes(capa, aj)
    n_cam = contar(instancias)
    comprobar(n_cam < 0.75 * n, "el recorte por cámara quita matas ({} de {})".format(n_cam, n))
    inf = escena.informe(capa)
    comprobar(inf.get("matas") == n_cam, "el informe cuenta lo mismo que el instanciador ({})".format(inf.get("matas")))
    comprobar(inf.get("memoria", 0) < inf.get("memoria_sin_instancias", 0), "las instancias ahorran memoria")
    total = escena.informe_escena()
    comprobar(total.matas == n_cam and total.unicos > 0, "informe de la escena")
    escena.hornear(capa)
    comprobar(escena.horneada(capa) and contar(instancias) == n_cam, "hornear no cambia la hierba")
    cmds.setAttr(capa + ".ajustes", cmds.getAttr(capa + ".ajustes").replace('"densidad": 100.0', '"densidad": 10.0'),
                 type="string")
    comprobar(contar(instancias) == n_cam, "horneada no se recalcula al cambiar ajustes")
    escena.deshornear(capa)
    comprobar(contar(instancias) < n_cam, "deshornear vuelve a calcular")
    cmds.setAttr(capa + ".ajustes", cmds.getAttr(capa + ".ajustes").replace('"densidad": 10.0', '"densidad": 100.0'),
                 type="string")

    # --- fase 4: acabado ------------------------------------------------------------------
    escena.fijar_material("clay")
    if arnold:
        comprobar("pradera_clay_ai" in (cmds.listConnections(escena.SG + ".aiSurfaceShader") or []), "material clay")
    escena.fijar_material("hierba")
    ruta_csv = os.path.join(tmp, "puntos.csv")
    filas = convertir.exportar_puntos(capa, ruta_csv)
    with open(ruta_csv, encoding="utf-8") as f:
        comprobar(len(f.readlines()) == filas + 1 and filas == n_cam, "exportar puntos CSV ({})".format(filas))
    aj = escena.ajustes(capa)
    aj.densidad = 2.0
    escena.guardar_ajustes(capa, aj)
    pocas = contar(instancias)
    malla = convertir.unir_en_malla(capa)
    comprobar(cmds.polyEvaluate(malla, triangle=True) == convertir.triangulos_render(capa),
              "unir en una malla ({} triángulos)".format(cmds.polyEvaluate(malla, triangle=True)))
    grupo = convertir.instancias_sueltas(capa)
    comprobar(len(cmds.listRelatives(grupo, children=True) or []) == pocas, "instancias sueltas ({})".format(pocas))

    # --- guardar y abrir -------------------------------------------------------------------
    cmds.file(new=True, force=True)
    capas = ejemplos.jardin_con_loma()
    cuentas = [contar(escena.instanciador(c)) for c in capas]
    comprobar(all(c > 0 for c in cuentas), "escena de ejemplo: tres capas con hierba {}".format(cuentas))
    archivo = os.path.join(tmp, "ejemplo.ma")
    cmds.file(rename=archivo)
    cmds.file(save=True, type="mayaAscii", force=True)
    print("  (escena de ejemplo: {} KB)".format(os.path.getsize(archivo) // 1024))
    cmds.file(new=True, force=True)
    cmds.file(archivo, open=True, force=True)
    otra_vez = [contar(escena.instanciador(c)) for c in capas]
    comprobar(otra_vez == cuentas, "al abrir la escena sale la misma hierba {}".format(otra_vez))
    for c in capas:
        print("  (capa {}: {})".format(c, {k: v for k, v in escena.informe(c).items()
                                          if k in ("matas", "triangulos", "descartadas", "visor")}))

    # --- prueba de carga ----------------------------------------------------------------------
    cmds.file(new=True, force=True)
    grande = cmds.polyPlane(width=5000, height=5000, subdivisionsX=100, subdivisionsY=100, name="campo")[0]
    inicio = time.time()
    capa = escena.crear_capa(grande, nombre="carga", mezcla=[["cesped", 100]], densidad=120.0,
                             opciones=sin_optimizar)
    n = contar(escena.instanciador(capa))
    segundos = time.time() - inicio
    print("  CARGA: {} matas en {:.1f} s".format(n, segundos))
    comprobar(n > 280000, "prueba de carga: unas 300.000 matas ({})".format(n))
    cmds.setAttr(capa + ".modo", 1)
    inicio = time.time()
    n_visor = contar(escena.instanciador(capa))
    print("  CARGA visor: {} matas en {:.2f} s".format(n_visor, time.time() - inicio))

    bien, _ = interfaz_maya.comprobar(mostrar=False)
    comprobar(bien or not arnold, "comprobar instalación")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        fallos.append("excepción")
    print("\nRESULTADO: " + ("OK" if not fallos else "FALLOS:\n  " + "\n  ".join(fallos)))
    sys.stdout.flush()
    os._exit(0 if not fallos else 1)
