document.addEventListener("DOMContentLoaded", function () {

    // =========================================
    // ELEMENTOS
    // =========================================

    const menubtn = document.getElementById("menubtn");
    const menu_bar = document.getElementById("menu_bar");
    const atras_menu = document.getElementById("atras_menu");

    const carritobtn = document.getElementById("carritobtn");
    const carrito_bar = document.getElementById("carrito_bar");

    const buscar_btn = document.getElementById("buscarbtn");
    const busqueda_div = document.getElementById("busqueda_div");

    const filtrosbtn = document.getElementById("filtrosbtn");
    const filtro_menu = document.getElementById("filtro_menu");
    
    const chatbtn = document.getElementById("chat_btn");
    const csrfToken = document.querySelector(
  'meta[name="csrf-token"]'
).content;

const respuesta = await fetch("/api/chat", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-CSRFToken": csrfToken
  },
  body: JSON.stringify({ mensaje: mensaje })
});
if (chatbtn) {
    chatbtn.addEventListener("click", function () {
        window.location.href = "/chatbox";
    });
}
    const cantidad_productos =
        document.getElementById("cantidad_productos");

const iniciar_secion_btn = document.getElementById("iniciar_secion_btn");
const registrarse_btn = document.getElementById("registrarse_btn");

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
    const productos =
        document.querySelectorAll(".tarjeta_producto, #producto");

    const botonesCarrito =
        document.querySelectorAll(".agregar-carrito");

// =========================================
// CHATBOT
// =========================================

	const barraMensajes =
		document.getElementById("bar_mensajes");

	const historialMensajes =
			document.getElementById("historial_mensajes");

	const enviarMensajeBtn =
		document.getElementById("enviar_mensaje_btn");


// =========================================
// ENVIAR MENSAJE
// =========================================

	async function enviarMensaje() {

		const mensaje =
			barraMensajes.value.trim();


    // No enviar mensajes vacíos
		if (!mensaje) {
			return;
		}


    // =====================================
    // MOSTRAR MENSAJE DEL USUARIO
    // =====================================

		const mensajeUsuario =
			document.createElement("div");

		mensajeUsuario.classList.add("mensaje_usuario");

		mensajeUsuario.textContent =
			"Tú: " + mensaje;

		historialMensajes.appendChild(
			mensajeUsuario
		);


    // Limpiar barra
		barraMensajes.value = "";


    // =====================================
    // INDICADOR DE RESPUESTA
    // =====================================

		const mensajeCargando =
			document.createElement("div");

		mensajeCargando.classList.add(
			"mensaje_asistente"
		);

		mensajeCargando.textContent =
			"Linneo: Escribiendo...";

		historialMensajes.appendChild(
			mensajeCargando
		);


    // Bajar automáticamente
		historialMensajes.scrollTop =
			historialMensajes.scrollHeight;
	

		try {

        // =================================
        // ENVIAR A FLASK
        // =================================

			const respuesta =
				await fetch("/api/chat", {

					method: "POST",

					headers: {
						"Content-Type":
							"application/json"
					},

					body: JSON.stringify({
						mensaje: mensaje
					})

				});


        // =================================
        // RECIBIR JSON
        // =================================

			const data =
				await respuesta.json();


        // =================================
        // QUITAR "ESCRIBIENDO..."
        // =================================

			mensajeCargando.remove();


        // =================================
        // COMPROBAR ERROR
        // =================================

			if (!respuesta.ok) {

				const error =
					document.createElement("div");

				error.classList.add(
					"mensaje_error"
				);
	
				error.textContent =
					"Error: " +
					(
						data.error ||
						"No se pudo procesar el mensaje."
					);

				historialMensajes.appendChild(
					error
				);

				return;
			}


        // =================================
        // MOSTRAR RESPUESTA
        // =================================

			const mensajeAsistente =
				document.createElement("div");

			mensajeAsistente.classList.add(
				"mensaje_asistente"
			);

			mensajeAsistente.textContent =
				"Linneo: " +
				data.respuesta;

			historialMensajes.appendChild(
				mensajeAsistente
			);


        // Bajar automáticamente

			historialMensajes.scrollTop =
				historialMensajes.scrollHeight;


		} catch (error) {

			console.error(
				"Error del chatbot:",
				error
			);


			mensajeCargando.remove();


			const mensajeError =
				document.createElement("div");

			mensajeError.classList.add(
				"mensaje_error"
			);

			mensajeError.textContent =
				"No se pudo conectar con Linneo.";


			historialMensajes.appendChild(
				mensajeError
			);

		}

	}


// =========================================
// BOTÓN ENVIAR
// =========================================


	if (enviarMensajeBtn) {

		enviarMensajeBtn.addEventListener(
			"click",
			enviarMensaje
		);

	}


// =========================================
// ENTER PARA ENVIAR
// =========================================

	if (barraMensajes) {

		barraMensajes.addEventListener(
			"keydown",
			function (evento) {
	
				if (evento.key === "Enter") {

					evento.preventDefault();

					enviarMensaje();

				}

			}
		);

	}

    // =========================================
    // CARRITO
    // =========================================
let carrito = [];

const contenidoCarrito =
    document.getElementById("contenido_carrito");

const precioCarrito =
    document.getElementById("productos_carrito_precio");
