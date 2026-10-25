document.addEventListener("DOMContentLoaded", function () {
    const menubtn = document.getElementById("menubtn");
    const menu_bar = document.getElementById("menu_bar");
    const atras_menu = document.getElementById("atras_menu");

    const carritobtn = document.getElementById("carritobtn");
    const carrito_bar = document.getElementById("carrito_bar");

    const buscar_btn = document.getElementById("buscarbtn");
    const busqueda_div = document.getElementById("busqueda_div");

    const filtrosbtn = document.getElementById("filtrosbtn");
    const filtro_menu = document.getElementById("filtro_menu");

    // Carrusel de novedades
    const atras_novedades = document.getElementById("atras_novedades");
    const adelante_novedades = document.getElementById("adelante_novedades");
    const imagenNovedades = document.getElementById("imagen");
    
const inventario = document.getElementById("inventario_section");
const clientes = document.getElementById("clientes_section");
const formulario = document.getElementById("modificar_inv");
const formularioStock = document.getElementById("form_stock");
const mensaje = document.getElementById("mensaje_admin");

const csrfToken = document.querySelector(
    'meta[name="csrf-token"]'
).content;

async function peticion(url, opciones = {}) {
    const respuesta = await fetch(url, {
        ...opciones,
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
            ...opciones.headers
        }
    });

    const datos = await respuesta.json().catch(() => ({}));

    if (!respuesta.ok) {
        throw new Error(
            datos.error || "No se pudo completar la operación."
        );
    }

    return datos;
}

function mostrarMensaje(texto, error = false) {
    mensaje.textContent = texto;
    mensaje.style.color = error ? "red" : "inherit";
}

function crearTabla(columnas, filas) {
    const tabla = document.createElement("table");
    const cabecera = tabla.createTHead().insertRow();

    for (const columna of columnas) {
        const th = document.createElement("th");
        th.textContent = columna;
        cabecera.appendChild(th);
    }

    const cuerpo = tabla.createTBody();

    for (const valores of filas) {
        const fila = cuerpo.insertRow();

        for (const valor of valores) {
            const celda = fila.insertCell();
            celda.textContent = valor == null ? "" : String(valor);
        }
    }

    return tabla;
}

function boton(texto, accion) {
    const elemento = document.createElement("button");
    elemento.type = "button";
    elemento.textContent = texto;
    elemento.addEventListener("click", accion);
    return elemento;
}

// ---------------- INVENTARIO ----------------

async function cargarInventario() {
    try {
        const productos = await peticion(
            "/api/admin/productos"
        );

        inventario.replaceChildren();

        const tabla = crearTabla(
            [
                "Código", "Nombre", "Categoría",
                "Compra", "Producción", "Venta", "Stock",
                "Acciones"
            ],
            []
        );

        const cuerpo = tabla.tBodies[0];

        for (const p of productos) {
            const fila = cuerpo.insertRow();

            const valores = [
                p.codigo,
                p.nombre,
                p.categoria,
                p.precio_compra,
                p.precio_manofactura,
                p.precio_venta,
                p.stock
            ];

            for (const valor of valores) {
                const celda = fila.insertCell();
                celda.textContent = String(valor ?? "");
            }

            const acciones = fila.insertCell();

            acciones.appendChild(
                boton("Editar", () => editarProducto(p))
            );

            acciones.appendChild(
                boton("Eliminar", () => eliminarProducto(p.codigo))
            );
        }

        inventario.appendChild(tabla);

    } catch (error) {
        mostrarMensaje(error.message, true);
    }
}

function editarProducto(p) {
    document.getElementById("codigo_original").value = p.codigo;
    document.getElementById("codigo").value = p.codigo;
    document.getElementById("nombre").value = p.nombre;
    document.getElementById("categoria").value = p.categoria;

    document.getElementById("precio_compra").value = p.precio_compra;
    document.getElementById("precio_manofactura").value =
        p.precio_manofactura;
    document.getElementById("precio_venta").value = p.precio_venta;
    document.getElementById("stock").value = p.stock;

    document.getElementById("titulo_formulario").textContent =
        "Editar producto";

    formulario.scrollIntoView({ behavior: "smooth" });
}

formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();

    const datos = {
        codigo_original:
            document.getElementById("codigo_original").value,
        codigo: document.getElementById("codigo").value.trim(),
        nombre: document.getElementById("nombre").value.trim(),
        categoria: document.getElementById("categoria").value.trim(),
        precio_compra:
            document.getElementById("precio_compra").value,
        precio_manofactura:
            document.getElementById("precio_manofactura").value,
        precio_venta:
            document.getElementById("precio_venta").value,
        stock: document.getElementById("stock").value
    };

    try {
        const resultado = await peticion(
            "/api/admin/productos",
            {
                method: "POST",
                body: JSON.stringify(datos)
            }
        );

        mostrarMensaje(resultado.mensaje);
        formulario.reset();
        document.getElementById("codigo_original").value = "";
        document.getElementById("titulo_formulario").textContent =
            "Añadir producto";

        await cargarInventario();

    } catch (error) {
        mostrarMensaje(error.message, true);
    }
});

