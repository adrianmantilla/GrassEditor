"""Renders de comprobación con Arnold (herramienta de desarrollo).

    mayapy herramientas/render_pradera.py /ruta/de/salida

Deja en la carpeta:

* pradera_tipos.png: lámina con los ocho tipos (un parche de cada uno);
* pradera_niveles.png: un tipo en sus tres niveles de detalle, de cerca;
* pradera_ejemplo_optimizado.png y pradera_ejemplo_sin_optimizar.png: la
  escena de ejemplo con y sin recorte, detalle por distancia y aclarado,
  con el tiempo de cada render y las cifras de cada capa en informe.txt.
"""

import glob
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
ANCHO, ALTO = 1280, 720


def _iniciar():
    import maya.standalone
    maya.standalone.initialize(name="python")
    from maya import cmds
    if not cmds.pluginInfo("mtoa", query=True, loaded=True):
        cmds.loadPlugin("mtoa")
    cmds.loadPlugin(os.path.join(RAIZ, "plug-ins", "pradera_plugin.py"))
    return cmds


def _ajustes(cmds):
    import mtoa.core
    mtoa.core.createOptions()
    cmds.setAttr("defaultRenderGlobals.currentRenderer", "arnold", type="string")
    for atributo, valor in (("AASamples", 4), ("GIDiffuseSamples", 2), ("GITransmissionDepth", 4),
                            ("abortOnLicenseFail", 0)):
        if cmds.attributeQuery(atributo, node="defaultArnoldRenderOptions", exists=True):
            cmds.setAttr("defaultArnoldRenderOptions." + atributo, valor)
    cmds.setAttr("defaultArnoldDriver.ai_translator", "png", type="string")
    for ajuste in (dict(outputTransformEnabled=True), dict(outputUseViewTransform=True)):
        try:
            cmds.colorManagementPrefs(edit=True, **ajuste)
        except (RuntimeError, TypeError):
            pass
    cmds.setAttr("defaultResolution.width", ANCHO)
    cmds.setAttr("defaultResolution.height", ALTO)
    cmds.setAttr("defaultResolution.deviceAspectRatio", ANCHO / float(ALTO))


def _render(cmds, base, camara):
    cmds.setAttr("defaultRenderGlobals.imageFilePrefix", base, type="string")
    inicio = time.time()
    cmds.arnoldRender(width=ANCHO, height=ALTO, camera=camara, batch=True)
    segundos = time.time() - inicio
    raiz = cmds.workspace(query=True, rootDirectory=True) or ""
    hechas = glob.glob(base + "*.png") + [
        r for r in glob.glob(os.path.join(raiz, "images", "**", "*.png"), recursive=True)
        if os.path.getmtime(r) >= inicio]
    return segundos, (sorted(hechas, key=os.path.getmtime)[-1] if hechas else "SIN IMAGEN")


def _luces(cmds):
    cielo = cmds.shadingNode("aiSkyDomeLight", asLight=True, name="cielo")
    forma = cmds.listRelatives(cielo, shapes=True)[0]
    cmds.setAttr(forma + ".color", 0.75, 0.85, 1.0, type="double3")
    cmds.setAttr(forma + ".intensity", 0.8)
    sol = cmds.listRelatives(cmds.directionalLight(name="solShape", intensity=2.5), parent=True)[0]
    cmds.setAttr(sol + ".rotate", -40, 35, 0, type="double3")


def _camara(cmds, nombre, ojo, mira, fov=45):
    camara = cmds.camera(name=nombre)[0]
    camara = cmds.rename(camara, nombre)
    cmds.viewPlace(camara, eye=ojo, lookAt=mira, perspective=True)
    cmds.camera(camara, edit=True, horizontalFieldOfView=fov, farClipPlane=1e6)
    for otra in cmds.ls(type="camera"):
        cmds.setAttr(otra + ".renderable", 0)
    cmds.setAttr(cmds.listRelatives(camara, shapes=True)[0] + ".renderable", 1)
    return camara


def _suelo_clay(cmds, suelo):
    material = cmds.shadingNode("aiStandardSurface", asShader=True, name="tierra")
    cmds.setAttr(material + ".baseColor", 0.22, 0.17, 0.12, type="double3")
    cmds.setAttr(material + ".specular", 0.1)
    grupo = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="tierraSG")
    cmds.connectAttr(material + ".outColor", grupo + ".surfaceShader")
    cmds.sets(suelo, edit=True, forceElement=grupo)