// =========================================
// CARRITO
// =========================================

// =========================================
// MOSTRAR CARRITO
// =========================================

const listaCarrito = document.getElementById("lista_carrito");

function actualizarCarrito() {
    if (!contenidoCarrito || !precioCarrito) {
        console.error("No se encontró el contenedor del carrito");
    }

    let subtotal = 0;

    // Limpiar la tabla y el panel lateral
    if (listaCarrito) listaCarrito.innerHTML = "";
    if (contenidoCarrito) contenidoCarrito.innerHTML = "";

    carrito.forEach(function (producto) {
        const cantidad = producto.cantidad || 1;
        const precio = Number(producto.precio);
        const totalProducto = precio * cantidad;

        subtotal += totalProducto;

        // Agregar fila a la tabla de compra
        if (listaCarrito) {
            const fila = document.createElement("tr");

            const celdaNombre = document.createElement("td");
            celdaNombre.textContent = producto.nombre;

            const celdaCantidad = document.createElement("td");
            celdaCantidad.textContent = cantidad;

            const celdaPrecio = document.createElement("td");
            celdaPrecio.textContent = "$" + precio.toFixed(2);

            fila.append(celdaNombre, celdaCantidad, celdaPrecio);
            listaCarrito.appendChild(fila);
        }

        // Mostrar producto en el carrito lateral
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
        cantidad_productos.textContent = carrito.reduce(
            (total, producto) => total + (producto.cantidad || 1),
            0
        );
    }
}




// =========================================
// AGREGAR PRODUCTOS
// =========================================


botonesCarrito.forEach(function (boton) {

    boton.addEventListener(
        "click",
        function () {
            const nombre =
                boton.dataset.productoNombre;

            const precio =
                Number(
                    boton.dataset.productoPrecio
                );


            if ( !nombre || isNaN(precio)) {

                console.error(
                    "Datos del producto incorrectos",
                    {
                      
                        nombre,
                        precio
                    }
                );

                return;
            }


const existente = carrito.find(
    producto => producto.nombre === nombre
);

if (existente) {
    existente.cantidad = (existente.cantidad || 1) + 1;
} else {
    carrito.push({
        nombre: nombre,
        precio: precio,
        cantidad: 1
    });
}


            actualizarCarrito();


            console.log(
                "Carrito:",
                carrito
            );

        }
    );

});


// =========================================
// MOSTRAR CARRITO AL INICIAR
// =========================================

actualizarCarrito();
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
    // SISTEMA DE FILTROS DEL CATÁLOGO
    // =========================================

    const contenedorCatalogo =
        document.getElementById("catalogo");

    const opcionesOrden =
        document.querySelectorAll('input[name="orden"]');

    let categoriaSeleccionada = "";
    let ordenSeleccionado = "";

    // Normaliza texto para comparar categorías
    function normalizarTexto(texto) {
        return String(texto || "")
            .trim()
            .toLocaleLowerCase("es");
    }

    // Aplica todos los filtros y el orden
    function aplicarFiltros() {

        if (!contenedorCatalogo) {
            return;
        }

        const tarjetas = Array.from(
            contenedorCatalogo.querySelectorAll(
                ".tarjeta_producto"
            )
        );

        // Filtrar por categoría
        tarjetas.forEach(function (producto) {

            const categoriaProducto =
                normalizarTexto(
                    producto.dataset.categoria
                );

            const coincideCategoria =
                categoriaSeleccionada === "" ||
                categoriaProducto ===
                    normalizarTexto(categoriaSeleccionada);

            producto.hidden = !coincideCategoria;
        });

        // Ordenar el catálogo completo
        const tarjetasOrdenadas = [...tarjetas];

        tarjetasOrdenadas.sort(function (a, b) {

            const nombreA = normalizarTexto(
                a.dataset.nombre
            );

            const nombreB = normalizarTexto(
                b.dataset.nombre
            );

            const precioA = Number(
                a.dataset.precio
            );

            const precioB = Number(
                b.dataset.precio
            );

            switch (ordenSeleccionado) {

                case "alfabetico":
                    return nombreA.localeCompare(
                        nombreB,
                        "es",
                        { sensitivity: "base" }
                    );

                case "mayorprecio":
                    return precioB - precioA;

                case "menorprecio":
                    return precioA - precioB;

                default:
                    return 0;
            }
        });

        // Reordenar las tarjetas en el HTML
        tarjetasOrdenadas.forEach(function (producto) {
            contenedorCatalogo.appendChild(producto);
        });
    }

    // =========================================
    // BOTONES DE CATEGORÍA
    // =========================================

    botonesCategoria.forEach(function (boton) {

        boton.addEventListener("click", function () {

            categoriaSeleccionada =
                boton.dataset.categoria || "";

            console.log(
                "Categoría seleccionada:",
                categoriaSeleccionada
            );

            aplicarFiltros();
        });

    });

    // =========================================
    // ORDEN ALFABÉTICO Y POR PRECIO
    // =========================================

    opcionesOrden.forEach(function (opcion) {

        opcion.addEventListener("change", function () {

            if (!opcion.checked) {
                return;
            }

            ordenSeleccionado = opcion.value;

            aplicarFiltros();
        });
    });

    // Mostrar todos los productos al iniciar
    aplicarFiltros();



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