async function eliminarProducto(codigo) {
    if (!confirm(`¿Eliminar el producto ${codigo}?`)) {
        return;
    }

    try {
        const resultado = await peticion(
            `/api/admin/productos/${encodeURIComponent(codigo)}`,
            { method: "DELETE" }
        );

        mostrarMensaje(resultado.mensaje);
        await cargarInventario();

    } catch (error) {
        mostrarMensaje(error.message, true);
    }
}

document.getElementById("cancelar_edicion")
    .addEventListener("click", () => {
        formulario.reset();
        document.getElementById("codigo_original").value = "";
        document.getElementById("titulo_formulario").textContent =
            "Añadir producto";
    });

// ---------------- AÑADIR STOCK ----------------

formularioStock.addEventListener("submit", async (evento) => {
    evento.preventDefault();

    const codigo = document.getElementById("producto_codigo")
        .value.trim();

    const cantidad = Number(
        document.getElementById("cantidad_producto").value
    );

    if (!Number.isSafeInteger(cantidad) || cantidad <= 0) {
        mostrarMensaje("Introduce una cantidad entera positiva.", true);
        return;
    }

    try {
        const resultado = await peticion("/api/admin/stock", {
            method: "POST",
            body: JSON.stringify({ codigo, cantidad })
        });

        mostrarMensaje(resultado.mensaje);
        formularioStock.reset();
        await cargarInventario();

    } catch (error) {
        mostrarMensaje(error.message, true);
    }
});

// ---------------- USUARIOS ----------------

async function cargarUsuarios() {
    try {
        const usuarios = await peticion("/api/admin/usuarios");

        clientes.replaceChildren();

        const tabla = crearTabla(
            ["ID", "Usuario", "Correo", "Teléfono", "Rol"],
            usuarios.map(u => [
                u.id, u.username, u.email, u.phone, u.rol
            ])
        );

        clientes.appendChild(tabla);

    } catch (error) {
        mostrarMensaje(error.message, true);
    }
}

