"""
gui.py — interfaz gráfica de escritorio del pipeline (Tkinter, incluido en
Python, no requiere instalar nada extra). Es una envoltura visual sobre
los mismos módulos que ya usa main.py (vacante_parser, matcher, render) —
la lógica del pipeline no cambió, solo cómo le das los datos.

Uso:
    python src/gui.py
"""

import os
import queue
import sys
import threading
from pathlib import Path
from tkinter import Tk, StringVar, Text, END, DISABLED, NORMAL, WORD, BOTH, X, LEFT
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

import matcher
import render
import vacante_parser
from intake_common import generar_nombre_carpeta, guardar_vacante, carpeta_cv_full
from curador_keywords import (
    cargar_master,
    cargar_ignoradas,
    guardar_ignorada,
    recolectar_keywords_vistas,
    encontrar_sin_mapear,
    SUGERENCIAS_PATH,
)
from matcher import recolectar_tags_conocidos
from tkinter import Listbox, SINGLE, END as TK_END, Y as TK_Y, RIGHT as TK_RIGHT

RAIZ = Path(__file__).parent.parent
VACANTES_DIR = RAIZ / "vacantes"


class ColaEscritor:
    """Redirige print() hacia una cola thread-safe que la ventana lee periódicamente."""

    def __init__(self, cola: queue.Queue):
        self.cola = cola

    def write(self, texto):
        if texto.strip():
            self.cola.put(texto)

    def flush(self):
        pass


