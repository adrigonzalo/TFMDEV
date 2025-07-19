import cv2
import mediapipe as mp
import numpy as np
import os
import csv

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)

    if angle > 180.0:
        angle = 360 - angle
    return angle
 
class ShoulderPressDetector:

    def __init__(self, csv_file_path='coords_press_hombro.csv'):

        # Inicializar el modelo de MediaPipe Pose para esta instancia
        self.pose_model = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

        # Inicializacion de las variables de estado para el ejercicio
        self.stage = None
        self.reps = 0 # Contador de repeticiones CORRECTAS
        self.incorrect_reps = 0 # Contador de repeticiones INCORRECTAS
        self.shoulder_plane_status_r = "OK"
        self.shoulder_plane_status_l = "OK"
        self.max_angle_reached = 0
        self.last_rep_outcome_state = None
        self.current_stage_for_export = "no_pose"
        
        # Umbrales del ejercicio (ajustables)
        self.Z_THRESHOLD_FORWARD = 0.23
        self.Z_THRESHOLD_BACKWARD = -0.23
        self.ANGLE_THRESHOLD_FULL_EXTENSION = 150
        self.ELBOW_ANGLE_DOWN = 100 # Codos flexionados (abajo)
        self.ELBOW_ANGLE_UP = 160 # Codos extendidos (arriba)

        # Configuracion CSV
        self.csv_file_path = csv_file_path
        self.csv_headers = ['class']
        for val in range(1, 33 + 1):

            self.csv_headers += ['x{}'.format(val), 'y{}'.format(val), 'z{}'.format(val), 'v{}'.format(val)]

        self._initialize_csv() # Llama al metodo para inicializar el CSV

    def _initialize_csv(self):

        # Borrar el archivo CSV si ya existe y crear con encabezado
        if os.path.exists(self.csv_file_path):

            os.remove(self.csv_file_path)
            print(f"Archivo CSV '{self.csv_file_path}' existente ha sido borrado.")

        with open(self.csv_file_path, mode='w', newline='') as f:

            csv_writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(self.csv_headers)

        print(f"Archivo CSV '{self.csv_file_path}' creado con el encabezado.")

    def _export_landmark(self, results, action):

        try:
            if results.pose_landmarks:
                
                keypoints = np.array([[res.x, res.y, res.z, res.visibility] for res in results.pose_landmarks.landmark]).flatten()
                keypoints_list = keypoints.tolist()
                keypoints_list.insert(0, action)

                with open(self.csv_file_path, mode='a', newline='') as f:

                    csv_writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                    csv_writer.writerow(keypoints_list)
        except Exception as e:

            pass # No mostrar errores de exportacion en el stream continuo

    def process_frame(self, frame):

        # Invertir el frame horizontalmente para que actue como un espejo
        frame = cv2.flip(frame, 1)
        
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False

        results = self.pose_model.process(image) # Usar self.pose_model

        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        self.current_stage_for_export = "no_pose" # Etiqueta predeterminada si no hay pose

        angle_r_elbow, angle_l_elbow = -1, -1 # Default values

        try:
            landmarks_data = results.pose_landmarks.landmark

            # Obtener coordenadas 3D de los puntos clave (x, y, z)
            r_shoulder = [landmarks_data[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x,
                          landmarks_data[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y,
                          landmarks_data[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].z]
            r_elbow = [landmarks_data[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x,
                       landmarks_data[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y,
                       landmarks_data[mp_pose.PoseLandmark.RIGHT_ELBOW.value].z]
            r_wrist = [landmarks_data[mp_pose.PoseLandmark.RIGHT_WRIST.value].x,
                       landmarks_data[mp_pose.PoseLandmark.RIGHT_WRIST.value].y,
                       landmarks_data[mp_pose.PoseLandmark.RIGHT_WRIST.value].z]

            l_shoulder = [landmarks_data[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x,
                          landmarks_data[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y,
                          landmarks_data[mp_pose.PoseLandmark.LEFT_SHOULDER.value].z]
            l_elbow = [landmarks_data[mp_pose.PoseLandmark.LEFT_ELBOW.value].x,
                       landmarks_data[mp_pose.PoseLandmark.LEFT_ELBOW.value].y,
                       landmarks_data[mp_pose.PoseLandmark.LEFT_ELBOW.value].z]
            l_wrist = [landmarks_data[mp_pose.PoseLandmark.LEFT_WRIST.value].x,
                       landmarks_data[mp_pose.PoseLandmark.LEFT_WRIST.value].y,
                       landmarks_data[mp_pose.PoseLandmark.LEFT_WRIST.value].z]

            angle_r_elbow = calculate_angle(r_shoulder[:2], r_elbow[:2], r_wrist[:2])
            angle_l_elbow = calculate_angle(l_shoulder[:2], l_elbow[:2], l_wrist[:2])

            z_diff_r = r_elbow[2] - r_shoulder[2]
            if z_diff_r > self.Z_THRESHOLD_FORWARD:

                self.shoulder_plane_status_r = "ADELANTE"

            elif z_diff_r < self.Z_THRESHOLD_BACKWARD:

                self.shoulder_plane_status_r = "ATRAS"
            else:

                self.shoulder_plane_status_r = "OK"

            z_diff_l = l_elbow[2] - l_shoulder[2]
            if z_diff_l > self.Z_THRESHOLD_FORWARD:

                self.shoulder_plane_status_l = "ADELANTE"

            elif z_diff_l < self.Z_THRESHOLD_BACKWARD:

                self.shoulder_plane_status_l = "ATRAS"
            else:

                self.shoulder_plane_status_l = "OK"

            # Logica de deteccion de repeticiones y asignacion de stage para exportacion
            avg_elbow_angle = (angle_r_elbow + angle_l_elbow) / 2

            if avg_elbow_angle < self.ELBOW_ANGLE_DOWN: # Codos flexionados (abajo)

                self.stage = "down"
                self.current_stage_for_export = "down"
                self.max_angle_reached = 0
                self.last_rep_outcome_state = None

            elif avg_elbow_angle > self.ELBOW_ANGLE_UP: # Codos extendidos (arriba)

                if self.stage == 'down':

                    if self.shoulder_plane_status_r == "OK" and self.shoulder_plane_status_l == "OK":

                        if self.max_angle_reached >= self.ANGLE_THRESHOLD_FULL_EXTENSION:

                            self.stage = "up"
                            self.reps += 1
                            self.current_stage_for_export = "correct_up"
                            self.last_rep_outcome_state = "correct_up"

                        else:

                            self.stage = "invalid"
                            self.incorrect_reps += 1
                            self.current_stage_for_export = "incorrect_short_range"
                            self.last_rep_outcome_state = "incorrect_short_range"
                    else:

                        self.stage = "invalid"
                        self.incorrect_reps += 1
                        self.current_stage_for_export = "incorrect_plane"
                        self.last_rep_outcome_state = "incorrect_plane"
                else:

                    if self.last_rep_outcome_state is not None:

                        self.current_stage_for_export = self.last_rep_outcome_state
                    else:

                        self.stage = "up_initial"
                        self.current_stage_for_export = "up_initial"

            else: # Fase de transicion

                if self.stage == "down" or self.stage == "up_initial":

                    self.max_angle_reached = max(self.max_angle_reached, avg_elbow_angle)
                    self.current_stage_for_export = "transition"

                elif self.last_rep_outcome_state is not None:

                    self.current_stage_for_export = self.last_rep_outcome_state

                else:

                    self.current_stage_for_export = "transition"

            self._export_landmark(results, self.current_stage_for_export)

        except Exception as e:
            pass # No mostrar errores en el stream continuo

        # Dibujar los puntos clave y las conexiones
        if results.pose_landmarks:
            
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                                    mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=2),
                                    mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2))



        # Retorna el fotograma procesado y los datos del ejercicio para ser enviados por Flask
        return image, {
            'reps': self.reps,
            'incorrect_reps': self.incorrect_reps,
            'stage': self.stage,
            'csv_stage': self.current_stage_for_export,
            'max_angle': int(self.max_angle_reached),
            'shoulder_plane_r': self.shoulder_plane_status_r,
            'shoulder_plane_l': self.shoulder_plane_status_l
        }

    def reset_counters(self):
        """
        Reinicia los contadores y el estado del detector de Press de Hombro.
        """
        self.reps = 0
        self.incorrect_reps = 0
        self.stage = None # o el estado inicial que consideres apropiado
        self.shoulder_plane_status_r = "OK"
        self.shoulder_plane_status_l = "OK"
        self.max_angle_reached = 0
        self.last_rep_outcome_state = None
        self.current_stage_for_export = "no_pose"
        print("Contadores del detector de Press de Hombro reseteados.")
