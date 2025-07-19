import cv2
import mediapipe as mp
import numpy as np
import os
import csv
import traceback


mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

def calculate_angle(a, b, c):
    """
    Calcula el angulo entre tres puntos.
    Basado en la logica "angle = np.degrees(radians); if angle > 180.0: angle = 360 - angle".
    """
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.degrees(radians)

    if angle > 180.0:
        angle = 360 - angle
    elif angle < 0:
        angle = abs(angle)
    return angle

def evaluate_squat(knee_angle, hip_angle, back_angle):
    """
    Evalua la forma de la sentadilla basandose en los angulos calculados.
    Se espera que estos angulos sean los internos (hip-knee-ankle, shoulder-hip-knee, shoulder-hip-ankle).

    Parametros:
    knee_angle (float): angulo de la rodilla en grados.
    hip_angle (float): angulo de la cadera en grados.
    back_angle (float): angulo de la espalda en grados.

    Retorna:
    str: Un mensaje indicando si la sentadilla es correcta o que desviacion se detecto.
    """
    feedback = "Forma Correcta"

    KNEE_IDEAL_MIN = 20
    HIP_IDEAL_MIN = 40
    BACK_IDEAL_MIN = 70

    if knee_angle is not None and knee_angle < KNEE_IDEAL_MIN:
        feedback = "Rodillas se doblan demasiado"
    elif hip_angle is not None and hip_angle < HIP_IDEAL_MIN:
        feedback = "Caderas se doblan demasiado"
    elif back_angle is not None and back_angle < BACK_IDEAL_MIN:
        feedback = "Espalda se inclina demasiado"
    
    return feedback