class App:
    def __init__(self, root):
        self.root = root
        root.title("CV Pipeline")
        root.geometry("760x720")

        self.cola_log = queue.Queue()
        self.vacantes_pendientes = []  # lista de (metadata, descripcion)
        self.botones_accion = []

        notebook = ttk.Notebook(root)
        notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self.tab_vacante = ttk.Frame(notebook)
        self.tab_full = ttk.Frame(notebook)
        self.tab_keywords = ttk.Frame(notebook)
        notebook.add(self.tab_vacante, text="Vacante(s)")
        notebook.add(self.tab_full, text="CV Full")
        notebook.add(self.tab_keywords, text="Keywords")

        self._armar_tab_vacante()
        self._armar_tab_full()
        self._armar_tab_keywords()

        ttk.Button(root, text="Abrir carpeta de vacantes", command=self._abrir_carpeta_vacantes).pack(
            anchor="w", padx=10, pady=(0, 5)
        )

        ttk.Label(root, text="Registro:").pack(anchor="w", padx=10)
        self.log = ScrolledText(root, height=10, wrap=WORD, state=DISABLED)
        self.log.pack(fill=BOTH, expand=False, padx=10, pady=(0, 10))

        self.root.after(100, self._drenar_log)

    def _abrir_carpeta_vacantes(self):
        VACANTES_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(VACANTES_DIR)
        except AttributeError:
            # os.startfile solo existe en Windows; en otros sistemas se avisa en vez de tronar
            messagebox.showinfo(
                "No disponible",
                f"Tu sistema no soporta abrir carpetas automáticamente.\nRuta: {VACANTES_DIR}",
            )

    # ---------- Tab 1: Vacante(s) ----------
    def _armar_tab_vacante(self):
        frame = self.tab_vacante

        self.var_titulo = StringVar()
        self.var_empresa = StringVar()
        self.var_ubicacion = StringVar()
        self.var_modalidad = StringVar()
        self.var_url = StringVar()
        self.var_idioma = StringVar(value="es")

        self._campo(frame, "Título del puesto:", self.var_titulo)
        self._campo(frame, "Empresa:", self.var_empresa)
        self._campo(frame, "Ubicación:", self.var_ubicacion)
        self._campo(frame, "Modalidad (remoto/híbrido/presencial):", self.var_modalidad)
        self._campo(frame, "URL de la vacante (opcional):", self.var_url)

        ttk.Label(frame, text="Descripción completa de la vacante (pégala aquí):").pack(
            anchor="w", padx=10, pady=(10, 0)
        )
        self.txt_descripcion = ScrolledText(frame, height=8, wrap=WORD)
        self.txt_descripcion.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        botones = ttk.Frame(frame)
        botones.pack(fill=X, padx=10, pady=(0, 5))
        ttk.Button(botones, text="+ Agregar a la lista", command=self._agregar_vacante).pack(side=LEFT)
        ttk.Button(botones, text="Vaciar lista", command=self._vaciar_lista).pack(side=LEFT, padx=(8, 0))

        ttk.Label(frame, text="Vacantes en cola:").pack(anchor="w", padx=10)
        self.lista_pendientes = Text(frame, height=4, state=DISABLED)
        self.lista_pendientes.pack(fill=X, padx=10, pady=(0, 10))

        idioma_frame = ttk.Frame(frame)
        idioma_frame.pack(fill=X, padx=10, pady=(0, 5))
        ttk.Label(idioma_frame, text="Idioma del CV:").pack(side=LEFT)
        ttk.Radiobutton(idioma_frame, text="Español", variable=self.var_idioma, value="es").pack(side=LEFT, padx=5)
        ttk.Radiobutton(idioma_frame, text="Inglés", variable=self.var_idioma, value="en").pack(side=LEFT, padx=5)
        ttk.Radiobutton(idioma_frame, text="Ambos", variable=self.var_idioma, value="both").pack(side=LEFT, padx=5)

        btn = ttk.Button(frame, text="Generar CV(s) de la lista", command=self._generar_vacantes)
        btn.pack(padx=10, pady=(5, 10), anchor="e")
        self.botones_accion.append(btn)

    def _campo(self, frame, etiqueta, var):
        f = ttk.Frame(frame)
        f.pack(fill=X, padx=10, pady=3)
        ttk.Label(f, text=etiqueta, width=32).pack(side=LEFT)
        ttk.Entry(f, textvariable=var).pack(side=LEFT, fill=X, expand=True)

    def _agregar_vacante(self):
        titulo = self.var_titulo.get().strip()
        empresa = self.var_empresa.get().strip()
        if not titulo or not empresa:
            messagebox.showwarning("Faltan datos", "Título y Empresa son obligatorios.")
            return
        descripcion = self.txt_descripcion.get("1.0", END).strip()
        if not descripcion:
            messagebox.showwarning("Faltan datos", "Pega la descripción de la vacante.")
            return

        metadata = {
            "titulo": titulo,
            "empresa": empresa,
            "ubicacion": self.var_ubicacion.get().strip(),
            "modalidad": self.var_modalidad.get().strip(),
            "url": self.var_url.get().strip(),
        }
        self.vacantes_pendientes.append((metadata, descripcion))
        self._refrescar_lista_pendientes()

        for var in (self.var_titulo, self.var_empresa, self.var_ubicacion, self.var_modalidad, self.var_url):
            var.set("")
        self.txt_descripcion.delete("1.0", END)

    def _vaciar_lista(self):
        self.vacantes_pendientes.clear()
        self._refrescar_lista_pendientes()

    def _refrescar_lista_pendientes(self):
        self.lista_pendientes.config(state=NORMAL)
        self.lista_pendientes.delete("1.0", END)
        for metadata, _ in self.vacantes_pendientes:
            self.lista_pendientes.insert(END, f"- {metadata['empresa']} · {metadata['titulo']}\n")
        self.lista_pendientes.config(state=DISABLED)

    def _generar_vacantes(self):
        if not self.vacantes_pendientes:
            messagebox.showwarning("Lista vacía", "Agrega al menos una vacante antes de generar.")
            return
        lang = self.var_idioma.get()
        vacantes = list(self.vacantes_pendientes)
        self.vacantes_pendientes.clear()
        self._refrescar_lista_pendientes()
        self._ejecutar_en_hilo(self._procesar_vacantes, vacantes, lang)

    def _procesar_vacantes(self, vacantes, lang):
        for i, (metadata, descripcion) in enumerate(vacantes, start=1):
            print(f"=== Procesando {i}/{len(vacantes)}: {metadata['empresa']} — {metadata['titulo']} ===")
            nombre_carpeta = generar_nombre_carpeta(metadata["empresa"], metadata["titulo"])
            carpeta = guardar_vacante(VACANTES_DIR / nombre_carpeta, metadata, descripcion)
            vacante_parser.main(str(carpeta), "python")
            matcher.main(str(carpeta), 3, 2)
            render.main(str(carpeta), lang)
            print(f"Listo: {carpeta}\n")
        print("=== Todos los CVs fueron generados ===")

    # ---------- Tab 2: CV Full ----------
    def _armar_tab_full(self):
        frame = self.tab_full
        self.var_nombre_full = StringVar(value="cv_full")
        self.var_idioma_full = StringVar(value="es")

        self._campo(frame, "Nombre de la carpeta:", self.var_nombre_full)

        idioma_frame = ttk.Frame(frame)
        idioma_frame.pack(fill=X, padx=10, pady=10)
        ttk.Label(idioma_frame, text="Idioma del CV:").pack(side=LEFT)
        ttk.Radiobutton(idioma_frame, text="Español", variable=self.var_idioma_full, value="es").pack(side=LEFT, padx=5)
        ttk.Radiobutton(idioma_frame, text="Inglés", variable=self.var_idioma_full, value="en").pack(side=LEFT, padx=5)
        ttk.Radiobutton(idioma_frame, text="Ambos", variable=self.var_idioma_full, value="both").pack(side=LEFT, padx=5)

        btn = ttk.Button(frame, text="Generar CV completo", command=self._generar_full)
        btn.pack(padx=10, pady=10, anchor="e")
        self.botones_accion.append(btn)

    def _generar_full(self):
        nombre = self.var_nombre_full.get().strip() or "cv_full"
        try:
            carpeta_cv_full(VACANTES_DIR, nombre)
        except ValueError as error:
            messagebox.showwarning("Nombre inválido", str(error))
            return
        lang = self.var_idioma_full.get()
        self._ejecutar_en_hilo(self._procesar_full, nombre, lang)

    def _procesar_full(self, nombre, lang):
        carpeta = carpeta_cv_full(VACANTES_DIR, nombre)
        print(f"=== Generando CV completo en {carpeta} ===")
        matcher.main(str(carpeta), 0, 0, full=True)
        render.main(str(carpeta), lang)
        print("=== Listo ===")

    # ---------- Tab 3: Keywords (curador de keyword_tag_map) ----------
    def _armar_tab_keywords(self):
        frame = self.tab_keywords

        info = (
            "¿Qué es esto? keyword_tag_map traduce las frases que usan las vacantes "
            "(ej. \"Power BI\") a los tags cortos que tú usas en tus bullets (ej. \"dashboards\"). "
            "Sin ese puente, el matcher no sabría qué logros mostrarte para esa vacante.\n\n"
            "Si una keyword ya tiene un tag con el MISMO nombre (ej. \"Kanban\" -> tag \"kanban\"), "
            "se resuelve sola y no aparece aquí. Esta pestaña solo te pregunta por las que "
            "de verdad necesitan tu decisión.\n\n"
            "Cómo usarla: 1) Buscar pendientes. 2) Elige una keyword de la lista. "
            "3) Escribe para filtrar tus tags y elige el que le corresponda (o Ignorar). "
            "4) Al final, copia el bloque generado dentro de keyword_tag_map en tu perfil.yaml."
        )
        lbl_info = ttk.Label(frame, text=info, wraplength=680, justify=LEFT)
        lbl_info.pack(anchor="w", padx=10, pady=10)

        ttk.Button(frame, text="Buscar keywords sin mapear", command=self._buscar_pendientes).pack(
            anchor="w", padx=10, pady=(0, 10)
        )

        cuerpo = ttk.Frame(frame)
        cuerpo.pack(fill=BOTH, expand=True, padx=10)

        # Columna izquierda: keywords pendientes
        col_izq = ttk.Frame(cuerpo)
        col_izq.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))
        ttk.Label(col_izq, text="Keywords sin mapear:").pack(anchor="w")
        self.lista_pendientes_kw = Listbox(col_izq, height=12, selectmode=SINGLE, exportselection=False)
        self.lista_pendientes_kw.pack(fill=BOTH, expand=True)
        ttk.Button(col_izq, text="Ignorar seleccionada", command=self._ignorar_kw_seleccionada).pack(
            anchor="w", pady=(5, 0)
        )

        # Columna derecha: buscador de tags
        col_der = ttk.Frame(cuerpo)
        col_der.pack(side=LEFT, fill=BOTH, expand=True)
        ttk.Label(col_der, text="Buscar tag (escribe para filtrar):").pack(anchor="w")
        self.var_busqueda_tag = StringVar()
        entry_busqueda = ttk.Entry(col_der, textvariable=self.var_busqueda_tag)
        entry_busqueda.pack(fill=X)
        entry_busqueda.bind("<KeyRelease>", self._filtrar_tags)
        self.lista_tags_filtrados = Listbox(col_der, height=11, selectmode=SINGLE, exportselection=False)
        self.lista_tags_filtrados.pack(fill=BOTH, expand=True, pady=(5, 0))
        ttk.Button(col_der, text="Asignar tag a la keyword seleccionada", command=self._asignar_tag).pack(
            anchor="w", pady=(5, 0)
        )

        ttk.Button(frame, text="Generar bloque YAML para copiar", command=self._generar_bloque_yaml).pack(
            anchor="e", padx=10, pady=10
        )

        self._tags_conocidos_cache = []
        self._mapeos_nuevos = {}

    def _buscar_pendientes(self):
        master = cargar_master()
        ignoradas = cargar_ignoradas()
        keywords_vistas = recolectar_keywords_vistas()
        sin_mapear = encontrar_sin_mapear(keywords_vistas, master, ignoradas)

        self._tags_conocidos_cache = sorted(recolectar_tags_conocidos(master))
        self._mapeos_nuevos = {}

        self.lista_pendientes_kw.delete(0, TK_END)
        for kw in sin_mapear:
            self.lista_pendientes_kw.insert(TK_END, kw)

        self.lista_tags_filtrados.delete(0, TK_END)
        for tag in self._tags_conocidos_cache:
            self.lista_tags_filtrados.insert(TK_END, tag)

        if not sin_mapear:
            messagebox.showinfo("Sin pendientes", "No hay keywords sin mapear por ahora.")

    def _filtrar_tags(self, event=None):
        texto = self.var_busqueda_tag.get().strip().lower()
        self.lista_tags_filtrados.delete(0, TK_END)
        for tag in self._tags_conocidos_cache:
            if texto in tag.lower():
                self.lista_tags_filtrados.insert(TK_END, tag)

    def _ignorar_kw_seleccionada(self):
        seleccion = self.lista_pendientes_kw.curselection()
        if not seleccion:
            messagebox.showwarning("Nada seleccionado", "Selecciona una keyword de la lista primero.")
            return
        kw = self.lista_pendientes_kw.get(seleccion[0])
        guardar_ignorada(kw)
        self.lista_pendientes_kw.delete(seleccion[0])

    def _asignar_tag(self):
        sel_kw = self.lista_pendientes_kw.curselection()
        sel_tag = self.lista_tags_filtrados.curselection()
        if not sel_kw or not sel_tag:
            messagebox.showwarning("Falta selección", "Selecciona una keyword Y un tag antes de asignar.")
            return
        kw = self.lista_pendientes_kw.get(sel_kw[0])
        tag = self.lista_tags_filtrados.get(sel_tag[0])
        self._mapeos_nuevos[kw] = tag
        self.lista_pendientes_kw.delete(sel_kw[0])

    def _generar_bloque_yaml(self):
        if not self._mapeos_nuevos:
            messagebox.showinfo("Nada que generar", "Todavía no has asignado ningún tag nuevo.")
            return
        lineas = [f'  "{kw}": [{tag}]' for kw, tag in self._mapeos_nuevos.items()]
        bloque = "\n".join(lineas)
        SUGERENCIAS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SUGERENCIAS_PATH.write_text(bloque + "\n", encoding="utf-8")

        from tkinter import Toplevel

        popup = Toplevel(self.root)
        popup.title("Bloque para pegar en keyword_tag_map")
        txt = ScrolledText(popup, width=70, height=15, wrap=WORD)
        txt.pack(padx=10, pady=10, fill=BOTH, expand=True)
        txt.insert("1.0", bloque)
        ttk.Label(popup, text=f"También se guardó en: {SUGERENCIAS_PATH}").pack(padx=10, pady=(0, 10))

    # ---------- Utilidades de hilo/log ----------
    def _ejecutar_en_hilo(self, funcion, *args):
        # Corre el trabajo pesado (parser/matcher/render, que tardan unos segundos
        # por el navegador de Playwright) en un hilo aparte, para que la ventana
        # no se quede "congelada" mientras procesa.
        for b in self.botones_accion:
            b.config(state=DISABLED)

        def wrapper():
            stdout_original = sys.stdout
            sys.stdout = ColaEscritor(self.cola_log)
            try:
                funcion(*args)
            except Exception as e:
                print(f"[ERROR] {e}")
            finally:
                sys.stdout = stdout_original
                self.cola_log.put("__DONE__")

        threading.Thread(target=wrapper, daemon=True).start()

    def _drenar_log(self):
        try:
            while True:
                linea = self.cola_log.get_nowait()
                if linea == "__DONE__":
                    for b in self.botones_accion:
                        b.config(state=NORMAL)
                    continue
                self.log.config(state=NORMAL)
                self.log.insert(END, linea)
                self.log.see(END)
                self.log.config(state=DISABLED)
        except queue.Empty:
            pass
        self.root.after(100, self._drenar_log)


def main():
    root = Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
