document.addEventListener('DOMContentLoaded', () => {

    // Constantes para almacenar etiquetas con clases similares
    const navLinks = document.querySelectorAll('.nav-link');
    const contentSections = document.querySelectorAll('.content-section');
    const backButton = document.getElementById('back-button');

    // Variables globales para almacenar las instancias de los gráficos de Chart.js
    let chartRepsInstance = null;
    let chartConfusionMatrixInstance = null;
    let chartRocInstance = null;
    let chartPrInstance = null;

    // Diccionario para el historial de navegación
    const navigationHistory = [];

    // Variable para controlar si la detección en vivo está activa en el frontend
    let isLiveDetectionActive = false;

    // Flag para controlar si la detención del video es intencional por el usuario
    let isIntentionalStop = false;

    //FUNCIONES PRINCIPALES PARA GESTIONAR LA VISIBILIDAD DE SECCIONES

    /**
     * Oculta todas las secciones de contenido y luego muestra solo la sección deseada.
     * También actualiza el texto del breadcrumb.
     * @param {string} targetId - El ID de la sección de contenido a mostrar (sin '#').
     * @param {string} breadcrumbText - El texto a mostrar en el breadcrumb para esta sección.
     * @param {boolean} pushToHistory - Si se debe añadir la navegación al historial.
     */

    function showSection(targetId, breadcrumbText, pushToHistory = true) {
        console.log(`[showSection] Attempting to show section: ${targetId} with breadcrumb: ${breadcrumbText}`);

        // Oculta todas las secciones
        contentSections.forEach(section => {
            section.classList.remove('active');
            section.style.display = 'none';
        });

        // Muestra la sección deseada
        const targetSection = document.getElementById(targetId);
        if (targetSection) {

            targetSection.classList.add('active');
            targetSection.style.display = 'flex';
            console.log(`[showSection] Successfully set display: flex for #${targetId}`);

        } else {

            console.error(`[showSection] Target section with ID '#${targetId}' not found!`);
        }

        // Gestionar el historial de navegación y la visibilidad del botón de retroceso
        if (pushToHistory) {

            // Asegurarse de no añadir duplicados si es la misma página consecutiva
            if (navigationHistory.length === 0 || navigationHistory[navigationHistory.length - 1].id !== targetId) {

                navigationHistory.push({ id: targetId, breadcrumb: breadcrumbText });
            }
        }

        // Mostrar el botón de retroceso si hay más de un elemento en el historial
        if (backButton) {

            if (navigationHistory.length > 1) {
                
                backButton.style.display = 'block'; // Tambien se puede poner como 'flex' 
            } else {

                backButton.style.display = 'none';
            }
        }
        
    }

    // Manejar el botón de retroceso
    if (backButton) {

        backButton.addEventListener('click', () => {

            if (navigationHistory.length > 1) {

                navigationHistory.pop(); // Eliminar la página actual
                const previousPage = navigationHistory[navigationHistory.length - 1]; // Obtener la página anterior
                showSection(previousPage.id, previousPage.breadcrumb, false); // Mostrar sin añadir al historial

                // Actualizar la clase 'active' en el sidebar para el enlace correspondiente
                navLinks.forEach(nav => {

                    nav.classList.remove('active');
                    if (nav.dataset.content + '-content' === previousPage.id) {

                        nav.classList.add('active');
                    }
                });

            } else if (navigationHistory.length === 1) {

                // Si solo queda una página, volver a la Home y ocultar el botón
                showSection('home-content', 'Inicio', false);
                navigationHistory.pop(); // Vaciar el historial

                if (backButton) backButton.style.display = 'none';

                // Asegurarse de que el enlace de 'Inicio' en la sidebar esté activo
                const homeNavLink = document.querySelector('.sidebar-menu a[data-content="home"]');

                if (homeNavLink) {

                    homeNavLink.classList.add('active');
                }
            }
        });
    }

    // Lógica para obtener datos de ejercicio (polling) de Live Detection
    let livePollingIntervalId = null;

    function startLivePollingExerciseData() {

        stopLivePollingExerciseData(); // Asegurarse de que no haya otro intervalo activo
        const repsDisplay = document.getElementById('live-detection-reps');
        const incorrectRepsDisplay = document.getElementById('live-detection-incorrect-reps');
        const stageDisplay = document.getElementById('live-detection-stage');

        livePollingIntervalId = setInterval(() => {

            fetch('/exercise_data')
                .then(response => response.json())
                .then(data => {
                    if (repsDisplay) repsDisplay.textContent = data.reps !== undefined ? data.reps : '0';
                    if (incorrectRepsDisplay) incorrectRepsDisplay.textContent = data.incorrect_reps !== undefined ? data.incorrect_reps : '0';
                    if (stageDisplay) stageDisplay.textContent = data.stage !== undefined ? data.stage : 'N/A';
                })
                .catch(error => {
                    console.error('Error al obtener datos de ejercicio:', error);
                });
        }, 500); // Poll cada 500ms
    }

    function stopLivePollingExerciseData() {

        if (livePollingIntervalId) {

            clearInterval(livePollingIntervalId);
            livePollingIntervalId = null;
            console.log("Polling de datos de ejercicio detenido.");
        }
    }

    /**
     * Inicia un nuevo stream de video y detección de pose para un ejercicio específico.
     * @param {string} exerciseType - El tipo de ejercicio (ej: 'squats', 'pushups').
     */

    function startNewLiveDetection(exerciseType) {

        const videoStreamImg = document.getElementById('video-stream-img');
        const liveVideoLoader = document.getElementById('live-video-loader');
        const detectionStatus = document.getElementById('live-detection-status');
        const liveStartDetectionBtn = document.getElementById('live-start-detection');
        const liveDetectionContent = document.getElementById('live-detection-content');
        const selectionMenu = liveDetectionContent.querySelector('.selection-menu-container');
        const videoDisplayArea = liveDetectionContent.querySelector('.video-display-area');

        // Detener cualquier stream activo antes de iniciar uno nuevo
        stopVideoFeed();

        // Mostrar el área de video y el loader
        if (selectionMenu) selectionMenu.style.display = 'none';
        if (videoDisplayArea) videoDisplayArea.style.display = 'flex';
        if (liveVideoLoader) liveVideoLoader.style.display = 'flex'; // Mostrar loader

        // Reiniciar los contadores en la UI antes de la nueva detección
        document.getElementById('live-detection-reps').textContent = '0';
        document.getElementById('live-detection-incorrect-reps').textContent = '0';
        document.getElementById('live-detection-stage').textContent = 'Inicializando...';
        
        // Cargar el stream de video desde Flask
        if (videoStreamImg) {

            // Resetear la bandera antes de intentar cargar una nueva fuente
            isIntentionalStop = false; 
            videoStreamImg.src = `/video_feed/${exerciseType}`;
            console.log(`Solicitando video feed para: ${exerciseType}`);

            // Manejar la carga de la imagen del stream
            videoStreamImg.onload = () => {

                if (liveVideoLoader) liveVideoLoader.style.display = 'none'; // Ocultar loader una vez que la imagen empieza a cargar
                if (detectionStatus) detectionStatus.textContent = 'Detectando...';
                if (liveStartDetectionBtn) {

                    liveStartDetectionBtn.querySelector('i').classList.remove('fa-play');
                    liveStartDetectionBtn.querySelector('i').classList.add('fa-pause');
                }

                isLiveDetectionActive = true;
                startLivePollingExerciseData(); // Iniciar polling una vez que el stream está cargando
                console.log("Video feed cargado.");
            };

            videoStreamImg.onerror = () => {

                // Solo mostrar el error si no es una detención intencional
                if (isIntentionalStop) {
                    
                    console.log("Video feed detenido intencionalmente por el usuario. No se muestra error de carga.");
                    isIntentionalStop = false; // Resetear la bandera
                    return; // Salir sin mostrar la notificación de error
                }

                console.error("Error al cargar el video feed. Verifique si la cámara está en uso o no disponible.");
                if (liveVideoLoader) liveVideoLoader.style.display = 'none';
                if (detectionStatus) detectionStatus.textContent = 'Error de carga';
                isLiveDetectionActive = false;
                stopLivePollingExerciseData();
                // Usar un método de notificación personalizado en lugar de alert()
                const notification = document.getElementById('notification');
                if (notification) {

                    notification.querySelector('.notification-title').textContent = 'Error de Cámara';
                    notification.querySelector('.notification-content').textContent = 'No se pudo iniciar el stream de la cámara. Asegúrate de que esté conectada y no esté en uso por otra aplicación.';
                    notification.classList.add('show', 'error');
                }
            };
        }
    }

    //Detiene el feed de video y el polling, y restablece la UI de Live Detection.
    function stopVideoFeed() {

        // Salir del modo de pantalla completa si está activo
        if (document.fullscreenElement) {

            if (document.exitFullscreen) {

                document.exitFullscreen();

            } else if (document.mozCancelFullScreen) { /* Firefox */

                document.mozCancelFullScreen();

            } else if (document.webkitExitFullscreen) { /* Chrome, Safari and Opera */

                document.webkitExitFullscreen();

            } else if (document.msExitFullscreen) { /* IE/Edge */

                document.msExitFullscreen();
            }
        }

        const videoStreamImg = document.getElementById('video-stream-img');
        if (videoStreamImg) {

            // Establecer la bandera a true ANTES de cambiar el src para evitar que onerror dispare el mensaje
            isIntentionalStop = true; 
            if (videoStreamImg.src) { // Solo vaciar src si ya tiene uno (para evitar el error al cargar la página)

                videoStreamImg.src = ""; // Detiene la carga del stream
            }
            console.log("Stream de video frontend detenido.");
        }
        
        // Enviar solicitud al backend para detener el procesamiento
        fetch('/stop_feed')
            .then(response => {

                if (response.ok) {

                    console.log('Feed de video detenido en el servidor.');

                } else {

                    console.error('Error al detener el feed en el servidor.');
                }
            })
            .catch(error => console.error('Error de red al detener el feed:', error));
        
        stopLivePollingExerciseData();
        isLiveDetectionActive = false;

        // Restablecer contadores y estado en la UI
        const repsDisplay = document.getElementById('live-detection-reps');
        const incorrectRepsDisplay = document.getElementById('live-detection-incorrect-reps');
        const stageDisplay = document.getElementById('live-detection-stage');
        const detectionStatus = document.getElementById('live-detection-status');
        const liveStartDetectionBtn = document.getElementById('live-start-detection');

        if (repsDisplay) repsDisplay.textContent = '0';
        if (incorrectRepsDisplay) incorrectRepsDisplay.textContent = '0';
        if (stageDisplay) stageDisplay.textContent = 'N/A';
        if (detectionStatus) detectionStatus.textContent = 'Esperando selección';

        // Asegurarse de que el botón de play/pause tenga el icono de play
        if (liveStartDetectionBtn) {

            const icon = liveStartDetectionBtn.querySelector('i');
            icon.classList.remove('fa-pause');
            icon.classList.add('fa-play');
        }

        // Ocultar el área de video y mostrar el menú de selección
        const liveDetectionContent = document.getElementById('live-detection-content');
        const selectionMenu = liveDetectionContent.querySelector('.selection-menu-container');
        const videoDisplayArea = liveDetectionContent.querySelector('.video-display-area');
        
        if (videoDisplayArea) videoDisplayArea.style.display = 'none';
        if (selectionMenu) selectionMenu.style.display = 'flex';
        console.log("Detección en vivo detenida por completo y UI reseteada.");
    }


    // FUNCIONES PARA RENDERIZAR LOS GRÁFICOS CON CHART.JS

    function destroyAllCharts() {

        if (chartRepsInstance) { chartRepsInstance.destroy(); chartRepsInstance = null; }
        if (chartConfusionMatrixInstance) { chartConfusionMatrixInstance.destroy(); chartConfusionMatrixInstance = null; }
        if (chartRocInstance) { chartRocInstance.destroy(); chartRocInstance = null; }
        if (chartPrInstance) { chartPrInstance.destroy(); chartPrInstance = null; }
        console.log("Charts: Todas las instancias anteriores se han eliminado.");
    }

    // Gráfico de Barras (Repeticiones Correctas vs. Incorrectas)
    function renderRepsChart(chartData) {

        const ctx = document.getElementById('chart-reps');
        if (!ctx) { console.error("Canvas 'chart-reps' no encontrado."); return; }
        if (chartRepsInstance) chartRepsInstance.destroy();

        // Agregado: Validación de chartData.values antes de renderizar
        if (!chartData || !chartData.values || chartData.values.length === 0) {

            console.warn("Datos de Repeticiones inválidos o vacíos. No se renderizará el gráfico de Repeticiones.");
            const container = ctx.parentNode;
            container.innerHTML = '<p class="chart-error-message">Datos de Repeticiones no disponibles o incompletos.</p>';
            return;
        }


        chartRepsInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: chartData.chart_title,
                    data: chartData.values,
                    backgroundColor: [
                        'rgba(52, 152, 219, 0.8)', // Primary color for correct
                        'rgba(231, 76, 60, 0.8)'   // Alert color for incorrect
                    ],
                    borderColor: [
                        'rgba(52, 152, 219, 1)',
                        'rgba(231, 76, 60, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Número de Repeticiones' }
                    },
                    x: {
                        title: { display: true, text: 'Tipo de Repetición' }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: chartData.chart_title || 'Resultados de Repeticiones',
                        font: { size: 16 }
                    },
                    legend: { display: false }
                }
            }
        });
    }

    // Gráfico de Mapa de Calor (Matriz de Confusión)
    function renderConfusionMatrixChart(chartData) {
        const ctx = document.getElementById('chart-confusion-matrix');
        if (!ctx) { console.error("Canvas 'chart-confusion-matrix' no encontrado."); return; }
        if (chartConfusionMatrixInstance) chartConfusionMatrixInstance.destroy();

        // Validar si la matriz de datos es válida
        if (!chartData || !chartData.matrix || chartData.matrix.length === 0 || 
            !chartData.labels || chartData.labels.length === 0 ||
            !chartData.prediction_labels || chartData.prediction_labels.length === 0) {

            console.warn("Datos de la Matriz de Confusión inválidos o vacíos. No se renderizará el gráfico.");
            const container = ctx.parentNode;
            container.innerHTML = '<p class="chart-error-message">Datos de la Matriz de Confusión no disponibles o incompletos.</p>';
            return;
        }

        // Convertir la matriz 2D a un formato de puntos para el heatmap
        const dataPoints = [];
        chartData.matrix.forEach((row, i) => {
            row.forEach((value, j) => {
                dataPoints.push({
                    x: chartData.prediction_labels[j], // Predicciones en X
                    y: chartData.labels[i],             // Reales en Y
                    v: value
                });
            });
        });

        chartConfusionMatrixInstance = new Chart(ctx, {
            type: 'matrix', // Requiere el plugin chartjs-chart-matrix
            data: {
                labels: {
                    x: chartData.prediction_labels,
                    y: chartData.labels
                },
                datasets: [{
                    label: chartData.chart_title,
                    data: dataPoints,
                    backgroundColor(context) {
                        const value = context.dataset.data[context.dataIndex].v;
                        const maxVal = Math.max(...dataPoints.map(p => p.v));
                        const alpha = maxVal > 0 ? value / maxVal : 0; // Escala el color según el valor, evitar división por cero
                        
                        // Acceder a las etiquetas con prefijo
                        const realLabelWithPrefix = chartData.labels[context.dataIndex.y];
                        const predLabelWithPrefix = chartData.prediction_labels[context.dataIndex.x];
                        
                        // Extraer el nombre de la clase real y de la predicción, con validación
                        const realClass = typeof realLabelWithPrefix === 'string' ? realLabelWithPrefix.replace('Real ', '') : '';
                        const predClass = typeof predLabelWithPrefix === 'string' ? predLabelWithPrefix.replace('Pred. ', '') : '';

                        // Comparar los nombres de clase para determinar si es diagonal
                        const isDiagonal = realClass === predClass;

                        if (isDiagonal) {
                            return `rgba(46, 204, 113, ${alpha})`; // secondary-color (verde)
                        } else {
                            return `rgba(231, 76, 60, ${alpha})`; // alert-color (rojo)
                        }
                    },
                    borderColor: 'rgba(0,0,0,0.1)',
                    borderWidth: 1,
                    width(context) {
                        const a = context.chart.chartArea;
                        // Añadir comprobación para 'a' y sus propiedades antes de usar
                        if (!a || isNaN(a.right) || isNaN(a.left)) return 0;
                        return (a.right - a.left) / chartData.prediction_labels.length - 2; // Ancho de celda
                    },
                    height(context) {
                        const a = context.chart.chartArea;
                        // Añadir comprobación para 'a' y sus propiedades antes de usar
                        if (!a || isNaN(a.bottom) || isNaN(a.top)) return 0;
                        return (a.bottom - a.top) / chartData.labels.length - 2; // Alto de celda
                    },
                    // Texto dentro de las celdas
                    fontColor: '#FFFFFF', // Cambiado a blanco para mejor visibilidad
                    fontStyle: 'bold',
                    fontSize: 14 
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: chartData.chart_title,
                        font: { size: 16 }
                    },
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title() { return ''; },
                            label(context) {
                                const p = context.dataset.data[context.dataIndex];
                                return [`Real: ${p.y.replace('Real ', '')}`, `Predicción: ${p.x.replace('Pred. ', '')}`, `Valor: ${p.v}`];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'category',
                        labels: chartData.prediction_labels,
                        grid: { display: false },
                        ticks: { display: true }
                    },
                    y: {
                        type: 'category',
                        labels: chartData.labels,
                        offset: true,
                        grid: { display: false },
                        ticks: { display: true }
                    }
                }
            }
        });
    }

    // Gráfico de Líneas (Curva ROC)
    function renderRocChart(chartData) {
        const ctx = document.getElementById('chart-roc');
        if (!ctx) { console.error("Canvas 'chart-roc' no encontrado."); return; }
        if (chartRocInstance) chartRocInstance.destroy();

        // Validar si los datos FPR y TPR son válidos para la gráfica
        if (!chartData || !chartData.fpr || !chartData.tpr || chartData.fpr.length === 0 || chartData.tpr.length === 0) {
            console.warn("Datos de ROC inválidos o vacíos. No se renderizará el gráfico ROC.");
            const container = ctx.parentNode;
            container.innerHTML = '<p class="chart-error-message">Datos de la curva ROC no disponibles o incompletos.</p>';
            return;
        }


        chartRocInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartData.fpr, // FPR en el eje X
                datasets: [{
                    label: 'Curva ROC',
                    data: chartData.tpr.map((tpr, i) => ({ x: chartData.fpr[i], y: tpr })), // Datos como pares (FPR, TPR)
                    borderColor: 'rgba(52, 152, 219, 1)', // primary-color
                    backgroundColor: 'rgba(52, 152, 219, 0.2)',
                    fill: true,
                    tension: 0.4, // Suavizar la línea
                    pointRadius: 3,
                    pointBackgroundColor: 'rgba(52, 152, 219, 1)'
                },
                {
                    label: 'Línea de No-Discriminación (AUC=0.5)',
                    data: [{ x: 0, y: 0 }, { x: 1, y: 1 }],
                    borderColor: 'rgba(128, 128, 128, 0.5)', // Gris
                    borderDash: [5, 5], // Línea punteada
                    fill: false,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: `${chartData.chart_title} (AUC: ${chartData.auc.toFixed(4)})`, // Formatear AUC
                        font: { size: 16 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.x !== null && context.parsed.y !== null) {
                                    label += `FPR: ${context.parsed.x.toFixed(2)}, TPR: ${context.parsed.y.toFixed(2)}`;
                                }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Tasa de Falsos Positivos (FPR)'
                        },
                        min: 0,
                        max: 1
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Tasa de Verdaderos Positivos (TPR)'
                        },
                        min: 0,
                        max: 1
                    }
                }
            }
        });
    }

    // Gráfico de Líneas (Curva Precision-Recall)
    function renderPrChart(chartData) {

        const ctx = document.getElementById('chart-pr');
        if (!ctx) { console.error("Canvas 'chart-pr' no encontrado."); return; }
        if (chartPrInstance) chartPrInstance.destroy();

        // Validar si los datos de Precision y Recall son válidos para la gráfica
        if (!chartData || !chartData.precision || !chartData.recall || chartData.precision.length === 0 || chartData.recall.length === 0) {

            console.warn("Datos de Precision-Recall inválidos o vacíos. No se renderizará el gráfico PR.");
            const container = ctx.parentNode;
            container.innerHTML = '<p class="chart-error-message">Datos de la curva Precision-Recall no disponibles o incompletos.</p>';
            return;
        }

        chartPrInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartData.recall, // Recall en el eje X
                datasets: [{
                    label: 'Curva Precision-Recall',
                    data: chartData.precision.map((precision, i) => ({ x: chartData.recall[i], y: precision })), // Datos como pares (Recall, Precision)
                    borderColor: 'rgba(46, 204, 113, 1)', // secondary-color
                    backgroundColor: 'rgba(46, 204, 113, 0.2)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3,
                    pointBackgroundColor: 'rgba(46, 204, 113, 1)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: chartData.chart_title,
                        font: { size: 16 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.x !== null && context.parsed.y !== null) {
                                    label += `Recall: ${context.parsed.x.toFixed(2)}, Precision: ${context.parsed.y.toFixed(2)}`;
                                }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Recall'
                        },
                        min: 0,
                        max: 1
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Precision'
                        },
                        min: 0,
                        max: 1
                    }
                }
            }
        });
    }

    // Función para poblar la tabla del Reporte de Clasificación
    function populateClassificationReportTable(reportData) {
        const tableBody = document.querySelector('#classification-report-table tbody');
        const tableHeaderRow = document.querySelector('#classification-report-table thead tr');
        if (!tableBody || !tableHeaderRow) {

            console.error("Elementos de tabla de reporte de clasificación no encontrados.");
            return;
        }

        // Limpiar el cuerpo de la tabla
        tableBody.innerHTML = '';

        // Agregado: Validación de reportData
        if (!reportData || !reportData.data || reportData.data.length === 0) {
            
            console.warn("Datos del Reporte de Clasificación inválidos o vacíos. No se poblará la tabla.");
            const row = tableBody.insertRow();
            const cell = row.insertCell(0);
            cell.colSpan = reportData.headers ? reportData.headers.length : 5;
            cell.textContent = 'No hay datos de reporte de clasificación disponibles.';
            document.getElementById('classification-report-panel').style.display = 'flex'; // Mostrar panel incluso con mensaje de no datos
            return;
        }

        // `reportData.headers` y `reportData.data` vienen del backend
        reportData.data.forEach(rowData => {
            const row = tableBody.insertRow();
            reportData.headers.forEach(header => {
                const cell = row.insertCell();
                const value = rowData[header];

                // Formatear valores numéricos a 2 decimales para precisión, recall, f1-score
                if (header === "Precision" || header === "Recall" || header === "F1-Score") {

                    cell.textContent = typeof value === 'number' ? value.toFixed(2) : value;

                } else {

                    cell.textContent = value;
                }
            });
        });
        document.getElementById('classification-report-panel').style.display = 'flex'; // Mostrar la tabla
    }

    // MANEJO DE EVENTOS

    // Maneja los clics en los enlaces de navegación
    navLinks.forEach(link => {

        link.addEventListener('click', function(event) {
            event.preventDefault(); // Evitar el comportamiento predeterminado del enlace (cambio de URL)
            console.log(`NavLink Click: Se ha hecho click en: ${this.textContent}`);
            
            // Obtener el ID de la sección del atributo data-content
            const targetId = this.dataset.content + '-content'; 
            // Obtener texto para breadcrumb
            const breadcrumbText = this.querySelector('span') ? this.querySelector('span').textContent : this.textContent.trim(); 

            // Solo navegar si es una sección diferente a la actual
            if (navigationHistory.length > 0 && navigationHistory[navigationHistory.length - 1].id === targetId) {

                console.log("NavLink Click: Ya se encuentra en la seccion. No es necesario cambiar.");

                if (sidebar && sidebar.classList.contains('active')) {

                    sidebar.classList.remove('active');
                    console.log("NavLink Click: Barra lateral cerrado porque ya se encuentra en la seccion.");
                }
                                
                return; // No hacer nada si ya estamos en la sección de destino
            }

            // Remover la clase 'active' de todos los enlaces de la barra lateral
            document.querySelectorAll('.sidebar-menu a').forEach(sidebarLink => {
                sidebarLink.classList.remove('active');
            });

            // Añadir la clase 'active' al enlace de la barra lateral correspondiente
            const correspondingSidebarLink = document.querySelector(`.sidebar-menu a[data-content="${this.dataset.content}"]`);
            if (correspondingSidebarLink) {

                correspondingSidebarLink.classList.add('active');
            }


            // Manejar transiciones de sección específicas (detener video, reiniciar vistas de análisis)
            if (targetId !== 'live-detection-content') {

                console.log("NavLink Click: Saliendo de la seccion de Detecicon en Vivo, parando el feed de video.");
                stopVideoFeed(); // Asegurarse de detener la cámara y resetear la UI de live detection
            }

            // Lógica para preparar la sección de destino antes de mostrarla
            if (targetId === 'live-detection-content') {

                console.log("NavLink Click: Entrando en la seccion de Deteccion en Vivo.");
                const currentSectionElement = document.getElementById(targetId);
                const selectionMenu = currentSectionElement.querySelector('.selection-menu-container');
                const videoDisplayArea = currentSectionElement.querySelector('.video-display-area');
                
                // Asegurarse de que el menú de selección esté visible y el área de video oculta
                if (selectionMenu) {

                    selectionMenu.style.display = 'flex'; // Mostrar el menú de selección de ejercicio
                    console.log("NavLink Click: La seleccion del menu Deteccion en Vivo se ha cambiado a display: flex.");
                }
                if (videoDisplayArea) {

                    videoDisplayArea.style.display = 'none'; // Ocultar el área de video inicialmente
                    console.log("NavLink Click: Area de reproduccion del menu de Deteccion en Vivo se ha cambiado a display:none.");
                }
                // Asegurarse de que el status inicial sea 'Esperando selección'
                const detectionStatus = document.getElementById('live-detection-status');
                if (detectionStatus) detectionStatus.textContent = 'Esperando selección';

            } else if (targetId === 'analysis-content') {

                console.log("NavLink Click: Entrando en la seccion de Analiss. Escondiendo area de resultados.");
                // Ocultar el área de resultados y mostrar el menú de selección de análisis
                const analysisResultsArea = document.getElementById('analysis-results-area');
                if (analysisResultsArea) analysisResultsArea.style.display = 'none';

                const analysisSelectionMenu = document.getElementById('analysis-content').querySelector('.selection-menu-container');
                if (analysisSelectionMenu) analysisSelectionMenu.style.display = 'flex';

                destroyAllCharts(); // Asegurarse de destruir cualquier gráfico anterior
                document.getElementById('analysis-metrics-panel').style.display = 'none';
                document.getElementById('classification-report-panel').style.display = 'none';
                document.getElementById('analysis-charts-container').style.display = 'none';

            } else if (targetId === 'home-content') {

                // No hay lógica específica de reseteo para la página de inicio más allá de ocultar/mostrar secciones

            } else if (targetId === 'help-content') {

                // No hay lógica específica de reseteo para la página de ayuda más allá de ocultar/mostrar secciones
            }


            // Mostrar la sección después de toda la lógica de preparación
            showSection(targetId, breadcrumbText);

            if (sidebar && sidebar.classList.contains('active')) {

                sidebar.classList.remove('active');
                console.log("[NavLink Click] Sidebar closed after navigation.");
            }            
        });
    });

    // Maneja los clics en los botones de selección de ejercicio en Live Detection
    const liveDetectionMenuButtons = document.querySelectorAll('#live-detection-content .menu-button');
    liveDetectionMenuButtons.forEach(button => {
        button.addEventListener('click', function() {
            const exerciseType = this.dataset.exerciseType; // 'squats', 'pushups', etc.
            console.log(`Menu Button Click: Se ha hehco click en: ${this.textContent} (Exercise Type: ${exerciseType})`);

            // Iniciar la detección en vivo para el ejercicio seleccionado
            startNewLiveDetection(exerciseType);
        });
    });

    // Maneja los clics en el botón de PAUSA/REANUDAR de la Detección en Vivo
    const liveStartDetectionBtn = document.getElementById('live-start-detection');
    if (liveStartDetectionBtn) {

        liveStartDetectionBtn.addEventListener('click', function() {
            const icon = this.querySelector('i');
            const status = document.getElementById('live-detection-status');

            // Solo permitir pausar/reanudar si la detección en vivo está activa
            if (!isLiveDetectionActive) {

                console.log("Detección en vivo no activa, no se puede pausar/reanudar.");
                const notification = document.getElementById('notification'); // Obtener elemento de notificación

                if (notification) {

                    notification.querySelector('.notification-title').textContent = 'Acción No Permitida';
                    notification.querySelector('.notification-content').textContent = 'Por favor, selecciona un ejercicio para iniciar la detección en vivo antes de intentar pausar/reanudar.';
                    notification.classList.add('show', 'warning'); // Mostrar notificación de advertencia
                }
                return;
            }

            // Cambiar el icono y el texto de estado inmediatamente para una mejor UX
            let newStatusText = '';
            if (icon.classList.contains('fa-pause')) {

                icon.classList.remove('fa-pause');
                icon.classList.add('fa-play');
                newStatusText = 'Pausando...';

            } else {

                icon.classList.remove('fa-play');
                icon.classList.add('fa-pause');
                newStatusText = 'Reanudando...';

            }
            if (status) status.textContent = newStatusText;

            fetch('/toggle_detection_pause', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                console.log("Respuesta de Flask /toggle_detection_pause:", data.status);
                if (data.status === 'Pausado') {

                    // Ya hemos cambiado el icono y el texto arriba
                    if (status) status.textContent = 'Pausado';
                    stopLivePollingExerciseData(); // Detener el polling al pausar

                } else if (data.status === 'Reanudado') {

                    // Ya hemos cambiado el icono y el texto arriba
                    if (status) status.textContent = 'Detectando...';
                    startLivePollingExerciseData(); // Reanudar el polling al reanudar

                } else {

                    console.warn("Estado desconocido recibido de Flask:", data.status);
                    if (status) status.textContent = 'Error de estado';

                }
            })
            .catch(error => {

                console.error('Error al alternar pausa/reanudación de detección:', error);
                if (status) status.textContent = 'Error de control';
                // Revertir el icono si hay un error de comunicación
                if (icon.classList.contains('fa-play')) { // Si está en "play" (estado de pausa fallido)

                    icon.classList.remove('fa-play');
                    icon.classList.add('fa-pause'); // Vuelve a "pause"

                } else { // Si está en "pause" (estado de reanudación fallido)

                    icon.classList.remove('fa-pause');
                    icon.classList.add('fa-play'); // Vuelve a "play"
                }
                // Mostrar notificación de error
                const notification = document.getElementById('notification');
                if (notification) {

                    notification.querySelector('.notification-title').textContent = 'Error de Control';
                    notification.querySelector('.notification-content').textContent = `No se pudo alternar el estado de la detección: ${error.message}.`;
                    notification.classList.add('show', 'error');
                }
            });
        });
    }

    // Botón de detener detección en la sección de Live Detection
    const liveStopDetectionBtn = document.getElementById('live-stop-detection');
    if (liveStopDetectionBtn) {

        liveStopDetectionBtn.addEventListener('click', function() {
            stopVideoFeed(); // Llama a la función para detener el stream y el polling
            console.log("Detección en vivo detenida por el usuario.");
        });
    } else {

        console.warn("El botón #live-stop-detection no fue encontrado. Asegúrate de añadirlo a tu HTML.");
    }
     
    // Lógica para los botones de análisis
    const analysisMenuButtons = document.querySelectorAll('#analysis-content .menu-button');
    analysisMenuButtons.forEach(button => {

        button.addEventListener('click', function() {

            const exerciseType = this.dataset.analysisType;
            console.log(`[Menu Button Click] Clicked on: ${this.textContent} (Analysis Type: ${exerciseType})`);

            const analysisSelectionMenu = document.getElementById('analysis-content').querySelector('.selection-menu-container');
            const analysisResultsArea = document.getElementById('analysis-results-area');
            const analysisLoader = document.getElementById('analysis-loader');
            const analysisProgressBar = document.getElementById('analysis-progress-container');
            const analysisMetricsPanel = document.getElementById('analysis-metrics-panel');
            const classificationReportPanel = document.getElementById('classification-report-panel');
            const analysisChartsContainer = document.getElementById('analysis-charts-container');

            // Ocultar el menú de selección y mostrar el área de resultados
            if (analysisSelectionMenu) analysisSelectionMenu.style.display = 'none';
            if (analysisResultsArea) analysisResultsArea.style.display = 'flex';

            // Mostrar el loader y la barra de progreso, ocultar resultados anteriores
            if (analysisLoader) analysisLoader.style.display = 'flex';
            if (analysisProgressBar) analysisProgressBar.style.display = 'block'; // Block para la barra de progreso
            if (analysisMetricsPanel) analysisMetricsPanel.style.display = 'none';
            if (classificationReportPanel) classificationReportPanel.style.display = 'none';
            if (analysisChartsContainer) analysisChartsContainer.style.display = 'none';
            destroyAllCharts(); // Limpiar gráficos anteriores

            console.log(`Iniciando análisis para: ${exerciseType}`);
            fetch('/analyze_exercise', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ exercise_type: exerciseType }),
            })
            .then(response => {

                if (!response.ok) {

                    // Intentar leer el mensaje de error del backend
                    return response.json().then(errorData => {
                        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {

                console.log("DEBUG: Resultados del análisis recibidos del backend:", data);
                if (analysisLoader) analysisLoader.style.display = 'none'; // Ocultar loader
                if (analysisProgressBar) analysisProgressBar.style.display = 'none'; // Ocultar barra de progreso

                if (data.status === 'success') {

                    // Mostrar los paneles de resultados
                    if (analysisMetricsPanel) analysisMetricsPanel.style.display = 'flex';
                    if (classificationReportPanel) classificationReportPanel.style.display = 'flex';
                    if (analysisChartsContainer) analysisChartsContainer.style.display = 'flex';

                    // Rellenar la tabla de métricas
                    const metricsBody = document.getElementById('metrics-table-body');
                    if (metricsBody) {

                        metricsBody.innerHTML = ''; // Limpiar tabla
                        for (const key in data.metrics) {

                            const row = metricsBody.insertRow();
                            const cellMetric = row.insertCell();
                            const cellValue = row.insertCell();
                            cellMetric.textContent = key.replace(/_/g, ' ').replace('optimal angle range', 'Rango de ángulo óptimo').replace('training time s', 'Tiempo de entrenamiento (s)').replace('evaluation time s', 'Tiempo de evaluación (s)'); // Formato legible
                            cellValue.textContent = data.metrics[key];
                        }
                    }

                    // Poblar la tabla del reporte de clasificación
                    if (data.classification_report_data) {

                        populateClassificationReportTable(data.classification_report_data);

                    } else {

                        console.warn("No se encontraron datos para el reporte de clasificación.");
                        // Opcional: Mostrar un mensaje en la tabla de clasificación
                    }
                    

                    // Renderizar los gráficos
                    console.log("Rendering Reps Chart...", data.chart_data_reps);
                    renderRepsChart(data.chart_data_reps);
                    console.log("Rendering Confusion Matrix Chart...", data.confusion_matrix_data);
                    renderConfusionMatrixChart(data.confusion_matrix_data);
                    console.log("Rendering ROC Chart...", data.roc_data);
                    renderRocChart(data.roc_data);
                    console.log("Rendering PR Chart...", data.pr_data);
                    renderPrChart(data.pr_data);

                } else {

                    // Mostrar un mensaje de error en el área de resultados
                    if (analysisResultsArea) {

                        analysisResultsArea.innerHTML = `<p class="chart-error-message">Error en el análisis: ${data.error || 'Mensaje desconocido'}</p>`;
                    }
                    console.error("Error del backend en el análisis:", data.error);
                }
            })
            .catch(error => {

                console.error('Error al iniciar el análisis:', error);
                if (analysisLoader) analysisLoader.style.display = 'none';
                if (analysisProgressBar) analysisProgressBar.style.display = 'none';
                if (analysisResultsArea) {

                    analysisResultsArea.innerHTML = `<p class="chart-error-message">Error de conexión o del servidor: ${error.message}</p>`;
                    analysisResultsArea.style.display = 'flex'; // Asegurarse de que el área de resultados se muestre para el mensaje de error
                }
            });
        });
    });

    // Manejador para los botones de descarga de gráficos
    document.querySelectorAll('.chart-btn[data-chart-id]').forEach(button => {
        
        button.addEventListener('click', function() {

            const chartId = this.dataset.chartId;
            let chartInstance;

            switch (chartId) {

                case 'chart-reps':
                    chartInstance = chartRepsInstance;
                    break;
                case 'chart-confusion-matrix':
                    chartInstance = chartConfusionMatrixInstance;
                    break;
                case 'chart-roc':
                    chartInstance = chartRocInstance;
                    break;
                case 'chart-pr':
                    chartInstance = chartPrInstance;
                    break;
                default:
                    console.error('ID de gráfico desconocido:', chartId);
                    return;
            }

            if (chartInstance) {

                // Obtener la URL de la imagen del gráfico
                const image = chartInstance.toBase64Image();

                // Crear un enlace para descargar la imagen
                const a = document.createElement('a');
                a.href = image;
                a.download = `${chartId}.png`; // Nombre del archivo
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);

            } else {

                console.warn(`No se encontró la instancia del gráfico para descargar: ${chartId}`);
                
                const notification = document.getElementById('notification');

                if (notification) {

                    notification.querySelector('.notification-title').textContent = 'Descarga Fallida';
                    notification.querySelector('.notification-content').textContent = `No se pudo descargar el gráfico. Asegúrate de que el análisis se haya completado.`;
                    notification.classList.add('show', 'warning');
                }
            }
        });
    });

    // Función para mostrar notificaciones
    // Asegurarse de que tu HTML tenga un div con id="notification" y las clases "notification-header", "notification-title", "notification-content", "notification-close"
    // y los estilos en style_claude.css
    const notificationElement = document.getElementById('notification');
    const notificationCloseBtn = document.querySelector('.notification-close');

    if (notificationCloseBtn && notificationElement) {

        notificationCloseBtn.addEventListener('click', function() {

            notificationElement.classList.remove('show', 'error', 'warning', 'success'); // Remover todas las clases de estado
        });
    }


    // Inicializar la página en "Inicio" y configurar el historial
    // Solo cuando se carga la página por primera vez
    if (navigationHistory.length === 0) {

        showSection('home-content', 'Inicio', true); // Añadir Inicio al historial
        // Asegurarse de que el enlace de 'Inicio' en la sidebar esté activo
        const homeNavLink = document.querySelector('.sidebar-menu a[data-content="home"]');
        if (homeNavLink) {

            homeNavLink.classList.add('active');
        }
    }

    // Lógica del Carrusel de Imágenes en la Sección de Inicio
    const heroImages = document.querySelectorAll('.hero-image');
    let currentImageIndex = 0;
    const carouselIntervalTime = 5000; // Cambia la imagen cada 5 segundos (5000 ms)

    //Muestra la imagen actual y oculta las demás.
    function showImage() {

        heroImages.forEach((image, index) => {

            if (index === currentImageIndex) {

                image.classList.add('active');

            } else {

                image.classList.remove('active');
            }
        });
    }

    //Avanza a la siguiente imagen en el carrusel. Si llega al final, vuelve al principio.
    function nextImage() {

        currentImageIndex = (currentImageIndex + 1) % heroImages.length;
        showImage();
    }

    // Inicializar el carrusel: mostrar la primera imagen y empezar el intervalo
    if (heroImages.length > 0) {

        showImage(); // Asegurarse de que la primera imagen esté activa al cargar
        setInterval(nextImage, carouselIntervalTime);
    }

    // Logica para el boton toggle-sidebar
    const toggleSidebarBtn = document.querySelector('.toggle-sidebar');
    const sidebar = document.querySelector('.sidebar');

    if (toggleSidebarBtn && sidebar) {

        toggleSidebarBtn.addEventListener('click', () => {

            sidebar.classList.toggle('active');
        });

    } // Fin de la logica

    // Lógica para el botón de Pantalla Completa
    const fullscreenButton = document.querySelector('.video-controls-right .fa-expand').closest('button');
    const videoContainer = document.querySelector('.video-container'); 

    if (fullscreenButton && videoContainer) {

        fullscreenButton.addEventListener('click', () => {

            if (!document.fullscreenElement) {

                // Entrar en modo pantalla completa
                if (videoContainer.requestFullscreen) {

                    videoContainer.requestFullscreen();

                } else if (videoContainer.mozRequestFullScreen) { /* Firefox */

                    videoContainer.mozRequestFullScreen();

                } else if (videoContainer.webkitRequestFullscreen) { /* Chrome, Safari & Opera */

                    videoContainer.webkitRequestFullscreen();

                } else if (videoContainer.msRequestFullscreen) { /* IE/Edge */

                    videoContainer.msRequestFullscreen();
                }
            } else {

                // Salir del modo pantalla completa

                if (document.exitFullscreen) {

                    document.exitFullscreen();

                } else if (document.mozCancelFullScreen) { /* Firefox */

                    document.mozCancelFullScreen();

                } else if (document.webkitExitFullscreen) { /* Chrome, Safari and Opera */

                    document.webkitExitFullscreen();

                } else if (document.msExitFullscreen) { /* IE/Edge */

                    document.msExitFullscreen();
                }
            }
        });

        // Event listener para cambiar el icono del botón cuando el estado de pantalla completa cambie
        document.addEventListener('fullscreenchange', () => {

            const icon = fullscreenButton.querySelector('i');

            if (document.fullscreenElement) {
                
                icon.classList.remove('fa-expand');
                icon.classList.add('fa-compress');
                videoContainer.classList.add('is-fullscreen'); // Añadir clase para estilos CSS específicos

            } else {

                icon.classList.remove('fa-compress');
                icon.classList.add('fa-expand');
                videoContainer.classList.remove('is-fullscreen'); // Quitar clase
            }
        });

        document.addEventListener('webkitfullscreenchange', () => { // Para navegadores basados en Webkit

            const icon = fullscreenButton.querySelector('i');

            if (document.webkitFullscreenElement) {

                icon.classList.remove('fa-expand');
                icon.classList.add('fa-compress');
                videoContainer.classList.add('is-fullscreen');

            } else {

                icon.classList.remove('fa-compress');
                icon.classList.add('fa-expand');
                videoContainer.classList.remove('is-fullscreen');
            }
        });
    }

});