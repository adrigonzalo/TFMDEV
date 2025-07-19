from flask import Flask, render_template, Response, jsonify, request
import cv2
import threading
import time
import os
import numpy as np

# Generacion de PDFs
from fpdf import FPDF

# Importar los detectores de pose
from utils.shoulder_press_flask import ShoulderPressDetector
from utils.flexiones_prueba_flask import PushupDetector
from utils.sentadilla_trasera_prueba_analiza_flask import SquatDetector
from utils.peso_muerto_prueba_analiza_flask import DeadliftDetector

# Importar la función para entrenar y evaluar el modelo
# Asegurarse de que 'model' exista y tenga la función 'entrenar_y_evaluar_modelo'
from model_3 import entrenar_y_evaluar_modelo

app = Flask(__name__)

# CONFIGURACIÓN GLOBAL
cap = None
current_detector = None
output_frame = None
latest_exercise_data = {}
processing_active = False
frame_lock = threading.Lock()
data_lock = threading.Lock()
pose_detection_paused = False 

active_detectors = {
    "shoulder_press": ShoulderPressDetector(csv_file_path=os.path.join(os.getcwd(), 'data', 'coords_press_hombro.csv')),
    "pushups": PushupDetector(csv_file_path=os.path.join(os.getcwd(), 'data', 'coords_flexiones.csv')),
    "squats": SquatDetector(csv_file_name=os.path.join(os.getcwd(), 'data', 'coords_sentadilla.csv')),
    "deadlift": DeadliftDetector(csv_file_name=os.path.join(os.getcwd(), 'data', 'coords_peso_muerto.csv'))
}

# Rutas a los archivos CSV de coordenadas para cada ejercicio
CSV_PATHS = {
    "squats": os.path.join(os.getcwd(), 'data', 'coords_sentadilla.csv'),
    "pushups": os.path.join(os.getcwd(), 'data', 'coords_flexiones.csv'),
    "deadlift": os.path.join(os.getcwd(), 'data', 'coords_peso_muerto.csv'),
    "shoulder_press": os.path.join(os.getcwd(), 'data', 'coords_press_hombro.csv'),
}

# Rutas para guardar los modelos entrenados
MODEL_PATHS = {
    "squats": os.path.join(os.getcwd(), 'models', 'sentadilla_model.pkl'),
    "pushups": os.path.join(os.getcwd(), 'models', 'flexiones_model.pkl'),
    "deadlift": os.path.join(os.getcwd(), 'models', 'peso_muerto_model.pkl'),
    "shoulder_press": os.path.join(os.getcwd(), 'models', 'press_hombro_model.pkl'),
}


# Configuracion para guardar PDFs de Feedback
PDF_SAVE_DIR = "feedback_pdfs"
os.makedirs(PDF_SAVE_DIR, exist_ok=True)


