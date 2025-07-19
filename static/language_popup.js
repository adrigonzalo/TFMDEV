document.addEventListener('DOMContentLoaded', () => {

    console.log("language_popup.js: DOMContentLoaded cargado. Iniciando script del pop-up.");

    const languagePopup = document.getElementById('language-popup');
    const patternContainer = document.getElementById('language-overlay');
    const closeWelcomePopupButton = document.getElementById('close-welcome-popup');

    console.log("language_popup.js: Elementos HTML seleccionados:", {
        languagePopup: languagePopup,
        patternContainer: patternContainer,
        closeWelcomePopupButton: closeWelcomePopupButton
    });

    if (!languagePopup) console.error("language_popup.js: ERROR - Elemento con ID 'language-popup' no encontrado.");
    if (!patternContainer) console.error("language_popup.js: ERROR - Elemento con ID 'language-overlay' no encontrado.");
    if (!closeWelcomePopupButton) console.error("language_popup.js: ERROR - Elemento con ID 'close-welcome-popup' no encontrado.");

    let animationIntervals = [];

    let containerWidth = patternContainer ? patternContainer.offsetWidth : window.innerWidth;
    let containerHeight = patternContainer ? patternContainer.offsetHeight : window.innerHeight;

    const MIN_LINE_LENGTH_PX = 100;
    const MAX_LINE_LENGTH_PX = 250;
    const LINE_DRAW_DURATION = 2500;
    const POINT_FADE_DURATION = 400;
    const INITIAL_POINT_OPACITY = 0.5;
    const LINE_OPACITY = 0.5;
    const POINT_SIZE = 12;
    const LINE_THICKNESS = 10;
    const NUMBER_OF_SIMULTANEOUS_LINES = 20;

    const resizeObserver = new ResizeObserver(entries => {

        for (let entry of entries) {

            if (entry.target === patternContainer) {
                containerWidth = entry.contentRect.width;
                containerHeight = entry.contentRect.height;
            }
        }
    });
    if (patternContainer) {

        resizeObserver.observe(patternContainer);
    }

    function clearPattern() {

        if (patternContainer) {

            patternContainer.innerHTML = '';
        }
        animationIntervals.forEach(interval => clearInterval(interval));
        animationIntervals = [];
        console.log("language_popup.js: Patrón de animación limpiado.");
    }

    function createPoint(x, y) {

        if (!patternContainer) return;
        const point = document.createElement('div');
        point.classList.add('pattern-point');
        point.style.left = `${x}px`;
        point.style.top = `${y}px`;
        point.style.width = `${POINT_SIZE}px`;
        point.style.height = `${POINT_SIZE}px`;
        point.style.opacity = INITIAL_POINT_OPACITY;
        patternContainer.appendChild(point);

        setTimeout(() => {

            point.style.opacity = 0;
            point.addEventListener('transitionend', () => point.remove(), { once: true });
        }, LINE_DRAW_DURATION - POINT_FADE_DURATION);
    }

    function createLine(x1, y1, x2, y2) {

        if (!patternContainer) return;
        const line = document.createElement('div');
        line.classList.add('pattern-line');
        line.style.left = `${x1}px`;
        line.style.top = `${y1}px`;
        
        const rootStyles = getComputedStyle(document.documentElement);
        // Obtener el color secundario de las variables CSS
        const secondaryColor = rootStyles.getPropertyValue('--secondary-color').trim();
        let r, g, b;

        // Intentar parsear el color (puede ser HEX o RGB)
        if (secondaryColor.startsWith('#')) {

            r = parseInt(secondaryColor.substring(1, 3), 16);
            g = parseInt(secondaryColor.substring(3, 5), 16);
            b = parseInt(secondaryColor.substring(5, 7), 16);

        } else if (secondaryColor.startsWith('rgb')) {

            const rgbMatch = secondaryColor.match(/\d+/g);

            if (rgbMatch) {

                [r, g, b] = rgbMatch.map(Number);

            } else {

                r = 199; g = 115; b = 222; // Valor por defecto si falla el parseo
            }
        } else {

            r = 199; g = 115; b = 222; // Valor por defecto si no es ni HEX ni RGB
        }

        // Aplicar el color con la opacidad deseada (LINE_OPACITY)
        line.style.backgroundColor = `rgba(${r}, ${g}, ${b}, ${LINE_OPACITY})`;
        line.style.height = `${LINE_THICKNESS}px`;

        console.log("Creando línea:", { x1, y1, x2, y2 });
        console.log("Color de línea calculado:", line.style.backgroundColor);
        console.log("Opacidad de línea aplicada:", LINE_OPACITY);
        console.log("Altura de línea (grosor):", line.style.height);
        
        
        const dx = x2 - x1;
        const dy = y2 - y1;
        const length = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx) * 180 / Math.PI;

        line.style.width = '0px';
        line.style.transform = `rotate(${angle}deg)`;
        patternContainer.appendChild(line);

        // Fuerza un reflow para asegurar que la transición de width se aplique correctamente
        void line.offsetWidth; 

        console.log("Longitud de línea a animar:", length, "px");

        setTimeout(() => {

            line.style.width = `${length}px`;

            console.log("Animando ancho de línea a:", line.style.width);
        }, 10); 

        // La línea se hace transparente y se elimina después de un tiempo
        setTimeout(() => {

            line.style.opacity = 0;
            line.addEventListener('transitionend', () => line.remove(), { once: true });

            console.log("Línea desapareciendo/removiendo.");
            
        }, LINE_DRAW_DURATION - POINT_FADE_DURATION);
    }

    function drawPattern() {

        if (!patternContainer || !languagePopup || languagePopup.classList.contains('hidden')) {

            return;
        }

        const startX = Math.random() * containerWidth;
        const startY = Math.random() * containerHeight;

        // Asegurarse de que el punto final no se salga demasiado del contenedor
        let endX = startX + (Math.random() * 2 - 1) * MAX_LINE_LENGTH_PX;
        let endY = startY + (Math.random() * 2 - 1) * MAX_LINE_LENGTH_PX;

        // Limitar endX y endY a los límites del contenedor
        endX = Math.max(0, Math.min(containerWidth, endX));
        endY = Math.max(0, Math.min(containerHeight, endY));

        createPoint(startX, startY);
        createLine(startX, startY, endX, endY);
    }

    function startPatternAnimation() {

        console.log("language_popup.js: startPatternAnimation() llamado.");
        if (animationIntervals.length === 0) { 

            for (let i = 0; i < NUMBER_OF_SIMULTANEOUS_LINES; i++) {

                setTimeout(() => {

                    drawPattern();
                    const interval = setInterval(drawPattern, LINE_DRAW_DURATION);
                    animationIntervals.push(interval);
                }, (LINE_DRAW_DURATION / NUMBER_OF_SIMULTANEOUS_LINES) * i);
            }
            console.log("language_popup.js: Animación del patrón iniciada.");

        } else {

            console.log("language_popup.js: Animación del patrón ya en curso, no se reinicia.");
        }
    }

    function showWelcomePopup() {

        console.log("language_popup.js: showWelcomePopup() llamado.");

        if (!languagePopup || !patternContainer) {

            console.error("language_popup.js: No se puede mostrar el popup, elementos no encontrados.");
            return;
        }

        patternContainer.style.display = 'block'; 
        languagePopup.style.display = 'block';   

        patternContainer.classList.remove('hidden');
        languagePopup.classList.remove('hidden');

        patternContainer.style.opacity = '1';
        languagePopup.style.opacity = '1';
        languagePopup.style.transform = 'translate(-50%, -50%) scale(1)'; 
        
        console.log("language_popup.js: Clases de languagePopup:", languagePopup.classList.value);
        console.log("language_popup.js: Estilos aplicados a languagePopup:", languagePopup.style.opacity, languagePopup.style.transform, languagePopup.style.display);
        console.log("language_popup.js: Clases de patternContainer:", patternContainer.classList.value);
        console.log("language_popup.js: Estilos aplicados a patternContainer:", patternContainer.style.opacity, patternContainer.style.display);
        
        startPatternAnimation();
        console.log("language_popup.js: Pop-up y overlay mostrados.");
    }

    
    //Oculta el pop-up de bienvenida y el overlay, y detiene la animación.
    function hideWelcomePopup() {

        console.log("language_popup.js: hideWelcomePopup() llamado.");
        if (!languagePopup || !patternContainer) return;

        // Inicia la transición de salida (opacidad y transform)
        languagePopup.style.opacity = '0';
        languagePopup.style.transform = 'translate(-50%, -50%) scale(0.8)'; // Efecto de encogimiento al ocultar
        patternContainer.style.opacity = '0';

        // Una vez terminada la transición, ocultar con display: none;
        setTimeout(() => {

            languagePopup.style.display = 'none'; // Asegura que el pop-up no sea visible
            patternContainer.style.display = 'none'; // Asegura que el overlay no sea visible
            languagePopup.classList.add('hidden'); // Añadir la clase 'hidden'
            patternContainer.classList.add('hidden'); // Igual para el overlay

            clearPattern(); // Limpia y detiene la animación del patrón
            console.log("language_popup.js: Pop-up y overlay ocultados.");
        }, 300); // Este tiempo debe coincidir con la 'transition-speed' del CSS
    }

    if (closeWelcomePopupButton) {

        closeWelcomePopupButton.addEventListener('click', () => {
            console.log("language_popup.js: Botón 'EMPEZAR' clickeado. Intentando ocultar pop-up."); // Debugging: confirmar clic
            hideWelcomePopup();
        });
    } else {
        
        console.error("language_popup.js: ERROR - Botón 'close-welcome-popup' no encontrado para añadir event listener.");
    }

    showWelcomePopup();
});