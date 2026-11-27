
document.addEventListener("DOMContentLoaded", function () {

    // =====================================================
    // ELEMENTOS DEL HTML
    // =====================================================

    const $ = (id) => document.getElementById(id);

    const menubtn = $("menubtn");
    const menu_bar = $("menu_bar");
    const atras_menu = $("atras_menu")
     const paquete = document.getElementById("paquete_pedido");

    const carritobtn = $("carritobtn");
    const carrito_bar = $("carrito_bar");
    const cerrarCarrito = $("cerrar_carrito");

    const listaCarrito = $("lista_carrito");
    const subtotalLabel = $("subtotal_carrito");
    const cantidadProductos = $("cantidad_productos");

    const favoritosBtn = $("favoritos_btn");
    const favoritosBar = $("favoritos_bar");
    const cerrarFavoritos = $("cerrar_favoritos");
    const contenidoFavoritos = $("contenido_favoritos");

    const buscarBtn = $("buscarbtn");
    const busquedaDiv = $("busqueda_div");

    const imagenNovedades = $("imagen");
    const contadorNovedades = $("contador");
    const atrasNovedades = $("atras_novedades");
    const adelanteNovedades = $("adelante_novedades");
const ver_personalizado = document.getElementById("ver_personalizado");

/* =========================================
   FINANZAS
========================================= */

const tablaFinanzas = document.getElementById("tabla_ventas");
const mensajeFinanzas = document.getElementById("mensaje");

const buscarFinanzas = document.getElementById("buscar");
const filtroEstadoFinanzas = document.getElementById("filtro_estado");
const actualizarFinanzasBtn = document.getElementById("actualizar");

const detalleSeccion = document.getElementById("detalle_seccion");
const detalleVenta = document.getElementById("detalle_venta");

let operaciones = [];

/* =========================================
   FORMATO DE DINERO
========================================= */

function dinero(valor) {
    return new Intl.NumberFormat("es-MX", {
        style: "currency",
        currency: "MXN"
    }).format(Number(valor || 0));
}

/* =========================================
   CREAR ELEMENTOS
========================================= */

function crearElemento(tag, texto = "") {
    const nodo = document.createElement(tag);
    nodo.textContent = texto ?? "";
    return nodo;
}

/* =========================================
   CARGAR FINANZAS DESDE EL SERVIDOR
========================================= */

async function cargarFinanzas() {

    if (!tablaFinanzas || !mensajeFinanzas) return;

    mensajeFinanzas.textContent = "Cargando información...";

    if (actualizarFinanzasBtn) {
        actualizarFinanzasBtn.disabled = true;
    }

    try {

        const respuesta = await fetch("/api/admin/finanzas/ventas", {
    method: "GET",
    credentials: "same-origin",
    headers: {
        "Accept": "application/json"
    }
});

        const datos = await respuesta.json();

        if (!respuesta.ok) {
            throw new Error(
                datos.error || "No se pudieron cargar las finanzas."
            );
        }

        if (!datos.resumen || !Array.isArray(datos.ventas)) {
            throw new Error("La respuesta del servidor tiene un formato incorrecto.");
        }

        operaciones = datos.ventas;

        actualizarResumenFinanzas(datos.resumen);

        mostrarOperaciones();

        mensajeFinanzas.textContent = "Finanzas actualizadas correctamente.";

    } catch (error) {

        console.error("Error en finanzas:", error);

        mensajeFinanzas.textContent = error.message;

        tablaFinanzas.replaceChildren();

        const fila = crearElemento("tr");
        const celda = crearElemento("td", error.message);

        celda.colSpan = 7;

        fila.appendChild(celda);
        tablaFinanzas.appendChild(fila);

    } finally {

        if (actualizarFinanzasBtn) {
            actualizarFinanzasBtn.disabled = false;
        }

    }
}

/* =========================================
   ACTUALIZAR RESUMEN FINANCIERO
========================================= */

function actualizarResumenFinanzas(resumen) {

    const campos = {
        ingresos: dinero(resumen.ingresos),
        costos: dinero(resumen.costos),
        ganancia: dinero(resumen.ganancia_bruta),
        perdida: dinero(resumen.perdida),
        pendiente: dinero(resumen.pendiente_cobro),
        operaciones: resumen.operaciones ?? 0
    };

    Object.entries(campos).forEach(([id, valor]) => {

        const elemento = document.getElementById(id);

        if (elemento) {
            elemento.textContent = valor;
        }

    });

}

/* =========================================
   FILTRAR OPERACIONES
========================================= */

function mostrarOperaciones() {

    if (!tablaFinanzas) return;

    const busqueda = buscarFinanzas
        ? buscarFinanzas.value.toLowerCase().trim()
        : "";

    const estado = filtroEstadoFinanzas
        ? filtroEstadoFinanzas.value
        : "";

    const filtradas = operaciones.filter(venta => {

        const comprador = String(venta.comprador || "").toLowerCase();

        const detalles = Array.isArray(venta.detalles)
            ? venta.detalles
            : [];

        const coincideBusqueda =
            comprador.includes(busqueda) ||
            detalles.some(item =>
                String(item.producto || "")
                    .toLowerCase()
                    .includes(busqueda)
            );

        const coincideEstado =
            !estado || venta.estado_pago === estado;

        return coincideBusqueda && coincideEstado;

    });

    tablaFinanzas.replaceChildren();

    if (filtradas.length === 0) {

        const fila = crearElemento("tr");
        const celda = crearElemento(
            "td",
            "No hay operaciones encontradas."
        );

        celda.colSpan = 7;

        fila.appendChild(celda);
        tablaFinanzas.appendChild(fila);

        return;
    }

    filtradas.forEach(venta => {

        const fila = crearElemento("tr");

        const datos = [
            `${venta.tipo === "pedido" ? "P" : "V"}-${venta.id}`,
            venta.fecha
                ? new Date(venta.fecha).toLocaleString("es-MX")
                : "Sin fecha",
            venta.comprador || "Sin comprador",
            venta.tipo === "pedido"
                ? "Pedido digital"
                : venta.canal || "Sin canal",
            dinero(venta.total),
            venta.estado_pago || "Desconocido"
        ];

        datos.forEach(texto => {
            fila.appendChild(crearElemento("td", texto));
        });

        const celdaAccion = crearElemento("td");

        const boton = crearElemento("button", "Ver detalles");

        boton.type = "button";

        boton.addEventListener("click", () => {
            mostrarDetalleVenta(venta);
        });

        celdaAccion.appendChild(boton);
        fila.appendChild(celdaAccion);

        tablaFinanzas.appendChild(fila);

    });

}

/* =========================================
   MOSTRAR DETALLES DE UNA VENTA
========================================= */

function mostrarDetalleVenta(venta) {

    if (!detalleSeccion || !detalleVenta) return;

    detalleVenta.replaceChildren();

    const titulo = crearElemento(
        "h3",
        `Operación ${venta.tipo} #${venta.id}`
    );

    detalleVenta.appendChild(titulo);

    const informacion = [
        ["Comprador", venta.comprador],
        ["Contacto", venta.contacto],
        ["Fecha", venta.fecha
            ? new Date(venta.fecha).toLocaleString("es-MX")
            : "Sin fecha"],
        ["Canal", venta.canal],
        ["Método de pago", venta.metodo_pago],
        ["Estado", venta.estado_pago],
        ["Subtotal", dinero(venta.subtotal)],
        ["Descuento", dinero(venta.descuento)],
        ["Total", dinero(venta.total)],
        ["Costo de mercancía", dinero(venta.costo)],
        [
            "Ganancia",
            venta.ganancia === null ||
            venta.ganancia === undefined
                ? "Costo histórico desconocido"
                : dinero(venta.ganancia)
        ]
    ];

    informacion.forEach(([etiqueta, valor]) => {

        const parrafo = crearElemento("p");

        const nombre = crearElemento(
            "strong",
            `${etiqueta}: `
        );

        parrafo.appendChild(nombre);

        parrafo.appendChild(
            document.createTextNode(String(valor ?? "No disponible"))
        );

        detalleVenta.appendChild(parrafo);

    });

    detalleVenta.appendChild(
        crearElemento("h3", "Productos adquiridos")
    );

    const tabla = crearElemento("table");
    const thead = crearElemento("thead");
    const filaEncabezado = crearElemento("tr");

    [
        "Código",
        "Producto",
        "Cantidad",
        "Precio unitario",
        "Costo unitario",
        "Total"
    ].forEach(texto => {
        filaEncabezado.appendChild(
            crearElemento("th", texto)
        );
    });

    thead.appendChild(filaEncabezado);
    tabla.appendChild(thead);

    const tbody = crearElemento("tbody");

    const detalles = Array.isArray(venta.detalles)
        ? venta.detalles
        : [];

    detalles.forEach(item => {

        const fila = crearElemento("tr");

        const valores = [
            item.codigo,
            item.producto,
            item.cantidad,
            dinero(item.precio),
            item.costo_unitario === null ||
            item.costo_unitario === undefined
                ? "Desconocido"
                : dinero(item.costo_unitario),
            dinero(item.total)
        ];

        valores.forEach(valor => {
            fila.appendChild(
                crearElemento("td", String(valor ?? ""))
            );
        });

        tbody.appendChild(fila);

    });

    tabla.appendChild(tbody);
    detalleVenta.appendChild(tabla);

    detalleSeccion.hidden = false;

    detalleSeccion.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });

}
if (chatBtn) {

    chatBtn.addEventListener(
        "click",
        alternarChat
    );

}
/* =========================================
   EVENTOS
========================================= */