// Inicialización del panel.
cargarInventario();
cargarUsuarios();

    const contadorNovedades = document.getElementById("contador");

    const imagenes = [
        "novedades/1.jpg",
        "novedades/2.jpg",
        "novedades/3.jpg"
    ];

    let indice = 0;

    function mostrarImagen() {
        if (!imagenNovedades || !contadorNovedades) {
            return;
        }

        imagenNovedades.src = imagenes[indice];
        imagenNovedades.alt = "Novedad " + (indice + 1);
        contadorNovedades.textContent =
            `Imagen ${indice + 1} de ${imagenes.length}`;
    }

    function siguiente() {
        indice = (indice + 1) % imagenes.length;
        mostrarImagen();
    }

    function anterior() {
        indice = (indice - 1 + imagenes.length) % imagenes.length;
        mostrarImagen();
    }

    if (adelante_novedades) {
        adelante_novedades.addEventListener("click", siguiente);
    }

    if (atras_novedades) {
        atras_novedades.addEventListener("click", anterior);
    }

    mostrarImagen();

    // Navegación
    const chatbtn = document.getElementById("chat_btn");

    if (chatbtn) {
        chatbtn.addEventListener("click", function () {
            window.location.href = "/chatbox";
        });
    }

    const cantidad_productos =
        document.getElementById("cantidad_productos");

    const iniciar_secion_btn =
        document.getElementById("iniciar_secion_btn");

    const registrarse_btn =
        document.getElementById("registrarse_btn");

    if (iniciar_secion_btn) {
        iniciar_secion_btn.addEventListener("click", function () {
            window.location.href = "/iniciar_sesion";
        });
    }

    if (registrarse_btn) {
        registrarse_btn.addEventListener("click", function () {
            window.location.href = "/registrarse";
        });
    }

    const botonesCategoria = document.querySelectorAll(
        ".sec_btn[data-categoria]"
    );

    const productos = document.querySelectorAll(
        ".tarjeta_producto, #producto"
    );

    const botonesCarrito =
        document.querySelectorAll(".agregar-carrito");

    function llevar_pag(pagina) {
        window.location.href = pagina;
    }

      // POPUP DE DESCUENTO
    const popup =
        document.getElementById("popup") ||
        document.querySelector(".popup");

    const cerrarPopupBtn =
        document.getElementById("quitar_popup");

    if (popup) {
        // Asegurar que el popup pueda mostrarse.
        popup.hidden = false;

        window.setTimeout(function () {
            popup.classList.add("visible");
        }, 700);
    } else {
        console.warn(
            "No se encontró el popup. Revisa el HTML."
        );
    }

    if (popup && cerrarPopupBtn) {
        cerrarPopupBtn.addEventListener("click", function () {
            popup.classList.remove("visible");
        });
    }

    // Chatbot
    const barraMensajes =
        document.getElementById("bar_mensajes");

    const historialMensajes =
        document.getElementById("historial_mensajes");

    const enviarMensajeBtn =
        document.getElementById("enviar_mensaje_btn");

    async function enviarMensaje() {
        if (!barraMensajes || !historialMensajes) {
            return;
        }

        const mensaje = barraMensajes.value.trim();

        if (!mensaje) {
            return;
        }

        const mensajeUsuario = document.createElement("div");
        mensajeUsuario.classList.add("mensaje_usuario");
        mensajeUsuario.textContent = "Tú: " + mensaje;

        historialMensajes.appendChild(mensajeUsuario);
        barraMensajes.value = "";

        const mensajeCargando = document.createElement("div");
        mensajeCargando.classList.add("mensaje_asistente");
        mensajeCargando.textContent = "Linneo: Escribiendo...";

        historialMensajes.appendChild(mensajeCargando);
        historialMensajes.scrollTop =
            historialMensajes.scrollHeight;

        try {
            const respuesta = await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    mensaje: mensaje
                })
            });

            const data = await respuesta.json();
            mensajeCargando.remove();

            if (!respuesta.ok) {
                const error = document.createElement("div");
                error.classList.add("mensaje_error");
                error.textContent =
                    "Error: " +
                    (data.error ||
                        "No se pudo procesar el mensaje.");

                historialMensajes.appendChild(error);
                return;
            }

            const mensajeAsistente =
                document.createElement("div");

            mensajeAsistente.classList.add("mensaje_asistente");
            mensajeAsistente.textContent =
                "Linneo: " + (data.respuesta || "");

            historialMensajes.appendChild(mensajeAsistente);
            historialMensajes.scrollTop =
                historialMensajes.scrollHeight;

        } catch (error) {
            console.error("Error del chatbot:", error);
            mensajeCargando.remove();

            const mensajeError = document.createElement("div");
            mensajeError.classList.add("mensaje_error");
            mensajeError.textContent =
                "No se pudo conectar con Linneo.";

            historialMensajes.appendChild(mensajeError);
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
            if (evento.key === "Enter") {
                evento.preventDefault();
                enviarMensaje();
            }
        });
    }

    // Carrito guardado en el navegador
    let carrito = [];

    try {
        const carritoGuardado = JSON.parse(
            localStorage.getItem("linneoCarrito") || "[]"
        );

        if (Array.isArray(carritoGuardado)) {
            carrito = carritoGuardado;
        }
    } catch (error) {
        carrito = [];
    }

    const contenidoCarrito =
        document.getElementById("contenido_carrito");

    const precioCarrito =
        document.getElementById("productos_carrito_precio");

    const listaCarrito =
        document.getElementById("lista_carrito");

    function actualizarCarrito() {
        let subtotal = 0;

        if (listaCarrito) {
            listaCarrito.innerHTML = "";
        }

        if (contenidoCarrito) {
            contenidoCarrito.innerHTML = "";
        }

        carrito.forEach(function (producto) {
            const cantidad = producto.cantidad || 1;
            const precio = Number(producto.precio) || 0;
            const totalProducto = precio * cantidad;

            subtotal += totalProducto;

            if (listaCarrito) {
                const fila = document.createElement("tr");

                const celdaNombre = document.createElement("td");
                celdaNombre.textContent = producto.nombre;

                const celdaCantidad = document.createElement("td");
                celdaCantidad.textContent = cantidad;

                const celdaPrecio = document.createElement("td");
                celdaPrecio.textContent =
                    "$" + precio.toFixed(2);

                fila.append(
                    celdaNombre,
                    celdaCantidad,
                    celdaPrecio
                );

                listaCarrito.appendChild(fila);
            }

            if (contenidoCarrito) {
                const div = document.createElement("div");
                div.classList.add("producto-carrito");

                div.textContent =
                    producto.nombre + " x " + cantidad +
                    " — $" + totalProducto.toFixed(2);

                contenidoCarrito.appendChild(div);
            }
        });

        if (carrito.length === 0 && listaCarrito) {
            const fila = document.createElement("tr");
            const celda = document.createElement("td");

            celda.colSpan = 3;
            celda.textContent = "El carrito está vacío.";

            fila.appendChild(celda);
            listaCarrito.appendChild(fila);
        }

        if (carrito.length === 0 && contenidoCarrito) {
            contenidoCarrito.textContent =
                "El carrito está vacío.";
        }

        if (precioCarrito) {
            precioCarrito.textContent =
                "$" + subtotal.toFixed(2);
        }

        if (cantidad_productos) {
            cantidad_productos.textContent =
                carrito.reduce(function (total, producto) {
                    return total + (producto.cantidad || 1);
                }, 0);
        }

        try {
            localStorage.setItem(
                "linneoCarrito",
                JSON.stringify(carrito)
            );
        } catch (error) {
            // El carrito sigue disponible durante esta visita.
        }

        const subtotalLabel =
            document.getElementById("subtotal_carrito");

        if (subtotalLabel) {
            subtotalLabel.textContent =
                "$" + subtotal.toFixed(2);
        }
    }

    // Agregar productos al carrito
    botonesCarrito.forEach(function (boton) {
        boton.addEventListener("click", function () {
            const nombre = boton.dataset.productoNombre;
            const precio = Number(
                boton.dataset.productoPrecio
            );

            if (!nombre || Number.isNaN(precio)) {
                console.error("Datos del producto incorrectos", {
                    nombre,
                    precio
                });
                return;
            }

            const existente = carrito.find(function (producto) {
                return producto.nombre === nombre;
            });

            if (existente) {
                existente.cantidad =
                    (existente.cantidad || 1) + 1;
            } else {
                carrito.push({
                    nombre: nombre,
                    precio: precio,
                    cantidad: 1
                });
            }

            actualizarCarrito();
        });
    });

    actualizarCarrito();
        // Control de stock
    productos.forEach(function (producto) {
        const stockElemento =
            producto.querySelector(".producto_stock");

        const disponibilidad =
            producto.querySelector(".disponibilidad_favicon");

        const botonCarrito =
            producto.querySelector(".agregar-carrito");

        if (!stockElemento) {
            return;
        }

        const stock = Number(
            stockElemento.textContent
                .replace("Stock:", "")
                .trim()
        );

        if (disponibilidad) {
            disponibilidad.style.backgroundColor =
                stock <= 0 ? "red" : "var(--verde-musgo)";
        }

        if (botonCarrito && stock <= 0) {
            botonCarrito.disabled = true;
            botonCarrito.style.display = "none";
        }
    });

    // Filtros y orden del catálogo
    const contenedorCatalogo =
        document.getElementById("catalogo");

    const opcionesOrden =
        document.querySelectorAll('input[name="orden"]');

    let categoriaSeleccionada = "";
    let ordenSeleccionado = "";

    function normalizarTexto(texto) {
        return String(texto || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .trim()
            .toLocaleLowerCase("es");
    }

    function aplicarFiltros() {
        if (!contenedorCatalogo) {
            return;
        }

        const tarjetas = Array.from(
            contenedorCatalogo.querySelectorAll(
                ".tarjeta_producto"
            )
        );

        tarjetas.forEach(function (producto) {
            const categoriaProducto = normalizarTexto(
                producto.dataset.categoria
            );

            const coincideCategoria =
                !categoriaSeleccionada ||
                categoriaProducto ===
                    normalizarTexto(categoriaSeleccionada);

            producto.hidden = !coincideCategoria;
        });

        const tarjetasOrdenadas = [...tarjetas];

        tarjetasOrdenadas.sort(function (a, b) {
            const nombreA = normalizarTexto(a.dataset.nombre);
            const nombreB = normalizarTexto(b.dataset.nombre);

            const precioA = Number(a.dataset.precio) || 0;
            const precioB = Number(b.dataset.precio) || 0;

            switch (ordenSeleccionado) {
                case "alfabetico":
                    return nombreA.localeCompare(nombreB, "es");

                case "mayorprecio":
                    return precioB - precioA;

                case "menorprecio":
                    return precioA - precioB;

                default:
                    return 0;
            }
        });

        tarjetasOrdenadas.forEach(function (producto) {
            contenedorCatalogo.appendChild(producto);
        });
    }

    botonesCategoria.forEach(function (boton) {
        boton.addEventListener("click", function () {
            categoriaSeleccionada =
                boton.dataset.categoria || "";

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

    // Buscador desplegable
    if (buscar_btn && busqueda_div) {
        buscar_btn.addEventListener("click", function () {
            busqueda_div.classList.toggle("visible");
        });
    }

    // Menú de filtros
    if (filtrosbtn && filtro_menu) {
        filtrosbtn.addEventListener("click", function () {
            filtro_menu.hidden = !filtro_menu.hidden;

            filtrosbtn.setAttribute(
                "aria-expanded",
                String(!filtro_menu.hidden)
            );
        });
    }

    // Menú principal
    function desplegar_menu() {
        if (menu_bar) {
            menu_bar.classList.toggle("visible");
        }
    }

    if (menubtn && menu_bar) {
        menubtn.addEventListener("click", desplegar_menu);
    }

    if (atras_menu && menu_bar) {
        atras_menu.addEventListener("click", desplegar_menu);
    }

    // Panel del carrito
    function desplegar_carrito() {
        if (carrito_bar) {
            carrito_bar.classList.toggle("visible");
        }
    }

    if (carritobtn && carrito_bar) {
        carritobtn.addEventListener("click", desplegar_carrito);
    }

    // Categorías de la portada
    const botonesPortada =
        document.querySelectorAll(".botones_catalogo");

    const seccionProductos =
        document.getElementById("productos");

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

    botonesPortada.forEach(function (boton) {
        boton.addEventListener("click", function () {
            const terminos = categoriasPortada[boton.id] || [];

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
                    return texto.includes(termino);
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

            let aviso = document.getElementById(
                "aviso_filtro_portada"
            );

            if (!aviso && seccionProductos) {
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

    // Botón para ver el catálogo completo
    const catalogoBtn = document.getElementById(
        "catalogo_completo_btn"
    );

    if (catalogoBtn) {
        catalogoBtn.addEventListener("click", function () {
            window.location.href = "/catalogo";
        });
    }

    // Favoritos: aviso provisional
    const favoritosBtn =
        document.getElementById("favoritos_btn");

    if (favoritosBtn) {
        favoritosBtn.addEventListener("click", function () {
            const favoritos = document.querySelectorAll(
                ".tarjeta_producto.es-favorito"
            );

            if (favoritos.length) {
                favoritos.forEach(function (tarjeta) {
                    tarjeta.scrollIntoView({
                        behavior: "smooth",
                        block: "center"
                    });
                });
            } else {
                alert(
                    "Todavía no tienes productos favoritos. " +
                    "La lista de favoritos se puede añadir al catálogo."
                );
            }
        });
    }

    // Comprar: requiere una ruta real de checkout en Flask
    const comprarBtn = document.getElementById(
        "comprar_carrito_btn"
    );

       if (comprarBtn) {
        comprarBtn.addEventListener("click", function () {
            if (!carrito.length) {
                alert(
                    "Tu carrito está vacío. Agrega algún producto antes de continuar."
                );
                return;
            }

            alert(
                "Tu carrito tiene productos. Para finalizar la compra, " +
                "conecta este botón con la ruta de checkout de Flask."
            );
        });
    }

    // CONTROL DE STOCK
    // =========================================
    // CONTROL DE STOCK
    // =========================================

    productos.forEach(function (producto) {

        const stockElemento =
            producto.querySelector(".producto_stock");

        const disponibilidad =
            producto.querySelector(
                ".disponibilidad_favicon"
            );

        const botonCarrito =
            producto.querySelector(".agregar-carrito");


        if (!stockElemento) {
            return;
        }


        const stock = Number(
            stockElemento.textContent
                .replace("Stock:", "")
                .trim()
        );


        // =====================================
        // INDICADOR DE DISPONIBILIDAD
        // =====================================

        if (disponibilidad) {

            if (stock <= 0) {

                disponibilidad.style.backgroundColor =
                    "red";

            } else {

                disponibilidad.style.backgroundColor =
                    "var(--verde-musgo)";

            }

        }


        // =====================================
        // DESACTIVAR SI NO HAY STOCK
        // =====================================

        if (botonCarrito && stock <= 0) {

            botonCarrito.disabled = true;
            botonCarrito.style.display = "none";

        }

    });


    // =========================================
    // BUSCADOR
    // =========================================

    if (buscar_btn && busqueda_div) {

        buscar_btn.addEventListener(
            "click",
            function () {

                busqueda_div.classList.toggle(
                    "visible"
                );

            }
        );

    }


    // =========================================
    // FILTROS
    // =========================================

    if (filtrosbtn && filtro_menu) {

        filtrosbtn.addEventListener(
            "click",
            function () {

                filtro_menu.hidden =
                    !filtro_menu.hidden;

                filtrosbtn.setAttribute(
                    "aria-expanded",
                    String(!filtro_menu.hidden)
                );

            }
        );

    }


    // =========================================
    // MENÚ PRINCIPAL
    // =========================================

    function desplegar_menu() {

        if (!menu_bar) {
            return;
        }

        menu_bar.classList.toggle("visible");

    }


    if (menubtn && menu_bar) {

        menubtn.addEventListener(
            "click",
            desplegar_menu
        );

    }


    if (atras_menu && menu_bar) {

        atras_menu.addEventListener(
            "click",
            desplegar_menu
        );

    }


    // =========================================
    // CARRITO
    // =========================================

    function desplegar_carrito() {

        if (!carrito_bar) {
            return;
        }

        carrito_bar.classList.toggle("visible");

    }


    if (carritobtn && carrito_bar) {

        carritobtn.addEventListener(
            "click",
            desplegar_carrito
        );

    }


});