class SquatDetector:
    def __init__(self, csv_file_name='coords_sentadilla.csv'):
        self.pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

        # Variables de estado para el contador de repeticiones y la evaluacion
        self.KNEE_ANGLE_UP_THRESHOLD = 160
        self.KNEE_ANGLE_DOWN_THRESHOLD = 110

        self.squat_state = "up"
        self.reps_count = 0
        self.incorrect_reps_count = 0
        self.current_feedback = "Esperando..."
        self.repetition_has_error = False

        # Configuracion CSV
        self.csv_file_name = csv_file_name
        self.landmarks_header = ['class']
        for val in range(1, 33 + 1):
            self.landmarks_header += ['x{}'.format(val), 'y{}'.format(val), 'z{}'.format(val), 'v{}'.format(val)]
        self._initialize_csv()

    def _initialize_csv(self):
        # Eliminar el archivo CSV existente si lo hay
        if os.path.exists(self.csv_file_name):
            os.remove(self.csv_file_name)
            print(f"Archivo '{self.csv_file_name}' existente eliminado.")

        # Crear o abrir el archivo CSV para escribir el encabezado
        with open(self.csv_file_name, mode='w', newline='') as f:
            csv_writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(self.landmarks_header)
        print(f"Archivo CSV '{self.csv_file_name}' creado con el encabezado.")

    def _export_landmark(self, results, action):
        """
        Exporta los landmarks de la pose detectada a un archivo CSV.
        """
        try:
            if results.pose_landmarks:
                
                keypoints = np.array([[res.x, res.y, res.z, res.visibility] for res in results.pose_landmarks.landmark]).flatten()
                keypoints_list = keypoints.tolist()
                keypoints_list.insert(0, action)

                with open(self.csv_file_name, mode='a', newline='') as f:
                    csv_writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                    csv_writer.writerow(keypoints_list)
        except Exception as e:
            pass

    def process_frame(self, frame):
        """
        Procesa un solo fotograma para la deteccion de sentadillas.

        Args:
            frame (np.array): El fotograma de video (BGR).

        Returns:
            tuple: Un fotograma procesado (BGR) y un diccionario con las metricas.
        """
        # Invertir el frame horizontalmente para que actue como un espejo
        frame = cv2.flip(frame, 1)

        # Convertir a RGB para MediaPipe
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False

        # Realizar la deteccion de pose
        results = self.pose.process(image)

        # Volver a BGR para OpenCV
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        # Inicializar metricas para el retorno
        metrics = {
            'reps': self.reps_count,
            'incorrect_reps': self.incorrect_reps_count,
            'feedback': self.current_feedback,
            'knee_angle': -1, # Valores predeterminados
            'hip_angle': -1,
            'back_angle': -1
        }

        try:
            if results.pose_landmarks:

                landmarks = results.pose_landmarks.landmark

                # Obtener coordenadas de los landmarks relevantes
                shoulder_left = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
                hip_left = [landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x, landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y]
                knee_left = [landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x, landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y]
                ankle_left = [landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x, landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y]

                # Calcular los angulos de interes (rodilla, cadera, espalda)
                knee_angle = calculate_angle(hip_left, knee_left, ankle_left)
                hip_angle = calculate_angle(shoulder_left, hip_left, knee_left)
                back_angle = calculate_angle(shoulder_left, hip_left, ankle_left)

                metrics['knee_angle'] = int(knee_angle)
                metrics['hip_angle'] = int(hip_angle)
                metrics['back_angle'] = int(back_angle)

                # Evaluar la forma de la sentadilla en cada frame
                form_feedback = evaluate_squat(knee_angle, hip_angle, back_angle)

                if form_feedback != "Forma Correcta":

                    self.repetition_has_error = True
                    self.current_feedback = form_feedback
                else:

                    # Si no hay errores de forma, restablecer el feedback, a menos que ya estemos en una repetición con error
                    if not self.repetition_has_error:
                         
                         self.current_feedback = "Forma Correcta"


                # Lógica para detectar repeticiones y actualizar el estado
                if self.squat_state == "up":

                    if knee_angle < self.KNEE_ANGLE_DOWN_THRESHOLD:

                        self.squat_state = "down"
                        self.current_feedback = "Bajando..." # Esto se usa si la transición es a 'down'
                        self.repetition_has_error = False # Resetear error para la nueva repeticion

                elif self.squat_state == "down":

                    if knee_angle > self.KNEE_ANGLE_UP_THRESHOLD:

                        self.squat_state = "up"
                        if not self.repetition_has_error:

                            self.reps_count += 1
                            self.current_feedback = "Repetición Correcta"
                            self._export_landmark(results, 'correct_rep')
                        else:

                            self.incorrect_reps_count += 1
                            # Mantener el feedback de error si hubo uno
                            # self.current_feedback ya contendria el error
                            self._export_landmark(results, self.current_feedback.replace(" ", "_").lower())
                        self.repetition_has_error = False # Resetear para la siguiente

                # El 'stage' refleja el estado de movimiento (arriba/abajo) o el feedback específico.
                # Se prioriza el feedback si hay un error o una repetición completada,
                # de lo contrario, se muestra el estado de la sentadilla (subiendo/bajando/arriba/abajo).

                # Primero, establecer el stage basado en el estado general de la sentadilla
                if self.squat_state == "up":

                    # Si estamos en "up" state, el usuario esta arriba o subiendo
                    if knee_angle > self.KNEE_ANGLE_UP_THRESHOLD - 5: # Pequeño buffer para el estado "arriba"
                         metrics['stage'] = "Arriba"
                    else:
                         metrics['stage'] = "Subiendo..." # Si el ángulo de la rodilla es menor que el umbral "up" pero aún en estado "up", es probable que esté subiendo.

                elif self.squat_state == "down":

                    # Si estamos en "down" state, el usuario esta abajo o bajando
                    if knee_angle < self.KNEE_ANGLE_DOWN_THRESHOLD + 5: # Pequeño buffer para el estado "abajo"
                        metrics['stage'] = "Abajo"
                    else:
                        metrics['stage'] = "Bajando..." # Si el ángulo de la rodilla es mayor que el umbral "down" pero aún en estado "down", es probable que esté bajando.
                
                # Sobreescribir 'stage' con feedback específico si se detecta un error o se completa una repetición
                if self.repetition_has_error:

                    # Si hubo un error en la repetición actual, mostrar ese feedback
                    metrics['stage'] = self.current_feedback

                elif "Correcta" in self.current_feedback and self.squat_state == "up":

                    # Si se acaba de completar una repetición correcta y estamos en el estado "up"
                    metrics['stage'] = "Repetición Correcta"

                elif "Incorrecta" in self.current_feedback and self.squat_state == "up":
                    
                    # Si se acaba de completar una repetición incorrecta y estamos en el estado "up"
                    metrics['stage'] = self.current_feedback

                # ******* FIN MODIFICACIÓN CLAVE *******

                # Exportar landmarks basado en el estado actual de la sentadilla
                # Se exporta el estado para cada frame, o el tipo de repeticion al finalizar
                if self.squat_state == "up" and ("Correcta" in self.current_feedback or "Incorrecta" in self.current_feedback):
                    if "Correcta" in self.current_feedback:
                        self._export_landmark(results, 'correct_rep')
                    elif "Incorrecta" in self.current_feedback:
                        self._export_landmark(results, self.current_feedback.replace(" ", "_").lower())
                else:
                    self._export_landmark(results, self.squat_state)
                
                mp_drawing.draw_landmarks(
                    image,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2)
                )

                # ******* NUEVAS LÍNEAS DE CÓDIGO PARA VISUALIZAR ÁNGULOS *******
                h, w, c = image.shape
                scale_x, scale_y = w, h

                # Coordenadas en píxeles para mostrar el texto
                # Nota: Los landmarks x e y están normalizados entre 0 y 1.
                # Multiplicamos por el ancho y alto de la imagen para obtener las coordenadas en píxeles.
                hip_left_coords = tuple(np.multiply(hip_left, [scale_x, scale_y]).astype(int))
                knee_left_coords = tuple(np.multiply(knee_left, [scale_x, scale_y]).astype(int))
    
                # Mostrar el ángulo de la cadera izquierda
                cv2.putText(image, f"Cadera: {int(hip_angle)}",
                            hip_left_coords,
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)

                # Mostrar el ángulo de la rodilla izquierda
                cv2.putText(image, f"Rodilla: {int(knee_angle)}",
                            knee_left_coords,
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)    

                cv2.putText(image, f"Espalda: {int(back_angle)}",
                            tuple(np.multiply(shoulder_left, [scale_x, scale_y]).astype(int)), # Colocado cerca del hombro izquierdo
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)

        except Exception as e:
            # **** CAMBIO CLAVE AQUI ****
            # Imprimimos el error para que puedas verlo en la consola.
            print(f"Error durante el procesamiento del frame o visualización de ángulos: {e}")
            # Puedes añadir más información de depuración si es necesario, como traceback:
            traceback.print_exc()
            pass
                    
        # Retorna el fotograma procesado y los datos del ejercicio
        return image, metrics

    def reset_counters(self):
        """
        Reinicia los contadores y el estado del detector de sentadillas.
        """
        self.squat_state = "up"
        self.reps_count = 0
        self.incorrect_reps_count = 0
        self.current_feedback = "Esperando..."
        self.repetition_has_error = False