if (buscarFinanzas) {
    buscarFinanzas.addEventListener(
        "input",
        mostrarOperaciones
    );
}

if (filtroEstadoFinanzas) {
    filtroEstadoFinanzas.addEventListener(
        "change",
        mostrarOperaciones
    );
}

if (actualizarFinanzasBtn) {
    actualizarFinanzasBtn.addEventListener(
        "click",
        cargarFinanzas
    );
}

/* =========================================
   INICIALIZAR
========================================= */

if (tablaFinanzas && mensajeFinanzas) {
    cargarFinanzas();
}

if (ver_personalizado) {
    ver_personalizado.addEventListener("click", function() {
        window.location.href = "/pedido_personalizado";
    });
}
    

    const popup = $("popup");
    const cerrarPopup = $("quitar_popup");

    const csrfMeta = document.querySelector(
        'meta[name="csrf-token"]'
    );

    const csrfToken = csrfMeta
        ? csrfMeta.content
        : "";

    // =====================================================
    // UTILIDADES
    // =====================================================

    function normalizarTexto(texto) {
        return String(texto || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .trim()
            .toLowerCase();
    }

    function formatoPrecio(precio) {
        return "$" + Number(precio).toFixed(2);
    }

    function guardarLocalStorage(clave, datos) {
        try {
            localStorage.setItem(
                clave,
                JSON.stringify(datos)
            );
        } catch (error) {
            console.error(
                "Error al guardar " + clave,
                error
            );
        }
    }

    function recuperarLocalStorage(clave) {
        try {
            const datos = JSON.parse(
                localStorage.getItem(clave) || "[]"
            );

            return Array.isArray(datos) ? datos : [];

        } catch (error) {
            console.error(
                "Error al recuperar " + clave,
                error
            );

            return [];
        }
    }

    // =====================================================
    // PETICIONES HTTP
    // =====================================================

    async function peticion(url, opciones = {}) {

        const metodo = (
            opciones.method || "GET"
        ).toUpperCase();

        const cabeceras = {
            ...opciones.headers
        };

        if (opciones.body) {
            cabeceras["Content-Type"] =
                "application/json";
        }

        if (
            !["GET", "HEAD", "OPTIONS"].includes(metodo)
            && csrfToken
        ) {
            cabeceras["X-CSRFToken"] = csrfToken;
        }

        const respuesta = await fetch(url, {
            ...opciones,
            method: metodo,
            headers: cabeceras,
            credentials: "same-origin"
        });

        const datos = await respuesta.json().catch(
            () => ({})
        );

        if (!respuesta.ok) {
            throw new Error(
                datos.error ||
                datos.mensaje ||
                "Error HTTP " + respuesta.status
            );
        }

        return datos;
    }

// =====================================================
// CARRITO Y FAVORITOS: RECUPERAR DATOS
// =====================================================

let carrito = recuperarLocalStorage("linneoCarrito");
let favoritos = recuperarLocalStorage("linneoFavoritos");

// Validar productos guardados en el carrito
carrito = carrito
    .filter(function (p) {
        return p &&
            p.id !== undefined &&
            p.id !== null &&
            String(p.id).trim() !== "" &&
            typeof p.nombre === "string" &&
            Number.isFinite(Number(p.precio)) &&
            Number(p.precio) >= 0;
    })
    .map(function (p) {
        return {
            id: String(p.id),
            nombre: p.nombre,
            precio: Number(p.precio),
            cantidad: Math.max(1, parseInt(p.cantidad, 10) || 1),
            stock: p.stock === null || p.stock === undefined
                ? null
                : Math.max(0, Number(p.stock))
        };
    });

// Validar favoritos guardados
favoritos = favoritos
    .filter(function (p) {
        return p &&
            p.id !== undefined &&
            p.id !== null &&
            String(p.id).trim() !== "" &&
            typeof p.nombre === "string" &&
            Number.isFinite(Number(p.precio)) &&
            Number(p.precio) >= 0;
    })
    .map(function (p) {
        return {
            id: String(p.id),
            nombre: p.nombre,
            precio: Number(p.precio),
            stock: p.stock === null || p.stock === undefined
                ? null
                : Number(p.stock)
        };
    });


// =====================================================
// CARRITO: AGREGAR PRODUCTOS
// =====================================================

function agregarAlCarrito(id, nombre, precio, stockDisponible = null) {

    id = String(id ?? "").trim();
    nombre = String(nombre ?? "").trim();
    precio = Number(precio);

    const stock = stockDisponible === null ||
        stockDisponible === undefined ||
        stockDisponible === ""
            ? null
            : Number(stockDisponible);

    if (
        !id ||
        !nombre ||
        !Number.isFinite(precio) ||
        precio < 0 ||
        (
            stock !== null &&
            (!Number.isSafeInteger(stock) || stock < 0)
        )
    ) {
        alert("No se pudieron validar los datos del producto.");
        return;
    }

    

    const productoExistente = carrito.find(
    p => String(p.id) === id
);

    if (productoExistente) {

        if (
            stock !== null &&
            productoExistente.cantidad >= stock
        ) {
            alert("No hay más unidades disponibles.");
            return;
        }

        productoExistente.cantidad++;
        productoExistente.stock = stock;

    } else {

        carrito.push({
            id: id,
            nombre: nombre,
            precio: precio,
            cantidad: 1,
            stock: stock
        });

    }

    actualizarCarrito();
}


// =====================================================
// CARRITO: CAMBIAR CANTIDAD
// =====================================================

function cambiarCantidad(id, cambio) {

    const producto = carrito.find(
        p => p.id === String(id)
    );

    if (!producto) return;

    const nuevaCantidad = producto.cantidad + cambio;

    if (nuevaCantidad <= 0) {
        eliminarDelCarrito(id);
        return;
    }

    if (
        producto.stock !== null &&
        producto.stock !== undefined &&
        nuevaCantidad > producto.stock
    ) {
        alert("No hay más unidades disponibles.");
        return;
    }

    producto.cantidad = nuevaCantidad;

    actualizarCarrito();
}


// =====================================================
// CARRITO: ELIMINAR PRODUCTOS
// =====================================================

function eliminarDelCarrito(id) {

    carrito = carrito.filter(
        p => p.id !== String(id)
    );

    actualizarCarrito();
}


// =====================================================
// CARRITO: ACTUALIZAR TABLA
// =====================================================

function actualizarCarrito() {

    let subtotal = 0;
    let cantidadTotal = 0;

    if (listaCarrito) {

        listaCarrito.replaceChildren();

        if (carrito.length === 0) {

            const fila = document.createElement("tr");
            const celda = document.createElement("td");

            celda.colSpan = 4;
            celda.textContent = "El carrito está vacío.";

            fila.appendChild(celda);
            listaCarrito.appendChild(fila);

        } else {

            carrito.forEach(function (producto) {

                const fila = document.createElement("tr");

                // Nombre
                const nombre = document.createElement("td");
                nombre.textContent = producto.nombre;

                // Cantidad
                const cantidad = document.createElement("td");

                const botonMenos = document.createElement("button");
                botonMenos.type = "button";
                botonMenos.textContent = "−";

                botonMenos.addEventListener("click", function () {
                    cambiarCantidad(producto.id, -1);
                });

                const textoCantidad = document.createElement("span");
                textoCantidad.textContent =
                    " " + producto.cantidad + " ";

                const botonMas = document.createElement("button");
                botonMas.type = "button";
                botonMas.textContent = "+";

                botonMas.addEventListener("click", function () {
                    cambiarCantidad(producto.id, 1);
                });

                cantidad.append(
                    botonMenos,
                    textoCantidad,
                    botonMas
                );

                // Precio
                const precio = document.createElement("td");

                precio.textContent = formatoPrecio(
                    producto.precio * producto.cantidad
                );

                // Eliminar
                const eliminar = document.createElement("td");

                const botonEliminar =
                    document.createElement("button");

                botonEliminar.type = "button";
                botonEliminar.textContent = "✖";
                botonEliminar.className = "eliminar-carrito";

                botonEliminar.addEventListener("click", function () {
                    eliminarDelCarrito(producto.id);
                });

                eliminar.appendChild(botonEliminar);

                fila.append(
                    nombre,
                    cantidad,
                    precio,
                    eliminar
                );

                listaCarrito.appendChild(fila);

                subtotal += producto.precio * producto.cantidad;
                cantidadTotal += producto.cantidad;

            });

        }

    } else {

        carrito.forEach(function (producto) {
            subtotal += producto.precio * producto.cantidad;
            cantidadTotal += producto.cantidad;
        });

    }

    if (subtotalLabel) {
        subtotalLabel.textContent = formatoPrecio(subtotal);
    }

    if (cantidadProductos) {
        cantidadProductos.textContent = cantidadTotal;
    }

    guardarLocalStorage("linneoCarrito", carrito);
}


// =====================================================
// CARRITO: BOTONES DE PRODUCTOS
// =====================================================

document.querySelectorAll(".agregar-carrito").forEach(function (boton) {

    boton.addEventListener("click", function () {

        agregarAlCarrito(
            this.dataset.productoId,
            this.dataset.productoNombre,
            this.dataset.productoPrecio,
            this.dataset.productoStock
        );

        abrirCarrito();

    });

});


// =====================================================
// CARRITO: ABRIR Y CERRAR
// =====================================================

function abrirCarrito() {

    if (!carrito_bar) return;

    carrito_bar.classList.add("visible");

    if (carritobtn) {
        carritobtn.setAttribute("aria-expanded", "true");
    }

    actualizarCarrito();
}


function cerrarPanelCarrito() {

    if (!carrito_bar) return;

    carrito_bar.classList.remove("visible");

    if (carritobtn) {
        carritobtn.setAttribute("aria-expanded", "false");
    }

}


if (carritobtn) {

    carritobtn.addEventListener("click", function () {

        if (carrito_bar.classList.contains("visible")) {
            cerrarPanelCarrito();
        } else {
            abrirCarrito();
        }

    });

}


if (cerrarCarrito) {
    cerrarCarrito.addEventListener("click", cerrarPanelCarrito);
}


// =====================================================
// FAVORITOS: COMPROBAR PRODUCTOS
// =====================================================

function esFavorito(id) {

    return favoritos.some(
        p => p.id === String(id)
    );

}


// =====================================================
// FAVORITOS: ACTUALIZAR CORAZONES
// =====================================================

function actualizarBotonesFavoritos() {

    document.querySelectorAll(".favoritos_").forEach(function (boton) {

        const id = String(boton.dataset.productoId);
        const activo = esFavorito(id);

        boton.textContent = activo ? "♥" : "♡";

        boton.classList.toggle("es-favorito", activo);

        boton.setAttribute(
            "aria-label",
            activo ? "Quitar de favoritos" : "Agregar a favoritos"
        );

        boton.setAttribute("aria-pressed", String(activo));

    });

}


// =====================================================
// FAVORITOS: AGREGAR O QUITAR
// =====================================================

// =========================================
// ABRIR Y CERRAR CHATBOT
// =========================================

function alternarChat() {

    if (!chatBox || !chatBtn) return;

    const abierto = chatBox.hidden;

    chatBox.hidden = !abierto;

    chatBox.setAttribute(
        "aria-hidden",
        String(!abierto)
    );

    chatBtn.setAttribute(
        "aria-expanded",
        String(abierto)
    );

    if (abierto && barraMensajes) {

        setTimeout(function() {
            barraMensajes.focus();
        }, 100);

    }

}

// Botón flotante



// Botón de cerrar del encabezado

if (cerrarChatBtn) {

    cerrarChatBtn.addEventListener(
        "click",
        alternarChat
    );

}

// Cerrar con Escape

document.addEventListener("keydown", function(evento) {

    if (
        evento.key === "Escape" &&
        chatBox &&
        !chatBox.hidden
    ) {

        alternarChat();

    }

});

// =====================================================
// FAVORITOS: BOTONES DE PRODUCTOS
// =====================================================

document.querySelectorAll(".favoritos_").forEach(function (boton) {

    boton.addEventListener("click", function () {

        alternarFavorito(
            this.dataset.productoId,
            this.dataset.productoNombre,
            this.dataset.productoPrecio,
            this.dataset.productoStock
        );

    });

});


// =====================================================
// FAVORITOS: MOSTRAR PRODUCTOS
// =====================================================

// =====================================================
// FAVORITOS: ACTUALIZAR TABLA
// =====================================================

function actualizarFavoritos() {

    if (!contenidoFavoritos) return;

    let subtotal = 0;

    contenidoFavoritos.replaceChildren();

    if (favoritos.length === 0) {

        const fila = document.createElement("tr");
        const celda = document.createElement("td");

        celda.colSpan = 4;
        celda.textContent = "No tienes productos favoritos.";

        fila.appendChild(celda);
        contenidoFavoritos.appendChild(fila);

    } else {

        favoritos.forEach(function (producto) {

            const fila = document.createElement("tr");

            // Nombre del producto
            const nombre = document.createElement("td");

            nombre.textContent = producto.nombre;

            // Cantidad
            const cantidad = document.createElement("td");

            cantidad.textContent = "1";

            // Precio
            const precio = document.createElement("td");

            precio.textContent = formatoPrecio(
                producto.precio
            );

            // Acciones
            const acciones = document.createElement("td");

            const botonQuitar = document.createElement("button");

            botonQuitar.type = "button";
            botonQuitar.textContent = "✖";
            botonQuitar.className = "eliminar-carrito";

            botonQuitar.setAttribute(
                "aria-label",
                "Quitar de favoritos"
            );

            botonQuitar.addEventListener("click", function () {

                favoritos = favoritos.filter(
                    p => p.id !== producto.id
                );

                guardarLocalStorage(
                    "linneoFavoritos",
                    favoritos
                );

                actualizarFavoritos();
                actualizarBotonesFavoritos();

            });

            const botonAgregar = document.createElement("button");

            botonAgregar.type = "button";
            botonAgregar.textContent = "🛒";
            botonAgregar.className = "agregar-desde-favoritos";

            botonAgregar.setAttribute(
                "aria-label",
                "Agregar al carrito"
            );

            botonAgregar.addEventListener("click", function () {

                agregarAlCarrito(
                    producto.id,
                    producto.nombre,
                    producto.precio,
                    producto.stock
                );

                abrirCarrito();

            });

            acciones.append(
                botonQuitar,
                botonAgregar
            );

            fila.append(
                nombre,
                cantidad,
                precio,
                acciones
            );

            contenidoFavoritos.appendChild(fila);

            subtotal += producto.precio;

        });

    }

    const subtotalLabel = document.getElementById(
        "subtotal_favoritos"
    );

    if (subtotalLabel) {
        subtotalLabel.textContent = formatoPrecio(subtotal);
    }

    guardarLocalStorage(
        "linneoFavoritos",
        favoritos
    );

}


/* =========================================
   CAJA: COMPRADORES Y PRODUCTOS
==========================
/* =========================================
   CAJA: GESTIÓN DE PRODUCTOS DE LA VENTA
========================================= */

const botonAgregarProducto = $("agregar_producto");
const listaProductosCaja = $("lista_productos");

const cantidadCaja = $("cantidad");

const subtotalCaja = $("subtotal");
const descuentoCaja = $("descuento");
const descuentoTotalCaja = $("descuento_total");
const totalCaja = $("total");

const mensajeCaja = $("mensaje_caja");

// Productos seleccionados para la venta.
// Esta lista es independiente del catálogo.
let productosVenta = [];


/* =========================================
   AGREGAR PRODUCTO
========================================= */

function agregarProductoCaja() {

    const codigo = selectorProducto.value;

    const cantidad = Number(cantidadCaja.value);

    if (!codigo) {
        alert("Selecciona un producto.");
        return;
    }

    if (!Number.isSafeInteger(cantidad) || cantidad <= 0) {
        alert("Introduce una cantidad válida.");
        return;
    }

    // Buscar producto en el catálogo recibido del servidor.

    const producto = productosCaja.find(
        p => String(p.codigo) === String(codigo)
    );

    if (!producto) {
        alert("No se encontró el producto seleccionado.");
        return;
    }

    const stock = Number(producto.stock);
    const precio = Number(producto.precio_venta);

    if (
        !Number.isSafeInteger(stock) ||
        stock < 0 ||
        !Number.isFinite(precio) ||
        precio < 0
    ) {
        alert("Los datos del producto no son válidos.");
        return;
    }

    if (stock === 0) {
        alert("Este producto no tiene existencias.");
        return;
    }

    // Comprobar si ya está agregado.

    const existente = productosVenta.find(
        p => p.codigo === String(codigo)
    );

    const cantidadActual = existente
        ? existente.cantidad
        : 0;

    if (cantidadActual + cantidad > stock) {
        alert("No hay suficiente stock disponible.");
        return;
    }

    if (existente) {

        existente.cantidad += cantidad;

    } else {

        productosVenta.push({

            codigo: String(producto.codigo),
            nombre: String(producto.nombre),
            stock: stock,
            cantidad: cantidad,
            precio: precio

        });

    }

    // Actualizar interfaz.

    actualizarTablaCaja();

    // Restablecer cantidad.

    cantidadCaja.value = 1;

    selectorProducto.value = "";

}


/* =========================================
   DIBUJAR TABLA DE PRODUCTOS
========================================= */

function actualizarTablaCaja() {

    if (!listaProductosCaja) return;

    listaProductosCaja.replaceChildren();

    if (productosVenta.length === 0) {

        const fila = document.createElement("tr");
        const celda = document.createElement("td");

        celda.colSpan = 6;
        celda.textContent = "No hay productos agregados.";

        fila.appendChild(celda);
        listaProductosCaja.appendChild(fila);

    } else {

        productosVenta.forEach(function(producto) {

            const fila = document.createElement("tr");

            // Nombre

            const nombre = document.createElement("td");
            nombre.textContent =
                producto.codigo + " | " + producto.nombre;

            // Stock

            const stock = document.createElement("td");
            stock.textContent = producto.stock;

            // Cantidad

            const cantidad = document.createElement("td");

            const botonMenos = document.createElement("button");
            botonMenos.type = "button";
            botonMenos.textContent = "−";

            botonMenos.addEventListener("click", function() {
                cambiarCantidadCaja(producto.codigo, -1);
            });

            const textoCantidad = document.createElement("span");
            textoCantidad.textContent =
                " " + producto.cantidad + " ";

            const botonMas = document.createElement("button");
            botonMas.type = "button";
            botonMas.textContent = "+";

            botonMas.addEventListener("click", function() {
                cambiarCantidadCaja(producto.codigo, 1);
            });

            cantidad.append(
                botonMenos,
                textoCantidad,
                botonMas
            );

            // Precio unitario

            const precio = document.createElement("td");
            precio.textContent =
                formatoPrecio(producto.precio);

            // Total del producto

            const total = document.createElement("td");
            total.textContent =
                formatoPrecio(
                    producto.precio * producto.cantidad
                );

            // Eliminar

            const accion = document.createElement("td");

            const eliminar = document.createElement("button");
            eliminar.type = "button";
            eliminar.textContent = "Eliminar";

            eliminar.addEventListener("click", function() {
                eliminarProductoCaja(producto.codigo);
            });

            accion.appendChild(eliminar);

            fila.append(
                nombre,
                stock,
                cantidad,
                precio,
                total,
                accion
            );

            listaProductosCaja.appendChild(fila);

        });

    }

    actualizarResumenCaja();

}


/* =========================================
   CAMBIAR CANTIDAD
========================================= */

function cambiarCantidadCaja(codigo, cambio) {

    const producto = productosVenta.find(
        p => p.codigo === String(codigo)
    );

    if (!producto) return;

    const nuevaCantidad = producto.cantidad + cambio;

    if (nuevaCantidad <= 0) {
        eliminarProductoCaja(codigo);
        return;
    }

    if (nuevaCantidad > producto.stock) {
        alert("No hay suficiente stock.");
        return;
    }

    producto.cantidad = nuevaCantidad;

    actualizarTablaCaja();

}


/* =========================================
   ELIMINAR PRODUCTO
========================================= */

function eliminarProductoCaja(codigo) {

    productosVenta = productosVenta.filter(
        p => p.codigo !== String(codigo)
    );

    actualizarTablaCaja();

}


/* =========================================
   CALCULAR SUBTOTAL Y TOTAL
========================================= */

function actualizarResumenCaja() {

    const subtotal = productosVenta.reduce(
        (total, producto) => {
            return total + (
                producto.precio * producto.cantidad
            );
        },
        0
    );

    let porcentaje = Number(descuentoCaja.value);

    if (!Number.isFinite(porcentaje)) {
        porcentaje = 0;
    }

    porcentaje = Math.min(
        100,
        Math.max(0, porcentaje)
    );

    const descuento = subtotal * porcentaje / 100;

    const total = subtotal - descuento;

    subtotalCaja.textContent =
        formatoPrecio(subtotal);

    descuentoTotalCaja.textContent =
        formatoPrecio(descuento);

    totalCaja.textContent =
        formatoPrecio(total);

}


/* =========================================
   EVENTOS DE LA CAJA
========================================= */

if (botonAgregarProducto) {

    botonAgregarProducto.addEventListener(
        "click",
        agregarProductoCaja
    );

}

if (descuentoCaja) {

    descuentoCaja.addEventListener(
        "input",
        actualizarResumenCaja
    );

}


actualizarTablaCaja();

const selectorComprador = $("comprador");
const selectorProducto = $("producto");

let compradoresCaja = [];
let productosCaja = [];

async function cargarCompradoresCaja() {

    if (!selectorComprador) return;

    selectorComprador.replaceChildren();

    const inicial = document.createElement("option");
    inicial.value = "";
    inicial.textContent = "Cargando compradores...";
    selectorComprador.appendChild(inicial);

    try {

        compradoresCaja = await peticion(
            "/api/admin/caja/compradores"
        );

        if (!Array.isArray(compradoresCaja)) {
            throw new Error("Formato de compradores incorrecto.");
        }

        selectorComprador.replaceChildren();

        const opcion = document.createElement("option");
        opcion.value = "";
        opcion.textContent = "Selecciona un comprador";

        selectorComprador.appendChild(opcion);

        compradoresCaja.forEach(function(usuario) {

            const option = document.createElement("option");

            option.value = usuario.id;

            option.textContent =
                usuario.username +
                (usuario.email ? " | " + usuario.email : "");

            selectorComprador.appendChild(option);

        });

        if (compradoresCaja.length === 0) {
            opcion.textContent = "No hay compradores registrados.";
        }

    } catch (error) {

        console.error("Error de compradores:", error);

        selectorComprador.replaceChildren();

        const option = document.createElement("option");
        option.value = "";
        option.textContent = "Error al cargar compradores.";

        selectorComprador.appendChild(option);

    }
}


async function cargarProductosCaja() {

    if (!selectorProducto) return;

    selectorProducto.replaceChildren();

    const inicial = document.createElement("option");
    inicial.value = "";
    inicial.textContent = "Cargando productos...";

    selectorProducto.appendChild(inicial);

    try {

        productosCaja = await peticion(
            "/api/admin/caja/productos"
        );

        if (!Array.isArray(productosCaja)) {
            throw new Error("Formato de productos incorrecto.");
        }

        selectorProducto.replaceChildren();

        const opcion = document.createElement("option");
        opcion.value = "";
        opcion.textContent = "Selecciona un producto";

        selectorProducto.appendChild(opcion);

        productosCaja.forEach(function(producto) {

            const option = document.createElement("option");

            option.value = producto.codigo;

            option.textContent =
                producto.codigo + " | " +
                producto.nombre + " | Stock: " +
                producto.stock + " | $" +
                Number(producto.precio_venta).toFixed(2);

            selectorProducto.appendChild(option);

        });

        if (productosCaja.length === 0) {
            opcion.textContent = "No hay productos disponibles.";
        }

    } catch (error) {

        console.error("Error de productos:", error);

        selectorProducto.replaceChildren();

        const option = document.createElement("option");
        option.value = "";
        option.textContent = "Error al cargar productos.";

        selectorProducto.appendChild(option);

    }
}


/* =========================================
   INICIALIZAR
========================================= */

async function inicializarCaja() {

    await Promise.all([
        cargarCompradoresCaja(),
        cargarProductosCaja()
    ]);

}

inicializarCaja();


// =====================================================
// FAVORITOS: ABRIR Y CERRAR
// =====================================================

function abrirFavoritos() {

    if (!favoritosBar) return;

    favoritosBar.classList.add("visible");

    if (favoritosBtn) {
        favoritosBtn.setAttribute("aria-expanded", "true");
    }

    actualizarFavoritos();

}


function cerrarPanelFavoritos() {

    if (!favoritosBar) return;

    favoritosBar.classList.remove("visible");

    if (favoritosBtn) {
        favoritosBtn.setAttribute("aria-expanded", "false");
    }

}


if (favoritosBtn) {

    favoritosBtn.addEventListener("click", function () {

        if (favoritosBar.classList.contains("visible")) {
            cerrarPanelFavoritos();
        } else {
            abrirFavoritos();
        }

    });

}


if (cerrarFavoritos) {
    cerrarFavoritos.addEventListener("click", cerrarPanelFavoritos);
}
// =====================================================
// BOTÓN COMPRAR
// =====================================================

const comprarBtn = $("comprar_carrito_btn");

if (comprarBtn) {
    comprarBtn.addEventListener("click", function () {
        if (carrito.length === 0) {
            alert("Tu carrito está vacío.");
            return;
        }

        window.location.assign("/comprar");
    });
}


// =====================================================
// FINALIZAR COMPRA Y REDIRIGIR AL PROVEEDOR DE PAGO
// =====================================================

const finalizarCompraBtn = $("finalizar_compra");

if (finalizarCompraBtn) {
    finalizarCompraBtn.addEventListener("click", async function (evento) {
        evento.preventDefault();

        const formularioEnvio = $("datos_compra");

        const metodo = document.querySelector(
            'input[name="metodo_pago"]:checked'
        )?.value;

        if (!carrito.length) {
            alert("Tu carrito está vacío.");
            return;
        }

        if (!["mercado_pago", "paypal"].includes(metodo)) {
            alert("Selecciona Mercado Pago o PayPal.");
            return;
        }

        if (formularioEnvio && !formularioEnvio.reportValidity()) {
            return;
        }

        const envio = {
            envio_metodo: $("metodo_envio")?.value || "",
            direccion: $("direccion")?.value?.trim() || "",
            codigo_postal: $("codigo_postal")?.value?.trim() || "",
            ciudad: $("ciudad")?.value?.trim() || "",
            estado: $("estado")?.value?.trim() || ""
        };

        const textoOriginal = finalizarCompraBtn.textContent;

        finalizarCompraBtn.disabled = true;
        finalizarCompraBtn.textContent = "Preparando pago...";

        try {
            // 1. Crear pedido pendiente en Linneo
            const pedido = await peticion("/api/pedidos", {
                method: "POST",
                body: JSON.stringify({
                    metodo_pago: metodo,
                    envio: envio,
                    productos: carrito.map(producto => ({
                        id: producto.id,
                        cantidad: producto.cantidad
                    }))
                })
            });

            // 2. Crear el pago en Mercado Pago o PayPal
            const pago = await peticion("/api/pagos/iniciar", {
                method: "POST",
                body: JSON.stringify({
                    pedido_id: pedido.pedido_id
                })
            });

            if (!pago.url || !/^https:\/\//i.test(pago.url)) {
                throw new Error(
                    "El proveedor no devolvió una dirección de pago segura."
                );
            }

            // 3. Enviar al cliente al sitio del proveedor
            window.location.assign(pago.url);

        } catch (error) {
            console.error("Error al finalizar compra:", error);

            alert(
                error.message ||
                "No se pudo iniciar el pago. Inténtalo nuevamente."
            );

            finalizarCompraBtn.disabled = false;
            finalizarCompraBtn.textContent =
                textoOriginal || "Continuar al pago";
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
    // MENÚ PRINCIPAL
    // =====================================================

    if (menubtn && menu_bar) {

        menubtn.addEventListener("click", function () {

            menu_bar.classList.toggle("visible");

        });

    }

    if (atras_menu && menu_bar) {

        atras_menu.addEventListener("click", function () {

            menu_bar.classList.remove("visible");

        });

    }

    // =====================================================
    // BUSCADOR
    // =====================================================

    if (buscarBtn && busquedaDiv) {

        buscarBtn.addEventListener(
            "click",
            function () {

                busquedaDiv.classList.toggle("visible");

            }
        );

    }

    // =====================================================
    // CARRUSEL DE NOVEDADES
    // =====================================================

    const imagenesNovedades = [
        "novedades/1.jpg",
        "novedades/2.jpg",
        "novedades/3.jpg"
    ];

    let indiceNovedad = 0;

    function mostrarNovedad() {

        if (!imagenNovedades || !contadorNovedades) {
            return;
        }

        imagenNovedades.src =
            imagenesNovedades[indiceNovedad];

        imagenNovedades.alt =
            "Novedad " + (indiceNovedad + 1);

        contadorNovedades.textContent =
            (indiceNovedad + 1) +
            " de " +
            imagenesNovedades.length;

    }

    if (adelanteNovedades) {

        adelanteNovedades.addEventListener(
            "click",
            function () {

                indiceNovedad =
                    (indiceNovedad + 1) %
                    imagenesNovedades.length;

                mostrarNovedad();

            }
        );

    }

    if (atrasNovedades) {

        atrasNovedades.addEventListener(
            "click",
            function () {

                indiceNovedad =
                    (
                        indiceNovedad -
                        1 +
                        imagenesNovedades.length
                    ) % imagenesNovedades.length;

                mostrarNovedad();

            }
        );

    }

    mostrarNovedad();

    // =====================================================
    // POPUP
    // =====================================================

    if (popup) {

        popup.hidden = false;

        window.setTimeout(function () {
            popup.classList.add("visible");
        }, 700);

    }

    if (popup && cerrarPopup) {

        cerrarPopup.addEventListener(
            "click",
            function () {

                popup.classList.remove("visible");

            }
        );

    }

   
    // =====================================================
    // CHATBOT LINNEO
    // =====================================================
    

    const barraMensajes = $("bar_mensajes");
    const historialMensajes = $("historial_mensajes");
    const enviarMensajeBtn = $("enviar_mensaje_btn");
    const chatBtn = $("chat_btn");
    const chatBox = $("chat_box");
    const formChat = $("form_chat");

    let esperandoRespuesta = false;

    // Mostrar mensajes de manera segura
    function agregarMensaje(texto, clase) {

        const mensaje = document.createElement("div");

        mensaje.className = clase;
        mensaje.textContent = texto;

        historialMensajes.appendChild(mensaje);

        historialMensajes.scrollTop =
            historialMensajes.scrollHeight;

        return mensaje;
    }

    // Abrir y cerrar chatbot
    function alternarChat() {

        if (!chatBox) return;

        const abierto = chatBox.hidden;

        chatBox.hidden = !abierto;

        chatBtn.setAttribute(
            "aria-expanded",
            String(abierto)
        );

        if (abierto && barraMensajes) {
            barraMensajes.focus();
        }
    }

    if (chatBtn) {
        chatBtn.addEventListener(
            "click",
            alternarChat
        );
    }

    // Enviar mensaje
    async function enviarMensaje(evento) {

        if (evento) evento.preventDefault();

        if (
            !barraMensajes ||
            !historialMensajes ||
            esperandoRespuesta
        ) {
            return;
        }

        const texto = barraMensajes.value.trim();

        if (!texto) return;

        if (texto.length > 4000) {
            agregarMensaje(
                "El mensaje supera el límite permitido.",
                "mensaje_error"
            );
            return;
        }

        esperandoRespuesta = true;

        enviarMensajeBtn.disabled = true;

        enviarMensajeBtn.textContent = "Enviando...";

        barraMensajes.disabled = true;

        agregarMensaje(
            "Tú: " + texto,
            "mensaje_usuario"
        );

        barraMensajes.value = "";

        const cargando = agregarMensaje(
            "Linneo: Escribiendo...",
            "mensaje_asistente"
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

            cargando.remove();

            if (
                typeof datos.respuesta !== "string" ||
                !datos.respuesta.trim()
            ) {
                throw new Error(
                    "Linneo no pudo generar una respuesta."
                );
            }

            agregarMensaje(
                "Linneo: " + datos.respuesta,
                "mensaje_asistente"
            );

        } catch (error) {

            cargando.remove();

            agregarMensaje(
                "Linneo: " +
                (error.message ||
                    "No pude conectarme. Inténtalo nuevamente."),
                "mensaje_error"
            );

        } finally {

            esperandoRespuesta = false;

            enviarMensajeBtn.disabled = false;

            enviarMensajeBtn.textContent = "Enviar";

            barraMensajes.disabled = false;

            barraMensajes.focus();

        }
    }

    // El formulario controla el envío
    if (formChat) {

        formChat.addEventListener(
            "submit",
            enviarMensaje
        );

    }
    


    // =====================================================
    // CONTROL DE STOCK
    // =====================================================

    document.querySelectorAll(
        ".tarjeta_producto"
    ).forEach(function (producto) {

        const stockElemento =
            producto.querySelector(".producto_stock");

        const indicador =
            producto.querySelector(".disponibilidad_favicon");

        const botonCarrito =
            producto.querySelector(".agregar-carrito");

        if (!stockElemento) return;

        const stock = Number(
            stockElemento.textContent
                .replace(/Stock:/i, "")
                .trim()
        );

        if (!Number.isFinite(stock)) return;

        if (indicador) {

            indicador.style.backgroundColor =
                stock <= 0
                    ? "red"
                    : "var(--verde-musgo)";

        }

        if (botonCarrito) {

            botonCarrito.disabled = stock <= 0;

            if (stock <= 0) {
                botonCarrito.textContent =
                    "Sin existencias";
            }

        }

    });

    // =====================================================
    // CATEGORÍAS DE LA PORTADA
    // =====================================================

    const botonesPortada = document.querySelectorAll(
        ".botones_catalogo"
    );

    const seccionProductos = $("productos");

    const categorias = {

        mariposas_btn: ["mariposa", "mariposas"],

        escarabajos_btn: [
            "escarabajo",
            "escarabajos"
        ],

        odonatos_btn: [
            "odonato",
            "odonatos",
            "libelula",
            "libelulas"
        ],

        fosiles_btn: [
            "fosil",
            "fosiles"
        ],

        esqueletos_btn: [
            "esqueleto",
            "esqueletos"
        ],

        minerales_btn: [
            "mineral",
            "minerales"
        ]

    };

    botonesPortada.forEach(function (boton) {

        boton.addEventListener("click", function () {

            const terminos =
                categorias[boton.id] || [];

            const tarjetas = document.querySelectorAll(
                "#productos .tarjeta_producto"
            );

            if (tarjetas.length === 0) {
                window.location.href = "/catalogo";
                return;
            }

            let coincidencias = 0;

            tarjetas.forEach(function (tarjeta) {

                const texto = normalizarTexto(
                    tarjeta.dataset.categoria +
                    " " +
                    tarjeta.dataset.nombre
                );

                const coincide = terminos.some(
                    termino => texto.includes(
                        normalizarTexto(termino)
                    )
                );

                tarjeta.hidden = !coincide;

                if (coincide) coincidencias++;

            });

            if (seccionProductos) {

                seccionProductos.scrollIntoView({
                    behavior: "smooth"
                });

            }

            let aviso = $("aviso_filtro_portada");

            if (!aviso && seccionProductos) {

                aviso = document.createElement("p");
                aviso.id = "aviso_filtro_portada";

                seccionProductos.before(aviso);

            }

            if (aviso) {

                aviso.textContent = coincidencias
                    ? "Se encontraron " +
                      coincidencias +
                      " productos."
                    : "No hay productos de esta categoría en la portada.";

            }

        });

    });

// ================================================
// PROMOCIONES: ADMINISTRADOR
// ================================================

/* =========================================
   CUPONES
========================================= */

const formularioCupones = document.getElementById("form_cupones");

const mensajeCupones = document.getElementById("mensaje_cupones");

const listaCupones = document.getElementById("lista_cupones");

const cuponGenerado = document.getElementById("cupon_generado");

async function cargarPromocionesAdmin() {
    if (!listaPromocionesAdmin) return;

    try {
        const promociones = await peticion("/api/admin/promociones");

        if (!Array.isArray(promociones)) {
            throw new Error("La API no devolvió una lista de promociones.");
        }

        listaPromocionesAdmin.replaceChildren();

        if (promociones.length === 0) {
            listaPromocionesAdmin.textContent =
                "No hay promociones registradas.";
            return;
        }

        promociones.forEach(function(promo) {
            const tarjeta = document.createElement("div");
            tarjeta.className = "tarjeta-promocion-admin";

            const nombre = document.createElement("p");
            nombre.textContent =
                `${promo.nombre || "Producto"} - ${promo.descuento}% de descuento`;

            const codigo = document.createElement("p");
            codigo.textContent =
                "Código: " + (promo.producto_codigo || promo.codigo || "");

            const estado = document.createElement("p");
            estado.textContent =
                promo.activa === false
                    ? "Estado: Desactivada"
                    : "Estado: Registrada";

            const eliminar = document.createElement("button");
            eliminar.type = "button";
            eliminar.textContent = "Eliminar promoción";

            eliminar.addEventListener("click", async function() {
                if (!confirm("¿Eliminar esta promoción?")) return;

                eliminar.disabled = true;

                try {
                    await peticion(
                        "/api/admin/promociones/" +
                        encodeURIComponent(promo.id),
                        { method: "DELETE" }
                    );

                    await cargarPromocionesAdmin();

                    if (mensajePromocion) {
                        mensajePromocion.textContent =
                            "Promoción eliminada correctamente.";
                    }

                } catch(error) {
                    alert(error.message);
                    eliminar.disabled = false;
                }
            });

            tarjeta.append(nombre, codigo, estado, eliminar);
            listaPromocionesAdmin.appendChild(tarjeta);
        });

    } catch(error) {
        console.error("Error al cargar promociones:", error);

        if (mensajePromocion) {
            mensajePromocion.textContent = error.message;
        }
    }
}


// CREAR PROMOCIÓN

if (formularioPromocion) {
    formularioPromocion.addEventListener("submit", async function(evento) {
        evento.preventDefault();

        const codigo = $("codigo_promocion")?.value.trim();
        const descuento = Number($("descuento_promocion")?.value);
        const inicioValor = $("inicio_promocion")?.value;
        const finValor = $("fin_promocion")?.value;

        if (!codigo || !inicioValor || !finValor) {
            if (mensajePromocion) {
                mensajePromocion.textContent =
                    "Completa todos los campos.";
            }
            return;
        }

        const inicio = new Date(inicioValor);
        const fin = new Date(finValor);

        if (
            !Number.isFinite(descuento) ||
            descuento <= 0 ||
            descuento > 100 ||
            Number.isNaN(inicio.getTime()) ||
            Number.isNaN(fin.getTime()) ||
            fin <= inicio
        ) {
            if (mensajePromocion) {
                mensajePromocion.textContent =
                    "Revisa el descuento y las fechas.";
            }
            return;
        }

        const datos = {
            codigo: codigo,
            descuento: descuento,
            inicio: inicio.toISOString(),
            fin: fin.toISOString()
        };

        try {
            if (mensajePromocion) {
                mensajePromocion.textContent = "Guardando promoción...";
            }

            const resultado = await peticion(
                "/api/admin/promociones",
                {
                    method: "POST",
                    body: JSON.stringify(datos)
                }
            );

            if (mensajePromocion) {
                mensajePromocion.textContent =
                    resultado.mensaje ||
                    "Promoción creada correctamente.";
            }

            formularioPromocion.reset();

            await cargarPromocionesAdmin();

            // Actualizar también las ofertas de la tienda
            await cargarOfertas();

        } catch(error) {
            console.error("Error al crear promoción:", error);

            if (mensajePromocion) {
                mensajePromocion.textContent = error.message;
            }
        }
    });
}


// ================================================
// PROMOCIONES: TIENDA
// ================================================

const contenedorOfertas = $("productos_promocion");

async function cargarOfertas() {
    if (!contenedorOfertas) return;

    try {
        contenedorOfertas.textContent = "Cargando ofertas...";

        const promociones = await peticion("/api/promociones");

        if (!Array.isArray(promociones)) {
            throw new Error("La API de ofertas devolvió un formato incorrecto.");
        }

        contenedorOfertas.replaceChildren();

        if (promociones.length === 0) {
            contenedorOfertas.textContent =
                "No hay ofertas disponibles actualmente.";
            return;
        }

        promociones.forEach(function(promo) {

            const codigo = promo.codigo || promo.producto_codigo;

            if (
                !codigo ||
                !promo.nombre ||
                !Number.isFinite(Number(promo.precio_oferta))
            ) {
                console.error("Promoción con datos incompletos:", promo);
                return;
            }

            const tarjeta = document.createElement("article");
            tarjeta.className = "tarjeta_producto tarjeta_oferta";

            const nombre = document.createElement("h3");
            nombre.textContent = promo.nombre;

            const precioOriginal = document.createElement("p");
            precioOriginal.textContent =
                "Precio original: " +
                formatoPrecio(promo.precio_original);

            const descuento = document.createElement("p");
            descuento.textContent =
                "¡" + promo.descuento + "% de descuento!";

            const precioOferta = document.createElement("p");
            precioOferta.textContent =
                "Precio de oferta: " +
                formatoPrecio(promo.precio_oferta);

            const boton = document.createElement("button");
            boton.type = "button";
            boton.className = "agregar-carrito";
            boton.textContent = "Agregar al carrito";

            boton.dataset.productoId = codigo;
            boton.dataset.productoNombre = promo.nombre;
            boton.dataset.productoPrecio = promo.precio_oferta;
            boton.dataset.productoStock = promo.stock;

            if (Number(promo.stock) <= 0) {
                boton.disabled = true;
                boton.textContent = "Sin existencias";
            }

            tarjeta.append(
                nombre,
                precioOriginal,
                descuento,
                precioOferta,
                boton
            );

            contenedorOfertas.appendChild(tarjeta);
        });

        if (contenedorOfertas.children.length === 0) {
            contenedorOfertas.textContent =
                "No se encontraron ofertas con datos válidos.";
        }

    } catch(error) {
        console.error("Error al cargar ofertas:", error);

        contenedorOfertas.textContent =
            "No se pudieron cargar las ofertas: " + error.message;
    }
}


// EVENTOS DE LOS BOTONES CREADOS DINÁMICAMENTE

if (contenedorOfertas) {
    contenedorOfertas.addEventListener("click", function(evento) {

        const boton = evento.target.closest(".agregar-carrito");

        if (!boton || !contenedorOfertas.contains(boton)) return;

        agregarAlCarrito(
            boton.dataset.productoId,
            boton.dataset.productoNombre,
            boton.dataset.productoPrecio,
            boton.dataset.productoStock
        );

        abrirCarrito();
    });
}


// INICIALIZAR

cargarPromocionesAdmin();
cargarOfertas();

    // =====================================================
    // ADMINISTRACIÓN: INVENTARIO Y USUARIOS
    // =====================================================
    //======================================================
    //FUNCIONES PEDIDO
    //======================================================
  let cantidad_ejemplares = 0;

if (paquete) {
    if (paquete.value === "individual") {
        cantidad_ejemplares = 1;
    } else if (paquete.value === "trio") {
        cantidad_ejemplares = 3;
    } else if (paquete.value === "quinteto") {
        cantidad_ejemplares = 5;
    } else {
        cantidad_ejemplares = 9;
    }
}
	
	
    
    
	const visiblidad_password_btn = document.getElementById("visiblidad_password_btn");
	const passw = document.getElementById("passw");
	function mostrar_contrasena(){
		if(passw.type=="password"){
			passw.type="text";
		}else{
			passw.type="password";
		}
		
	}
    const inventario = $("inventario_section");
    const clientes = $("clientes_section");
    const formulario = $("modificar_inv");
    const formularioStock = $("form_stock");
    const mensajeAdmin = $("mensaje_admin");
    const cancelarEdicion = $("cancelar_edicion");

    function mostrarMensaje(texto, error = false) {

        if (mensajeAdmin) {

            mensajeAdmin.textContent = texto;

            mensajeAdmin.style.color =
                error ? "red" : "inherit";

        } else {

            console.log(texto);

        }

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

    function obtenerValor(id) {
        return $(id) ? $(id).value : "";
    }

    function establecerValor(id, valor) {

        if ($(id)) {
            $(id).value = valor ?? "";
        }

    }

    async function cargarInventario() {

        if (!inventario) return;

        try {

            const productos = await peticion(
                "/api/admin/productos"
            );

            if (!Array.isArray(productos)) {
                throw new Error("Respuesta de inventario incorrecta.");
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

            productos.forEach(function (p) {

                const fila = tabla.tBodies[0].insertRow();

                [
                    p.codigo,
                    p.nombre,
                    p.categoria,
                    p.precio_compra,
                    p.precio_manofactura,
                    p.precio_venta,
                    p.stock
                ].forEach(function (valor) {

                    const celda = fila.insertCell();
                    celda.textContent = valor ?? "";

                });

                const acciones = fila.insertCell();

                const editar = document.createElement("button");
                editar.type = "button";
                editar.textContent = "Editar";

                editar.addEventListener("click", function () {

                    establecerValor("codigo_original", p.codigo);
                    establecerValor("codigo", p.codigo);
                    establecerValor("nombre", p.nombre);
                    establecerValor("categoria", p.categoria);
                    establecerValor("precio_compra", p.precio_compra);
                    establecerValor("precio_manofactura", p.precio_manofactura);
                    establecerValor("precio_venta", p.precio_venta);
                    establecerValor("stock", p.stock);

                    if ($("titulo_formulario")) {
                        $("titulo_formulario").textContent =
                            "Editar producto";
                    }

                    formulario.scrollIntoView({
                        behavior: "smooth"
                    });

                });

                const eliminar = document.createElement("button");
                eliminar.type = "button";
                eliminar.textContent = "Eliminar";

                eliminar.addEventListener("click", async function () {

                    if (!confirm("¿Eliminar el producto " + p.codigo + "?")) {
                        return;
                    }

                    try {

                        await peticion(
                            "/api/admin/productos/" +
                            encodeURIComponent(p.codigo),
                            { method: "DELETE" }
                        );

                        mostrarMensaje("Producto eliminado.");
                        await cargarInventario();

                    } catch (error) {

                        mostrarMensaje(error.message, true);

                    }

                });

                acciones.append(editar, eliminar);

            });

            inventario.appendChild(tabla);

        } catch (error) {

            mostrarMensaje(error.message, true);

        }

    }

    if (formulario) {

        formulario.addEventListener("submit", async function (evento) {

            evento.preventDefault();

            const datos = {

                codigo_original: obtenerValor("codigo_original"),
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
                    resultado.mensaje || "Producto guardado."
                );

                formulario.reset();
                establecerValor("codigo_original", "");

                if ($("titulo_formulario")) {
                    $("titulo_formulario").textContent =
                        "Añadir producto";
                }

                await cargarInventario();

            } catch (error) {

                mostrarMensaje(error.message, true);

            }

        });

    }

    if (cancelarEdicion && formulario) {

        cancelarEdicion.addEventListener("click", function () {

            formulario.reset();
            establecerValor("codigo_original", "");

            if ($("titulo_formulario")) {
                $("titulo_formulario").textContent =
                    "Añadir producto";
            }

        });

    }

    if (formularioStock) {

        formularioStock.addEventListener("submit", async function (evento) {

            evento.preventDefault();

            const codigo = obtenerValor("producto_codigo").trim();
            const cantidad = Number(
                obtenerValor("cantidad_producto")
            );

            if (!codigo || !Number.isSafeInteger(cantidad) || cantidad <= 0) {

                mostrarMensaje(
                    "Introduce un código y una cantidad válida.",
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
                            codigo: codigo,
                            cantidad: cantidad
                        })
                    }
                );

                mostrarMensaje(
                    resultado.mensaje || "Stock actualizado."
                );

                formularioStock.reset();
                await cargarInventario();

            } catch (error) {

                mostrarMensaje(error.message, true);

            }

        });

    }

    async function cargarUsuarios() {

        if (!clientes) return;

        try {

            const usuarios = await peticion(
                "/api/admin/usuarios"
            );

            if (!Array.isArray(usuarios)) {
                throw new Error("Respuesta de usuarios incorrecta.");
            }

            clientes.replaceChildren();

            clientes.appendChild(
                crearTabla(
                    ["ID", "Usuario", "Correo", "Teléfono", "Rol"],
                    usuarios.map(function (u) {
                        return [
                            u.id,
                            u.username,
                            u.email,
                            u.phone,
                            u.rol
                        ];
                    })
                )
            );

        } catch (error) {

            mostrarMensaje(error.message, true);

        }

    }

    if (inventario) cargarInventario();
    if (clientes) cargarUsuarios();

/* =========================================
   CAJA: CONFIRMAR Y REGISTRAR VENTA
========================================= */

const botonTerminarCaja = $("terminar_pago");

if (botonTerminarCaja) {

    botonTerminarCaja.addEventListener("click", async function () {
		console.log("¡Se pulsó registrar venta!");

        if (productosVenta.length === 0) {
            alert("Agrega al menos un producto a la venta.");
            return;
        }

        const canal = $("canal")?.value;
        const tipoComprador = $("tipo_comprador")?.value;
        const metodoPago = $("metodo_pago")?.value;
        const estadoPago = $("estado_pago")?.value;

        let usuarioId = null;
        let compradorNombre = "";
        let compradorContacto = "";

        if (!canal || !tipoComprador || !metodoPago || !estadoPago) {
    alert("Completa los datos de la venta.");
    return;
}

        if (tipoComprador === "registrado") {

            const compradorSeleccionado = selectorComprador?.value;

            if (!compradorSeleccionado) {
                alert("Selecciona un comprador registrado.");
                return;
            }

            usuarioId = Number(compradorSeleccionado);

            if (!Number.isSafeInteger(usuarioId) || usuarioId <= 0) {
                alert("El comprador seleccionado no es válido.");
                return;
            }

        } else if (tipoComprador === "externo") {

            compradorNombre = $("nombre_externo")?.value.trim() || "";
            compradorContacto = $("contacto_externo")?.value.trim() || "";

            if (!compradorNombre) {
                alert("Escribe el nombre del comprador.");
                return;
            }

        } else {
            alert("Selecciona un tipo de comprador válido.");
            return;
        }

        const descuento = Number(descuentoCaja.value);

        if (!Number.isFinite(descuento) || descuento < 0 || descuento > 100) {
            alert("El descuento debe estar entre 0 y 100.");
            return;
        }

        const datosVenta = {
            canal: canal,
            usuario_id: usuarioId,
            comprador_nombre: compradorNombre,
            comprador_contacto: compradorContacto,
            descuento: descuento,
            metodo_pago: metodoPago,
            estado_pago: estadoPago,

            productos: productosVenta.map(function (producto) {
                return {
                    codigo: producto.codigo,
                    cantidad: producto.cantidad
                };
            })
        };

        if (!confirm("¿Confirmas el registro de esta venta?")) {
            return;
        }

        botonTerminarCaja.disabled = true;
        botonTerminarCaja.textContent = "Registrando...";

        try {

            const resultado = await peticion(
                "/api/admin/caja/venta",
                {
                    method: "POST",
                    body: JSON.stringify(datosVenta)
                }
            );

            if (mensajeCaja) {
                mensajeCaja.textContent =
                    resultado.mensaje || "Venta registrada correctamente.";
            }

            // Limpiar la venta únicamente después del éxito.
            productosVenta = [];

            if (descuentoCaja) {
                descuentoCaja.value = 0;
            }

            actualizarTablaCaja();

            // Actualizar el catálogo y el stock mostrado.
            await cargarProductosCaja();

            // Restablecer el formulario de comprador externo.
            if ($("nombre_externo")) {
                $("nombre_externo").value = "";
            }

            if ($("contacto_externo")) {
                $("contacto_externo").value = "";
            }

        } catch (error) {

            if (mensajeCaja) {
                mensajeCaja.textContent =
                    error.message || "No se pudo registrar la venta.";
            }

            console.error("Error al registrar la venta:", error);

        } finally {

            botonTerminarCaja.disabled = false;
            botonTerminarCaja.textContent = "Terminar pago";

        }

    });

}

    // =====================================================
    // CHATBOT Y NAVEGACIÓN
    // =====================================================


    if (chatBtn) {

        chatBtn.addEventListener("click", function () {

            window.location.href = "/chatbox";

        });

    }
    const tipoCompradorSelect = $("tipo_comprador");
const compradorRegistrado = $("comprador_registrado");
const compradorExterno = $("comprador_externo");

function actualizarTipoComprador() {
    if (!tipoCompradorSelect || !compradorRegistrado || !compradorExterno) {
        return;
    }

    const esExterno = tipoCompradorSelect.value === "externo";

    compradorRegistrado.hidden = esExterno;
    compradorExterno.hidden = !esExterno;

    // Evita que se envíen datos del comprador que no corresponde.
    const selector = $("comprador");
    const nombre = $("nombre_externo");

    if (selector) {
        selector.disabled = esExterno;
    }

    if (nombre) {
        nombre.required = esExterno;
    }
}

if (tipoCompradorSelect) {
    tipoCompradorSelect.addEventListener(
        "change",
        actualizarTipoComprador
    );

    actualizarTipoComprador();
}
       

/* =========================================
   PEDIDOS PERSONALIZADOS LINNEO
========================================= */


const cantidades = document.querySelectorAll(
    ".cantidad_especie"
);

const filtros = document.querySelectorAll(
    ".filtro_especie"
);

const contador = $("contador_especies");
const limiteTexto = $("limite_especies");
const mensajeEspecies = $("mensaje_especies");

const alineacion = $("alineacion_especies");
const colorMarco = $("color_marco");
const vistaPrevia = $("vista_previa_marco");

const formularioPedido = $("form_pedido_personalizado");
const botonConfirmar = $("confirmar_pedido");
const mensajePedido = $("mensaje_pedido");

const limites = {
    individual: 1,
    trio: 3,
    quinteto: 5
};

function obtenerLimite() {
    return limites[paquete.value] || 1;
}

function obtenerTotal() {
    return Array.from(cantidades).reduce(
        (total, input) => {
            return total + (Number(input.value) || 0);
        },
        0
    );
}

/* =========================================
   DISTRIBUCIÓN AUTOMÁTICA
========================================= */

function distribucionAutomatica() {

    const cantidad = obtenerLimite();

    if (cantidad === 1) {
        alineacion.value = "vertical";
    } else if (cantidad === 3) {
        alineacion.value = "horizontal";
    } else {
        alineacion.value = "diagonal";
    }

}

/* =========================================
   CONTROLAR CANTIDADES
========================================= */

function actualizarCantidades(inputModificado = null) {

    const limite = obtenerLimite();

    let total = obtenerTotal();

    if (total > limite && inputModificado) {

        const diferencia = total - limite;

        inputModificado.value = Math.max(
            0,
            Number(inputModificado.value) - diferencia
        );

    }

    cantidades.forEach(function(input) {

        const stock = Math.max(
            0,
            Number(input.dataset.stock) || 0
        );

        const seleccionados = obtenerTotal();

        const otros = seleccionados -
            (Number(input.value) || 0);

        const disponibles = Math.max(
            0,
            Math.min(stock, limite - otros)
        );

        input.max = disponibles;

        input.disabled =
            disponibles === 0 &&
            Number(input.value) === 0;

    });

    const seleccionados = obtenerTotal();

    contador.textContent =
        `Seleccionados: ${seleccionados} / ${limite}`;

    limiteTexto.textContent =
        `Puedes seleccionar hasta ${limite} ejemplar(es).`;

    if (seleccionados === limite) {

        mensajeEspecies.textContent =
            "¡Has completado tu paquete!";

    } else {

        mensajeEspecies.textContent =
            `Puedes seleccionar ${limite - seleccionados} ejemplar(es) más.`;

    }

    actualizarVistaPrevia();

}

/* =========================================
   CAMBIAR PAQUETE
========================================= */

if (paquete) {

    paquete.addEventListener("change", function() {

        const limite = obtenerLimite();

        let restantes = limite;

        cantidades.forEach(function(input) {

            const actual = Number(input.value) || 0;

            const stock = Math.max(
                0,
                Number(input.dataset.stock) || 0
            );

            const permitido = Math.min(
                actual,
                stock,
                restantes
            );

            input.value = permitido;

            restantes -= permitido;

        });

        distribucionAutomatica();

        actualizarCantidades();

    });

}

/* =========================================
   CAMBIAR CANTIDADES
========================================= */

cantidades.forEach(function(input) {

    input.addEventListener("input", function() {

        const limite = obtenerLimite();

        const stock = Math.max(
            0,
            Number(this.dataset.stock) || 0
        );

        const otros = obtenerTotal() -
            (Number(this.value) || 0);

        let cantidad = Number(this.value);

        if (!Number.isSafeInteger(cantidad) || cantidad < 0) {
            cantidad = 0;
        }

        const maximo = Math.max(
            0,
            Math.min(stock, limite - otros)
        );

        this.value = Math.min(cantidad, maximo);

        actualizarCantidades(this);

    });

});

/* =========================================
   VISTA PREVIA DEL MARCO
========================================= */

function actualizarVistaPrevia() {

    if (!vistaPrevia) return;

    vistaPrevia.replaceChildren();

    const claseColor = colorMarco.value;
    const claseAlineacion = alineacion.value;

    vistaPrevia.className =
        `marco-preview ${claseColor} ${claseAlineacion}`;

    let seleccionados = [];

    cantidades.forEach(function(input) {

        const cantidad = Number(input.value) || 0;

        for (let i = 0; i < cantidad; i++) {

            seleccionados.push({
                nombre: input.dataset.nombre || "Ejemplar"
            });

        }

    });

    if (seleccionados.length === 0) {

        const texto = document.createElement("p");

        texto.textContent =
            "Selecciona tus especies para visualizar el marco.";

        vistaPrevia.appendChild(texto);

        return;

    }

    seleccionados.forEach(function(especie) {

        const ejemplar = document.createElement("div");

        ejemplar.className = "ejemplar-preview";

        ejemplar.textContent = especie.nombre;

        vistaPrevia.appendChild(ejemplar);

    });

}

/* =========================================
   CAMBIAR DISTRIBUCIÓN Y COLOR
========================================= */

if (alineacion) {
    alineacion.addEventListener(
        "change",
        actualizarVistaPrevia
    );
}

if (colorMarco) {
    colorMarco.addEventListener(
        "change",
        actualizarVistaPrevia
    );
}

/* =========================================
   FILTRAR ESPECIES
========================================= */

filtros.forEach(function(boton) {

    boton.addEventListener("click", function() {

        const categoria = this.dataset.categoria;

        filtros.forEach(function(filtro) {
            filtro.classList.remove("activo");
        });

        this.classList.add("activo");

        document.querySelectorAll(".tarjeta_especie")
            .forEach(function(tarjeta) {

                tarjeta.hidden =
                    tarjeta.dataset.categoria !== categoria;

            });

    });

});

/* =========================================
   VALIDAR Y ENVIAR PEDIDO
========================================= */

if (formularioPedido) {

    formularioPedido.addEventListener(
        "submit",
        async function(evento) {

            evento.preventDefault();

            const total = obtenerTotal();
            const limite = obtenerLimite();

            if (total !== limite) {

                mensajePedido.textContent =
                    `Debes seleccionar exactamente ${limite} ejemplar(es).`;

                return;

            }

            const especies = [];

            cantidades.forEach(function(input) {

                const cantidad = Number(input.value) || 0;

                if (cantidad > 0) {

                    especies.push({
                        codigo: input.dataset.codigo,
                        nombre: input.dataset.nombre,
                        cantidad: cantidad
                    });

                }

            });

            const dedicatoria =
                $("texto_dedicatoria").value.trim();

            const datosPedido = {

                paquete: paquete.value,

                cantidad_ejemplares: total,

                especies: especies,

                distribucion: alineacion.value,

                color_marco: colorMarco.value,

                dedicatoria: {
                    texto: dedicatoria,
                    posicion: $("posicion_dedicatoria").value,
                    tipografia: $("tipografia").value
                }

            };

            if (!confirm(
                "¿Deseas confirmar tu pedido personalizado?"
            )) {
                return;
            }

            botonConfirmar.disabled = true;

            botonConfirmar.textContent =
                "Registrando pedido...";

            mensajePedido.textContent =
                "Enviando tu pedido...";

            try {

                const resultado = await peticion(
                    "/api/pedidos/personalizados",
                    {
                        method: "POST",
                        body: JSON.stringify(datosPedido)
                    }
                );

                mensajePedido.textContent =
                    resultado.mensaje ||
                    "¡Tu pedido personalizado se registró correctamente!";

                if (resultado.url) {

                    window.location.assign(resultado.url);

                } else {

                    formularioPedido.reset();

                    cantidades.forEach(function(input) {
                        input.value = 0;
                    });

                    distribucionAutomatica();
                    actualizarCantidades();

                }

            } catch(error) {

                mensajePedido.textContent =
                    error.message ||
                    "No se pudo registrar el pedido.";

            } finally {

                botonConfirmar.disabled = false;

                botonConfirmar.textContent =
                    "Confirmar pedido personalizado";

            }

        }
    );

}

/* =========================================
   INICIALIZACIÓN
========================================= */

if (paquete && cantidades.length > 0) {

    distribucionAutomatica();

    actualizarCantidades();

}
   const formularioCuponesAdmin =
    document.getElementById("form_cupones");

    const mensajeCuponesAdmin = document.getElementById("mensaje_cupones");

    const lista = document.getElementById("lista_cupones");

    const generado = document.getElementById("cupon_generado");

    if (!formularioCuponesAdmin || !lista) return;

    const csrf = document.querySelector(
        'meta[name="csrf-token"]'
    )?.content;

    async function cargarCupones() {

        try {

            const respuesta = await fetch(
                "/api/admin/cupones"
            );

            const datos = await respuesta.json();

            if (!respuesta.ok) {
                throw new Error(datos.error || "Error cargando cupones.");
            }

            lista.replaceChildren();

            if (!datos.length) {

                const fila = document.createElement("tr");
                const celda = document.createElement("td");

                celda.colSpan = 5;
                celda.textContent = "No hay cupones registrados.";

                fila.appendChild(celda);
                lista.appendChild(fila);

                return;
            }

            datos.forEach(cupon => {

                const fila = document.createElement("tr");

                const codigo = document.createElement("td");
                codigo.textContent = cupon.codigo;

                const qr = document.createElement("td");
                qr.textContent = "Ver QR al generar";

                const descuento = document.createElement("td");
                descuento.textContent = cupon.descuento + "%";

                const categoria = document.createElement("td");
                categoria.textContent = cupon.categoria;

                const estado = document.createElement("td");

                estado.textContent = cupon.utilizado
                    ? "Utilizado"
                    : cupon.activo
                        ? "Disponible"
                        : "Desactivado";

                fila.append(
                    codigo,
                    qr,
                    descuento,
                    categoria,
                    estado
                );

                lista.appendChild(fila);

            });

        } catch (error) {

            mensajeCuponesAdmin.textContent = error.message;

        }

    }

    formularioCuponesAdmin.addEventListener("submit", async function (evento) {

        evento.preventDefault();

        mensaje.textContent = "Generando cupón...";

        generado.replaceChildren();

        const descuento = document.getElementById(
            "cupon_descuento"
        ).value;

        const categoria = document.getElementById(
            "cupon_categoria"
        ).value;

        try {

            const respuesta = await fetch(
                "/api/admin/cupones",
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrf
                    },

                    body: JSON.stringify({
                        descuento: descuento,
                        categoria: categoria
                    })
                }
            );

            const datos = await respuesta.json();

            if (!respuesta.ok) {
                throw new Error(
                    datos.error || "No se pudo crear el cupón."
                );
            }

            mensaje.textContent = datos.mensaje;

            const titulo = document.createElement("h3");
            titulo.textContent = "Cupón generado";

            const codigo = document.createElement("p");
            codigo.textContent = "Código: " + datos.codigo;

            const imagen = document.createElement("img");

            imagen.src = "data:image/png;base64," + datos.qr;
            imagen.alt = "Código QR del cupón";
            imagen.width = 200;

            generado.append(
                titulo,
                codigo,
                imagen
            );

            formularioCuponesAdmin.reset();

            await cargarCupones();

        } catch (error) {

            mensaje.textContent = error.message;

        }

    });

    cargarCupones();


});
