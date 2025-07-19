document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('feedback-form');
    const q3SiRadio = document.getElementById('q3_si');
    const q3Details = document.getElementById('q3_details');
    const q8SiRadio = document.getElementById('q8_si');
    const q8Details = document.getElementById('q8_details');
    const formMessage = document.getElementById('form-message');
    const backToHomeButton = document.getElementById('back-to-home');

    // Función para mostrar/ocultar el textarea de detalles para la pregunta 3
    function toggleQ3Details() {
        if (q3SiRadio.checked) {
            q3Details.style.display = 'block';
            q3Details.setAttribute('required', 'required');
        } else {
            q3Details.style.display = 'none';
            q3Details.removeAttribute('required');
            q3Details.value = ''; // Limpiar el valor si se oculta
        }
    }

    // Función para mostrar/ocultar el textarea de detalles para la pregunta 8
    function toggleQ8Details() {
        if (q8SiRadio.checked) {
            q8Details.style.display = 'block';
            q8Details.setAttribute('required', 'required');
        } else {
            q8Details.style.display = 'none';
            q8Details.removeAttribute('required');
            q8Details.value = ''; // Limpiar el valor si se oculta
        }
    }

    // Escuchadores de eventos para las preguntas con campos condicionales
    document.querySelectorAll('input[name="q3"]').forEach(radio => {
        radio.addEventListener('change', toggleQ3Details);
    });
    document.querySelectorAll('input[name="q8"]').forEach(radio => {
        radio.addEventListener('change', toggleQ8Details);
    });

    // Llamada inicial para establecer el estado correcto al cargar la página
    toggleQ3Details();
    toggleQ8Details();

    // Manejador del envío del formulario
    form.addEventListener('submit', async (event) => {
        event.preventDefault(); // Evita el envío por defecto del formulario

        // Recolectar datos del formulario
        const formData = new FormData(form);
        const data = {};
        
        // Mapear nombres de las preguntas a sus IDs de pregunta del backend
        const questionMap = {
            'q1': '¿Fue sencillo comenzar a usar la web?',
            'q2': '¿La pantalla y los menús de la aplicación son claros y fáciles de entender?',
            'q3': '¿Tuviste algún problema técnico importante mientras lo utilizabas?',
            'q3_details': 'Detalles del problema técnico (si aplica)', // Campo adicional
            'q4': '¿Crees que cualquier persona, independientemente de su familiaridad con la tecnología, podría manejar este sistema sin problemas?',
            'q5': '¿Hay algo que, al modificarlo, haría que el dispositivo fuera aún más sencillo de usar?',
            'q6': '¿La información sobre tus posturas fue correcta ?',
            'q7': '¿Cuánto te ayudó la información de la herramienta a detectar tus errores al ejecutar los movimientos?',
            'q8': '¿Hubo algún momento en que sentiste que lo que se te indicaba sobre tu postura no era acertado?',
            'q8_details': 'Detalles del acierto/error en postura (si aplica)', // Campo adicional
            'q9': '¿La aplicacion contribuyó a mejorar tus posturas mientras te ejercitabas?',
            'q10': '¿Recomendarías esta web a otras personas interesadas en optimizar su técnica y postura al hacer ejercicio?',
            'q11': '¿Tienes algún otro comentario o sugerencia?'
        };

        // Rellenar el objeto de datos
        for (let [key, value] of formData.entries()) {
            // Si es un campo de radio que tiene un campo de detalle, ajustamos el valor
            if (key === 'q3' && value === 'Sí') {
                data[questionMap[key]] = value + " (" + q3Details.value + ")";
            } else if (key === 'q8' && value === 'Sí') {
                data[questionMap[key]] = value + " (" + q8Details.value + ")";
            }
            // Para los campos de texto libre o radios normales
            else if (questionMap[key]) {
                data[questionMap[key]] = value;
            }
        }

        // Eliminar las claves de detalles si la respuesta asociada es 'No'
        if (formData.get('q3') === 'No') {
            delete data[questionMap['q3_details']];
        }
        if (formData.get('q8') === 'No') {
            delete data[questionMap['q8_details']];
        }

        // Validación adicional para los campos de texto si son requeridos por el radio
        if (q3SiRadio.checked && q3Details.value.trim() === '') {
            showMessage('Por favor, detalla el problema técnico.', 'error');
            return;
        }
        if (q8SiRadio.checked && q8Details.value.trim() === '') {
            showMessage('Por favor, especifica el ejercicio y el tipo de error.', 'error');
            return;
        }

        // Enviar los datos al backend
        try {
            const response = await fetch('/submit_feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (response.ok) {
                showMessage(result.message, 'success');
                form.reset(); // Limpia el formulario
                toggleQ3Details(); // Restablece visibilidad de detalles
                toggleQ8Details(); // Restablece visibilidad de detalles
            } else {
                showMessage(result.message || 'Error al enviar el feedback.', 'error');
            }
        } catch (error) {
            console.error('Error al enviar el feedback:', error);
            showMessage('Error de conexión. Inténtalo de nuevo más tarde.', 'error');
        }
    });

    // Función para mostrar mensajes de estado
    function showMessage(message, type) {
        formMessage.textContent = message;
        formMessage.className = `form-message ${type}`; // Clase para estilos de éxito/error
        formMessage.style.display = 'block';
        // Ocultar el mensaje después de unos segundos
        setTimeout(() => {
            formMessage.style.display = 'none';
        }, 5000);
    }

    // Botón de volver al inicio
    backToHomeButton.addEventListener('click', () => {
        window.location.href = '/'; // Redirige a la página principal
    });
});