import cv2
import mediapipe as mp
import numpy as np
import os
import csv

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

def calculate_angle(a, b, c):

    """Calcula el angulo entre tres puntos."""
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.degrees(radians)

    # Convertir el ángulo para que siempre esté entre 0 y 180 grados
    if angle < 0:

        angle += 360 # Convertir ángulos negativos a su equivalente positivo

    if angle > 180.0:

        angle = 360 - angle # Asegurarse de que es el ángulo más pequeño

    return angle

class DeadliftDetector:

    def __init__(self, csv_file_name='coords_peso_muerto.csv'):

        self.pose_model = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
        
        # Variables de estado para el peso muerto
        self.correct_reps = 0 # Contador de repeticiones correctas
        self.incorrect_reps = 0 # Contador de repeticiones incorrectas
        self.stage = "initial"  # Estado actual: "initial", "down", "transition", "up"
        self.current_action_for_export = None # Para exportar al CSV
        self.rep_status = "unknown" # Estado de la repetición actual ("correct", "incorrect", "unknown")
        
        # Para detectar el inicio de la subida desde el punto más bajo
        self.min_hip_angle_in_down = 180 # Registra el ángulo de cadera más bajo alcanzado durante el descenso

        # Umbrales para el angulo de la cadera
        # hip_angle_threshold_up: Ángulo de cadera flexionado (90-100 grados), indica el punto más bajo.
        # hip_angle_threshold_down: Ángulo de cadera extendido (150-170 grados), indica la posición de pie.
        self.hip_angle_threshold_down = 150  # Ángulo de cadera para posición de "arriba" (casi extendido)
        self.hip_angle_threshold_up = 90     # Ángulo de cadera para posición de "abajo" (flexionado)

        # Umbrales para detectar postura incorrecta
        # Rodilla
        self.knee_angle_threshold_min_down = 100 # Angulo mínimo de rodilla al bajar (evitar rodillas bloqueadas o excesivamente estiradas)
        self.knee_angle_threshold_max_down = 160 # Angulo máximo de rodilla al bajar (evitar excesiva flexión)
        self.knee_lock_threshold = 170 # Ángulo para considerar que la rodilla está "bloqueada" o casi recta (usado en "transition")

        # Torso (espalda)
        # torso_straight_threshold_up: Ángulo del torso cuando la espalda está recta en la parte superior del movimiento.
        self.torso_straight_threshold_up = 170 # Ángulo del torso para considerarse "recto" en la parte superior del movimiento
        # torso_rounded_threshold: Ángulo por debajo del cual el torso se considera "redondeado" (incorrecto).
        self.torso_rounded_threshold = 120 # Ángulo por debajo del cual el torso se considera "redondeado" (incorrecto)
        
        # Configuracion CSV
        self.csv_file_name = csv_file_name
        self.csv_headers = ['class']
        for val in range(1, 33 + 1):

            self.csv_headers += ['x{}'.format(val), 'y{}'.format(val), 'z{}'.format(val), 'v{}'.format(val)]

        self._initialize_csv()

    def _initialize_csv(self):

        # Borrar el archivo CSV si ya existe y crear con encabezado
        if os.path.exists(self.csv_file_name):

            os.remove(self.csv_file_name)
            print(f"Archivo CSV '{self.csv_file_name}' existente ha sido borrado.")

        with open(self.csv_file_name, mode='w', newline='') as f:

            csv_writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(self.csv_headers)

        print(f"Archivo CSV '{self.csv_file_name}' creado con el encabezado.")

    def _export_landmark(self, results, action):
        """
        Exporta los landmarks de MediaPipe a un archivo CSV.
        results: Objeto de resultados de pose de MediaPipe.
        action: Etiqueta de la accion (e.g., 'initial', 'down', 'transition', 'up').
        """
        try:
            if results.pose_landmarks and action:

                keypoints = np.array([[res.x, res.y, res.z, res.visibility] for res in results.pose_landmarks.landmark]).flatten()
                keypoints_list = keypoints.tolist() 
                keypoints_list.insert(0, action)

                with open(self.csv_file_name, mode='a', newline='') as f:

                    csv_writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                    csv_writer.writerow(keypoints_list)

        except Exception as e:
            # print(f"Error al exportar landmark: {e}") # Descomentar para depuración
            pass

    def process_frame(self, frame):
        """
        Procesa un solo fotograma para detectar la pose, aplicar la logica del peso muerto
        y generar la salida para Flask.
        frame: Un fotograma de video (numpy array de OpenCV).
        Retorna:
            - image: El fotograma procesado con los dibujos.
            - metrics: Un diccionario con las metricas del ejercicio.
        """
        # Invertir el frame horizontalmente para que actue como un espejo
        frame = cv2.flip(frame, 1)
        
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False

        results = self.pose_model.process(image)

        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        # Inicializar ángulos a 0 para asegurar que siempre estén definidos,
        # en caso de que no se detecten landmarks.
        left_hip_angle = 0 
        right_hip_angle = 0
        left_knee_angle = 0 
        right_knee_angle = 0 
        torso_angle = 0 

        try:
            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark

                # Obtener coordenadas de los landmarks relevantes
                left_shoulder = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
                right_shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
                left_hip = [landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x, landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y]
                right_hip = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
                left_knee = [landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x, landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y]
                right_knee = [landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y]
                left_ankle = [landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x, landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y]
                right_ankle = [landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y]
                
                # Para el ángulo del torso: hombro, cadera y punto vertical
                # Unimos los puntos de cadera y hombro de ambos lados para un punto central
                mid_hip = [(left_hip[0] + right_hip[0]) / 2, (left_hip[1] + right_hip[1]) / 2]
                mid_shoulder = [(left_shoulder[0] + right_shoulder[0]) / 2, (left_shoulder[1] + right_shoulder[1]) / 2]

                # Punto vertical hacia abajo desde la cadera para medir el ángulo del torso con la vertical
                vertical_from_hip = [mid_hip[0], mid_hip[1] + 0.1] 
                torso_angle = calculate_angle(mid_shoulder, mid_hip, vertical_from_hip)

                # Calcular los angulos
                left_hip_angle = calculate_angle(left_shoulder, left_hip, left_knee)
                right_hip_angle = calculate_angle(right_shoulder, right_hip, right_knee)
                avg_hip_angle = (left_hip_angle + right_hip_angle) / 2

                left_knee_angle = calculate_angle(left_hip, left_knee, left_ankle) 
                right_knee_angle = calculate_angle(right_hip, right_knee, right_ankle) 
                avg_knee_angle = (left_knee_angle + right_knee_angle) / 2 



                # Logica para el contador de repeticiones de peso muerto y exportacion de landmarks
                
                # Estado INITIAL: Persona de pie, lista para empezar la bajada
                if self.stage == "initial":

                    # Si la cadera empieza a flexionarse por debajo del umbral de "arriba"
                    if avg_hip_angle < self.hip_angle_threshold_down: 

                        self.stage = "down"
                        self.rep_status = "none" # Asumimos none al inicio, se puede invalidar más tarde
                        self.min_hip_angle_in_down = avg_hip_angle # Inicializamos el ángulo más bajo de cadera
                        print("Transición a DOWN desde INITIAL.") # Debug

                # Estado DOWN: Persona bajando el peso
                elif self.stage == "down":

                    # Actualizar el ángulo de cadera más bajo alcanzado durante el descenso
                    if avg_hip_angle < self.min_hip_angle_in_down:

                        self.min_hip_angle_in_down = avg_hip_angle
                    
                    # Chequeos de postura durante la bajada (si la rep es marcada incorrecta, se mantiene)
                    # Rodillas demasiado dobladas o rectas al inicio de la bajada
                    if not (self.knee_angle_threshold_min_down < avg_knee_angle < self.knee_angle_threshold_max_down):

                        self.rep_status = "incorrect"
                        print("DOWN: Rodillas fuera de rango ideal.") # Debug
                    
                    # Espalda redondeada durante la bajada
                    if torso_angle < self.torso_rounded_threshold:

                        self.rep_status = "incorrect"
                        print("DOWN: Torso redondeado.") # Debug

                    # Transición de DOWN a TRANSITION: cuando el ángulo de cadera empieza a aumentar 
                    # significativamente desde su punto más bajo (indicando el inicio de la subida)
                    # Se usa un pequeño buffer (5 grados) para evitar fluctuaciones
                    if avg_hip_angle > self.min_hip_angle_in_down + 5: 

                        self.stage = "transition"
                        print("Transición a TRANSITION desde DOWN.") # Debug

                # Estado TRANSITION: Persona subiendo el peso, desde abajo hasta casi arriba
                elif self.stage == "transition":

                    # Chequeos de postura CONTINUOS durante la subida
                    
                    # FALLO: Rodillas bloqueadas ANTES que la espalda esté recta
                    # Esto ocurre si el ángulo de la rodilla es casi recto (> knee_lock_threshold)
                    # Y el torso aún NO está recto (torso_angle < torso_straight_threshold_up - un margen)
                    if avg_knee_angle > self.knee_lock_threshold and \
                       torso_angle < self.torso_straight_threshold_up - 10: 
                        
                        if self.rep_status == "correct": # Solo marcar como incorrecta si no lo estaba ya

                            self.rep_status = "incorrect"
                            print("TRANSITION: Rodillas bloqueadas prematuramente (antes que la espalda).") # Debug

                    # FALLO: Espalda redondeada durante la subida
                    if torso_angle < self.torso_rounded_threshold:

                        if self.rep_status == "correct":

                            self.rep_status = "incorrect"
                            print("TRANSITION: Torso redondeado durante la subida.") # Debug
    

                    # Transición de TRANSITION a UP: La cadera ha alcanzado la extensión completa
                    if avg_hip_angle > self.hip_angle_threshold_down: 

                        self.stage = "up"
                        print(f"Transición a UP desde TRANSITION") # Debug

                        # Evaluación final de la repetición al llegar a la cima
                        # Si la rep_status es 'correct' hasta ahora Y la postura final es buena
                        if self.rep_status == "correct":
                            
                            self.correct_reps += 1
                            self.state = "correct_rep"
                            print(f"¡Repetición CORRECTA! Total correctas: {self.correct_reps}")
                        else:

                            self.incorrect_reps += 1
                            self.state = "incorrect_rep"
                            print(f"¡Repetición INCORRECTA! Total incorrectas: {self.incorrect_reps}")
                            
                        self.rep_status = "unknown" # Resetear el estado para la siguiente repetición

                # Estado UP: Persona ha completado la repetición y está de pie
                elif self.stage == "up":

                    # Permanecemos en "up" un momento y luego volvemos a "initial" si la persona se mantiene erguida.
                    # Esto permite un pequeño margen para estabilizarse antes de la siguiente repetición.
                    # Si el ángulo de cadera permanece extendido (por encima del umbral de "arriba" - un pequeño buffer)
                    # Y no hay ninguna señal de volver a bajar (no queremos transicionar a "initial" si está empezando a bajar de nuevo)
                    if avg_hip_angle > self.hip_angle_threshold_down - 5: 

                        self.stage = "initial"
                        print("Volviendo a INITIAL desde UP.") # Debug


                # Exportamos landmarks para los estados relevantes de la repetición
                if self.stage in ["down", "transition", "up", "correct_rep","incorrect_rep"]:

                    self._export_landmark(results, self.stage) 
                    
                else:

                    self.current_action_for_export = None # No exportar si no estamos en una fase de repetición activa


                # Visualizar los angulos en la imagen
                cv2.putText(image, f"L-Hip: {int(left_hip_angle)}",
                                tuple(np.multiply(left_hip, [image.shape[1], image.shape[0]]).astype(int)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(image, f"R-Hip: {int(right_hip_angle)}",
                                tuple(np.multiply(right_hip, [image.shape[1], image.shape[0]]).astype(int)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
                
                cv2.putText(image, f"L-Knee: {int(left_knee_angle)}",
                                tuple(np.multiply(left_knee, [image.shape[1], image.shape[0]]).astype(int)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(image, f"R-Knee: {int(right_knee_angle)}",
                                tuple(np.multiply(right_knee, [image.shape[1], image.shape[0]]).astype(int)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
                
                cv2.putText(image, f"Torso: {int(torso_angle)}",
                                tuple(np.multiply(mid_hip, [image.shape[1], image.shape[0]]).astype(int)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)


            # Dibujar los puntos clave y las conexiones de MediaPipe
            if results.pose_landmarks:
                mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                                        mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=2),
                                        mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2))
            else:
                pass # No dibujar si no hay landmarks detectados
        except Exception as e:
            # print(f"Error en el procesamiento del fotograma: {e}") # Descomentar para depuración de errores
            pass



        # Retorna el fotograma procesado y los datos del ejercicio para ser enviados por Flask 
        return image, { 
            'correct_reps': self.correct_reps, 
            'incorrect_reps': self.incorrect_reps, 
            'stage': self.stage, 
            'csv_stage': self.stage, # Ahora current_action_for_export se basa directamente en self.stage
            'left_hip_angle': int(left_hip_angle), 
            'right_hip_angle': int(right_hip_angle),
            'left_knee_angle': int(left_knee_angle), 
            'right_knee_angle': int(right_knee_angle), 
            'torso_angle': int(torso_angle) 
        }

    def reset_counters(self):
        """
        Reinicia los contadores y el estado del detector de peso muerto.
        """
        self.correct_reps = 0 
        self.incorrect_reps = 0 
        self.stage = "initial" 
        self.current_action_for_export = None
        self.rep_status = "unknown" 
        self.min_hip_angle_in_down = 180 # Reiniciar también el ángulo mínimo de cadera
        print("Contadores del detector de Peso Muerto reseteados.")

    def __del__(self):
        if hasattr(self, 'pose_model'):
            self.pose_model.close()