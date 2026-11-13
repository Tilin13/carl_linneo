
document.addEventListener("DOMContentLoaded", function () {

    // =====================================================
    // ELEMENTOS DEL HTML
    // =====================================================

    const $ = (id) => document.getElementById(id);

    const menubtn = $("menubtn");
    const menu_bar = $("menu_bar");
    const atras_menu = $("atras_menu");

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

function alternarFavorito(id, nombre, precio, stockDisponible = null) {

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
        precio < 0
    ) {
        console.error("Los datos del favorito no son válidos.");
        return;
    }

    if (esFavorito(id)) {

        favoritos = favoritos.filter(
            p => p.id !== id
        );

    } else {

        favoritos.push({
            id: id,
            nombre: nombre,
            precio: precio,
            stock: stock
        });

    }

    guardarLocalStorage("linneoFavoritos", favoritos);

    actualizarBotonesFavoritos();
    actualizarFavoritos();

}


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

function actualizarFavoritos() {

    if (!contenidoFavoritos) return;

    contenidoFavoritos.replaceChildren();

    if (favoritos.length === 0) {

        const mensaje = document.createElement("p");
        mensaje.textContent = "No tienes productos favoritos.";

        contenidoFavoritos.appendChild(mensaje);

        return;

    }

    favoritos.forEach(function (producto) {

        const tarjeta = document.createElement("div");
        tarjeta.className = "producto-favorito";

        const nombre = document.createElement("h3");
        nombre.textContent = producto.nombre;

        const precio = document.createElement("p");
        precio.textContent = formatoPrecio(producto.precio);

        const quitar = document.createElement("button");
        quitar.type = "button";
        quitar.textContent = "♥ Quitar de favoritos";

        quitar.addEventListener("click", function () {

            favoritos = favoritos.filter(
                p => p.id !== producto.id
            );

            guardarLocalStorage("linneoFavoritos", favoritos);

            actualizarFavoritos();
            actualizarBotonesFavoritos();

        });

        const agregar = document.createElement("button");
        agregar.type = "button";
        agregar.textContent = "🛒 Agregar al carrito";

        agregar.addEventListener("click", function () {

            agregarAlCarrito(
                producto.id,
                producto.nombre,
                producto.precio,
                producto.stock
            );

            abrirCarrito();

        });

        tarjeta.append(
            nombre,
            precio,
            quitar,
            agregar
        );

        contenidoFavoritos.appendChild(tarjeta);

    });

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

    comprarBtn.addEventListener("click", async function () {

        if (carrito.length === 0) {

            alert("Tu carrito está vacío.");

            return;
        }

        const confirmar = confirm(
            "¿Deseas confirmar tu compra?"
        );

        if (!confirmar) return;

        comprarBtn.disabled = true;

        comprarBtn.textContent = "Procesando...";

        try {

            const resultado = await peticion(
                "/api/pedidos",
                {
                    method: "POST",

                    body: JSON.stringify({

                        productos: carrito.map(function (producto) {

                            return {
                                id: producto.id,
                                cantidad: producto.cantidad
                            };

                        })

                    })

                }
            );

            if (!resultado.url) {

                throw new Error(
                    "No se recibió la dirección del pedido."
                );

            }

            // Vaciar carrito únicamente después de confirmar
            // que el servidor ha registrado la compra.

            carrito = [];

            actualizarCarrito();

            // Abrir los detalles del pedido.
            window.location.assign(resultado.url);

        } catch (error) {

            alert(error.message);

            comprarBtn.disabled = false;

            comprarBtn.textContent = "Comprar";

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

    // =====================================================
    // CATÁLOGO COMPLETO
    // =====================================================

    const catalogoBtn = $("catalogo_completo_btn");

    if (catalogoBtn) {

        catalogoBtn.addEventListener(
            "click",
            function () {

                window.location.href = "/catalogo";

            }
        );

    }

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
        const paquete = document.getElementById("paquete_pedido");
    const cantidades = document.querySelectorAll(".cantidad_especie");
    const filtros = document.querySelectorAll(".filtro_especie");
    
    const crear_mi_marco = document.getElementById("crear_mi_marco");
    if (crear_mi_marco) {
    crear_mi_marco.addEventListener("click", function() {
        window.location.href = "/crear_pedido";
    });}

    const contador = document.getElementById("contador_especies");
    const limiteTexto = document.getElementById("limite_especies");
    const mensaje = document.getElementById("mensaje_especies");

    if (!paquete || cantidades.length === 0) return;

    const limites = {
        individual: 1,
        trio: 3,
        quinteto: 5
    };

    function obtenerLimite() {
        return limites[paquete.value] || 1;
    }

    function obtenerTotal() {
        return Array.from(cantidades).reduce(function (total, input) {
            return total + (Number(input.value) || 0);
        }, 0);
    }

    function actualizarCantidades(inputModificado = null) {

        const limite = obtenerLimite();
        let total = obtenerTotal();

        // Si el cliente supera el límite, corregir su selección.
        if (total > limite && inputModificado) {

            const anterior = Number(inputModificado.value);

            inputModificado.value = Math.max(
                0,
                anterior - (total - limite)
            );

        }

        // Actualizar el máximo permitido para cada especie.
        cantidades.forEach(function (input) {

            const stock = Number(input.dataset.stock);
            const seleccionados = obtenerTotal();

            const disponiblesParaEstaEspecie =
                limite - (seleccionados - Number(input.value));

            input.max = Math.max(
                0,
                Math.min(stock, disponiblesParaEstaEspecie)
            );

            input.disabled =
                Number(input.max) === 0 &&
                Number(input.value) === 0;

        });

        const seleccionados = obtenerTotal();

        contador.textContent =
            "Seleccionados: " + seleccionados + " / " + limite;

        limiteTexto.textContent =
            "Puedes seleccionar hasta " + limite + " ejemplar(es).";

        if (seleccionados === limite) {
            mensaje.textContent = "¡Has completado tu paquete!";
        } else {
            mensaje.textContent =
                "Puedes seleccionar " + (limite - seleccionados) +
                " ejemplar(es) más.";
        }
    }

    // Cambiar de paquete.
    paquete.addEventListener("change", function () {

        const limite = obtenerLimite();
        let restantes = limite;

        cantidades.forEach(function (input) {

            const actual = Number(input.value);
            const stock = Number(input.dataset.stock);

            const permitido = Math.min(
                actual,
                stock,
                restantes
            );

            input.value = permitido;
            restantes -= permitido;

        });

        actualizarCantidades();
    });

    // Controlar las cantidades.
    cantidades.forEach(function (input) {

        input.addEventListener("input", function () {

            let cantidad = Number(this.value);

            if (!Number.isInteger(cantidad) || cantidad < 0) {
                cantidad = 0;
            }

            const stock = Number(this.dataset.stock);
            const limite = obtenerLimite();

            const otros = obtenerTotal() - (Number(this.value) || 0);

            const maximo = Math.max(
                0,
                Math.min(stock, limite - otros)
            );

            this.value = Math.min(cantidad, maximo);

            actualizarCantidades(this);

        });

    });

    // Filtrar por categoría.
    filtros.forEach(function (boton) {

        boton.addEventListener("click", function () {

            const categoria = this.dataset.categoria;

            filtros.forEach(function (f) {
                f.classList.remove("activo");
            });

            this.classList.add("activo");

            document.querySelectorAll(".tarjeta_especie")
                .forEach(function (tarjeta) {

                    tarjeta.hidden =
                        tarjeta.dataset.categoria !== categoria;

                });

        });

    });

    actualizarCantidades();

});