# FUNCIONES DE PROCESAMIENTO DE VIDEO EN VIVO
def start_video_processing(detector_key, camera_id=0): 
    global cap, current_detector, processing_active, output_frame, latest_exercise_data, pose_detection_paused

    # Detener cualquier procesamiento activo antes de iniciar uno nuevo
    if processing_active:
        print("Ya hay un procesamiento activo. Deteniéndolo primero.")
        stop_video_processing()
        time.sleep(0.5) # Pequeña pausa para asegurar que el hilo anterior se cierre

    # Reiniciar current_detector a None antes de asignarlo para el nuevo ejercicio
    current_detector = None 
    
    # Limpiar el último fotograma y datos de ejercicio al iniciar un nuevo stream
    with frame_lock:

        output_frame = None 

    with data_lock:
        
        latest_exercise_data = {
            "reps": 0,
            "incorrect_reps": 0,
            "stage": "Inicializando..." # Estado inicial mientras la cámara se abre
        }


    if detector_key in active_detectors:
        current_detector = active_detectors[detector_key]
        print(f"Iniciando detección para: {detector_key}")
    else:
        print(f"Error: Detector '{detector_key}' no encontrado. No se iniciará la detección de pose para este tipo de ejercicio.")
        processing_active = False 
        with data_lock:

            latest_exercise_data = {
                "reps": 0,
                "incorrect_reps": 0,
                "stage": "ERROR: Ejercicio no válido"
            }
        return

    # Reiniciar contadores y datos del detector seleccionado antes de iniciar el procesamiento
    current_detector.reset_counters() # Asegurarse de que los detectores tienen un método reset_counters()
    

    cap = cv2.VideoCapture(camera_id) # 0 para la webcam por defecto
    if not cap.isOpened():

        print("Error: No se pudo abrir la cámara. Asegúrate de que esté conectada y no esté en uso.")
        processing_active = False
        with data_lock:

            latest_exercise_data["stage"] = "ERROR: Cámara no disponible"

        return


    processing_active = True
    pose_detection_paused = False # Asegurarse de que no esté pausado al iniciar un nuevo feed
    print("Cámara abierta y procesamiento iniciado.")

    while processing_active:

        ret, frame = cap.read()

        if not ret:

            print("Error: No se pudo leer el fotograma. Deteniendo procesamiento.")
            processing_active = False 

            with data_lock:

                latest_exercise_data["stage"] = "ERROR: Stream de cámara falló"

            break

        processed_img = frame.copy() 
        current_exercise_data = latest_exercise_data # Obtener los últimos datos para mantenerlos si está pausado

        if not pose_detection_paused and current_detector: # Solo procesar si no está pausado y hay un detector
            processed_img, current_exercise_data = current_detector.process_frame(frame)

        elif pose_detection_paused:
            # Si está pausado, puedes mostrar un mensaje en el frame original
            cv2.putText(processed_img, 'PAUSADO', (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3, cv2.LINE_AA)

        elif not current_detector: # Caso de error si no hay detector (aunque el flujo debería prevenir esto)
            cv2.putText(processed_img, 'ERROR: Detector no inicializado', (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3, cv2.LINE_AA)

        # Convertir el fotograma procesado a JPEG para el stream
        ret, jpeg = cv2.imencode('.jpg', processed_img)
        if ret:

            with frame_lock:

                output_frame = jpeg.tobytes()

            with data_lock:

                # Solo actualizar los datos de ejercicio si la detección NO está pausada
                if not pose_detection_paused:

                    latest_exercise_data = current_exercise_data # Actualizar con los datos más recientes
        
        # Pequeña pausa para no saturar la CPU
        time.sleep(0.01) # ~100 FPS 

    print("Bucle de procesamiento de video finalizado.")
    stop_video_processing_resources() # Asegura que los recursos se liberen al salir del bucle

def stop_video_processing_resources():
    
    global cap
    if cap:

        print("Liberando recursos de la cámara...")
        cap.release()
    cap = None # Asegurar que cap se resetee a None
    print("Recursos de video liberados.")

def stop_video_processing():

    global processing_active, latest_exercise_data, pose_detection_paused
    if processing_active:

        print("Solicitando detención del procesamiento de video...")
        processing_active = False
        pose_detection_paused = False # Asegurarse de resetear el estado de pausa al detener completamente
        # Dar un pequeño tiempo para que el hilo termine su ejecución
        time.sleep(0.5) 
        stop_video_processing_resources() # Llamar a la función que libera recursos
        print("Procesamiento de video detenido completamente.")
    else:

        print("El procesamiento de video ya está detenido.")

    # Restablecer los datos del ejercicio al detener el procesamiento
    with data_lock:

        latest_exercise_data = {

            "reps": 0,
            "incorrect_reps": 0,
            "stage": "Detenido" # Estado al detener
        }


# Función generadora para el stream de video (MJPEG)
def generate_frames():

    global output_frame, processing_active, frame_lock

    # Esperar a que el hilo de procesamiento se active y produzca el primer fotograma
    # Añadir un tiempo de espera para evitar un bucle infinito si el procesamiento nunca comienza
    timeout_start = time.time()
    # Espera hasta que el procesamiento esté activo Y haya un fotograma disponible
    while not processing_active or output_frame is None:

        if time.time() - timeout_start > 15:  # 15 segundos de timeout para dar tiempo a la inicialización

            print("Tiempo de espera agotado: El procesamiento de video no se inició o no produjo un fotograma en 15 segundos.")
            # Si hay un error, puedes intentar enviar un fotograma de "error"
            error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(error_frame, 'ERROR: Camara no disponible', (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
            ret, jpeg = cv2.imencode('.jpg', error_frame)

            if ret:

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            break
        time.sleep(0.1) # Pequeña pausa para evitar el uso excesivo de CPU

    # Ahora, el bucle principal para enviar fotogramas
    while processing_active:

        with frame_lock:

            if output_frame is not None:

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + output_frame + b'\r\n')
        time.sleep(0.03) # Controla la tasa de fotogramas enviados al navegador (ej. ~30 FPS)
    print("Generador de frames finalizado.")



def get_next_feedback_filename(): 

    """
    Genera el siguiente nombre de archivo incremental para el PDF de feedback.
    Ejemplo: Feedback_1.pdf, Feedback_2.pdf, etc.
    """
    base_name = "Feedback" 
    extension = ".pdf" 
    i = 1 
    while True: 

        filename = os.path.join(PDF_SAVE_DIR, f"{base_name}_{i}{extension}") 

        if not os.path.exists(filename): 

            return filename 
        i += 1 

# RUTAS DE FLASK

@app.route('/')
def index():

    # Renderizar el archivo HTML principal
    return render_template('index.html') # Asegurarse de que el nombre de tu archivo HTML sea correcto

@app.route('/video_feed/<exercise_type>')
def video_feed(exercise_type):

    # Inicia el procesamiento de video en un hilo separado
    # Esto es crucial para que Flask no bloquee la interfaz de usuario

    # Iniciar el nuevo procesamiento con el detector solicitado
    # El threading.Thread se inicia en modo daemon para que se cierre con la aplicación Flask
    thread = threading.Thread(target=start_video_processing, args=(exercise_type,))
    thread.daemon = True 
    thread.start()

    # Retorna la respuesta para el stream MJPEG
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stop_feed')
def stop_feed():

    # Ruta para detener el stream de video de forma explícita
    stop_video_processing()
    return "Video feed stopped", 200

@app.route('/exercise_data')
def get_exercise_data():

    # Ruta para obtener los últimos datos del ejercicio vía AJAX (polling)
    global latest_exercise_data
    with data_lock:

        # Aquí se puede añadir cualquier transformación o filtrado si es necesario
        return jsonify(latest_exercise_data)

# Ruta para pausar/reanudar la deteccion 
@app.route('/toggle_detection_pause', methods=['POST'])
def toggle_detection_pause():

    global pose_detection_paused, current_detector, processing_active # Asegurarse de incluir processing_active aquí
    # Solo alternar si hay un detector actualmente activo y el procesamiento está activo
    if current_detector and processing_active:

        pose_detection_paused = not pose_detection_paused
        status_message = "Pausado" if pose_detection_paused else "Reanudado"
        print(f"Detección de pose: {status_message}")
        return jsonify({"status": status_message}), 200
    # Si no hay detector activo o el procesamiento no está en marcha, no se puede pausar/reanudar.
    return jsonify({"status": "No hay detección activa para pausar/reanudación"}), 400


# Ruta para analisis de datos del modelo 
@app.route('/analyze_exercise', methods=['POST'])
def analyze_exercise():

    data = request.get_json()
    exercise_type = data.get('exercise_type')

    if exercise_type not in CSV_PATHS or exercise_type not in MODEL_PATHS:

        return jsonify({"error": "Tipo de ejercicio no válido o rutas de archivo no configuradas"}), 400

    csv_file = CSV_PATHS[exercise_type]
    model_output_file = MODEL_PATHS[exercise_type]

    try:

        # Llama a la función real de entrenamiento y evaluación del modelo
        # entrenar_y_evaluar_modelo devuelve un diccionario
        # con todas las métricas y datos de gráficos necesarios.
        analysis_results = entrenar_y_evaluar_modelo(csv_file, model_output_file)

        if analysis_results:

            # Asegurarse de que el status sea 'success' si la función devuelve resultados
            # y los datos existen.
            analysis_results["status"] = "success"
            print(f"Análisis exitoso para {exercise_type}. Devolviendo resultados.")
            return jsonify(analysis_results), 200
        
        else:

            print(f"Fallo en el entrenamiento del modelo para {exercise_type}. La función retornó None o un valor vacío.")
            return jsonify({"error": "Fallo en el entrenamiento o evaluación del modelo", "status": "failed"}), 500
        
    except Exception as e:

        print(f"Error durante el análisis del ejercicio {exercise_type}: {e}")
        return jsonify({"error": f"Error interno del servidor durante el análisis: {str(e)}", "status": "error"}), 500

# Ruta para el formulario de feedback
@app.route('/feedback_form')
def feedback_form():

    return render_template('index_form.html')

@app.route('/submit_feedback', methods=['POST']) 
def submit_feedback(): 

    """
    Recibe los datos del formulario de feedback y genera un PDF con las respuestas.
    """
    try:
        data = request.get_json() 
        if not data: 

            return jsonify({"status": "error", "message": "No se recibieron datos JSON"}), 400 

        pdf = FPDF() 
        pdf.add_page() 
        pdf.set_font("Arial", size=12) 

        pdf.multi_cell(0, 10, "Formulario e Feedback de la Herramienta") #
        pdf.ln(10) 

        questions_order = [ 
            "¿Fue sencillo comenzar a usar la web?",
            "¿La pantalla y los menús de la aplicación son claros y fáciles de entender?",
            "¿Tuviste algún problema técnico importante mientras lo utilizabas?",
            "¿Crees que cualquier persona, independientemente de su familiaridad con la tecnología, podría manejar este sistema sin problemas?",
            "¿Hay algo que, al modificarlo, haría que el dispositivo fuera aún más sencillo de usar?",
            "¿La información sobre tus posturas fue correcta ?",
            "¿Cuánto te ayudó la información de la herramienta a detectar tus errores al ejecutar los movimientos?",
            "¿Hubo algún momento en que sentiste que lo que se te indicaba sobre tu postura no era acertado?",
            "¿La aplicacion contribuyó a mejorar tus posturas mientras te ejercitabas?",
            "¿Recomendarías esta web a otras personas interesadas en optimizar su técnica y postura al hacer ejercicio?",
            "¿Tienes algún otro comentario o sugerencia?"
        ]

        for question in questions_order: 

            answer = data.get(question, "No respondido") 
            pdf.multi_cell(0, 7, f"Pregunta: {question}") 
            pdf.multi_cell(0, 7, f"Respuesta: {answer}") 
            pdf.ln(3) 

        pdf_filename = get_next_feedback_filename() 
        pdf.output(pdf_filename) 

        print(f"Feedback PDF guardado: {pdf_filename}") 
        return jsonify({"status": "success", "message": "Feedback recibido y PDF generado", "filename": os.path.basename(pdf_filename)}), 200 

    except Exception as e: 

        print(f"Error procesando el feedback: {e}") 
        return jsonify({"status": "error", "message": f"Error interno del servidor: {str(e)}"}), 500 

if __name__ == '__main__':

    try:

        app.run(host='127.0.0.1', port=8080, debug=True, threaded=True, use_reloader=False) # use_reloader=False para evitar problemas de doble ejecución con hilos

    finally:

        print("Aplicación Flask finalizada. Asegurando que los recursos de video estén liberados.")
        stop_video_processing() # Asegura que la cámara se libere al cerrar la app