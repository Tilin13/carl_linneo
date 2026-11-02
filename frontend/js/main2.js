
document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    // =====================================================
    // ELEMENTOS GENERALES
    // =====================================================

    const $ = (id) => document.getElementById(id);

    const menubtn = $("menubtn");
    const menu_bar = $("menu_bar");
    const atras_menu = $("atras_menu");

    const carritobtn = $("carritobtn");
    const carrito_bar = $("carrito_bar");

    const buscar_btn = $("buscarbtn");
    const busqueda_div = $("busqueda_div");

    const filtrosbtn = $("filtrosbtn");
    const filtro_menu = $("filtro_menu");

    const cantidad_productos = $("cantidad_productos");

    // Carrusel
    const atras_novedades = $("atras_novedades");
    const adelante_novedades = $("adelante_novedades");
    const imagenNovedades = $("imagen");
    const contadorNovedades = $("contador");

    // Administración
    const inventario = $("inventario_section");
    const clientes = $("clientes_section");
    const formulario = $("modificar_inv");
    const formularioStock = $("form_stock");
    const mensajeAdmin = $("mensaje_admin");
    const cancelarEdicion = $("cancelar_edicion");

    // Carrito
    const listaCarrito = $("lista_carrito");
    const subtotalLabel = $("subtotal_carrito");
    const cerrarCarrito = $("cerrar_carrito");

    // Favoritos
    const favoritosBtn = $("favoritos_btn");
    const favoritosBar = $("favoritos_bar");
    const contenidoFavoritos = $("contenido_favoritos");
    const cerrarFavoritos = $("cerrar_favoritos");

    // Chatbot
    const barraMensajes = $("bar_mensajes");
    const historialMensajes = $("historial_mensajes");
    const enviarMensajeBtn = $("enviar_mensaje_btn");

    // Token CSRF
    const csrfMeta = document.querySelector(
        'meta[name="csrf-token"]'
    );

    const csrfToken = csrfMeta
        ? csrfMeta.content
        : "";

    // =====================================================
    // PETICIONES HTTP
    // =====================================================

    async function peticion(url, opciones = {}) {
        const metodo = (opciones.method || "GET").toUpperCase();

        const cabeceras = {
            Accept: "application/json",
            ...opciones.headers
        };

        if (opciones.body !== undefined && opciones.body !== null) {
            cabeceras["Content-Type"] = "application/json";
        }

        if (!["GET", "HEAD", "OPTIONS"].includes(metodo)) {
            if (!csrfToken) {
                throw new Error(
                    "Falta el token CSRF. Comprueba la configuración del servidor."
                );
            }

            cabeceras["X-CSRFToken"] = csrfToken;
        }

        const respuesta = await fetch(url, {
            ...opciones,
            method: metodo,
            headers: cabeceras,
            credentials: "same-origin"
        });

        if (respuesta.status === 204 || metodo === "HEAD") {
            if (!respuesta.ok) {
                throw new Error(`Error HTTP ${respuesta.status}`);
            }

            return {};
        }

        const contenido = await respuesta.text();

        let datos = {};

        if (contenido) {
            try {
                datos = JSON.parse(contenido);
            } catch {
                throw new Error(
                    "El servidor devolvió una respuesta que no es JSON válido."
                );
            }
        }

        if (!respuesta.ok) {
            throw new Error(
                datos.error ||
                datos.mensaje ||
                `Error HTTP ${respuesta.status}`
            );
        }

        return datos;
    }

    // =====================================================
    // UTILIDADES GENERALES
    // =====================================================

    function mostrarMensaje(texto, error = false) {
        if (mensajeAdmin) {
            mensajeAdmin.textContent = texto;
            mensajeAdmin.style.color = error ? "red" : "inherit";
        }

        if (error) {
            console.error(texto);
        }
    }

    function normalizarTexto(texto) {
        return String(texto ?? "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .trim()
            .toLocaleLowerCase("es");
    }

    function obtenerValor(id) {
        const elemento = $(id);
        return elemento ? elemento.value : "";
    }

    function establecerValor(id, valor) {
        const elemento = $(id);

        if (elemento) {
            elemento.value = valor ?? "";
        }
    }

    function crearBoton(texto, accion, clase = "") {
        const elemento = document.createElement("button");

        elemento.type = "button";
        elemento.textContent = texto;

        if (clase) {
            elemento.className = clase;
        }

        elemento.addEventListener("click", accion);

        return elemento;
    }

    function crearTabla(columnas, filas) {
        const tabla = document.createElement("table");
        const cabecera = tabla.createTHead().insertRow();

        columnas.forEach(function (columna) {
            const th = document.createElement("th");
            th.textContent = columna;
            cabecera.appendChild(th);
        });

        const cuerpo = tabla.createTBody();

        filas.forEach(function (valores) {
            const fila = cuerpo.insertRow();

            valores.forEach(function (valor) {
                const celda = fila.insertCell();
                celda.textContent = valor ?? "";
            });
        });

        return tabla;
    }

    // =====================================================
    // ADMINISTRACIÓN: INVENTARIO
    // =====================================================

    async function cargarInventario() {
        if (!inventario) return;

        try {
            const productos = await peticion(
                "/api/admin/productos"
            );

            if (!Array.isArray(productos)) {
                throw new Error(
                    "Formato de inventario incorrecto."
                );
            }

            inventario.replaceChildren();

            const tabla = crearTabla(
                [
                    "Código",
                    "Nombre",
                    "Categoría",
                    "Compra",
                    "Producción",
                    "Venta",
                    "Stock",
                    "Acciones"
                ],
                []
            );

            const cuerpo = tabla.tBodies[0];

            productos.forEach(function (producto) {
                const fila = cuerpo.insertRow();

                const valores = [
                    producto.codigo,
                    producto.nombre,
                    producto.categoria,
                    producto.precio_compra,
                    producto.precio_manofactura,
                    producto.precio_venta,
                    producto.stock
                ];

                valores.forEach(function (valor) {
                    const celda = fila.insertCell();
                    celda.textContent = valor ?? "";
                });

                const acciones = fila.insertCell();

                acciones.appendChild(
                    crearBoton("Editar", function () {
                        editarProducto(producto);
                    })
                );

                acciones.appendChild(
                    crearBoton("Eliminar", function () {
                        eliminarProducto(producto.codigo);
                    })
                );
            });

            inventario.appendChild(tabla);

        } catch (error) {
            mostrarMensaje(error.message, true);
        }
    }

    function editarProducto(producto) {
        if (!formulario) return;

        establecerValor("codigo_original", producto.codigo);
        establecerValor("codigo", producto.codigo);
        establecerValor("nombre", producto.nombre);
        establecerValor("categoria", producto.categoria);

        establecerValor("precio_compra", producto.precio_compra);
        establecerValor("precio_manofactura", producto.precio_manofactura);
        establecerValor("precio_venta", producto.precio_venta);
        establecerValor("stock", producto.stock);

        const titulo = $("titulo_formulario");

        if (titulo) {
            titulo.textContent = "Editar producto";
        }

        formulario.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }

    function reiniciarFormulario() {
        if (!formulario) return;

        formulario.reset();
        establecerValor("codigo_original", "");

        const titulo = $("titulo_formulario");

        if (titulo) {
            titulo.textContent = "Añadir producto";
        }
    }

    if (formulario) {
        formulario.addEventListener("submit", async function (evento) {
            evento.preventDefault();

            const datos = {
                codigo_original: obtenerValor("codigo_original").trim(),
                codigo: obtenerValor("codigo").trim(),
                nombre: obtenerValor("nombre").trim(),
                categoria: obtenerValor("categoria").trim(),
                precio_compra: obtenerValor("precio_compra"),
                precio_manofactura: obtenerValor("precio_manofactura"),
                precio_venta: obtenerValor("precio_venta"),
                stock: obtenerValor("stock")
            };

            if (!datos.codigo || !datos.nombre || !datos.categoria) {
                mostrarMensaje(
                    "Completa el código, nombre y categoría.",
                    true
                );
                return;
            }

            try {
                const resultado = await peticion(
                    "/api/admin/productos",
                    {
                        method: "POST",
                        body: JSON.stringify(datos)
                    }
                );

                mostrarMensaje(
                    resultado.mensaje || "Producto guardado correctamente."
                );

                reiniciarFormulario();
                await cargarInventario();

            } catch (error) {
                mostrarMensaje(error.message, true);
            }
        });
    }

    if (cancelarEdicion) {
        cancelarEdicion.addEventListener(
            "click",
            reiniciarFormulario
        );
    }

    async function eliminarProducto(codigo) {
        if (!codigo) {
            mostrarMensaje("Código de producto no válido.", true);
            return;
        }

        if (!window.confirm(`¿Eliminar el producto ${codigo}?`)) {
            return;
        }

        try {
            const resultado = await peticion(
                `/api/admin/productos/${encodeURIComponent(codigo)}`,
                { method: "DELETE" }
            );

            mostrarMensaje(
                resultado.mensaje || "Producto eliminado correctamente."
            );

            await cargarInventario();

        } catch (error) {
            mostrarMensaje(error.message, true);
        }
    }

    // =====================================================
    // ADMINISTRACIÓN: STOCK
    // =====================================================

    if (formularioStock) {
        formularioStock.addEventListener("submit", async function (evento) {
            evento.preventDefault();

            const codigo = obtenerValor("producto_codigo").trim();
            const cantidad = Number(
                obtenerValor("cantidad_producto")
            );

            if (!codigo) {
                mostrarMensaje("Selecciona un producto.", true);
                return;
            }

            if (!Number.isSafeInteger(cantidad) || cantidad <= 0) {
                mostrarMensaje(
                    "Introduce una cantidad entera positiva.",
                    true
                );
                return;
            }

            try {
                const resultado = await peticion(
                    "/api/admin/stock",
                    {
                        method: "POST",
                        body: JSON.stringify({
                            codigo,
                            cantidad
                        })
                    }
                );

                mostrarMensaje(
                    resultado.mensaje || "Stock actualizado correctamente."
                );

                formularioStock.reset();
                await cargarInventario();

            } catch (error) {
                mostrarMensaje(error.message, true);
            }
        });
    }

    // =====================================================
    // ADMINISTRACIÓN: USUARIOS
    // =====================================================

    async function cargarUsuarios() {
        if (!clientes) return;

        try {
            const usuarios = await peticion(
                "/api/admin/usuarios"
            );

            if (!Array.isArray(usuarios)) {
                throw new Error(
                    "Formato de usuarios incorrecto."
                );
            }

            clientes.replaceChildren();

            const tabla = crearTabla(
                ["ID", "Usuario", "Correo", "Teléfono", "Rol"],
                usuarios.map(function (usuario) {
                    return [
                        usuario.id,
                        usuario.username,
                        usuario.email,
                        usuario.phone,
                        usuario.rol
                    ];
                })
            );

            clientes.appendChild(tabla);

        } catch (error) {
            mostrarMensaje(error.message, true);
        }
    }

    if (inventario) {
        cargarInventario();
    }

    if (clientes) {
        cargarUsuarios();
    }

    // =====================================================
    // CARRUSEL DE NOVEDADES
    // =====================================================

    const imagenes = [
        "novedades/1.jpg",
        "novedades/2.jpg",
        "novedades/3.jpg"
    ];

    let indiceImagen = 0;

    function mostrarImagen() {
        if (!imagenNovedades) return;

        imagenNovedades.src = imagenes[indiceImagen];
        imagenNovedades.alt = `Novedad ${indiceImagen + 1}`;

        if (contadorNovedades) {
            contadorNovedades.textContent =
                `Imagen ${indiceImagen + 1} de ${imagenes.length}`;
        }
    }

    function siguienteImagen() {
        indiceImagen = (indiceImagen + 1) % imagenes.length;
        mostrarImagen();
    }

    function anteriorImagen() {
        indiceImagen =
            (indiceImagen - 1 + imagenes.length) % imagenes.length;

        mostrarImagen();
    }

    if (adelante_novedades) {
        adelante_novedades.addEventListener(
            "click",
            siguienteImagen
        );
    }

    if (atras_novedades) {
        atras_novedades.addEventListener(
            "click",
            anteriorImagen
        );
    }

    if (imagenes.length) {
        mostrarImagen();
    }

    // =====================================================
    // NAVEGACIÓN
    // =====================================================

    const navegacion = [
        ["chat_btn", "/chatbox"],
        ["iniciar_secion_btn", "/iniciar_sesion"],
        ["registrarse_btn", "/registrarse"],
        ["catalogo_completo_btn", "/catalogo"]
    ];

    navegacion.forEach(function ([id, ruta]) {
        const elemento = $(id);

        if (elemento) {
            elemento.addEventListener("click", function () {
                window.location.href = ruta;
            });
        }
    });

    // =====================================================
    // MENÚ PRINCIPAL
    // =====================================================

    function alternarPanel(boton, panel) {
        if (!boton || !panel) return;

        const visible = panel.classList.toggle("visible");

        boton.setAttribute(
            "aria-expanded",
            String(visible)
        );
    }

    if (menubtn && menu_bar) {
        menubtn.addEventListener("click", function () {
            alternarPanel(menubtn, menu_bar);
        });
    }

    if (atras_menu && menu_bar) {
        atras_menu.addEventListener("click", function () {
            menu_bar.classList.remove("visible");

            if (menubtn) {
                menubtn.setAttribute("aria-expanded", "false");
            }
        });
    }

    // =====================================================
    // POPUP DE DESCUENTO
    // =====================================================

    const popup = $("popup") || document.querySelector(".popup");
    const cerrarPopupBtn = $("quitar_popup");

    if (popup) {
        popup.hidden = false;

        window.setTimeout(function () {
            popup.classList.add("visible");
        }, 700);
    }

    if (popup && cerrarPopupBtn) {
        cerrarPopupBtn.addEventListener("click", function () {
            popup.classList.remove("visible");
        });
    }

    // =====================================================
    // CHATBOT LINNEO
    // =====================================================

    function agregarMensajeChat(clase, texto) {
        if (!historialMensajes) return null;

        const elemento = document.createElement("div");
        elemento.classList.add(clase);
        elemento.textContent = texto;

        historialMensajes.appendChild(elemento);
        historialMensajes.scrollTop =
            historialMensajes.scrollHeight;

        return elemento;
    }

    let enviandoMensaje = false;

    async function enviarMensaje() {
        if (!barraMensajes || !historialMensajes || enviandoMensaje) {
            return;
        }

        const texto = barraMensajes.value.trim();

        if (!texto) return;

        enviandoMensaje = true;

        if (enviarMensajeBtn) {
            enviarMensajeBtn.disabled = true;
        }

        agregarMensajeChat(
            "mensaje_usuario",
            "Tú: " + texto
        );

        barraMensajes.value = "";

        const cargando = agregarMensajeChat(
            "mensaje_asistente",
            "Linneo: Escribiendo..."
        );

        try {
            const datos = await peticion(
                "/api/chat",
                {
                    method: "POST",
                    body: JSON.stringify({
                        mensaje: texto
                    })
                }
            );

            if (cargando) cargando.remove();

            agregarMensajeChat(
                "mensaje_asistente",
                "Linneo: " +
                (datos.respuesta || "No se recibió una respuesta.")
            );

        } catch (error) {
            if (cargando) cargando.remove();

            agregarMensajeChat(
                "mensaje_error",
                "No se pudo conectar con Linneo: " + error.message
            );

            console.error("Error del chatbot:", error);

        } finally {
            enviandoMensaje = false;

            if (enviarMensajeBtn) {
                enviarMensajeBtn.disabled = false;
            }

            barraMensajes.focus();
        }
    }

    if (enviarMensajeBtn) {
        enviarMensajeBtn.addEventListener(
            "click",
            enviarMensaje
        );
    }

    if (barraMensajes) {
        barraMensajes.addEventListener("keydown", function (evento) {
            if (evento.key === "Enter" && !evento.shiftKey) {
                evento.preventDefault();
                enviarMensaje();
            }
        });
    }

    // =====================================================
    // CARRITO Y FAVORITOS
    // =====================================================

// =====================================================
// CARRITO Y FAVORITOS
// =====================================================

let carrito = [];
let favoritos = [];

// =====================================================
// RECUPERAR DATOS
// =====================================================

function recuperarDatos(clave) {
    try {
        const datos = JSON.parse(
            localStorage.getItem(clave) || "[]"
        );

        return Array.isArray(datos) ? datos : [];

    } catch (error) {
        console.error("Error al recuperar datos:", error);
        return [];
    }
}

carrito = recuperarDatos("linneoCarrito");

favoritos = recuperarDatos("linneoFavoritos");

// Normalizar carrito
carrito = carrito.filter(producto =>
    producto &&
    producto.id != null &&
    producto.nombre &&
    Number.isFinite(Number(producto.precio)) &&
    Number(producto.precio) >= 0 &&
    Number.isSafeInteger(Number(producto.cantidad)) &&
    Number(producto.cantidad) > 0
).map(producto => ({
    id: String(producto.id),
    nombre: String(producto.nombre),
    precio: Number(producto.precio),
    cantidad: Number(producto.cantidad)
}));

// Normalizar favoritos
favoritos = favoritos.filter(producto =>
    producto &&
    producto.id != null &&
    producto.nombre &&
    Number.isFinite(Number(producto.precio)) &&
    Number(producto.precio) >= 0
).map(producto => ({
    id: String(producto.id),
    nombre: String(producto.nombre),
    precio: Number(producto.precio)
}));

// =====================================================
// GUARDAR DATOS
// =====================================================

function guardarCarrito() {
    localStorage.setItem(
        "linneoCarrito",
        JSON.stringify(carrito)
    );
}

function guardarFavoritos() {
    localStorage.setItem(
        "linneoFavoritos",
        JSON.stringify(favoritos)
    );
}

// =====================================================
// CARRITO: AGREGAR PRODUCTOS
// =====================================================

function agregarAlCarrito(id, nombre, precio) {

    id = String(id ?? "").trim();
    nombre = String(nombre ?? "").trim();
    precio = Number(precio);

    if (
        !id ||
        !nombre ||
        !Number.isFinite(precio) ||
        precio < 0
    ) {
        console.error("Datos incorrectos del producto.");
        return;
    }

    const existente = carrito.find(
        producto => producto.id === id
    );

    if (existente) {
        existente.cantidad++;
    } else {
        carrito.push({
            id,
            nombre,
            precio,
            cantidad: 1
        });
    }

    actualizarCarrito();
}

// =====================================================
// CARRITO: ELIMINAR PRODUCTOS
// =====================================================

function eliminarDelCarrito(id) {

    carrito = carrito.filter(
        producto => producto.id !== String(id)
    );

    actualizarCarrito();
}

// =====================================================
// CARRITO: ACTUALIZAR VISTA
// =====================================================

function actualizarCarrito() {

    let subtotal = 0;
    let cantidadTotal = 0;

    if (listaCarrito) {
        listaCarrito.replaceChildren();
    }

    carrito.forEach(producto => {

        subtotal += producto.precio * producto.cantidad;
        cantidadTotal += producto.cantidad;

        if (!listaCarrito) return;

        const fila = document.createElement("tr");

        const nombre = document.createElement("td");
        nombre.textContent = producto.nombre;

        const cantidad = document.createElement("td");
        cantidad.textContent = producto.cantidad;

        const precio = document.createElement("td");
        precio.textContent =
            "$" + producto.precio.toFixed(2);

        const acciones = document.createElement("td");

        acciones.appendChild(
            crearBoton("✖", () => {
                eliminarDelCarrito(producto.id);
            }, "eliminar-carrito")
        );

        fila.append(
            nombre,
            cantidad,
            precio,
            acciones
        );

        listaCarrito.appendChild(fila);
    });

    if (listaCarrito && carrito.length === 0) {

        const fila = document.createElement("tr");
        const celda = document.createElement("td");

        celda.colSpan = 4;
        celda.textContent = "El carrito está vacío.";

        fila.appendChild(celda);
        listaCarrito.appendChild(fila);
    }

    if (subtotalLabel) {
        subtotalLabel.textContent =
            "$" + subtotal.toFixed(2);
    }

    if (cantidad_productos) {
        cantidad_productos.textContent =
            String(cantidadTotal);
    }

    guardarCarrito();
}

// =====================================================
// CARRITO: BOTONES DE PRODUCTOS
// =====================================================

document.querySelectorAll(".agregar-carrito").forEach(boton => {

    boton.addEventListener("click", evento => {

        evento.preventDefault();

        if (boton.disabled) return;

        agregarAlCarrito(
            boton.dataset.productoId,
            boton.dataset.productoNombre,
            boton.dataset.productoPrecio
        );

    });

});

// =====================================================
// CARRITO: ABRIR Y CERRAR
// =====================================================

if (carritobtn && carrito_bar) {

    carritobtn.addEventListener("click", () => {

        alternarPanel(carritobtn, carrito_bar);

    });

}

if (cerrarCarrito && carrito_bar) {

    cerrarCarrito.addEventListener("click", () => {

        carrito_bar.classList.remove("visible");

        if (carritobtn) {
            carritobtn.setAttribute(
                "aria-expanded",
                "false"
            );
        }

    });

}

// =====================================================
// FAVORITOS: COMPROBAR SI EXISTE
// =====================================================

function esFavorito(id) {

    return favoritos.some(
        producto => producto.id === String(id)
    );

}

// =====================================================
// FAVORITOS: ACTUALIZAR BOTONES
// =====================================================

function actualizarBotonesFavoritos() {

    document.querySelectorAll(".favorito_producto").forEach(boton => {

        const activo = esFavorito(
            boton.dataset.productoId
        );

        boton.textContent = activo ? "♥" : "♡";

        boton.classList.toggle(
            "es-favorito",
            activo
        );

        boton.setAttribute(
            "aria-pressed",
            String(activo)
        );

        boton.setAttribute(
            "aria-label",
            activo
                ? "Quitar de favoritos"
                : "Agregar a favoritos"
        );

    });

}

// =====================================================
// FAVORITOS: AGREGAR Y QUITAR
// =====================================================

function alternarFavorito(boton) {

    const id = String(
        boton.dataset.productoId ?? ""
    ).trim();

    const nombre = String(
        boton.dataset.productoNombre ?? ""
    ).trim();

    const precio = Number(
        boton.dataset.productoPrecio
    );

    if (
        !id ||
        !nombre ||
        !Number.isFinite(precio) ||
        precio < 0
    ) {
        console.error("Datos incorrectos del favorito.");
        return;
    }

    if (esFavorito(id)) {

        favoritos = favoritos.filter(
            producto => producto.id !== id
        );

    } else {

        favoritos.push({
            id,
            nombre,
            precio
        });

    }

    guardarFavoritos();

    actualizarBotonesFavoritos();

    actualizarFavoritos();
}

// =====================================================
// FAVORITOS: MOSTRAR PRODUCTOS
// =====================================================

function actualizarFavoritos() {

    if (!contenidoFavoritos) return;

    contenidoFavoritos.replaceChildren();

    if (favoritos.length === 0) {

        const mensaje = document.createElement("p");

        mensaje.textContent =
            "No tienes productos favoritos.";

        contenidoFavoritos.appendChild(mensaje);

        return;
    }

    favoritos.forEach(producto => {

        const div = document.createElement("div");

        div.classList.add("producto-favorito");

        const nombre = document.createElement("p");
        nombre.textContent = producto.nombre;

        const precio = document.createElement("p");

        precio.textContent =
            "$" + producto.precio.toFixed(2);

        const quitarBtn = crearBoton(
            "♥ Quitar de favoritos",
            () => {

                favoritos = favoritos.filter(
                    p => p.id !== producto.id
                );

                guardarFavoritos();

                actualizarFavoritos();

                actualizarBotonesFavoritos();

            }
        );

        const carritoBtn = crearBoton(
            "🛒 Agregar al carrito",
            () => {

                agregarAlCarrito(
                    producto.id,
                    producto.nombre,
                    producto.precio
                );

            }
        );

        div.append(
            nombre,
            precio,
            quitarBtn,
            carritoBtn
        );

        contenidoFavoritos.appendChild(div);

    });

}

// =====================================================
// FAVORITOS: DETECTAR CLICS
// =====================================================

document.addEventListener("click", evento => {

    const boton = evento.target.closest(
        ".favorito_producto"
    );

    if (!boton) return;

    evento.preventDefault();

    alternarFavorito(boton);

});

// =====================================================
// FAVORITOS: ABRIR Y CERRAR
// =====================================================

if (favoritosBtn && favoritosBar) {

    favoritosBtn.addEventListener("click", () => {

        alternarPanel(favoritosBtn, favoritosBar);

        actualizarFavoritos();

    });

}

if (cerrarFavoritos && favoritosBar) {

    cerrarFavoritos.addEventListener("click", () => {

        favoritosBar.classList.remove("visible");

        if (favoritosBtn) {

            favoritosBtn.setAttribute(
                "aria-expanded",
                "false"
            );

        }

    });

}

// =====================================================
// INICIALIZAR CARRITO Y FAVORITOS
// =====================================================

actualizarCarrito();

actualizarBotonesFavoritos();

actualizarFavoritos();


    // =====================================================
    // FILTROS Y ORDEN DEL CATÁLOGO
    // =====================================================

    const botonesCategoria = document.querySelectorAll(
        ".sec_btn[data-categoria]"
    );

    const contenedorCatalogo = $("catalogo");

    const opcionesOrden = document.querySelectorAll(
        'input[name="orden"]'
    );

    let categoriaSeleccionada = "";
    let ordenSeleccionado = "";

    function aplicarFiltros() {
        if (!contenedorCatalogo) return;

        const tarjetas = Array.from(
            contenedorCatalogo.querySelectorAll(
                ".tarjeta_producto"
            )
        );

        tarjetas.forEach(function (producto) {
            const categoria = normalizarTexto(
                producto.dataset.categoria
            );

            const coincide =
                !categoriaSeleccionada ||
                categoria === normalizarTexto(
                    categoriaSeleccionada
                );

            producto.hidden = !coincide;
        });

        tarjetas.sort(function (a, b) {
            const nombreA = normalizarTexto(a.dataset.nombre);
            const nombreB = normalizarTexto(b.dataset.nombre);

            const precioA = Number(a.dataset.precio);
            const precioB = Number(b.dataset.precio);

            switch (ordenSeleccionado) {
                case "alfabetico":
                    return nombreA.localeCompare(nombreB, "es");

                case "mayorprecio":
                    return (
                        (Number.isFinite(precioB) ? precioB : 0) -
                        (Number.isFinite(precioA) ? precioA : 0)
                    );

                case "menorprecio":
                    return (
                        (Number.isFinite(precioA) ? precioA : 0) -
                        (Number.isFinite(precioB) ? precioB : 0)
                    );

                default:
                    return 0;
            }
        });

        tarjetas.forEach(function (producto) {
            contenedorCatalogo.appendChild(producto);
        });
    }

    botonesCategoria.forEach(function (botonCategoria) {
        botonCategoria.addEventListener("click", function () {
            categoriaSeleccionada =
                botonCategoria.dataset.categoria || "";

            aplicarFiltros();
        });
    });

    opcionesOrden.forEach(function (opcion) {
        opcion.addEventListener("change", function () {
            if (opcion.checked) {
                ordenSeleccionado = opcion.value;
                aplicarFiltros();
            }
        });
    });

    aplicarFiltros();

    // =====================================================
    // BUSCADOR DESPLEGABLE
    // =====================================================

    if (buscar_btn && busqueda_div) {
        buscar_btn.addEventListener("click", function () {
            alternarPanel(buscar_btn, busqueda_div);
        });
    }

    // =====================================================
    // MENÚ DE FILTROS
    // =====================================================

    if (filtrosbtn && filtro_menu) {
        filtrosbtn.addEventListener("click", function () {
            const visible = filtro_menu.hidden;

            filtro_menu.hidden = !visible;

            filtrosbtn.setAttribute(
                "aria-expanded",
                String(visible)
            );
        });
    }

    // =====================================================
    // CATEGORÍAS DE LA PORTADA
    // =====================================================

    const botonesPortada = document.querySelectorAll(
        ".botones_catalogo"
    );

    const seccionProductos = $("productos");

    const categoriasPortada = {
        mariposas_btn: ["mariposa", "mariposas"],
        escarabajos_btn: ["escarabajo", "escarabajos"],
        odonatos_btn: [
            "odonato",
            "odonatos",
            "libelula",
            "libelulas"
        ],
        fosiles_btn: ["fosil", "fosiles"],
        esqueletos_btn: ["esqueleto", "esqueletos"],
        minerales_btn: ["mineral", "minerales"]
    };

    botonesPortada.forEach(function (botonPortada) {
        botonPortada.addEventListener("click", function () {
            const terminos =
                categoriasPortada[botonPortada.id] || [];

            const tarjetas = Array.from(
                document.querySelectorAll(
                    "#productos .tarjeta_producto"
                )
            );

            if (tarjetas.length === 0) {
                window.location.href = "/catalogo";
                return;
            }

            let coincidencias = 0;

            tarjetas.forEach(function (tarjeta) {
                const texto = normalizarTexto(
                    (tarjeta.dataset.categoria || "") + " " +
                    (tarjeta.dataset.nombre || "")
                );

                const coincide = terminos.some(function (termino) {
                    return texto.includes(
                        normalizarTexto(termino)
                    );
                });

                tarjeta.hidden = !coincide;

                if (coincide) {
                    coincidencias++;
                }
            });

            if (seccionProductos) {
                seccionProductos.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });
            }

            let aviso = $("aviso_filtro_portada");

            if (
                !aviso &&
                seccionProductos &&
                seccionProductos.parentNode
            ) {
                aviso = document.createElement("p");
                aviso.id = "aviso_filtro_portada";
                aviso.setAttribute("role", "status");

                seccionProductos.parentNode.insertBefore(
                    aviso,
                    seccionProductos
                );
            }

            if (aviso) {
                aviso.textContent = coincidencias
                    ? `Mostrando ${coincidencias} producto(s) de la categoría seleccionada.`
                    : "No encontramos productos de esta categoría en la portada. Revisa el catálogo completo.";
            }
        });
    });

    console.info("LINNEO: JavaScript inicializado correctamente.");
});
