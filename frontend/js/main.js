
document.addEventListener("DOMContentLoaded", function () {
    // =====================================================
    // ELEMENTOS GENERALES
    // =====================================================

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
    const contadorNovedades = document.getElementById("contador");

    // Administración
    const inventario = document.getElementById("inventario_section");
    const clientes = document.getElementById("clientes_section");
    const formulario = document.getElementById("modificar_inv");
    const formularioStock = document.getElementById("form_stock");
    const mensajeAdmin = document.getElementById("mensaje_admin");

    const cancelarEdicion = document.getElementById("cancelar_edicion");

    // Token CSRF. La etiqueta meta debe existir en el HTML
    // de las páginas que envían peticiones al servidor.
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.content : "";

    // =====================================================
    // PETICIONES HTTP
    // =====================================================

    async function peticion(url, opciones = {}) {
        const cabeceras = {
            "Content-Type": "application/json",
            ...opciones.headers
        };

        const metodo = (opciones.method || "GET").toUpperCase();

        if (!["GET", "HEAD", "OPTIONS"].includes(metodo)) {
            if (!csrfToken) {
                throw new Error(
                    "Falta el token CSRF. Añade la etiqueta meta csrf-token al HTML."
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

        const datos = await respuesta.json().catch(() => ({}));

        if (!respuesta.ok) {
            throw new Error(
                datos.error ||
                datos.mensaje ||
                `Error HTTP ${respuesta.status}`
            );
        }

        return datos;
    }

    function mostrarMensaje(texto, error = false) {
        if (mensajeAdmin) {
            mensajeAdmin.textContent = texto;
            mensajeAdmin.style.color = error ? "red" : "inherit";
        } else if (error) {
            console.error(texto);
        } else {
            console.info(texto);
        }
    }

    // =====================================================
    // UTILIDADES PARA TABLAS Y BOTONES
    // =====================================================

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

    function obtenerValor(id) {
        const elemento = document.getElementById(id);
        return elemento ? elemento.value : "";
    }

    function establecerValor(id, valor) {
        const elemento = document.getElementById(id);

        if (elemento) {
            elemento.value = valor ?? "";
        }
    }

    // =====================================================
    // ADMINISTRACIÓN: INVENTARIO
    // =====================================================

    async function cargarInventario() {
        if (!inventario) {
            return;
        }

        try {
            const productos = await peticion("/api/admin/productos");

            if (!Array.isArray(productos)) {
                throw new Error(
                    "La respuesta del inventario no tiene el formato esperado."
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
                    boton("Editar", function () {
                        editarProducto(p);
                    })
                );

                acciones.appendChild(
                    boton("Eliminar", function () {
                        eliminarProducto(p.codigo);
                    })
                );
            }

            inventario.appendChild(tabla);
        } catch (error) {
            mostrarMensaje(error.message, true);
        }
    }

    function editarProducto(p) {
        if (!formulario) {
            return;
        }

        establecerValor("codigo_original", p.codigo);
        establecerValor("codigo", p.codigo);
        establecerValor("nombre", p.nombre);
        establecerValor("categoria", p.categoria);

        establecerValor("precio_compra", p.precio_compra);
        establecerValor("precio_manofactura", p.precio_manofactura);
        establecerValor("precio_venta", p.precio_venta);
        establecerValor("stock", p.stock);

        const titulo = document.getElementById("titulo_formulario");

        if (titulo) {
            titulo.textContent = "Editar producto";
        }

        formulario.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
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
                    "Completa el código, el nombre y la categoría.",
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

                formulario.reset();
                establecerValor("codigo_original", "");

                const titulo = document.getElementById("titulo_formulario");

                if (titulo) {
                    titulo.textContent = "Añadir producto";
                }

                await cargarInventario();
            } catch (error) {
                mostrarMensaje(error.message, true);
            }
        });
    }

    async function eliminarProducto(codigo) {
        if (!codigo) {
            mostrarMensaje("El código del producto no es válido.", true);
            return;
        }

        if (!window.confirm(`¿Eliminar el producto ${codigo}?`)) {
            return;
        }

        try {
            const resultado = await peticion(
                `/api/admin/productos/${encodeURIComponent(codigo)}`,
                {
                    method: "DELETE"
                }
            );

            mostrarMensaje(
                resultado.mensaje || "Producto eliminado correctamente."
            );

            await cargarInventario();
        } catch (error) {
            mostrarMensaje(error.message, true);
        }
    }

    if (cancelarEdicion && formulario) {
        cancelarEdicion.addEventListener("click", function () {
            formulario.reset();
            establecerValor("codigo_original", "");

            const titulo = document.getElementById("titulo_formulario");

            if (titulo) {
                titulo.textContent = "Añadir producto";
            }
        });
    }

    // =====================================================
    // ADMINISTRACIÓN: AÑADIR STOCK
    // =====================================================

    if (formularioStock) {
        formularioStock.addEventListener("submit", async function (evento) {
            evento.preventDefault();

            const codigo = obtenerValor("producto_codigo").trim();
            const cantidad = Number(
                obtenerValor("cantidad_producto")
            );

            if (!codigo) {
                mostrarMensaje("Selecciona o escribe un código de producto.", true);
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
                const resultado = await peticion("/api/admin/stock", {
                    method: "POST",
                    body: JSON.stringify({
                        codigo: codigo,
                        cantidad: cantidad
                    })
                });

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
        if (!clientes) {
            return;
        }

        try {
            const usuarios = await peticion("/api/admin/usuarios");

            if (!Array.isArray(usuarios)) {
                throw new Error(
                    "La respuesta de usuarios no tiene el formato esperado."
                );
            }

            clientes.replaceChildren();

            const tabla = crearTabla(
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
            );

            clientes.appendChild(tabla);
        } catch (error) {
            mostrarMensaje(error.message, true);
        }
    }

    // Solo intenta cargar datos administrativos si la página
    // contiene las secciones correspondientes.
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

    // =====================================================
    // NAVEGACIÓN Y CUENTA
    // =====================================================

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

    function llevar_pag(pagina) {
        window.location.href = pagina;
    }

    // =====================================================
    // POPUP DE DESCUENTO
    // =====================================================

    const popup =
        document.getElementById("popup") ||
        document.querySelector(".popup");

    const cerrarPopupBtn =
        document.getElementById("quitar_popup");

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
    // CHATBOT
    // =====================================================

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

        const textoMensaje = barraMensajes.value.trim();

        if (!textoMensaje) {
            return;
        }

        const mensajeUsuario = document.createElement("div");
        mensajeUsuario.classList.add("mensaje_usuario");
        mensajeUsuario.textContent = "Tú: " + textoMensaje;

        historialMensajes.appendChild(mensajeUsuario);
        barraMensajes.value = "";

        const mensajeCargando = document.createElement("div");
        mensajeCargando.classList.add("mensaje_asistente");
        mensajeCargando.textContent = "Linneo: Escribiendo...";

        historialMensajes.appendChild(mensajeCargando);
        historialMensajes.scrollTop = historialMensajes.scrollHeight;

        try {
            const cabeceras = {
                "Content-Type": "application/json"
            };

            if (csrfToken) {
                cabeceras["X-CSRFToken"] = csrfToken;
            }

            const respuesta = await fetch("/api/chat", {
                method: "POST",
                headers: cabeceras,
                credentials: "same-origin",
                body: JSON.stringify({
                    mensaje: textoMensaje
                })
            });

            const data = await respuesta.json().catch(() => ({}));

            mensajeCargando.remove();

            if (!respuesta.ok) {
                const error = document.createElement("div");
                error.classList.add("mensaje_error");
                error.textContent =
                    "Error: " +
                    (
                        data.error ||
                        data.mensaje ||
                        "No se pudo procesar el mensaje."
                    );

                historialMensajes.appendChild(error);
                historialMensajes.scrollTop =
                    historialMensajes.scrollHeight;
                return;
            }

            const mensajeAsistente = document.createElement("div");
            mensajeAsistente.classList.add("mensaje_asistente");
            mensajeAsistente.textContent =
                "Linneo: " + (data.respuesta || "No se recibió una respuesta.");

            historialMensajes.appendChild(mensajeAsistente);
            historialMensajes.scrollTop = historialMensajes.scrollHeight;
        } catch (error) {
            console.error("Error del chatbot:", error);
            mensajeCargando.remove();

            const mensajeError = document.createElement("div");
            mensajeError.classList.add("mensaje_error");
            mensajeError.textContent =
                "No se pudo conectar con Linneo.";

            historialMensajes.appendChild(mensajeError);
            historialMensajes.scrollTop = historialMensajes.scrollHeight;
        }
    }

    if (enviarMensajeBtn) {
        enviarMensajeBtn.addEventListener("click", enviarMensaje);
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
    // CARRITO GUARDADO EN EL NAVEGADOR
    // =====================================================

    let carrito = [];

    try {
        const carritoGuardado = JSON.parse(
            localStorage.getItem("linneoCarrito") || "[]"
        );

        if (Array.isArray(carritoGuardado)) {
            carrito = carritoGuardado.filter(function (producto) {
                return producto &&
                    typeof producto.nombre === "string" &&
                    Number.isFinite(Number(producto.precio));
            });
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
            listaCarrito.replaceChildren();
        }

        if (contenidoCarrito) {
            contenidoCarrito.replaceChildren();
        }

        carrito.forEach(function (producto) {
            const cantidad = Math.max(
                1,
                Number.parseInt(producto.cantidad, 10) || 1
            );

            const precio = Number(producto.precio) || 0;
            const totalProducto = precio * cantidad;

            subtotal += totalProducto;

            if (listaCarrito) {
                const fila = document.createElement("tr");

                const celdaNombre = document.createElement("td");
                celdaNombre.textContent = producto.nombre;

                const celdaCantidad = document.createElement("td");
                celdaCantidad.textContent = String(cantidad);

                const celdaPrecio = document.createElement("td");
                celdaPrecio.textContent = "$" + precio.toFixed(2);

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
            contenidoCarrito.textContent = "El carrito está vacío.";
        }

        if (precioCarrito) {
            precioCarrito.textContent = "$" + subtotal.toFixed(2);
        }

        if (cantidad_productos) {
            cantidad_productos.textContent = String(
                carrito.reduce(function (total, producto) {
                    return total +
                        (Number.parseInt(producto.cantidad, 10) || 1);
                }, 0)
            );
        }

        try {
            localStorage.setItem(
                "linneoCarrito",
                JSON.stringify(carrito)
            );
        } catch (error) {
            console.warn("No se pudo guardar el carrito en el navegador.");
        }

        const subtotalLabel =
            document.getElementById("subtotal_carrito");

        if (subtotalLabel) {
            subtotalLabel.textContent = "$" + subtotal.toFixed(2);
        }
    }

    // Agregar productos al carrito
    const botonesCarrito =
        document.querySelectorAll(".agregar-carrito");

    botonesCarrito.forEach(function (botonCarrito) {
        botonCarrito.addEventListener("click", function () {
            if (botonCarrito.disabled) {
                return;
            }

            const nombre = botonCarrito.dataset.productoNombre;
            const precio = Number(
                botonCarrito.dataset.productoPrecio
            );

            if (!nombre || !Number.isFinite(precio)) {
                console.error("Datos del producto incorrectos", {
                    nombre: nombre,
                    precio: precio
                });
                return;
            }

            const existente = carrito.find(function (producto) {
                return producto.nombre === nombre;
            });

            if (existente) {
                existente.cantidad =
                    (Number.parseInt(existente.cantidad, 10) || 1) + 1;
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

    // =====================================================
    // CONTROL DE STOCK EN LAS TARJETAS
    // =====================================================

    const botonesCategoria = document.querySelectorAll(
        ".sec_btn[data-categoria]"
    );

    const productos = document.querySelectorAll(
        ".tarjeta_producto, #producto"
    );

    function actualizarIndicadoresStock() {
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

            const stockTexto = stockElemento.textContent
                .replace(/Stock:/i, "")
                .trim();

            const stock = Number(stockTexto);

            if (!Number.isFinite(stock)) {
                return;
            }

            if (disponibilidad) {
                disponibilidad.style.backgroundColor =
                    stock <= 0 ? "red" : "var(--verde-musgo)";
            }

            if (botonCarrito) {
                if (stock <= 0) {
                    botonCarrito.disabled = true;
                    botonCarrito.style.display = "none";
                    botonCarrito.setAttribute(
                        "aria-label",
                        "Producto sin stock"
                    );
                } else {
                    botonCarrito.disabled = false;
                    botonCarrito.style.display = "";
                    botonCarrito.removeAttribute("aria-label");
                }
            }
        });
    }

    actualizarIndicadoresStock();

    // =====================================================
    // FILTROS Y ORDEN DEL CATÁLOGO
    // =====================================================

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
            contenedorCatalogo.querySelectorAll(".tarjeta_producto")
        );

        tarjetas.forEach(function (producto) {
            const categoriaProducto = normalizarTexto(
                producto.dataset.categoria
            );

            const coincideCategoria =
                !categoriaSeleccionada ||
                categoriaProducto === normalizarTexto(categoriaSeleccionada);

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
            busqueda_div.classList.toggle("visible");
        });
    }

    // =====================================================
    // MENÚ DE FILTROS
    // =====================================================

    if (filtrosbtn && filtro_menu) {
        filtrosbtn.addEventListener("click", function () {
            filtro_menu.hidden = !filtro_menu.hidden;

            filtrosbtn.setAttribute(
                "aria-expanded",
                String(!filtro_menu.hidden)
            );
        });
    }

    // =====================================================
    // MENÚ PRINCIPAL
    // =====================================================

    function desplegar_menu() {
        if (!menu_bar) {
            return;
        }

        menu_bar.classList.toggle("visible");

        if (menubtn) {
            menubtn.setAttribute(
                "aria-expanded",
                String(menu_bar.classList.contains("visible"))
            );
        }
    }

    if (menubtn && menu_bar) {
        menubtn.addEventListener("click", desplegar_menu);
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
    // PANEL DEL CARRITO
    // =====================================================

    function desplegar_carrito() {
        if (!carrito_bar) {
            return;
        }

        carrito_bar.classList.toggle("visible");

        if (carritobtn) {
            carritobtn.setAttribute(
                "aria-expanded",
                String(carrito_bar.classList.contains("visible"))
            );
        }
    }

    if (carritobtn && carrito_bar) {
        carritobtn.addEventListener("click", desplegar_carrito);
    }

    // =====================================================
    // CATEGORÍAS DE LA PORTADA
    // =====================================================

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

    botonesPortada.forEach(function (botonPortada) {
        botonPortada.addEventListener("click", function () {
            const terminos = categoriasPortada[botonPortada.id] || [];

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
                    return texto.includes(normalizarTexto(termino));
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

            if (!aviso && seccionProductos && seccionProductos.parentNode) {
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

    // =====================================================
    // BOTÓN PARA VER EL CATÁLOGO COMPLETO
    // =====================================================

    const catalogoBtn =
        document.getElementById("catalogo_completo_btn");

    if (catalogoBtn) {
        catalogoBtn.addEventListener("click", function () {
            window.location.href = "/catalogo";
        });
    }

    // =====================================================
    // FAVORITOS
    // =====================================================

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
                window.alert(
                    "Todavía no tienes productos favoritos. " +
                    "La lista de favoritos se puede añadir al catálogo."
                );
            }
        });
    }

    // =====================================================
    // COMPRAR
    // =====================================================

    const comprarBtn =
        document.getElementById("comprar_carrito_btn");

    if (comprarBtn) {
        comprarBtn.addEventListener("click", function () {
            if (!carrito.length) {
                window.alert(
                    "Tu carrito está vacío. Agrega algún producto antes de continuar."
                );
                return;
            }

            window.alert(
                "Tu carrito tiene productos. Para finalizar la compra, " +
                "conecta este botón con la ruta de checkout de Flask."
            );
        });
    }
});
