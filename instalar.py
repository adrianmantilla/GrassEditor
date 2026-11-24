"""Instalador de GrassEditor.

Arrastra este archivo desde el explorador de archivos hasta el visor de Maya.
Crea el módulo «grasseditor.mod» en tu carpeta de Maya apuntando a esta carpeta,
carga el plugin y lo marca para que se cargue siempre. Para desinstalar, borra
ese archivo .mod (la ruta se muestra en el Script Editor al instalar).

No muevas la carpeta del plugin después de instalar; si lo haces, vuelve a
arrastrar este archivo.
"""

import os
import sys

PLUGIN = "grasseditor_plugin"


def _raiz():
    return os.path.dirname(os.path.abspath(__file__))


def contenido_mod(raiz, version):
    raiz = raiz.replace("\\", "/")
    return ("+ GrassEditor {version} {raiz}\n"
            "scripts: scripts\n"
            "plug-ins: plug-ins\n").format(version=version, raiz=raiz)


def ruta_para_mod(raiz, carpeta_modulos):
    """La ruta que se escribe en el .mod.

    Maya puede leer mal el .mod si la ruta lleva tildes o eñes (p. ej. un usuario
    «José» en Windows). En ese caso, si la ruta relativa a la carpeta del .mod no
    las lleva (lo normal: la carpeta del usuario es común a las dos), se usa esa.
    """
    if raiz.isascii():
        return raiz
    try:
        relativa = os.path.relpath(raiz, carpeta_modulos)
    except ValueError:  # otra unidad en Windows
        return raiz
    return relativa if relativa.isascii() else raiz


def _version(raiz):
    ruta = os.path.join(raiz, "scripts", "grasseditor", "__init__.py")
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            if linea.startswith("__version__"):
                return linea.split("=")[1].strip().strip("\"'")
    return "0.0.0"


def instalar():
    from maya import cmds

    raiz = _raiz()
    print("GrassEditor | instalando desde " + raiz)
    version = _version(raiz)
    carpeta_modulos = os.path.join(cmds.internalVar(userAppDir=True), "modules")
    os.makedirs(carpeta_modulos, exist_ok=True)
    ruta_mod = os.path.join(carpeta_modulos, "grasseditor.mod")
    with open(ruta_mod, "w", encoding="utf-8") as f:
        f.write(contenido_mod(ruta_para_mod(raiz, carpeta_modulos), version))
    print("GrassEditor | módulo escrito en " + ruta_mod)

    # Para esta sesión, sin reiniciar Maya. Se quitan del path otras copias
    # del plugin que se hubieran instalado antes en esta misma sesión.
    scripts = os.path.join(raiz, "scripts")
    sys.path[:] = [p for p in sys.path
                   if os.path.normpath(p) == os.path.normpath(scripts)
                   or not os.path.isfile(os.path.join(p, "grasseditor", "__init__.py"))]
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    for nombre in [m for m in sys.modules if m == "grasseditor" or m.startswith("grasseditor.")]:
        del sys.modules[nombre]

    ruta_plugin = os.path.join(raiz, "plug-ins", PLUGIN + ".py")
    if cmds.pluginInfo(PLUGIN, query=True, loaded=True):
        cmds.unloadPlugin(PLUGIN, force=True)
    cmds.loadPlugin(ruta_plugin)
    cmds.pluginInfo(PLUGIN, edit=True, autoload=True)

    from grasseditor import interfaz_maya
    from grasseditor.i18n import t
    interfaz_maya.crear_menu()
    cmds.confirmDialog(title=t("instalado_titulo"), message=t("instalado_texto", version=version),
                       button=[t("boton_aceptar")])


def onMayaDroppedPythonFile(*_):
    """Maya llama a esta función al soltar el archivo en el visor."""
    try:
        instalar()
    except Exception as error:
        from maya import cmds
        cmds.confirmDialog(title="GrassEditor", message="No se pudo instalar GrassEditor: {}".format(error),
                           button=["OK"])
        raise
    finally:
        # Maya guarda el archivo soltado como módulo «instalar»: si luego se
        # suelta el instalar.py de otra carpeta en la misma sesión, reutilizaría
        # este y apuntaría a la carpeta antigua. Se olvida al terminar.
        sys.modules.pop(__name__, None)