def lamina_tipos(cmds, carpeta, informe):
    from pradera import escena, tipos
    cmds.file(new=True, force=True)
    _ajustes(cmds)
    _luces(cmds)
    camara = _camara(cmds, "cam_tipos", (0, 260, 620), (0, 20, 0), fov=60)
    for i, clave in enumerate(tipos.ORDEN):
        fila, columna = divmod(i, 4)
        suelo = cmds.polyPlane(width=110, height=110, subdivisionsX=4, subdivisionsY=4, name="parche_" + clave)[0]
        cmds.move((columna - 1.5) * 150, 0, (fila - 0.5) * 170, suelo)
        _suelo_clay(cmds, suelo)
        escena.crear_capa(suelo, nombre=clave, mezcla=[[clave, 100]], densidad=100.0,
                          opciones={"recorte": False, "lod": False, "aclarar": False})
    segundos, imagen = _render(cmds, os.path.join(carpeta, "pradera_tipos"), camara)
    informe.append("tipos: {:.1f} s {}".format(segundos, imagen))


def niveles(cmds, carpeta, informe):
    from pradera import escena
    cmds.file(new=True, force=True)
    _ajustes(cmds)
    _luces(cmds)
    camara = _camara(cmds, "cam_niveles", (0, 60, 260), (0, 25, 0), fov=40)
    for i in range(3):
        suelo = cmds.polyPlane(width=60, height=60, subdivisionsX=1, subdivisionsY=1, name="nivel{}".format(i))[0]
        cmds.move((i - 1) * 80, 0, 0, suelo)
        _suelo_clay(cmds, suelo)
        capa = escena.crear_capa(suelo, nombre="nivel{}".format(i), mezcla=[["silvestre", 100]], densidad=60.0,
                                 opciones={"recorte": False, "lod": True, "cerca": 1e6 if i == 0 else 0.01,
                                           "medio": 1e6 if i < 2 else 0.02, "aclarar": False})
        escena.conectar_camara(capa, camara)
    segundos, imagen = _render(cmds, os.path.join(carpeta, "pradera_niveles"), camara)
    informe.append("niveles: {:.1f} s {}".format(segundos, imagen))


def ejemplo(cmds, carpeta, informe):
    from pradera import ejemplos, escena
    from pradera import estadisticas as est
    cmds.file(new=True, force=True)
    _ajustes(cmds)
    capas = ejemplos.jardin_con_loma()
    _suelo_clay(cmds, "pradera_ejemplo_suelo")
    camara = "pradera_ejemplo_camara"
    for nombre, optimizar in (("optimizado", True), ("sin_optimizar", False)):
        for capa in capas:
            aj = escena.ajustes(capa)
            aj.opciones.update(recorte=optimizar, lod=optimizar, aclarar=optimizar)
            escena.guardar_ajustes(capa, aj)
        total = escena.informe_escena()
        segundos, imagen = _render(cmds, os.path.join(carpeta, "pradera_ejemplo_" + nombre), camara)
        informe.append("ejemplo {}: {:.1f} s, {} matas, {} triángulos, {} aprox. {}".format(
            nombre, segundos, est.miles(total.matas), est.corto(total.triangulos), est.bytes_legibles(total.memoria),
            imagen))
        for capa in capas:
            datos = escena.informe(capa)
            informe.append("   {}: {} matas, {} triángulos".format(capa, est.miles(datos.get("matas", 0)),
                                                                 est.corto(datos.get("triangulos", 0))))


def main(carpeta):
    cmds = _iniciar()
    os.makedirs(carpeta, exist_ok=True)
    informe = []
    for paso in (lamina_tipos, niveles, ejemplo):
        try:
            paso(cmds, carpeta, informe)
        except Exception as error:
            import traceback
            traceback.print_exc()
            informe.append("{}: ERROR {}".format(paso.__name__, error))
    texto = "\n".join(informe)
    with open(os.path.join(carpeta, "informe.txt"), "w", encoding="utf-8") as f:
        f.write(texto + "\n")
    print(texto)
    sys.stdout.flush()


if __name__ == "__main__":
    main(*sys.argv[1:])
    os._exit(0)
