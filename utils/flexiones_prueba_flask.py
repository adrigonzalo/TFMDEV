import cv2
import mediapipe as mp
import numpy as np
import os
import csv

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

def calculate_angle(a, b, c):

    """Calcula el angulo entre tres puntos (en 2D)."""
    a = np.array(a)  # Primer punto
    b = np.array(b)  # Punto medio (articulacion)
    c = np.array(c)  # ultimo punto

    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.degrees(radians)

    if angle > 180.0:

        angle = 360 - angle

    elif angle < 0:

        angle = abs(angle)

    return angle

class PushupDetector:

    def __init__(self, csv_file_path='coords_flexiones.csv'):

        # Configuracion de MediaPipe Pose
        self.pose_model = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

        # Variables de estado para la deteccion de flexiones
        self.counter_correct = 0 # Contador de repeticiones CORRECTAS
        self.counter_incorrect = 0 # Contador de repeticiones INCORRECTAS
        self.stage = None # 'down' o 'up' para el estado de la flexion
        self.current_export_label = 'neutral' # Etiqueta para el CSV (neutral, down, up, correct_finish, incorrect_finish)
        self.hip_angle_at_down_stage = None # Nueva variable para almacenar el ángulo de la cadera al alcanzar la posición "down"

        # Umbrales del ejercicio (ajustables)
        self.elbow_threshold_down = 100 # angulo del codo para considerar la posicion "abajo" 
        self.elbow_threshold_up = 160  # angulo del codo para considerar la posicion "arriba"
        # Umbral para la cadera. Un ángulo *menor* a este indica una cadera "caída" (postura incorrecta).
        # Por ejemplo, si una cadera recta es 170-180, un valor de 160 podría ser un buen umbral.
        self.incorrect_hip_angle_threshold = 160

        # Configuracion CSV
        self.csv_file_path = csv_file_path
        self.csv_headers = ['class']
        for val in range(1, 33 + 1):
            
            self.csv_headers += ['x{}'.format(val), 'y{}'.format(val), 'z{}'.format(val), 'v{}'.format(val)]

        self._initialize_csv() # Llama al metodo para inicializar el CSV

    def _initialize_csv(self):

        """
        Borra el archivo CSV si existe y lo crea con el encabezado.
        Esto asegura un nuevo archivo en cada inicio del detector.
        """
        if os.path.exists(self.csv_file_path):

            os.remove(self.csv_file_path)
            print(f"Archivo '{self.csv_file_path}' existente eliminado.")

        with open(self.csv_file_path, mode='w', newline='') as f:

            csv_writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(self.csv_headers)

        print(f"Archivo CSV '{self.csv_file_path}' creado con el encabezado.")

    def _export_landmark(self, results, action):

        """
        Exporta los landmarks de la pose actual a un archivo CSV.
        results: Objeto de resultados de MediaPipe Pose.
        action: Etiqueta para la fila (ej. 'up', 'down', 'correct_finish', 'incorrect_finish', 'neutral').
        """
        try:
            if results.pose_landmarks: # Asegurarse de que haya landmarks antes de intentar exportar

                keypoints = np.array([[res.x, res.y, res.z, res.visibility] for res in results.pose_landmarks.landmark]).flatten()
                keypoints_list = keypoints.tolist()
                keypoints_list.insert(0, action)

                with open(self.csv_file_path, mode='a', newline='') as f:

                    csv_writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                    csv_writer.writerow(keypoints_list)

        except Exception as e:
            # Ignorar errores si no se detectan landmarks o hay algun problema con los datos
            pass

    def process_frame(self, frame):

        """
        Procesa un solo fotograma de video para detectar flexiones.
        frame: Fotograma de entrada en formato BGR de OpenCV.
        Retorna:
            - image: Fotograma procesado con los landmarks y contadores dibujados.
            - metrics: Un diccionario con las metricas actuales del ejercicio.
        """

        # Invertir el frame horizontalmente para que actue como un espejo
        frame = cv2.flip(frame, 1)

        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False

        results = self.pose_model.process(image)

        image.flags.writeable = True 
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        self.current_export_label = 'neutral' # Valor predeterminado si no se detecta pose o etapa

        left_hip_angle, right_hip_angle, left_knee_angle, right_knee_angle, left_elbow_angle, right_elbow_angle = [-1]*6 # Default values

        try:
            landmarks = results.pose_landmarks.landmark

            # Obtener coordenadas de los landmarks relevantes
            left_shoulder = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            left_elbow = [landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
            left_wrist = [landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
            right_shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
            right_elbow = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
            right_wrist = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]
            
            left_hip = [landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x, landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y]
            left_knee = [landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x, landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y]
            left_ankle = [landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x, landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y]
            right_hip = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
            right_knee = [landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y]
            right_ankle = [landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y]


            # Calcular angulos
            left_hip_angle = calculate_angle(left_shoulder, left_hip, left_knee)
            right_hip_angle = calculate_angle(right_shoulder, right_hip, right_knee)
            left_knee_angle = calculate_angle(left_hip, left_knee, left_ankle)
            right_knee_angle = calculate_angle(right_hip, right_knee, right_ankle)
            left_elbow_angle = calculate_angle(left_shoulder, left_elbow, left_wrist)
            right_elbow_angle = calculate_angle(right_shoulder, right_elbow, right_wrist)

            # Lógica para el contador de repeticiones y determinación del estado 
            avg_elbow_angle = (left_elbow_angle + right_elbow_angle) / 2
            avg_hip_angle = (left_hip_angle + right_hip_angle) / 2


            if self.stage is None: # Estado inicial, esperando el primer movimiento "down"

                if avg_elbow_angle < self.elbow_threshold_down:

                    self.stage = "down"
                    self.current_export_label = 'down'
                    self.hip_angle_at_down_stage = avg_hip_angle # Guardar el ángulo de la cadera al llegar a 'down'

            elif self.stage == "up":

                # Si estamos en 'up' y el codo baja, iniciamos una nueva repetición (pasamos a 'down')
                if avg_elbow_angle < self.elbow_threshold_down:

                    self.stage = "down"
                    self.current_export_label = 'down'
                    self.hip_angle_at_down_stage = avg_hip_angle # Guardar el ángulo de la cadera al llegar a 'down'

            elif self.stage == "down":

                # Si estamos en 'down' y el codo sube, evaluamos la repetición
                if avg_elbow_angle > self.elbow_threshold_up:

                    # Transición de "down" a "up" - Posible final de una repetición
                    # Evaluamos la postura de la cadera registrada al inicio de la fase "down"
                    if self.hip_angle_at_down_stage is not None and self.hip_angle_at_down_stage < self.incorrect_hip_angle_threshold:

                        self.counter_incorrect += 1
                        self.current_export_label = 'incorrect_finish' # Etiqueta especifica para repeticion incorrecta

                    else:
                        
                        self.counter_correct += 1
                        self.current_export_label = 'correct_finish' # Etiqueta especifica para repeticion correcta

                    self.stage = "up" # Reseteamos el estado a 'up' para la siguiente repetición
                    self.hip_angle_at_down_stage = None # Limpiar el ángulo de la cadera almacenado
            
            # Exportar el estado del frame actual al CSV
            self._export_landmark(results, self.current_export_label)

            # Visualizacion de angulos y contadores en la imagen
            img_h, img_w, _ = image.shape
            scale_x = img_w
            scale_y = img_h

            cv2.putText(image, f"L-Hip: {int(left_hip_angle)}",
                                tuple(np.multiply(left_hip, [scale_x, scale_y]).astype(int)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(image, f"R-Hip: {int(right_hip_angle)}",
                                tuple(np.multiply(right_hip, [scale_x, scale_y]).astype(int)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(image, f"L-Knee: {int(left_knee_angle)}",
                                tuple(np.multiply(left_knee, [scale_x, scale_y]).astype(int)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(image, f"R-Knee: {int(right_knee_angle)}",
                                tuple(np.multiply(right_knee, [scale_x, scale_y]).astype(int)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(image, f"L-Elbow: {int(left_elbow_angle)}",
                                tuple(np.multiply(left_elbow, [scale_x, scale_y]).astype(int)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(image, f"R-Elbow: {int(right_elbow_angle)}",
                                tuple(np.multiply(right_elbow, [scale_x, scale_y]).astype(int)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)

            # Render detection para ver los landmarks
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                                     mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=2),
                                     mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2))

        except Exception as e:
            # print(f"Error procesando frame: {e}") # Para depuracion si quieres ver errores especificos
            pass # No se dibuja nada si no hay landmarks, el frame original BGR permanece o se devuelve como esta.


        # Retorna el fotograma procesado y los datos del ejercicio para ser enviados por Flask
        return image, {
            'reps': self.counter_correct,
            'incorrect_reps': self.counter_incorrect,
            'stage': self.stage,
            'current_export_label': self.current_export_label, # Para saber el ultimo estado registrado en CSV
            'L_Hip_Angle': int(left_hip_angle), 
            'R_Hip_Angle': int(right_hip_angle),
            'L_Knee_Angle': int(left_knee_angle),
            'R_Knee_Angle': int(right_knee_angle),
            'L_Elbow_Angle': int(left_elbow_angle),
            'R_Elbow_Angle': int(right_elbow_angle),
        }

    def reset_counters(self):
        """
        Reinicia los contadores y el estado del detector de flexiones.
        """
        self.counter_correct = 0
        self.counter_incorrect = 0
        self.stage = None # Reinicia el stage a su valor inicial
        self.current_export_label = 'neutral'
        self.hip_angle_at_down_stage = None # Limpiar también el ángulo de la cadera almacenado
        print("Contadores del detector de Flexiones reseteados.")